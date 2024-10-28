from dotenv import load_dotenv
import os
import openai 
from openai import AsyncOpenAI
import cv2
import pytesseract
import json
import requests
#from better_image import enhance_image
from utils import convert_image_to_base64
from prompt import prompt, keywords
import logging


logger = logging.getLogger(__name__)

load_dotenv()




# Поворот изображения на 90 градусов
def rotate_image_90_degrees(image, clockwise=False):
    # Поворот изображения на 90 градусов
    if clockwise:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    else:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)



# Проверка ориентации текста на русском языке
def check_text_orientation(image):
    logger.info("Начало проверки ориентации текста.")
    custom_config = '--oem 3 --psm 6 -l rus'  # Либо 11, в зависимости от ваших нужд
    text = pytesseract.image_to_string(image, config=custom_config)
    logger.info(f"Извлеченнный текст: {text}")
    
    # Проверка наличия ключевых слов (без учета регистра)
    if any(keyword in text.lower() for keyword in keywords):
        result=True
    else:
        result = False
    #result = len(text) > 10
    logger.info(f"Ориентация текста {'правильная' if result else 'неправильная'} (количество символов: {len(text)}).")

    return result



# Извлечение номера накладной с помощью openai
async def get_invoice_from_image(base64_image):
    try:
        logger.info("Начало запроса к OpenAI для извлечения номера накладной.")
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{
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
            }]
        )
        content = response.choices[0].message.content
        logger.info(f"Успешно извлечен номер накладной: {content}")
        return content
    except Exception as e:
        logger.error(f"Ошибка при запросе к OpenAI: {e}")
        return {"error": str(e)}

openai.api_key = os.getenv('OPENAI_API_KEY')
client = AsyncOpenAI()

# Основная функция для обработки изображения и получения номера накладной
async def get_number_using_openai(cv_image):
    try:
        #cv_image = enhance_image(cv_image)
        logger.info("Начало обработки изображения для извлечения номера накладной.")
        is_readable = check_text_orientation(cv_image)
        if not is_readable:
            for attempt in range(1,4):  # Проверяем 4 попытки: 0, 90, 180, 270 градусов
                cv_image = rotate_image_90_degrees(cv_image, clockwise=False)
                is_readable = check_text_orientation(cv_image)
                if is_readable:
                    logger.info(f"Текст стал читаемым после поворота (попытка {attempt}).")
                    break
            else:
                logger.warning("Не удалось сделать текст читаемым после четырех поворотов.")

        base64_image = convert_image_to_base64(cv_image)
        logger.debug("Изображение перекодировано в base64 для отправки в OpenAI.")
        
        invoice_data = await get_invoice_from_image(base64_image)
        logger.info("Номер накладной успешно извлечен.")
        # Убираем префикс "json" и переводим одинарные кавычки в двойные
        return json.loads(invoice_data)

    except requests.RequestException as e:
        logger.error(f"Ошибка сети при запросе: {e}")
        return {"error": str(e)}

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return {"error": str(e)}
