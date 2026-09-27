import asyncio
import time
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from config import BOT_TOKEN, MINI_APP_URL
from backend import db

ADMIN_IDS = {5253335910}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):
    url = f"{MINI_APP_URL}?v={int(time.time())}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Open Analyzer", web_app=WebAppInfo(url=url))]
    ])
    await message.answer("Tap below to open the channel/user analyzer:", reply_markup=keyboard)


@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    users = db.list_users()

    if not users:
        await message.answer("Пользователей пока нет.")
        return

    lines = [f"👥 Пользователи бота ({len(users)})\n"]
    for u in users:
        name = " ".join(filter(None, [u["first_name"], u["last_name"]])) or "-"
        username = f"@{u['username']}" if u["username"] else "-"
        lines.append(
            f"{name} | {username} | ID: {u['telegram_id']} | запросов: {u['requests_count']}"
        )

    text = "\n".join(lines)

    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await message.answer(text[i:i + 4000])
    else:
        await message.answer(text)


async def main():
    db.init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())