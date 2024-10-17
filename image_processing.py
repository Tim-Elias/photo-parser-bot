import io
import logging
from PIL import Image
import numpy as np
import cv2
from utils import get_QR
from state import user_images  # Импортируем данные о пользователях из state
from image_tasks import process_image  # Можно безопасно импортировать процессор изображения
from openai_image_app import get_number_using_openai
from utils import convert_image_to_base64, resize_image
from s3_utils import S3Handler
from post_requests import post_request

s3_handler = S3Handler()

async def handle_image(message, user_id, is_document, bot):
    logging.info(f"Обработка изображения от пользователя {user_id}.")

    # Проверка состояния пользователя
    if user_id not in user_images:
        user_images[user_id] = {}

    try:
        # Получение информации о файле
        if is_document:
            file_info = await bot.get_file(message.document.file_id)
        else:
            file_info = await bot.get_file(message.photo[-1].file_id)

        file_path = file_info.file_path
        file_extension = file_path.split('.')[-1]
        downloaded_file = await bot.download_file(file_path)
        image_stream = io.BytesIO(downloaded_file.getvalue())  # Получаем байтовые данные

        logging.info(f"Файл {file_path} загружен успешно.")

        # Открытие и обработка изображения
        try:
            pil_image = Image.open(image_stream)
            pil_image = pil_image.convert("RGB")
            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        except Exception as e:
            logging.error(f"Ошибка при открытии или обработке изображения: {e}")
            return  # Завершить обработку в случае ошибки

        # Конвертация изображения в base64
        base64_image = convert_image_to_base64(cv_image)

        # Увеличение размера изображения
        cv_image = resize_image(cv_image, scale_factor=2.0)

        # Извлечение номера накладной
        invoice = get_QR(cv_image)

        # Если номер накладной не найден, используем OpenAI
        if invoice is None:
            invoice_data = await get_number_using_openai(base64_image)
            invoice = invoice_data['number']
            error = invoice_data['error']

        if invoice == "Номер накладной отсутствует":
            if not error:
                await bot.send_message(user_id, "Не удалось распознать номер.")
                logging.warning(f"Не удалось распознать номер для пользователя {user_id}.")
        else:
            image_id = int(len(user_images[user_id]) + 1)
            user_images[user_id][image_id] = {
                "invoice": invoice,
                "file_extension": file_extension,
                "base64_image": base64_image,
            }
            logging.info(f"Изображение сохранено: {image_id} для пользователя {user_id} с накладной {invoice}.")

            # Запускаем обработку изображения сразу после сохранения
            await process_image(user_id, image_id, bot)  # Исправлено на process_image

    except Exception as e:
        logging.error(f"Ошибка при обработке изображения: {e}")
    finally:
        # Закрытие потоков изображения
        if 'pil_image' in locals():
            pil_image.close()
        if 'image_stream' in locals():
            image_stream.close()

async def invoice_processing(invoice, base64_image, file_extension, status):
    logging.info(f"Обработка накладной: {invoice}, статус: {status}.")

    try:
        status_s3, s3_file_key = await s3_handler.post_s3(base64_image, file_extension)
        headers = {'Content-Type': 'application/json'}
        
        result = await post_request(invoice, s3_file_key, status, headers)  # Теперь это асинхронно
        logging.info(f"Результат запроса на сервер: {result}")

        # Формируем сообщение пользователю
        if status == 'delivered':
            bot_message = f"Вы указали, что накладная {invoice} доставлена."
        elif status == 'received':
            bot_message = f"Вы указали, что накладная {invoice} получена."
        else:
            bot_message = "Вы указали прочее."

        # Обработка результата
        if result.get('error') == False:
            if status_s3['status'] == 'created':
                text = f"{bot_message} Скан успешно сохранен. {result.get('data')}"
                logging.info(f"Успех: {text}")
                return text
            elif status_s3['status'] == 'exists':
                text = f"{bot_message} Скан уже существует. {result.get('data')}"
                logging.warning(f"Предупреждение: {text}")
                return text
            else:
                text = f"{bot_message} Скан уже существует. {result.get('data')}"
                logging.warning(f"Предупреждение: {text}")
                return text
        else:
            error_msg = result.get('error_msg')
            logging.error(f"Ошибка при обработке изображения: {error_msg}")
    except Exception as e:
        logging.error(f"Ошибка при обработке накладной: {e}")