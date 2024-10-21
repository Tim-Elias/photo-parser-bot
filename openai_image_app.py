from dotenv import load_dotenv
import os
import openai 
from openai import AsyncOpenAI
import base64
import cv2
import numpy as np
from PIL import Image
import io
import pytesseract
import json
import requests
from utils import convert_image_to_base64
import logging

load_dotenv()

# Проверка ориентации изображения
def check_text_orientation(image):
    # Преобразуем изображение в градации серого
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray)
    # Определяем количество символов. Если их достаточно, считаем изображение правильным.
    return len(text) > 10

# Поворот изображения на 90 градусов
def rotate_image_90_degrees(image, clockwise=False):
    # Поворот изображения на 90 градусов
    if clockwise:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    else:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)

# Извлечение номера накладной с помощью openai
async def get_invoice_from_image(base64_image):
    try:
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                    },
                    },
                ],
                }
            ],
            max_tokens=300,
        )
        # Извлечение содержимого content
        content = response.choices[0].message.content
        logging.info(f"Извлечен номер накладной: {content}.")
        return content
    except Exception as e:
        logging.error(f"Произошла общая ошибка: {e}")
        return {"error": str(e)}

openai.api_key=os.getenv('OPENAI_API_KEY')
client = AsyncOpenAI()

prompt="""
{
    "role": "Ты ассистент логиста транспортной компании, ты интегрирован в чат telegram. ТЫ получаешь фотографии из чата",
    "prompt": "Ты можешь получать различные фотографии, в том числе фотографии документов на перевозку груза, или любые другие фотографии, например фотографии грузов",
    "tasks": [
        {
            "task01": {
                "task": "определи, предоставлена ли тебе фотография документа на перевозку груза, содержащая данные отправителя, получателя и номер документа",
                "result01": "Если фотография является документом на перевозку груза переходи к task02",
                "result02": "Если фотография не является документом на перевозку груза запиши в переменную error значение True, в переменную number значение "Номер накладной отсутствует""
            }
        },
        {
            "task02": "Если фотография является документом на перевозку груза, найди на фотографии номер документа.  Это самая крупная надпись печатными цифрами в левом или правом верхнем углу. Найди на фотографии номер документа. Все, что после номера игнорируй (например, если написано АЗ-22-04 от 29.12.2022, то номер это  АЗ-22-04). запиши в переменную error значение False,  в переменную number Номер документа"
        },
        {
            "task03": "верни в ответе объект с ключами и значениями error и number, например ",
            "example01": {
                "number": "АЗ-22-04",
                "error": "False"
            },
            "example02": {
                "number": "Номер накладной отсутствует",
                "error": "True"
            }
        }
    ]
}
"""

# Асинхронная функция для обработки изображения и извлечения номера накладной
async def get_number_using_openai(base64_image):
    try:
        # Декодируем изображение из base64
        image_data = base64.b64decode(base64_image)
        try:
            # Создаем поток для работы с изображением
            image_stream = io.BytesIO(image_data)
            pil_image = Image.open(image_stream)
            
            # Конвертируем изображение в формат RGB
            pil_image = pil_image.convert("RGB")
            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            
            # Проверка ориентации текста
            if not check_text_orientation(cv_image):
                # Поворот изображения, если текст не читается
                for _ in range(3):
                    cv_image = rotate_image_90_degrees(cv_image, clockwise=False)
                    if check_text_orientation(cv_image):
                        break

            # Конвертируем изображение обратно в base64
            base64_image = convert_image_to_base64(cv_image)
            
            # Асинхронно извлекаем данные накладной
            invoice_data = await get_invoice_from_image(base64_image)
            return json.loads(invoice_data)
        finally:
            # Закрываем изображения и поток
            pil_image.close()
            image_stream.close()
    except requests.RequestException as e:
        return {"error": str(e)}
    finally:
        del image_data, image_stream, pil_image, cv_image

    