import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from state import images  # Импортируем глобальные переменные для хранения состояний
from post_requests import post_and_process  # Ваша функция для POST-запроса
from utils import resize_image
from io import BytesIO
from aiogram.types import BufferedInputFile 
logger = logging.getLogger(__name__)

# Функция для обработки изображения
async def process_image(user_id, image_id, bot):
    logger.info(f"Начинаем обработку изображения {image_id} для пользователя {user_id}.")
    
    if image_id in images and images[image_id]:
        image_data = images[image_id]

        if image_data:
            invoice = image_data['invoice']
            pil_image = image_data['pil_image']  # Получаем изображение
            payloads = {"Number": invoice}
            headers = {'Content-Type': 'application/json'}

            response = await post_and_process(payloads, headers)
            logger.info(f"Ответ сервера на запрос накладной: {response.get('status')}")

            if response.get('status') == 'ok':
                try:
                    # Преобразование изображения в уменьшенную копию
                    thumbnail = resize_image(pil_image, scale_factor=0.5)

                    # Сохраняем уменьшенное изображение в буфер
                    image_buffer = BytesIO()
                    thumbnail.save(image_buffer, format='JPEG')
                    image_buffer.seek(0)  # Не забываем перемещать указатель в начало буфера

                    # Добавляем логирование для отладки
                    logger.info(f"Буфер изображения готов, размер: {image_buffer.getbuffer().nbytes} байт")

                    # Создаем объект BufferedInputFile для корректного использования в aiogram
                    input_file = BufferedInputFile(image_buffer.getvalue(), filename='thumbnail.jpg')
                    logger.info(f"Отправляем ответ на сообщение: {image_data['message_id']}")
                    # Отправка уменьшенной копии изображения
                    sent_message = await bot.send_photo(
                            user_id,
                            input_file,
                            caption=f"Выберите действие для накладной {invoice}:",  # Текст с описанием
                            reply_to_message_id=image_data['message_id'],  # Ответ на оригинальное сообщение
                            reply_markup=InlineKeyboardMarkup(
                                inline_keyboard=[
                                    [InlineKeyboardButton(text="Забрана", callback_data=f"received:{image_id}")],
                                    [InlineKeyboardButton(text="Доставлено", callback_data=f"delivered:{image_id}")],
                                    [InlineKeyboardButton(text="Прочее", callback_data=f"other:{image_id}")]
                                ]
                            )
                        )
                    # Сохраняем как message_id, так и caption для редактирования позже
                    images[image_id]['new_message_id']=sent_message.message_id
                    logger.info(f"Отправлено сообщение пользователю {user_id} с выбором действий.")
                    logger.info(f"Отправлено сообщение c message_id: {image_data['message_id']}.")
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






