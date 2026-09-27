from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from config import API_ID, API_HASH, SESSION_NAME

with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
    string_session = StringSession.save(client.session)
    print(string_session)