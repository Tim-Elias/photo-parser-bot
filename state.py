# state.py
# Хранилище для пользовательских данных и состояний
import os
from dotenv import load_dotenv

load_dotenv()

info_chat_ids = list(map(int, os.getenv('INFO_CHAT_IDS').split(',')))

user_images = {}
user_states = {}
images = {}
