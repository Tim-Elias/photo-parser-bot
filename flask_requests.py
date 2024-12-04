import logging
import json
import requests
import base64
import os
from io import BytesIO
from dotenv import load_dotenv
load_dotenv()

url = os.getenv('URL')

headers = {'Content-Type': 'application/json'}

def send_text_to_flask(message):
    url_t = url+"/gateway/text"  # URL вашего Flask-приложения

    # Подготовка данных
    data = {
        'message': {
            'user_id': message.from_user.id,
            'chat_id': message.chat.id,
            'timestamp': int(message.date.timestamp()),  # Отправляем как Unix-время (int)
            'text': message.text,  # Само текстовое сообщение
            'content_type': message.content_type
        }
    }

    # Логируем подготовленные данные
    logging.debug(f"Отправляем данные на {url_t}")

    try:
        response = requests.post(url_t, json=data, headers=headers)
        logging.debug(f"Ответ сервера: {response.status_code}")
    except Exception as e:
        logging.error(f"Ошибка отправки данных: {e}", exc_info=True)  # exc_info добавляет полный трейсбэк



def send_file_to_flask(file_content, file_name, message):
    url_f = url+"/gateway/file"  # URL ручки Flask
        # Преобразуем BytesIO в bytes
    if isinstance(file_content, BytesIO):  # Проверяем, если это объект BytesIO
        file_content = file_content.read()
    # Кодируем содержимое файла в Base64
    encoded_file = base64.b64encode(file_content).decode('utf-8')

    # Подготовка данных для отправки
    data = {
        'file_name': file_name,
        'file_content': encoded_file,  # Закодированное содержимое
        'message': {
            'user_id': message.from_user.id,
            'chat_id': message.chat.id,
            'timestamp': int(message.date.timestamp()),  # Отправляем как Unix-время (int)
            'caption': message.caption,  # Может быть None, если нет текста
            'content_type': message.content_type
        }
    }

    # Логируем подготовленные данные
    logging.debug(f"Отправляем данные на {url_f}")

    try:
        # Отправляем запрос
        response = requests.post(url_f, json=data, headers=headers)

        # Логируем успешный ответ
        logging.debug(f"Ответ сервера: {response.status_code}, {response.text}")
    except Exception as e:
        logging.error(f"Ошибка отправки файла: {e}", exc_info=True)