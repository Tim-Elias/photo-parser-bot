import cv2
from pyzbar.pyzbar import decode
from PIL import Image
import io
import numpy as np
import telebot
from telebot import types
import requests
import json
from botocore.client import Config
from botocore.exceptions import ClientError
import boto3
import base64
from dotenv import load_dotenv
import os
import threading
from utils.hash_string import hash_string
from openai_image_app import get_number_using_openai
from utils.resize_image import resize_image

# Бот для получения фото накладных с последующим сохранением в s3 хранилище и отправкой данных в Базу данных

load_dotenv()

# Инициализация хранилища
s3 = boto3.client(
        's3',
        endpoint_url=os.getenv('ENDPOINT_URL'),
        region_name=os.getenv('REGION_NAME'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        config=Config(s3={'addressing_style': 'path'})
    )

# Создаем сессию с постоянными учетными данными
session = boto3.Session(s3)
bucket_name = os.getenv('BUCKET_NAME')

url_check_number=os.getenv('URL_CHECK_NUMBER')
url_sent_data=os.getenv('URL_SENT_DATA')

# Словарь для хранения обработанных изображений для каждого пользователя
user_images = {}
user_states = {}

# Таймер для каждого пользователя
user_timers = {}

# Время ожидания для завершения приема изображений (в секундах)
WAIT_TIME = 5

# Распознавание qr-code
def get_QR(image):
    # Распознавание QR-кодов на изображении
    qr_codes = decode(image)

    if qr_codes:
        qr_data = qr_codes[0].data.decode('utf-8')
        return qr_data
    else:
       return None
        
# Преобразование изображения в base64
def convert_image_to_base64(image):
    # Преобразование изображения OpenCV в формат байтов
    _, buffer = cv2.imencode('.jpg', image)
    # Преобразование байтов в строку Base64
    base64_str = base64.b64encode(buffer).decode('utf-8')
    return base64_str

# Отправление пост запроса
def post_and_process(payload, headers):
    try:
        url=url_check_number
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                return {'error': 'Response is not a valid JSON'}
        else:
            return {'error': response.status_code}

    except requests.RequestException as e:
        return {'error': e}

# Существует ли уже такой объект в хранилище
def object_exists(bucket: str, key: str) -> bool:
    try:
        # Пытаемся получить метаданные объекта
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        # Проверяем ошибку "404 Not Found"
        if e.response['Error']['Code'] == '404':
            return False
        # Другие ошибки (например, проблемы с правами доступа) могут также возникнуть
        else:
            raise

# Запрос в 1с с данными
def post_request(qr_data, s3_file_key, status, headers):
    url=url_sent_data
    payload = {"Number" : f"{qr_data}", "hash" : f"{s3_file_key}", "status" : f"{status}"}
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    if response.status_code == 200:
        try:
            return response.json()
        except ValueError:
            return {'error': 'Response is not a valid JSON'}
    else:
        return {'error' : "Request failed"}

# Запуск таймера для бота
def start_timer(user_id):
    """Запускает таймер для пользователя."""
    if user_id in user_timers:
        user_timers[user_id].cancel()

    # Таймер ждет указанное время, а затем запускает обработку изображений
    user_timers[user_id] = threading.Timer(WAIT_TIME, process_next_image, args=[user_id])
    user_timers[user_id].start()

# Загрузка данных на s3
def post_s3(data, ext):
    try:
        hash = hash_string(data,'sha256')
        s3_file_key=f'{hash}.{ext}'
        # Проверяем есть ли уже такой объект в бакете
        if not object_exists(bucket_name, s3_file_key):    
            s3.put_object(
                Bucket=bucket_name,
                Key=s3_file_key,
                Body=data.encode('utf-8'),  # Преобразуем строку в байты
                ContentType='application/json'
                )
            response={'status' : 'created', 'data' : s3_file_key}
            return response, s3_file_key
        else:
            response={'status' : 'exists', 'data' : s3_file_key}
            return response, s3_file_key
    except requests.RequestException as e:
        response={'status' : 'error', 'error' : str(e)}
        return response

# Обработка накладной
def invoice_processing(message, invoice, base64_image, file_extension, status):
    status_s3, s3_file_key=post_s3(base64_image, file_extension)
    headers = {'Content-Type': 'application/json'}
    result=post_request(invoice, s3_file_key, status, headers)
    if status=='delivered':
        bot_message=f"Вы указали, что накладная {invoice} доставлена."
    elif status=='received':
        bot_message=f"Вы указали, что накладная {invoice} получена."
    else:
        bot_message="Вы указали прочее."
    if result.get('error')==False:
        if status_s3['status']=='created':
            text=f"{bot_message} Скан успешно сохранен. {result.get('data')}"
            return text
            #bot.send_message(message, f"{bot_message} Скан успешно сохранен. {result.get('data')}")
        elif status_s3['status']=='exists':
            text=f"{bot_message} Скан уже существует. {result.get('data')}"
            return(f"{bot_message} Скан уже существует. {result.get('data')}")
            #bot.send_message(message, f"{bot_message} Скан уже существует. {result.get('data')}")
        else:
            text=f"{bot_message} Скан уже существует. {result.get('data')}"
            return text
           
            
    else:
        error_msg=result.get('error_msg')
        bot.send_message(message, f"Ошибка при записи в 1с. Error: {error_msg}")

# Обработка изображения
def process_image(user_id, image_id):
    """Функция для обработки изображений после завершения таймера ожидания."""
    if user_id in user_images and user_images[user_id]:
        # Отправляем сообщение с выбором дальнейших действий
        image_data = user_images[user_id].get(image_id)
        invoice = image_data['invoice']
        base64_image = image_data['base64_image']
        user_states[user_id] = {'current_image': image_id}
        current_image_id = user_states[user_id]['current_image']
        payloads = {"Number" : invoice}
        headers = {'Content-Type': 'application/json'}
        response = post_and_process(payloads, headers)

        if response.get('status') == 'ok':
            if image_data:
                # Создаем Inline клавиатуру
                markup = types.InlineKeyboardMarkup()
                button1 = types.InlineKeyboardButton("Получено от отправителя", callback_data="received")
                button2 = types.InlineKeyboardButton("Доставлено получателю", callback_data="delivered")
                button3 = types.InlineKeyboardButton("Прочее", callback_data="other")
                markup.add(button1, button2, button3)
                bot.send_message(user_id, f"Выберите действие с накладной {invoice}:", reply_markup=markup)
        else:
            bot.send_message(user_id, f"Накладная {invoice} не найдена.")
            # Удаляем текущее изображение из списка
            del user_images[user_id][current_image_id]
            # Проверяем, есть ли еще изображения для обработки
            if user_images[user_id]:
                # Запускаем обработку следующего изображения
                process_next_image(user_id)
            else:
                user_states[user_id] = {}

    #else:
        #bot.send_message(user_id, "Изображения не найдены, отправьте хотя бы одно.")


# Запуск обработки следующего изображения
def process_next_image(user_id):
    """Функция для обработки следующего изображения."""
    if user_id in user_images and user_images[user_id]:
        # Получаем список всех изображений
        image_ids = list(user_images[user_id].keys())
        if image_ids:
            # Обрабатываем следующее изображение
            current_image_id = image_ids[0]
            process_image(user_id, current_image_id)
        #else:
            #bot.send_message(user_id, "Изображения не найдены, отправьте хотя бы одно.")

# Занесение данных об изображении в список изображений
def handle_image(message, user_id, is_document):
    # Если пользователь отправляет первое изображение, создаем пустой словарь
    if user_id not in user_images:
        user_images[user_id] = {}
        user_states[user_id] = {}
    try:
        if is_document:
            file_info = bot.get_file(message.document.file_id)
        else:
            file_info = bot.get_file(message.photo[-1].file_id)
        # Получаем информацию о файле и его содержимом
        file_path = file_info.file_path
        # Определяем расширение файла
        file_extension = file_path.split('.')[-1]
        # Скачиваем файл в память
        downloaded_file = bot.download_file(file_path)
        image_stream = io.BytesIO(downloaded_file)
        try:
            pil_image = Image.open(image_stream)
            # Проверяем формат изображения
            pil_image = pil_image.convert("RGB")
            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            # Преобразование изображения в Base64
            base64_image = convert_image_to_base64(cv_image)
            cv_image=resize_image(cv_image, scale_factor=2.0)
            # Обработка изображения
            invoice=get_QR(cv_image)
            if invoice==None:
                invoice_data=get_number_using_openai(base64_image)
                invoice=invoice_data['number']
                error=invoice_data['error']
            if invoice=="Номер накладной отсутствует":
                if not error:
                    bot.send_message(user_id, f"Не удалось распознать номер.")
            else:
                # Сохраняем изображение и его метаданные
                image_id = len(user_images[user_id]) + 1
                user_images[user_id][image_id]={
                        "invoice" : invoice,
                        "file_extension" : file_extension,
                        "base64_image" : base64_image,
                    }
            
            start_timer(user_id)
        finally:
            # Закрываем изображение и поток
            pil_image.close()
            image_stream.close()
    except Exception as e:
        print(f"Ошибка: {e}")
        #try:
            #bot.reply_to(message, "Произошла ошибка при обработке изображения.")
        #except:
            #print("Произошла ошибка при ответе на сообщение")
    finally:
    # Очищаем объекты для освобождения памяти
        del downloaded_file, image_stream, pil_image, cv_image

# Подготовка бота
tg_api_token=os.getenv('TG_API_TOKEN')
bot = telebot.TeleBot(tg_api_token)

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я ваш бот. Чем могу помочь?")


# Обработчик фотографий
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    # Проверка, переслано ли сообщение
    if message.forward_from:
        # Если сообщение переслано, используем ID оригинального отправителя
        user_id = message.forward_from.id
    else:
        # Иначе используем ID текущего чата (пользователя)
        user_id = message.chat.id
    handle_image(message, user_id, is_document=False)
    
# Обработчик документов
@bot.message_handler(content_types=['document'])
def handle_document(message):
    # Проверка, переслано ли сообщение
    if message.forward_from:
        # Если сообщение переслано, используем ID оригинального отправителя
        user_id = message.forward_from.id
    else:
        # Иначе используем ID текущего чата (пользователя)
        user_id = message.chat.id
    # Проверяем, является ли документ изображением
    file_name = message.document.file_name
    if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
        handle_image(message, user_id, is_document=True)
    #else:
        #bot.reply_to(message, "Пожалуйста, отправьте изображение в формате JPG или PNG.")


# Обработчик нажатий на inline-кнопки
@bot.callback_query_handler(func=lambda call: call.data in ["received", "delivered", "other"])
def handle_inline_button(call):
    user_id = call.message.chat.id
    if user_id not in user_states or 'current_image' not in user_states[user_id]:
        #bot.send_message(user_id, "Извините, изображения не найдены. Отправьте новые.")
        return

    current_image_id = user_states[user_id]['current_image']
    if user_id in user_images and current_image_id in user_images[user_id]:
        image_data = user_images[user_id][current_image_id]
        invoice = image_data['invoice']
        base64_image = image_data['base64_image']
        file_extension = image_data['file_extension']
        
        # Обрабатываем выбранное действие
        if call.data == "received":
            status = "received"
        elif call.data == "delivered":
            status = "delivered"
        elif call.data == "other":
            status = ""
        
        # Вызываем функцию обработки накладной
        text = invoice_processing(user_id, invoice, base64_image, file_extension, status)
        
        # Отправляем уведомление пользователю о получении данных
        bot.answer_callback_query(call.id, f"{text}")
        # Сворачиваем (удаляем) кнопки из сообщения
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

        # Удаляем текущее изображение из списка
        del user_images[user_id][current_image_id]
        # Проверяем, есть ли еще изображения для обработки
        if user_images[user_id]:
            # Запускаем обработку следующего изображения
            process_next_image(user_id)
        else:
            user_states[user_id] = {}
    
# Запуск бота
if __name__ == "__main__":
    bot.polling(none_stop=True)