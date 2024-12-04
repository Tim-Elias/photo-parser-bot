import aiohttp
import logging
import base64
from io import BytesIO
import os
from dotenv import load_dotenv

load_dotenv()


url = os.getenv('URL')


headers = {'Content-Type': 'application/json'}

async def send_text_to_flask(message):
    url_t = f"{url}/gateway/text"  # URL вашего Flask-приложения

    data = {
        'message': {
            'user_id': message.from_user.id,
            'chat_id': message.chat.id,
            'timestamp': int(message.date.timestamp()),  # Отправляем как Unix-время
            'text': message.text,
            'content_type': message.content_type
        }
    }

    logging.debug(f"Отправляем данные на {url_t}: {data}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url_t, json=data, headers=headers) as response:
                resp_text = await response.text()
                logging.debug(f"Ответ сервера: {response.status} {resp_text}")
    except Exception as e:
        logging.error(f"Ошибка отправки данных: {e}", exc_info=True)


async def send_file_to_flask(file_content, file_name, message):
    url_f = f"{url}/gateway/file"

    if isinstance(file_content, BytesIO):
        file_content = file_content.read()
    
    encoded_file = base64.b64encode(file_content).decode('utf-8')

    data = {
        'file_name': file_name,
        'file_content': encoded_file,
        'message': {
            'user_id': message.from_user.id,
            'chat_id': message.chat.id,
            'timestamp': int(message.date.timestamp()),
            'caption': message.caption,
            'content_type': message.content_type
        }
    }

    logging.debug(f"Отправляем файл на {url_f}: {file_name}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url_f, json=data, headers=headers) as response:
                resp_text = await response.text()
                logging.debug(f"Ответ сервера: {response.status} {resp_text}")
    except Exception as e:
        logging.error(f"Ошибка отправки файла: {e}", exc_info=True)
