# image_tasks.py
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from state import user_images, user_states  # Импортируем глобальные переменные для хранения состояний
from post_requests import post_and_process  # Ваша функция для POST-запроса

# Функция для обработки изображения
async def process_image(user_id: int, image_id: int, bot: Bot):
    logging.info(f"Начинаем обработку изображения {image_id} для пользователя {user_id}.")
    
    # Логируем краткое состояние user_images перед обработкой
    if user_id in user_images:
        logging.info(f"Пользователь {user_id} имеет {len(user_images[user_id])} изображений для обработки.")
    
    if user_id in user_images and user_images[user_id]:
        image_data = user_images[user_id].get(image_id)

        if image_data:
            invoice = image_data['invoice']
            payloads = {"Number": invoice}
            headers = {'Content-Type': 'application/json'}

            response = await post_and_process(payloads, headers)
            logging.info(f"Ответ сервера на запрос накладной: {response.get('status')}")

            if response.get('status') == 'ok':
                # Отправка сообщения с выбором действий
                markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="Получено", callback_data=f"received:{image_id}")],
                        [InlineKeyboardButton(text="Доставлено", callback_data=f"delivered:{image_id}")],
                        [InlineKeyboardButton(text="Прочее", callback_data=f"other:{image_id}")]
                    ]
                )
                await bot.send_message(user_id, f"Выберите действие для накладной {invoice}:", reply_markup=markup)
                logging.info(f"Отправлено сообщение пользователю {user_id} с выбором действий.")
            else:
                await bot.send_message(user_id, f"Накладная {invoice} не найдена.")
                logging.warning(f"Накладная {invoice} не найдена для пользователя {user_id}.")
                # Удаляем изображение из списка
                del user_images[user_id][image_id]
                logging.info(f"Изображение {image_id} удалено из списка для пользователя {user_id}.")
                # Логируем краткое состояние user_images после обработки
                if user_id in user_images:
                    logging.info(f"Пользователь {user_id} теперь имеет {len(user_images[user_id])} изображений.")
                if not user_images[user_id]:
                    user_states[user_id] = {}
                    logging.info(f"У пользователя {user_id} нет изображений для обработки.")


