import asyncio
import time
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from config import BOT_TOKEN, MINI_APP_URL, ADMIN_TOKEN

ADMIN_IDS = {5253335910}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def track_user_call(user):
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{MINI_APP_URL}/api/track-user",
                json={
                    "id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
                timeout=aiohttp.ClientTimeout(total=10),
            )
    except Exception as e:
        print(f"track-user failed: {e}", flush=True)


@dp.message(CommandStart())
async def start(message: Message):
    await track_user_call(message.from_user)

    url = f"{MINI_APP_URL}?v={int(time.time())}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Open Analyzer", web_app=WebAppInfo(url=url))]
    ])
    await message.answer("Tap below to open the channel/user analyzer:", reply_markup=keyboard)


@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{MINI_APP_URL}/api/admin/users",
                headers={"x-admin-token": ADMIN_TOKEN},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    await message.answer(f"Ошибка API: {resp.status}")
                    return
                users = await resp.json()
    except Exception as e:
        await message.answer(f"Не удалось получить список: {e}")
        return

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
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())