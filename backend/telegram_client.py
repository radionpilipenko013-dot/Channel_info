import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession, SQLiteSession
from config import API_ID, API_HASH, SESSION_NAME, SESSION_STRING

session = StringSession(SESSION_STRING) if SESSION_STRING else SQLiteSession(SESSION_NAME)

client = TelegramClient(session, API_ID, API_HASH)
lock = asyncio.Lock()