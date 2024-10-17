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



# Время ожидания для завершения приема изображений (в секундах)


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

def invoice_processing(chat_id, invoice, base64_image, file_extension, status):
    try:
        # Отправка изображения на S3 и получение ключа
        status_s3, s3_file_key = post_s3(base64_image, file_extension)
        
        # Установка заголовков для запроса
        headers = {'Content-Type': 'application/json'}
        
        # Отправка данных в 1С и получение результата
        result = post_request(invoice, s3_file_key, status, headers)
        
        # Определение сообщения в зависимости от статуса
        if status == 'delivered':
            bot_message = f"Вы указали, что накладная {invoice} доставлена."
        elif status == 'received':
            bot_message = f"Вы указали, что накладная {invoice} получена."
        else:
            bot_message = "Вы указали прочее."
        
        # Проверка результата и отправка сообщения пользователю
        if not result.get('error'):
            if status_s3['status'] == 'created':
                bot.send_message(chat_id, f"{bot_message} Скан успешно сохранен и привязан к накладной '{invoice}'. {result.get('data')}")
            elif status_s3['status'] == 'exists':
                bot.send_message(chat_id, f"{bot_message} Скан уже существует и привязан к накладной '{invoice}'. {result.get('data')}")
            else:
                bot.send_message(chat_id, "Ошибка при записи в хранилище S3.")
        else:
            error_msg = result.get('error_msg', 'Неизвестная ошибка.')
            bot.send_message(chat_id, f"Ошибка при записи в 1С. Error: {error_msg}")
    
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {str(e)}")


# Обработка изображения
def process_image(user_id, image_id):
    """Функция для обработки изображений."""
    if user_id in user_images and user_images[user_id]:
        image_data = user_images[user_id].get(image_id)
        if not image_data:
            bot.send_message(user_id, "Изображение не найдено.")
            return
        
        invoice = image_data['invoice']
        base64_image = image_data['base64_image']
        user_states[user_id] = {'current_image': image_id}
        current_image_id = user_states[user_id]['current_image']
        payloads = {"Number": invoice}
        headers = {'Content-Type': 'application/json'}
        
        try:
            response = post_and_process(payloads, headers)
            if response.get('status') == 'ok':
                markup = types.ReplyKeyboardMarkup(row_width=3)
                button1 = types.KeyboardButton("Получено от отправителя")
                button2 = types.KeyboardButton("Доставлено получателю")
                button3 = types.KeyboardButton("Прочее")
                markup.add(button1, button2, button3)
                bot.send_message(user_id, f"Выберите действие с накладной {invoice}:", reply_markup=markup)
            else:
                bot.send_message(user_id, f"Накладная {invoice} не найдена.")
                # Удаляем текущее изображение из списка
                del user_images[user_id][current_image_id]
                # Обрабатываем следующее изображение
                process_next_image(user_id)
        except Exception as e:
            bot.send_message(user_id, f"Произошла ошибка при обработке накладной {invoice}: {str(e)}")
            # Удаляем текущее изображение из списка
            del user_images[user_id][current_image_id]
            # Обрабатываем следующее изображение
            process_next_image(user_id)
    else:
        bot.send_message(user_id, "Изображения не найдены, отправьте хотя бы одно.")




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
        else:
            bot.send_message(user_id, "Изображения не найдены, отправьте хотя бы одно.")

# Занесение данных об изображении в список изображений
def handle_image(message, user_id, is_document):
    """Функция для обработки изображений и сохранения их в список."""
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
        file_extension = file_path.split('.')[-1]
        downloaded_file = bot.download_file(file_path)
        image_stream = io.BytesIO(downloaded_file)
        try:
            pil_image = Image.open(image_stream)
            pil_image = pil_image.convert("RGB")
            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            base64_image = convert_image_to_base64(cv_image)
            cv_image = resize_image(cv_image, scale_factor=2.0)
            invoice = get_QR(cv_image)
            if invoice == None:
                invoice_data = get_number_using_openai(base64_image)
                invoice = invoice_data['number']
                error = invoice_data['error']
            if invoice == "Номер накладной отсутствует":
                if error:
                    bot.send_message(user_id, "Это не курьерская накладная.")
                else:
                    bot.send_message(user_id, "Не удалось распознать номер.")
            else:
                # Сохраняем изображение и его метаданные
                image_id = len(user_images[user_id]) + 1
                user_images[user_id][image_id] = {
                    "invoice": invoice,
                    "file_extension": file_extension,
                    "base64_image": base64_image,
                }
                # Немедленно начинаем обработку изображения
                if len(user_images[user_id]) == 1:
                    process_image(user_id, image_id)
            
        finally:
            pil_image.close()
            image_stream.close()
    except Exception as e:
        print(f"Ошибка: {e}")
        try:
            bot.reply_to(message, "Произошла ошибка при обработке изображения.")
        except:
            print("Произошла ошибка при ответе на сообщение")
    finally:
        del downloaded_file, image_stream, pil_image, cv_image

# Подготовка бота
tg_api_token=os.getenv('TG_API_TOKEN')
bot = telebot.TeleBot(tg_api_token)

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_tg_id = message.from_user.id
    bot.reply_to(message, "Привет! Я ваш бот. Чем могу помочь?")


# Обработчик фотографий
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.chat.id
    handle_image(message, user_id, is_document=False)
    
# Обработчик документов
@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.chat.id
    file_name = message.document.file_name
    if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
        handle_image(message, user_id, is_document=True)
    else:
        bot.reply_to(message, "Пожалуйста, отправьте изображение в формате JPG или PNG.")

# Обработка выбора кнопки
@bot.message_handler(func=lambda message: message.text in ["Получено от отправителя", "Доставлено получателю", "Прочее"])
def handle_action(message):
    user_id = message.chat.id
    if user_id not in user_states or 'current_image' not in user_states[user_id]:
        bot.send_message(user_id, "Извините, изображения не найдены. Отправьте новые.")
        return

    current_image_id = user_states[user_id]['current_image']
    if user_id in user_images and current_image_id in user_images[user_id]:
        image_data = user_images[user_id][current_image_id]
        invoice = image_data['invoice']
        base64_image = image_data['base64_image']
        file_extension = image_data['file_extension']

        # Обработка статуса
        status_mapping = {
            "Получено от отправителя": "received",
            "Доставлено получателю": "delivered",
            "Прочее": ""
        }
        status = status_mapping.get(message.text, "")
        invoice_processing(message.chat.id, invoice, base64_image, file_extension, status)

        # Удаление кнопок из сообщения
        bot.edit_message_reply_markup(chat_id=user_id, message_id=message.message_id, reply_markup=None)

        # Удаляем текущее изображение из списка
        del user_images[user_id][current_image_id]

        # Обрабатываем следующее изображение
        process_next_image(user_id)
    else:
        bot.send_message(user_id, "Изображение не найдено или уже обработано.")

    
# Запуск бота
if __name__ == "__main__":
    bot.polling(none_stop=True)