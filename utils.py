import cv2
import base64
from pyzbar.pyzbar import decode

def convert_image_to_base64(image):
    _, buffer = cv2.imencode('.jpg', image)
    base64_str = base64.b64encode(buffer).decode('utf-8')
    return base64_str

def get_QR(image):
    qr_codes = decode(image)
    if qr_codes:
        return qr_codes[0].data.decode('utf-8')
    return None

def resize_image(image, scale_factor):
    width = int(image.shape[1] * scale_factor)
    height = int(image.shape[0] * scale_factor)
    return cv2.resize(image, (width, height))


import hashlib

# Преобразование в хэш
def hash_string(data: str, algorithm: str = 'sha256') -> str:
    # Создаем объект хэш-функции
    hash_obj = hashlib.new(algorithm)
    # Обновляем объект хэш-функции данными (строка должна быть закодирована в байты)
    hash_obj.update(data.encode('utf-8'))
    # Получаем хэш-сумму в виде шестнадцатеричной строки
    return hash_obj.hexdigest()