import re
import logging
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import GetCommonChatsRequest
from telethon.tl.types import (
    User, Channel, Chat,
    UserStatusOnline, UserStatusOffline,
    UserStatusRecently, UserStatusLastWeek, UserStatusLastMonth,
)
from telethon.errors import FloodWaitError
import asyncio

from backend.telegram_client import client, lock

URL_RE = re.compile(r'https?://\S+')
MAX_PARTICIPANTS = 5000
DEFAULT_MESSAGE_LIMIT = 1000  # используется, если limit не указан

logger = logging.getLogger("analyzer")


async def safe_iter_messages(entity, limit=None):
    while True:
        try:
            count = 0
            async for msg in client.iter_messages(entity, limit=limit):
                count += 1
                if count % 200 == 0:
                    logger.info(f"safe_iter_messages: обработано {count} сообщений (entity={entity})")
                yield msg
            logger.info(f"safe_iter_messages: завершено, всего {count} сообщений (entity={entity})")
            return
        except FloodWaitError as e:
            logger.warning(f"FloodWaitError: ожидание {e.seconds} секунд (entity={entity})")
            await asyncio.sleep(e.seconds)


async def get_first_message(entity):
    async for msg in client.iter_messages(entity, limit=1, reverse=True):
        return msg
    return None


async def get_last_message(entity):
    async for msg in client.iter_messages(entity, limit=1):
        return msg
    return None


async def get_photo_history(entity, limit=100):
    photos = await client.get_profile_photos(entity, limit=limit)
    return [{"id": p.id, "date": p.date.isoformat()} for p in photos]


def reaction_label(reaction):
    emoticon = getattr(reaction, "emoticon", None)
    if emoticon:
        return emoticon
    return "custom emoji"


def format_last_seen(status):
    if status is None:
        return "скрыт"
    if isinstance(status, UserStatusOnline):
        return "в сети сейчас"
    if isinstance(status, UserStatusOffline):
        return status.was_online.isoformat()
    if isinstance(status, UserStatusRecently):
        return "недавно"
    if isinstance(status, UserStatusLastWeek):
        return "на этой неделе"
    if isinstance(status, UserStatusLastMonth):
        return "в этом месяце"
    return "скрыт"


async def resolve_entity(query):
    query = str(query).strip()
    if query.lstrip("-").isdigit():
        query = int(query)

    try:
        return await client.get_entity(query)
    except ValueError:
        await client.get_dialogs()
        return await client.get_entity(query)


async def analyze_channel(entity, limit):
    if limit is None:
        limit = DEFAULT_MESSAGE_LIMIT
        logger.info(f"analyze_channel: limit не указан, использую дефолт {DEFAULT_MESSAGE_LIMIT}")

    logger.info(f"analyze_channel: старт для {getattr(entity, 'title', entity)}, limit={limit}")

    full = await client(GetFullChannelRequest(entity))
    linked_chat_id = full.full_chat.linked_chat_id
    participants_count = full.full_chat.participants_count

    if participants_count and participants_count > MAX_PARTICIPANTS:
        raise ValueError(
            f"Канал слишком большой ({participants_count} подписчиков). "
            f"Анализ доступен только для каналов до {MAX_PARTICIPANTS} подписчиков."
        )

    users = {}
    links_in_comments = []
    links_in_channel = []
    total_reactions = 0
    reactions_breakdown = {}

    first_msg = await get_first_message(entity)
    last_msg = await get_last_message(entity)

    logger.info("analyze_channel: сканирую сообщения канала")
    async for msg in safe_iter_messages(entity, limit):
        if msg.text:
            links_in_channel += URL_RE.findall(msg.text)
        if msg.reactions:
            for r in msg.reactions.results:
                label = reaction_label(r.reaction)
                total_reactions += r.count
                reactions_breakdown[label] = reactions_breakdown.get(label, 0) + r.count

    if linked_chat_id:
        logger.info("analyze_channel: сканирую привязанный чат комментариев")
        async for msg in safe_iter_messages(linked_chat_id, limit):
            if msg.sender_id:
                username = None
                if msg.sender:
                    username = getattr(msg.sender, "username", None)
                users[msg.sender_id] = username
            if msg.text:
                links_in_comments += URL_RE.findall(msg.text)

    logger.info("analyze_channel: завершено")

    return {
        "type": "channel",
        "title": entity.title,
        "channel_id": entity.id,
        "participants_count": participants_count,
        "first_message_date": first_msg.date.isoformat() if first_msg else None,
        "last_message_date": last_msg.date.isoformat() if last_msg else None,
        "total_reactions": total_reactions,
        "reactions_breakdown": reactions_breakdown,
        "users": [{"id": uid, "username": uname} for uid, uname in users.items()],
        "users_count": len(users),
        "links_in_comments": links_in_comments,
        "links_in_channel": links_in_channel,
        "comments_available": linked_chat_id is not None,
    }


