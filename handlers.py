import logging
from aiogram import Bot, Router, types, F  # Используем F для фильтрации
from aiogram.filters import Command
from state import user_images, user_states  # Глобальные переменные для состояния
from image_processing import handle_image, invoice_processing  # Функции для обработки изображений

# Создаем роутер для регистрации хендлеров
router = Router()

# Обработчик фотографий
@router.message(F.content_type == 'photo')
async def handle_photo(message: types.Message, bot: Bot):
    logging.info("Обработка фотографии.")
    user_id = message.from_user.id
    await handle_image(message, user_id, is_document=False, bot=bot)

# Обработчик документов
@router.message(F.content_type == 'document')
async def handle_document(message: types.Message, bot: Bot):
    logging.info("Обработка документа.")
    user_id = message.from_user.id
    file_name = message.document.file_name

    if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
        await handle_image(message, user_id, is_document=True, bot=bot)
    else:
        logging.warning(f"Некорректный формат файла для пользователя {user_id}: {file_name}")

# Обработчик callback-кнопок
# Обработчик callback-кнопок
@router.callback_query(lambda call: call.data.split(':')[0] in ["received", "delivered", "other"])
async def handle_inline_button(call: types.CallbackQuery, bot: Bot):
    user_id = call.message.chat.id
    action, image_id = call.data.split(':')

    logging.info(f"Получен запрос от пользователя {user_id} для изображения {image_id} с действием {action}.")

    # Добавляем дополнительные логи для отладки
    logging.info(f"Проверка наличия изображения {image_id} для пользователя {user_id}.")
    if user_id in user_images:
        logging.info(f"Текущие изображения для пользователя {user_id}: {list(user_images[user_id].keys())}")
    else:
        logging.warning(f"Состояние пользователя {user_id} отсутствует.")

    # Приводим image_id к правильному типу
    if user_id not in user_images or int(image_id) not in user_images[user_id]:
        logging.warning(f"Изображение {image_id} не найдено у пользователя {user_id}.")
        return

    image_data = user_images[user_id][int(image_id)]  # Убедитесь, что используете int
    invoice = image_data['invoice']
    
    logging.info(f"Обработка статуса '{action}' для накладной {invoice} от пользователя {user_id}.")

    # Вызываем функцию обработки накладной
    text = await invoice_processing(invoice, image_data.get('base64_image'), image_data.get('file_extension'), action)

    await call.answer(text)
    await call.message.edit_reply_markup(reply_markup=None)

    # Логируем информацию перед удалением изображения
    logging.info(f"Состояние перед удалением изображения {image_id} для пользователя {user_id}.")

    # Удаляем текущее изображение из списка
    del user_images[user_id][int(image_id)]
    logging.info(f"Изображение {image_id} удалено из списка для пользователя {user_id}.")

    # Проверяем, есть ли еще изображения для обработки
    if not user_images[user_id]:
        logging.info(f"У пользователя {user_id} больше нет изображений для обработки. Состояние сброшено.")
        
        # Проверяем, существует ли запись в user_states, прежде чем удалять её
        if user_id in user_states:
            del user_states[user_id]
        else:
            logging.warning(f"Пользователь {user_id} отсутствует в user_states.")
    
    # Логируем состояние после удаления, не выводя base64
    logging.info(f"Состояние user_images после обработки для пользователя {user_id}: {list(user_images.get(user_id, {}).keys())}")





