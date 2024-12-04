import logging
from aiogram import Bot, Router, types, F  # Используем F для фильтрации
from state import images, user_states  # Глобальные переменные для состояния
from image_processing import handle_image, invoice_processing  # Функции для обработки изображений
from aiogram.exceptions import TelegramForbiddenError
from flask_requests import send_file_to_flask, send_text_to_flask

logger = logging.getLogger(__name__)
# Создаем роутер для регистрации хендлеров
router = Router()

# Обработчик текстовых сообщений
@router.message(F.content_type == 'text')
async def handle_text_message(message: types.Message, bot: Bot):
    logger.info(f"Обработка текстового сообщения от пользователя {message.chat.id}.")
    try:
        await send_text_to_flask(message)  # Отправка текста в Flask
    except Exception as e:
        logger.error(f"Ошибка при обработке текстового сообщения: {e}")


@router.message(F.content_type == 'photo')
async def handle_photo(message: types.Message, bot: Bot):
    logger.info("Обработка фотографии.")
    user_id = message.chat.id
    # Берем самое большое изображение
    photo = message.photo[-1]
    # Получаем файл
    file_info = await bot.get_file(photo.file_id)
    # Получаем содержимое файла
    file_content = await bot.download_file(file_info.file_path)
    # Генерируем имя файла (например, используем file_id)
    file_name = f"{photo.file_id}.jpg"
    await send_file_to_flask(file_content, file_name, message)
    del file_content
    try:
        await handle_image(message, user_id, is_document=False, bot=bot)
    except TelegramForbiddenError:
        logger.error(f"Бот не может отправить сообщение пользователю {user_id}. Возможно, бот заблокирован.")
    except Exception as e:
        logger.error(f"Ошибка при обработке фотографии от пользователя {user_id}: {e}")


@router.message(F.content_type == 'document')
async def handle_document(message: types.Message, bot: Bot):
    logger.info("Обработка документа.")
    user_id = message.chat.id
    file_name = message.document.file_name

    try:
        if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
            # Если документ — это изображение, обрабатываем как файл
            file_info = await bot.get_file(message.document.file_id)
            file_content = await bot.download_file(file_info.file_path)
            file_name = f"{message.document.file_id}_{file_name}"
            await send_file_to_flask(file_content, file_name, message)
            del file_content
            await handle_image(message, user_id, is_document=True, bot=bot)
        else:
            # Для других документов
            logger.warning(f"Некорректный формат файла для пользователя {user_id}: {file_name}")
            document = message.document
            if document.file_size <= 5 * 1024 * 1024:  # Ограничение на размер файла (5 MB)
                file_info = await bot.get_file(document.file_id)
                file_content = await bot.download_file(file_info.file_path)
                file_name = f"{document.file_id}_{document.file_name}"
                await send_file_to_flask(file_content, file_name, message)
                del file_content
            else:
                logger.warning(f"Файл слишком большой для обработки: {file_name}")
    except TelegramForbiddenError:
        logger.error(f"Бот не может отправить сообщение пользователю {user_id}. Возможно, бот заблокирован.")
    except Exception as e:
        logger.error(f"Ошибка при обработке документа от пользователя {user_id}: {e}")



# Обработчик голосовых сообщений
@router.message(F.content_type == 'voice')
async def handle_audio(message: types.Message, bot: Bot):
    logger.info("Обработка голосового сообщения.")
    user_id = message.chat.id
    voice = message.voice

    try:
        file_info = await bot.get_file(voice.file_id)
        file_content = await bot.download_file(file_info.file_path)
        file_name = f"{voice.file_id}.ogg"
        await send_file_to_flask(file_content, file_name, message)  # Отправка аудио в Flask
        del file_content
    except TelegramForbiddenError:
        logger.error(f"Бот не может отправить сообщение пользователю {user_id}. Возможно, бот заблокирован.")
    except Exception as e:
        logger.error(f"Ошибка при обработке голосового сообщения от пользователя {user_id}: {e}")


# Обработчик callback-кнопок
@router.callback_query(lambda call: call.data.split(':')[0] in ["received", "delivered", "other"])
async def handle_inline_button(call: types.CallbackQuery, bot: Bot):
    user_id = call.message.chat.id
    action, image_id = call.data.split(':')
    logger.info(f"Получен запрос от пользователя {user_id} для изображения {image_id} с действием {action}.")
    try:
        if image_id not in images:
            return
        image_data = images[image_id]
        invoice = image_data['invoice']
        message_id = image_data.get('message_id')
        logger.info(f"Получен message_id.{message_id}")
        logger.info(f"Обработка статуса '{action}' для накладной {invoice} от пользователя {user_id}.")
        text, bot_message = await invoice_processing(invoice, image_data.get('base64_image'), image_data.get('file_extension'), action)
        await call.answer(text)

        # Удаляем предыдущее сообщение
        await bot.delete_message(chat_id=image_data['user_id'], message_id=image_data['new_message_id'])

        # Отправляем новое сообщение с ответом на оригинальное
        await bot.send_message(
            chat_id=image_data['user_id'],
            text=f"{bot_message}",
            reply_to_message_id=image_data['message_id']  # Ответ на оригинальное сообщение
        )

        del images[image_id]


    except Exception as e:
        logger.error(f"Ошибка при обработке callback-кнопки от пользователя {user_id}: {e}")


