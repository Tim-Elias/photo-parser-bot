import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.dispatcher.router import Router
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv
import os
from handlers import router  # Импортируем router из handlers

# Загрузить переменные окружения
load_dotenv()
API_TOKEN = os.getenv('TG_API_TOKEN')

# Создаем объекты бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Регистрируем router с хендлерами
dp.include_router(router)

@dp.message(Command("start"))
async def handle_start(message: Message):
    await message.answer("Привет, я бот!")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
