import logging
import os

# Убедимся, что директория для логов существует
if not os.path.exists('logs'):
    os.makedirs('logs')

# Настроим логирование
logging.basicConfig(
    level=logging.INFO,  # Уровень логов
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Формат логов
    handlers=[
        logging.FileHandler('logs/bot.log', mode='a', encoding='utf-8'),  # Запись логов в файл
        logging.StreamHandler()  # Дублирование логов в консоль
    ]
)

logger = logging.getLogger(__name__)

# Пример использования логгера
logger.info("Бот запущен!")
