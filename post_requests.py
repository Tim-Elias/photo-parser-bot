import json
import aiohttp
import os
import logging
from dotenv import load_dotenv

load_dotenv()

url_check_number = os.getenv('URL_CHECK_NUMBER')
url_sent_data = os.getenv('URL_SENT_DATA')

async def post_and_process(payload, headers):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url_check_number, data=json.dumps(payload), headers=headers) as response:
                
                
                if response.status == 200:
                    text_response = await response.text()  # Получаем текст
                    try:
                        logging.info(f"Статус ответа: {response.status}, текст ответа {response.text()}")
                        return json.loads(text_response)  # Пробуем преобразовать в JSON
                    except json.JSONDecodeError as json_error:
                        logging.error(f"Ошибка при декодировании JSON: {json_error}")
                        return {'error': f"Неправильный формат ответа: {text_response}"}
                else:
                    return {'error': f"HTTP Error: {response.status}"}
    except Exception as e:
        logging.error(f"Ошибка при выполнении POST запроса: {e}")
        return {'error': str(e)}

async def post_request(qr_data, s3_file_key, status, headers):
    payload = {
        "Number": f"{qr_data}",
        "hash": f"{s3_file_key}",
        "status": f"{status}"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url_sent_data, data=json.dumps(payload), headers=headers) as response:
                
                
                if response.status == 200:
                    logging.info(f"Статус ответа: {response.status}, текст ответа {response.text()}")
                    text_response = await response.text()  # Получаем текст
                    try:
                        return json.loads(text_response)  # Пробуем преобразовать в JSON
                    except json.JSONDecodeError as json_error:
                        logging.error(f"Ошибка при декодировании JSON: {json_error}, текст ответа: {text_response}")
                        return {'error': f"Неправильный формат ответа: {text_response}"}
                else:
                    return {'error': f"HTTP Error: {response.status}"}
        except Exception as e:
            logging.error(f"Ошибка при выполнении POST запроса: {e}")
            return {'error': str(e)}

