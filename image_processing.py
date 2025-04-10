import io
import uuid
import logging
from PIL import Image
import numpy as np
from aiogram.exceptions import TelegramForbiddenError
import cv2
from utils import get_QR, convert_image_to_base64
from state import images  # Импортируем данные о пользователях из state
# Можно безопасно импортировать процессор изображения
from image_tasks import process_image
from openai_image_app import get_number_using_openai
from s3_utils import S3Handler
from post_requests import post_request


s3_handler = S3Handler()

logger = logging.getLogger(__name__)


async def handle_image(message, user_id, is_document, bot):
    logger.info(f"Обработка изображения от пользователя {user_id}.")

    try:
        if is_document:
            file_info = await bot.get_file(message.document.file_id)
        else:
            file_info = await bot.get_file(message.photo[-1].file_id)

        file_path = file_info.file_path
        file_extension = file_path.split('.')[-1]
        downloaded_file = await bot.download_file(file_path)
        # Получаем байтовые данные
        image_stream = io.BytesIO(downloaded_file.getvalue())

        logger.info(f"Файл {file_path} загружен успешно.")

        # Открытие и обработка изображения
        try:
            pil_image = Image.open(image_stream)
            # Убедимся, что изображение в RGB формате
            pil_image = pil_image.convert("RGB")
            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

        except Exception as e:
            logger.error(f"Ошибка при открытии или обработке изображения: {e}")
            return

        base64_image = convert_image_to_base64(cv_image)
        invoice = get_QR(cv_image)
        logger.error(f"Извлекли номер из QR: {invoice}.")
        error = None
        if invoice is None:
            invoice_data = await get_number_using_openai(cv_image)
            invoice = invoice_data['number']
            error = invoice_data['error']

            logger.info(f"Получили номер через OpenAI: {invoice_data}")

            if invoice == "Номер накладной отсутствует":
                # Не продолжаем обработку
                try:
                    await bot.send_message(user_id, "Не удалось распознать номер накладной.")
                except TelegramForbiddenError:
                    logger.error(
                        f"Бот не может отправить сообщение пользователю {user_id}. Возможно, он заблокирован.")
                except Exception as e:
                    logger.exception(
                        f"Ошибка при отправке сообщения пользователю {user_id}: {e}")

                if error:
                    logger.warning(
                        f"Фото не является накладной для пользователя {user_id}.")
                else:
                    logger.warning(
                        f"Это накладная, но номер не удалось распознать для пользователя {user_id}.")
                return

        else:

            image_id = str(uuid.uuid4())
            images[image_id] = {
                "invoice": invoice,
                "file_extension": file_extension,
                "base64_image": base64_image,
                "message_id": message.message_id,
                "pil_image": pil_image,  # Сохраняем изображение
                "user_id": user_id,
                "new_message_id": None
            }

            logger.info(
                f"Изображение сохранено: {image_id} для пользователя {user_id} с накладной {invoice} с message_id: {images[image_id]['message_id']}.")
            await process_image(user_id, image_id, bot)

    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}")
    finally:
        if 'image_stream' in locals():
            image_stream.close()


async def invoice_processing(invoice, base64_image, file_extension, status):
    logger.info(f"Обработка накладной: {invoice}, статус: {status}.")

    try:
        status_s3, s3_file_key = await s3_handler.post_s3(base64_image, file_extension)
        headers = {'Content-Type': 'application/json'}

        # Теперь это асинхронно
        result = await post_request(invoice, s3_file_key, status, headers)
        logger.info(f"Результат запроса на сервер: {result}")

        # Формируем сообщение пользователю
        if status == 'delivered':
            bot_message = f"Вы указали, что накладная {invoice} доставлена."
        elif status == 'received':
            bot_message = f"Вы указали, что накладная {invoice} забрана."
        else:
            bot_message = f"Вы указали прочее для накладной {invoice}."

        # Обработка результата
        if result.get('error') is False:
            if status_s3['status'] == 'created':
                text = f"{bot_message} Скан успешно сохранен. {result.get('data')}"
                logger.info(f"Успех: {text}")
                return text, bot_message
            elif status_s3['status'] == 'exists':
                text = f"{bot_message} Скан уже существует. {result.get('data')}"
                logger.warning(f"Предупреждение: {text}")
                return text, bot_message
            else:
                text = f"{bot_message} Скан уже существует. {result.get('data')}"
                logger.warning(f"Предупреждение: {text}")
                return text, bot_message
        else:
            error_msg = result.get('error_msg')
            logger.error(f"Ошибка при обработке изображения: {error_msg}")
    except Exception as e:
        logger.error(f"Ошибка при обработке накладной: {e}")