async def analyze_user(entity):
    full = await client(GetFullUserRequest(entity))
    about = full.full_user.about

    common_chats = []
    try:
        result = await client(GetCommonChatsRequest(user_id=entity, max_id=0, limit=100))
        for chat in result.chats:
            common_chats.append({
                "title": getattr(chat, "title", None),
                "username": getattr(chat, "username", None),
                "id": chat.id,
            })
    except Exception:
        pass

    photo_history = await get_photo_history(entity)

    return {
        "type": "user",
        "id": entity.id,
        "username": entity.username,
        "first_name": entity.first_name,
        "last_name": entity.last_name,
        "phone": entity.phone,
        "bio": about,
        "premium": getattr(entity, "premium", False),
        "verified": getattr(entity, "verified", False),
        "scam": getattr(entity, "scam", False),
        "fake": getattr(entity, "fake", False),
        "deleted": getattr(entity, "deleted", False),
        "is_bot": entity.bot,
        "last_seen": format_last_seen(entity.status),
        "has_photo": entity.photo is not None,
        "photo_count": len(photo_history),
        "photo_history": photo_history,
        "blocked": getattr(full.full_user, "blocked", False),
        "in_contacts": getattr(entity, "contact", False),
        "mutual_contact": getattr(entity, "mutual_contact", False),
        "common_chats": common_chats,
        "common_chats_count": len(common_chats),
    }


async def get_user_activity(user_entity, chat_entity, limit=500):
    if limit is None:
        limit = DEFAULT_MESSAGE_LIMIT

    messages = []
    reactions_placed = 0

    async for msg in safe_iter_messages(chat_entity, limit):
        if msg.sender_id == user_entity.id:
            messages.append({
                "id": msg.id,
                "date": msg.date.isoformat(),
                "text": msg.text,
            })
        if msg.reactions and msg.reactions.recent_reactions:
            for r in msg.reactions.recent_reactions:
                peer = getattr(r, "peer_id", None)
                if peer and getattr(peer, "user_id", None) == user_entity.id:
                    reactions_placed += 1

    return {
        "type": "activity",
        "user_id": user_entity.id,
        "username": user_entity.username,
        "chat_title": getattr(chat_entity, "title", None),
        "messages_count": len(messages),
        "messages": messages,
        "reactions_placed": reactions_placed,
    }


async def analyze(query: str, limit: int | None):
    async with lock:
        entity = await resolve_entity(query)

        if isinstance(entity, User):
            return await analyze_user(entity)
        elif isinstance(entity, (Channel, Chat)):
            return await analyze_channel(entity, limit)
        else:
            raise ValueError("Unsupported entity type")


async def analyze_activity(user_query: str, chat_query: str, limit: int | None):
    async with lock:
        user_entity = await resolve_entity(user_query)
        chat_entity = await resolve_entity(chat_query)
        return await get_user_activity(user_entity, chat_entity, limit)