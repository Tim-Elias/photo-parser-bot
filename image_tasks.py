import logging
from io import BytesIO
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from state import images, info_chat_ids
from post_requests import post_and_process
from utils import resize_image
from image_processing import invoice_processing

logger = logging.getLogger(__name__)

# Функция для обработки изображения


async def process_image(user_id, image_id, bot):
    logger.info(
        f"Начинаем обработку изображения {image_id} для пользователя {user_id}.")

    if image_id in images and images[image_id]:
        image_data = images[image_id]

        if image_data:
            invoice = image_data['invoice']
            pil_image = image_data['pil_image']  # Получаем изображение
            payloads = {"Number": invoice}
            headers = {'Content-Type': 'application/json'}

            response = await post_and_process(payloads, headers)
            logger.info(
                f"Ответ сервера на запрос накладной: {response.get('status')}")

            if response.get('status') == 'ok':
                try:
                    # Преобразование изображения в уменьшенную копию
                    thumbnail = resize_image(pil_image, scale_factor=1)

                    # Сохраняем уменьшенное изображение в буфер
                    image_buffer = BytesIO()
                    thumbnail.save(image_buffer, format='JPEG')
                    # Не забываем перемещать указатель в начало буфера
                    image_buffer.seek(0)

                    logger.info(
                        f"Буфер изображения готов, размер: {image_buffer.getbuffer().nbytes} байт")

                    # Создаем объект BufferedInputFile для корректного использования в aiogram
                    input_file = BufferedInputFile(
                        image_buffer.getvalue(), filename='thumbnail.jpg')
                    logger.info(
                        f"Отправляем ответ на сообщение: {image_data['message_id']}")
                    logger.info(
                        f"user_id: {user_id}, info_chat_ids: {info_chat_ids}")
                    if user_id not in info_chat_ids:

                        sent_message = await bot.send_photo(
                            user_id,
                            input_file,
                            # Текст с описанием
                            caption=f"Выберите действие для накладной {invoice}:",
                            # Ответ на оригинальное сообщение
                            reply_to_message_id=image_data['message_id'],
                            reply_markup=InlineKeyboardMarkup(
                                inline_keyboard=[
                                    [InlineKeyboardButton(
                                        text="Забрана", callback_data=f"received:{image_id}")],
                                    [InlineKeyboardButton(
                                        text="Доставлено", callback_data=f"delivered:{image_id}")],
                                    [InlineKeyboardButton(
                                        text="Прочее", callback_data=f"other:{image_id}")]
                                ]
                            )
                        )
                        # Сохраняем как message_id, так и caption для редактирования позже
                        images[image_id]['new_message_id'] = sent_message.message_id
                        logger.info(
                            f"Отправлено сообщение пользователю {user_id} с выбором действий.")
                        logger.info(
                            f"Отправлено сообщение c message_id: {image_data['message_id']}.")

                    else:
                        text, _ = await invoice_processing(invoice, image_data.get('base64_image'), image_data.get('file_extension'), "other")
                        await bot.send_message(
                            chat_id=image_data['user_id'],
                            text=f"{text}",
                            # Ответ на оригинальное сообщение
                            reply_to_message_id=image_data.get('message_id')
                        )
                        del images[image_id]

                except Exception as e:
                    logger.error(f"Ошибка при обработке изображения: {e}")
                finally:
                    image_buffer.close()
            else:
                await bot.send_message(
                    user_id,
                    f"Накладная {invoice} не найдена.",
                    reply_to_message_id=image_data['message_id']
                )
                del images[image_id]
