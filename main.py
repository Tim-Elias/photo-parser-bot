import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv
from handlers import router  # Импортируем router из handlers
from logger import setup_logging
# Загрузить переменные окружения
load_dotenv()
API_TOKEN = os.getenv('TG_API_TOKEN')


logger = setup_logging()
logger.info("Бот запущен!")
# Создаем объекты бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Регистрируем router с хендлерами
dp.include_router(router)


@dp.message(Command("start"))
async def handle_start(message: Message):
    await message.answer("Привет, я бот!")


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
