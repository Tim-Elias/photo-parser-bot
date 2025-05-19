import logging
import os


def setup_logging(log_dir: str = "logs", log_filename: str = "bot.log", logger_name: str = "telegram_bot") -> logging.Logger:
    # Убедимся, что директория для логов существует
    os.makedirs(log_dir, exist_ok=True)

    # Полный путь до лог-файла
    log_path = os.path.join(log_dir, log_filename)

    # Настройка логирования
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path, mode='a', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger(logger_name)
    logger.debug("Логгер инициализирован.")
    return logger
