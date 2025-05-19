import json
import os
import logging
import aiohttp
from dotenv import load_dotenv

logger = logging.getLogger("telegram_bot")

load_dotenv()

url_check_number = os.getenv('URL_CHECK_NUMBER')
url_sent_data = os.getenv('URL_SENT_DATA')


async def post_and_process(payload, headers):
    try:
        logger.info(f"[CHECK_NUMBER] Отправка запроса на {url_check_number}")
        logger.debug(f"[CHECK_NUMBER] Payload: {json.dumps(payload)}")
        logger.debug(f"[CHECK_NUMBER] Headers: {headers}")
        async with aiohttp.ClientSession() as session:
            async with session.post(url_check_number, data=json.dumps(payload), headers=headers) as response:
                logger.info(
                    f"[CHECK_NUMBER] Получен ответ со статусом {response.status}")
                text_response = await response.text()  # Получаем текст
                logger.debug(f"[CHECK_NUMBER] Тело ответа: {text_response}")
                if response.status == 200:
                    try:
                        return json.loads(text_response)
                    except json.JSONDecodeError as json_error:
                        logger.error(
                            f"Ошибка при декодировании JSON: {json_error}")
                        return {'error': f"Неправильный формат ответа: {text_response}"}
                else:
                    return {'error': f"HTTP Error: {response.status}"}
    except Exception as e:
        logger.exception(
            f"[CHECK_NUMBER] Ошибка при выполнении POST запроса: {e}")
        return {'error': str(e)}


async def post_request(qr_data, s3_file_key, status, headers):
    payload = {
        "Number": f"{qr_data}",
        "hash": f"{s3_file_key}",
        "status": f"{status}"
    }
    logger.info(f"[SENT_DATA] Отправка запроса на {url_sent_data}")
    logger.debug(f"[SENT_DATA] Payload: {json.dumps(payload)}")
    logger.debug(f"[SENT_DATA] Headers: {headers}")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url_sent_data, data=json.dumps(payload), headers=headers) as response:
                logger.info(
                    f"[SENT_DATA] Получен ответ со статусом {response.status}")
                text_response = await response.text()
                logger.debug(f"[SENT_DATA] Тело ответа: {text_response}")
                if response.status == 200:
                    try:
                        return json.loads(text_response)
                    except json.JSONDecodeError as json_error:
                        logger.error(
                            f"[SENT_DATA] Ошибка при декодировании JSON: {json_error}")
                        return {'error': f"Неправильный формат ответа: {text_response}"}
                else:
                    return {'error': f"HTTP Error: {response.status}"}
        except Exception as e:
            logger.exception(
                f"[SENT_DATA] Ошибка при выполнении POST запроса: {e}")
            return {'error': str(e)}
