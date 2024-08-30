# Изменение размера изображения
import cv2

def resize_image(image, scale_factor=2.0):
    # Увеличиваем изображение в два раза
    width = int(image.shape[1] * scale_factor)
    height = int(image.shape[0] * scale_factor)
    dim = (width, height)
    resized_image = cv2.resize(image, dim, interpolation=cv2.INTER_CUBIC)
    return resized_image