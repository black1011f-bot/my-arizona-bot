import os
import time
import threading
import logging
import random
import re
import html
import io
import urllib.parse
import uuid
from datetime import datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo
from contextlib import contextmanager

import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException
from supabase import create_client, Client

# ==========================================
# КОНФИГУРАЦИЯ С ВСТАВЛЕННЫМИ КЛЮЧАМИ
# ==========================================
TELEGRAM_TOKEN = "8916669266:AAGFjRyvwjBjViNrSErZekUMj7SsM69OVNE"
SUPABASE_URL = "https://sbtitlayqkpllnaiyeld.supabase.co"
SUPABASE_SERVICE_KEY = "sb_secret_4TUxbjgi-beOqXWdjrdKvw_nUU7sDnP"

if not all([TELEGRAM_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_KEY]):
    raise ValueError("Не заданы все необходимые ключи")

bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=True, num_threads=20)

# Подключение к Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ==========================================
# НАСТРОЙКИ
# ==========================================
MANAGER_USERNAME = "bounqy31"
BOT_USERNAME = "arizona_coin_bot"
OWNER_USERNAME = "bounqy"
ADMIN_USERNAMES = {"bounqy31", "bounqy"}

SERVERS = [
    "🔥 Phoenix", "🌴 Tucson", "🌵 Scottdale", "⚜️ Chandler", "❄️ Brainburg",
    "🌊 Yuma", "✨ Saint-Rose", "🏛 Mesa", "❤️ Red-Rock", "🍀 Surprise",
    "⚡️ Prescott", "🌲 Glendale", "👑 Kingman", "⚓️ Winslow", "🌴 Payson",
    "💎 Gilbert", "🔥 Show-Low", "🌴 Casa-Grande", "📜 Page", "☀️ Sun-City",
    "👑 Queen-Creek", "🌵 Sedona", "🎄 Holiday", "🍀 Wednesday", "⚡️ Yava",
    "🌌 Faraway", "🎁 Christmas", "🐝 Bumble Bee", "🪞 Mirage", "💖 Love",
    "📱 Mobile I", "📱 Mobile II", "📱 Mobile III",
]

CATEGORIES = [
    "💍 Аксессуары и вещи",
    "🚗 Транспорт и тюнинг",
    "👕 Скины и охранники",
    "🏠 Недвижимость и бизнесы",
    "📦 Ресурсы и материалы",
]

BAD_WORDS = [
    "хуй", "хуе", "хуя", "хуи", "пизд", "еб", "бля", "сук", "залуп", "мраз",
    "ебан", "долбоеб", "сука", "блять", "ебать", "хуесос", "пидорас", "пидар",
    "мразь", "урод", "чмо", "шлюх", "блядь", "сукин", "залупа", "гандон",
    "ондон", "дроч", "ебуч", "еблан", "пиздюк", "выбляд", "samp-rp", "advance",
    "Arizona V", "Diamond", "продажа вирт", "продам вирты",
]

RATE_LIMIT_SECONDS = 0.6
AD_EXPIRY_HOURS = 48

# ==========================================
# ЛОГИРОВАНИЕ
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def get_msk_time():
    return datetime.now(ZoneInfo("Europe/Moscow"))

# ==========================================
# ПОТОКОБЕЗОПАСНЫЕ СОСТОЯНИЯ
# ==========================================
user_states = {}
state_lock = threading.Lock()
antispam_lock = threading.Lock()
user_last_message_time = {}

def get_state(uid: int) -> dict:
    with state_lock:
        return user_states.get(uid, {}).copy()

def set_state(uid: int, data: dict):
    with state_lock:
        srv = user_states.get(uid, {}).get("server") or get_user_server(uid)
        user_states[uid] = data
        if srv and "server" not in user_states[uid]:
            user_states[uid]["server"] = srv

def update_state(uid: int, **kwargs):
    with state_lock:
        if uid not in user_states:
            user_states[uid] = {}
        user_states[uid].update(kwargs)

def clear_state(uid: int):
    with state_lock:
        srv = user_states.get(uid, {}).get("server") or get_user_server(uid)
        user_states[uid] = {"server": srv} if srv else {}

# ==========================================
# РАБОТА С БАЗОЙ (UUID-версия)
# ==========================================

def get_user_uuid_by_telegram_id(telegram_id: int) -> str | None:
    """Возвращает UUID пользователя по telegram_id."""
    res = supabase.table("app_users").select("id").eq("telegram_id", telegram_id).execute()
    if res.data:
        return res.data[0]["id"]
    return None

def register_user(telegram_id: int, username: str) -> str:
    """Создаёт запись в app_users с UUID, если пользователь с таким telegram_id ещё не существует."""
    # Проверяем, есть ли пользователь с таким telegram_id
    res = supabase.table("app_users").select("id").eq("telegram_id", telegram_id).execute()
    if res.data:
        # Обновляем username, если изменился
        supabase.table("app_users").update({"username": username or ""}).eq("telegram_id", telegram_id).execute()
        return res.data[0]["id"]

    # Создаём нового пользователя
    new_uuid = uuid.uuid4()
    supabase.table("app_users").insert({
        "id": str(new_uuid),
        "username": username or "",
        "telegram_id": telegram_id,
        "telegram_username": username or "",
        "server": SERVERS[0],
        "last_ad_time": 0.0,
        "created_at": datetime.utcnow().isoformat()
    }).execute()
    return str(new_uuid)

def is_banned(user) -> bool:
    if not user:
        return False
    uid = get_user_uuid_by_telegram_id(user.id)
    if uid:
        res = supabase.table("app_users").select("banned").eq("id", uid).execute()
        if res.data and res.data[0].get("banned"):
            return True
    # Проверяем также таблицу bans (для обратной совместимости)
    res2 = supabase.table("bans").select("target").or_(f"target.eq.{user.id},target.eq.{user.username}").execute()
    return bool(res2.data)

def is_admin_or_owner_id(telegram_id: int) -> bool:
    uid = get_user_uuid_by_telegram_id(telegram_id)
    if not uid:
        return False
    res = supabase.table("app_users").select("username, is_admin").eq("id", uid).execute()
    if res.data:
        data = res.data[0]
        if data.get("username") and data["username"].lstrip("@") in ADMIN_USERNAMES:
            return True
        if data.get("is_admin"):
            return True
    res2 = supabase.table("approved_admins").select("user_id").eq("user_id", uid).execute()
    return bool(res2.data)

def is_owner(user) -> bool:
    if not user:
        return False
    if user.username and user.username.lstrip("@") == OWNER_USERNAME:
        return True
    uid = get_user_uuid_by_telegram_id(user.id)
    if not uid:
        return False
    res = supabase.table("app_users").select("username").eq("id", uid).execute()
    if res.data and res.data[0].get("username", "").lstrip("@") == OWNER_USERNAME:
        return True
    return False

def get_owner_id() -> str | None:
    res = supabase.table("app_users").select("id").eq("username", OWNER_USERNAME).execute()
    if res.data:
        return res.data[0]["id"]
    return None

def get_admin_chat_ids() -> list:
    res = supabase.table("admin_chats").select("chat_id").execute()
    return [row["chat_id"] for row in res.data]

def register_admin_chat(chat_id: int):
    supabase.table("admin_chats").upsert({"chat_id": chat_id}).execute()

def get_user_last_ad_time(telegram_id: int) -> float:
    uid = get_user_uuid_by_telegram_id(telegram_id)
    if not uid:
        return 0.0
    res = supabase.table("app_users").select("last_ad_time").eq("id", uid).execute()
    if res.data:
        return res.data[0].get("last_ad_time") or 0.0
    return 0.0

def set_user_last_ad_time(telegram_id: int, t: float):
    uid = get_user_uuid_by_telegram_id(telegram_id)
    if uid:
        supabase.table("app_users").update({"last_ad_time": t}).eq("id", uid).execute()

def is_user_premium(telegram_id: int) -> bool:
    uid = get_user_uuid_by_telegram_id(telegram_id)
    if not uid:
        return False
    now = time.time()
    res = supabase.table("premium_users").select("expires_at").eq("user_id", uid).execute()
    if res.data and res.data[0].get("expires_at", 0) > now:
        return True
    try:
        res2 = supabase.table("user_settings").select("vip_subscription").eq("user_id", uid).execute()
        if res2.data and res2.data[0].get("vip_subscription"):
            return True
    except:
        pass
    return False

def set_user_server(telegram_id: int, server: str):
    uid = get_user_uuid_by_telegram_id(telegram_id)
    if uid:
        supabase.table("app_users").update({"server": server}).eq("id", uid).execute()
        update_state(telegram_id, server=server)

def get_user_server(telegram_id: int) -> str:
    with state_lock:
        srv = user_states.get(telegram_id, {}).get("server")
        if srv:
            return srv
    uid = get_user_uuid_by_telegram_id(telegram_id)
    if uid:
        res = supabase.table("app_users").select("server").eq("id", uid).execute()
        if res.data and res.data[0].get("server"):
            srv = res.data[0]["server"]
            update_state(telegram_id, server=srv)
            return srv
    default = SERVERS[0]
    update_state(telegram_id, server=default)
    return default

# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def parse_flexible_price(text: str) -> int:
    if not text:
        raise ValueError("Пустая цена")
    cleaned = text.strip().lower()
    cleaned = cleaned.replace("$", "").replace("руб", "").replace("вк", "").replace("vc", "").strip()
    multiplier = 1
    if "миллиард" in cleaned or "ккк" in cleaned:
        multiplier = 1_000_000_000
        cleaned = cleaned.replace("миллиард", "").replace("ккк", "").strip()
    elif "кк" in cleaned or "kk" in cleaned or "лям" in cleaned or "лимон" in cleaned:
        multiplier = 1_000_000
        cleaned = cleaned.replace("кк", "").replace("kk", "").replace("лям", "").replace("лимон", "").strip()
    elif "к" in cleaned or "k" in cleaned or "тыс" in cleaned:
        multiplier = 1_000
        cleaned = cleaned.replace("к", "").replace("k", "").replace("тыс", "").strip()
    cleaned = cleaned.replace(" ", "").replace("_", "")
    if "." in cleaned or "," in cleaned:
        cleaned = cleaned.replace(",", ".")
        try:
            val = float(cleaned)
            return int(val * multiplier)
        except ValueError:
            cleaned = cleaned.replace(".", "")
    try:
        return int(float(cleaned) * multiplier)
    except ValueError:
        raise ValueError(f"Не удалось распознать цену: {text}")

def check_auto_moderation(text: str) -> bool:
    t_lower = text.lower()
    for w in BAD_WORDS:
        if w in t_lower:
            return False
    return True

def is_flooding(user_id: int) -> bool:
    if is_admin_or_owner_id(user_id):
        return False
    current_time = time.time()
    with antispam_lock:
        last_time = user_last_message_time.get(user_id, 0)
        if current_time - last_time < RATE_LIMIT_SECONDS:
            return True
        user_last_message_time[user_id] = current_time
    return False

def safe_send_message(chat_id, text, parse_mode="HTML", reply_markup=None):
    try:
        return bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)
    except ApiTelegramException as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        return bot.send_message(chat_id, text, parse_mode=None, reply_markup=reply_markup)

def safe_send_photo(chat_id, photo, caption, parse_mode="HTML", reply_markup=None):
    try:
        return bot.send_photo(chat_id, photo, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)
    except ApiTelegramException as e:
        logger.error(f"Ошибка отправки фото: {e}")
        return bot.send_photo(chat_id, photo, caption=caption, parse_mode=None, reply_markup=reply_markup)

def send_log_file(chat_id, filename, text_content, caption=None, reply_markup=None):
    file_bytes = io.BytesIO(text_content.encode("utf-8"))
    file_bytes.name = filename
    try:
        bot.send_document(chat_id, document=file_bytes, caption=caption, parse_mode="HTML", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Ошибка отправки файла логов: {e}")
        safe_send_message(chat_id, text_content[:4000], reply_markup=reply_markup)

# ==========================================
# КЛАВИАТУРЫ
# ==========================================
def kb_main_menu(user_id=None):
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row(types.KeyboardButton("🌐 Сменить игровой сервер"))
    m.row(types.KeyboardButton("💍 Аксессуары и вещи"), types.KeyboardButton("🚗 Транспорт и тюнинг"))
    m.row(types.KeyboardButton("👕 Скины и охранники"), types.KeyboardButton("🏠 Недвижимость и бизнесы"))
    m.row(types.KeyboardButton("📦 Ресурсы и материалы"))
    m.row(types.KeyboardButton("📤 Продать товар"), types.KeyboardButton("📥 Скупить товар"))
    m.row(types.KeyboardButton("🔄 Бартер / Обмен"), types.KeyboardButton("🏛 Аукционы"))
    m.row(types.KeyboardButton("👥 Рефералы и Бонусы"))
    m.row(types.KeyboardButton("💱 Курс VC и калькулятор"))
    m.row(types.KeyboardButton("🔍 Найти товар в базе"))
    m.row(types.KeyboardButton("❤️ Сохраненные"), types.KeyboardButton("📋 Мои публикации"))
    m.row(types.KeyboardButton("📊 Анализ цен на сервере"))
    m.row(types.KeyboardButton("💎 VIP-статус"), types.KeyboardButton("💬 Связаться с менеджером"))
    if user_id and is_admin_or_owner_id(user_id):
        m.row(types.KeyboardButton("👑 Админ-панель"))
    return m

def kb_cancel():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row(types.KeyboardButton("⬅️ Назад"), types.KeyboardButton("❌ Отменить действие"))
    return m

def kb_owner_input():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row(types.KeyboardButton("🔨 Забанить игрока"), types.KeyboardButton("⬅️ Назад"), types.KeyboardButton("❌ Отменить действие"))
    return m

# ==========================================
# ОБРАБОТЧИКИ
# ==========================================

@bot.message_handler(func=lambda m: is_flooding(m.from_user.id), content_types=["text", "photo"])
def handle_flood(m):
    try:
        bot.send_message(m.chat.id, "⚠️ <b>Слишком частые запросы!</b> Пожалуйста, отправляйте сообщения немного медленнее.")
    except:
        pass

@bot.callback_query_handler(func=lambda c: is_flooding(c.from_user.id))
def handle_flood_callback(c):
    try:
        bot.answer_callback_query(c.id, "⚠️ Не так быстро! Подождите пару секунд.", show_alert=False)
    except:
        pass

@bot.message_handler(func=lambda m: is_banned(m.from_user))
def blocked_user_message(m):
    safe_send_message(m.chat.id, "⛔ <b>Вы заблокированы в системе модерации.</b>", reply_markup=types.ReplyKeyboardRemove())

@bot.callback_query_handler(func=lambda c: is_banned(c.from_user))
def blocked_user_callback(c):
    try:
        bot.answer_callback_query(c.id, "⛔ Вы заблокированы!", show_alert=True)
    except:
        pass

# ==========================================
# КОМАНДА /START
# ==========================================
@bot.message_handler(commands=["start"])
def cmd_start(m):
    uid = m.from_user.id
    username = m.from_user.username or ""
    register_user(uid, username)
    set_user_server(uid, SERVERS[0])

    if is_banned(m.from_user):
        return safe_send_message(m.chat.id, "⛔ <b>Вы заблокированы в системе модерации.</b>", reply_markup=types.ReplyKeyboardRemove())

    # Реферальная ссылка
    args = m.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_telegram_id = int(args[1].replace("ref_", ""))
            if referrer_telegram_id != uid:
                referrer_uuid = get_user_uuid_by_telegram_id(referrer_telegram_id)
                if referrer_uuid:
                    # Проверяем, не регистрировался ли уже
                    res = supabase.table("referrals").select("1").eq("referrer_id", referrer_uuid).eq("referred_id", uid).execute()
                    if not res.data:
                        supabase.table("referrals").insert({
                            "referrer_id": referrer_uuid,
                            "referred_id": uid,
                            "last_active_date": get_msk_time().strftime("%Y-%m-%d")
                        }).execute()
                        # Начисляем VIP обоим
                        now_ts = time.time()
                        for target_tg_id in [referrer_telegram_id, uid]:
                            target_uuid = get_user_uuid_by_telegram_id(target_tg_id)
                            if target_uuid:
                                res_prem = supabase.table("premium_users").select("expires_at").eq("user_id", target_uuid).execute()
                                existing_exp = res_prem.data[0]["expires_at"] if res_prem.data and res_prem.data[0]["expires_at"] > now_ts else now_ts
                                new_exp = existing_exp + 10 * 86400
                                supabase.table("premium_users").upsert({"user_id": target_uuid, "expires_at": new_exp}).execute()
                        try:
                            safe_send_message(referrer_telegram_id, "🎉 <b>По вашей реферальной ссылке зарегистрировался новый друг!</b>\nВам и вашему другу начислен VIP-статус на 10 дней!")
                            safe_send_message(uid, "🎁 <b>Вы успешно зарегистрировались по реферальной ссылке!</b>\nВам начислен VIP-статус на 10 дней!")
                        except:
                            pass
        except Exception as e:
            logger.error(f"Реферальная ошибка: {e}")

    text = (
        f"👋 Приветствую, <b>{html.escape(m.from_user.first_name)}</b>!\n\n"
        f"🤖 Мы — <b>неофициальный бот</b> объявлений Arizona RP, созданный игроком.\n\n"
        f"🌐 <b>Игровой сервер по умолчанию:</b> {SERVERS[0]}.\n"
        f"Если вам нужно его сменить, нажмите на кнопку <b>«🌐 Сменить игровой сервер»</b> в меню ниже.\n\n"
        f"⚠️ <b>Безопасность и ответственность:</b> Бот является фанатским проектом. Администрация <b>не несет никакой ответственности</b> за ваши сделки, обмены и договоренности. Все действия вы совершаете на свой страх и риск!\n\n"
        f"Выберите нужный раздел в меню ниже:"
    )
    safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(uid))

# ==========================================
# /HELP
# ==========================================
@bot.message_handler(commands=["help"])
def cmd_help(m):
    uid = m.from_user.id
    help_text = (
        "❓ <b>Часто задаваемые вопросы (FAQ)</b>\n\n"
        "<b>1. Этот бот официальный?</b>\n"
        "Нет, это неофициальный бот объявлений, созданный игроком для игроков.\n\n"
        "<b>2. Как подать объявление о продаже?</b>\n"
        "Нажмите кнопку «📤 Продать товар», выберите сервер, категорию и отправьте текст с фото.\n\n"
        "<b>3. Как подать объявление о скупке?</b>\n"
        "Нажмите кнопку «📥 Скупить товар», укажите сервер, категорию и описание.\n\n"
        "<b>4. Почему моё объявление не появилось сразу?</b>\n"
        "Все объявления проходят предварительную модерацию администраторами.\n\n"
        "<b>5. Как работает реферальная система?</b>\n"
        "Приглашайте друзей по ссылке, и вы оба получаете VIP на 10 дней.\n\n"
        "<b>6. Безопасны ли сделки через бота?</b>\n"
        "⚠️ <b>Внимание:</b> администрация бота не несет ответственности за ваши сделки.\n\n"
        "<b>7. Как получить ежедневный бонус?</b>\n"
        "В разделе «👥 Рефералы и Бонусы» раз в 24 часа можно забирать случайную награду.\n\n"
        "<b>8. Что даёт VIP-статус?</b>\n"
        "Уменьшенный кулдаун на подачу объявлений (60 сек вместо 120).\n\n"
        "<b>9. Как изменить сервер?</b>\n"
        "Кнопка «🌐 Сменить игровой сервер».\n\n"
        "<b>10. Куда писать при проблемах?</b>\n"
        "Менеджер: @bounqy31 или VK: @bountyarz."
    )
    safe_send_message(m.chat.id, help_text, reply_markup=kb_main_menu(uid))

# ==========================================
# РЕФЕРАЛЫ И БОНУСЫ
# ==========================================
@bot.message_handler(func=lambda m: m.text == "👥 Рефералы и Бонусы")
def show_ref_bonus_menu(m):
    uid = m.from_user.id
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{uid}"
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={urllib.parse.quote('Залетай в лучший неофициальный бот объявлений Arizona RP!')}"

    # Получаем UUID пользователя
    user_uuid = get_user_uuid_by_telegram_id(uid)
    if not user_uuid:
        safe_send_message(m.chat.id, "Ошибка: пользователь не найден")
        return

    # Количество рефералов
    res = supabase.table("referrals").select("count", count="exact").eq("referrer_id", user_uuid).execute()
    ref_count = res.count or 0

    # Бонусы
    res_bonus = supabase.table("user_bonuses").select("*").eq("user_id", user_uuid).execute()
    bonus_row = res_bonus.data[0] if res_bonus.data else None
    last_claim_ts = bonus_row.get("last_claim_timestamp", 0.0) if bonus_row else 0.0
    vip_ads = bonus_row.get("vip_ads_count", 0) if bonus_row else 0

    current_ts = time.time()
    cooldown = 86400
    can_claim = (current_ts - last_claim_ts) >= cooldown
    remaining_time = int(cooldown - (current_ts - last_claim_ts)) if not can_claim else 0
    hours_rem = remaining_time // 3600
    mins_rem = (remaining_time % 3600) // 60

    text = (
        f"👥 <b>Рефералы и Бонусы</b>\n\n"
        f"Приглашайте друзей по вашей реферальной ссылке и получайте <b>VIP-статус на 10 дней</b> (и ваш друг тоже)!\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n<code>{ref_link}</code>\n\n"
        f"📊 Приглашено: <b>{ref_count}</b>\n"
        f"⭐ Бонусных VIP-объявлений: <b>{vip_ads}</b> (⚠️ <i>Неиспользованные удаляются по 1 шт. каждые 24 часа!</i>)\n\n"
        f"🎁 Ежедневный бонус обновляется каждые 24 часа!"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("📤 Поделиться ссылкой", url=share_url))
    if can_claim:
        markup.add(types.InlineKeyboardButton("🎁 Забрать ежедневный бонус", callback_data="claim_daily_bonus"))
    else:
        markup.add(types.InlineKeyboardButton(f"⏳ Бонус через {hours_rem}ч {mins_rem}мин", callback_data="bonus_cooldown_alert"))

    safe_send_message(m.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["claim_daily_bonus", "bonus_cooldown_alert"])
def cb_daily_bonus(call):
    uid = call.from_user.id
    user_uuid = get_user_uuid_by_telegram_id(uid)
    if not user_uuid:
        try:
            bot.answer_callback_query(call.id, "Ошибка: пользователь не найден", show_alert=True)
        except:
            pass
        return

    current_ts = time.time()
    cooldown = 86400

    res_bonus = supabase.table("user_bonuses").select("*").eq("user_id", user_uuid).execute()
    bonus_row = res_bonus.data[0] if res_bonus.data else None
    last_claim_ts = bonus_row.get("last_claim_timestamp", 0.0) if bonus_row else 0.0

    if current_ts - last_claim_ts < cooldown:
        remaining = int(cooldown - (current_ts - last_claim_ts))
        h = remaining // 3600
        m = (remaining % 3600) // 60
        try:
            bot.answer_callback_query(call.id, f"⚠️ Бонус можно забирать раз в 24 часа! Осталось: {h}ч {m}мин.", show_alert=True)
        except:
            pass
        return

    roll = random.randint(1, 100)
    today_str = get_msk_time().strftime("%Y-%m-%d")

    if roll <= 5:
        # VIP на 13 дней
        res_prem = supabase.table("premium_users").select("expires_at").eq("user_id", user_uuid).execute()
        base_exp = res_prem.data[0]["expires_at"] if res_prem.data and res_prem.data[0]["expires_at"] > current_ts else current_ts
        new_exp = base_exp + 13 * 86400
        supabase.table("premium_users").upsert({"user_id": user_uuid, "expires_at": new_exp}).execute()
        msg_reward = "🎉 <b>Поздравляем! Вы выбили VIP-подписку на 13 дней!</b>"
    else:
        if roll <= 35:
            ads_won = 1
        elif roll <= 60:
            ads_won = 2
        elif roll <= 80:
            ads_won = 3
        elif roll <= 92:
            ads_won = 4
        else:
            ads_won = 5
        current_ads = bonus_row.get("vip_ads_count", 0) if bonus_row else 0
        new_ads = current_ads + ads_won
        supabase.table("user_bonuses").upsert({
            "user_id": user_uuid,
            "last_claim_date": today_str,
            "last_claim_timestamp": current_ts,
            "vip_ads_count": new_ads,
            "vip_ads_expiry": current_ts + 86400
        }).execute()
        msg_reward = f"🎁 <b>Поздравляем! Вы выбили VIP-объявлений: {ads_won} шт.</b>\n(⚠️ <i>Неиспользованные удаляются по 1 шт. каждый день!</i>)"

    # Обновляем last_claim_timestamp
    supabase.table("user_bonuses").update({"last_claim_date": today_str, "last_claim_timestamp": current_ts}).eq("user_id", user_uuid).execute()

    try:
        bot.answer_callback_query(call.id, "🎉 Ежедневный бонус получен!", show_alert=True)
    except:
        pass

    safe_send_message(call.message.chat.id, msg_reward)
    show_ref_bonus_menu(call.message)

# ==========================================
# ОСТАЛЬНЫЕ ОБРАБОТЧИКИ КНОПОК
# ==========================================

@bot.message_handler(func=lambda m: m.text == "🌐 Сменить игровой сервер")
def change_server(m):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for i in range(0, len(SERVERS), 2):
        row_buttons = [types.KeyboardButton(s) for s in SERVERS[i:i+2]]
        markup.row(*row_buttons)
    markup.row(types.KeyboardButton("⬅️ Назад"), types.KeyboardButton("❌ Отменить действие"))
    safe_send_message(m.chat.id, "🌐 Выберите ваш игровой сервер:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in SERVERS)
def select_srv(m):
    srv = m.text
    uid = m.from_user.id
    if srv in SERVERS:
        set_user_server(uid, srv)
        safe_send_message(m.chat.id, f"✅ Сервер изменён на: <b>{html.escape(srv)}</b>", reply_markup=kb_main_menu(uid))

@bot.message_handler(func=lambda m: m.text in ["❌ Отменить действие", "⬅️ Назад"])
def cancel_action(m):
    uid = m.from_user.id
    clear_state(uid)
    safe_send_message(m.chat.id, "❌ Действие отменено.", reply_markup=kb_main_menu(uid))

@bot.message_handler(func=lambda m: m.text == "💎 VIP-статус")
def info_premium(m):
    uid = m.from_user.id
    is_prem = is_user_premium(uid)
    status_text = "✅ <b>Активен</b>" if is_prem else "❌ <b>Неактивен</b>"
    user_uuid = get_user_uuid_by_telegram_id(uid)
    if user_uuid:
        res = supabase.table("premium_users").select("expires_at").eq("user_id", user_uuid).execute()
        if res.data and res.data[0]["expires_at"] > time.time():
            exp_date = datetime.fromtimestamp(res.data[0]["expires_at"], ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M")
            status_text += f" (до {exp_date} МСК)"
    text = (
        f"💎 <b>VIP-статус в системе</b>\n\n"
        f"Статус: {status_text}\n\n"
        f"<b>Преимущества VIP:</b>\n"
        f"• Уменьшенный кулдаун (60 сек вместо 120)\n"
        f"• Приоритет и особый знак\n\n"
        f"Выберите вариант приобретения VIP за Telegram Stars (⭐):"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("👑 VIP на 30 дней — 100 ⭐", callback_data="buy_vip_30"),
        types.InlineKeyboardButton("👑 VIP навсегда — 500 ⭐", callback_data="buy_vip_forever")
    )
    safe_send_message(m.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["buy_vip_30", "buy_vip_forever"])
def cb_buy_vip(call):
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    if call.data == "buy_vip_30":
        prices = [types.LabeledPrice(label="VIP на 30 дней", amount=100)]
        payload = "premium_30"
        title = "VIP на 30 дней"
        description = "VIP-подписка на 30 дней за 100 звёзд"
    else:
        prices = [types.LabeledPrice(label="VIP навсегда", amount=500)]
        payload = "premium_forever"
        title = "VIP навсегда"
        description = "Пожизненная VIP-подписка за 500 звёзд"

    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title=title,
            description=description,
            invoice_payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="vip_sub"
        )
    except Exception as e:
        logger.error(f"Ошибка инвойса VIP: {e}")

# ==========================================
# ПРОДАЖА / СКУПКА (ОБЪЯВЛЕНИЯ)
# ==========================================
def validate_ad_submission(telegram_id: int) -> tuple[bool, str]:
    now_msk = get_msk_time()
    current_time = now_msk.time()
    start_window = dtime(8, 0, 0)
    end_window = dtime(22, 0, 0)
    if not (start_window <= current_time <= end_window):
        return False, "❌ Отправка объявлений доступна только с <b>08:00 до 22:00 МСК</b>."

    is_prem = is_user_premium(telegram_id)
    cooldown_seconds = 60 if is_prem else 120
    last_time = get_user_last_ad_time(telegram_id)
    elapsed = time.time() - last_time
    if elapsed < cooldown_seconds:
        remaining = int(cooldown_seconds - elapsed)
        cooldown_label = "1 минута" if is_prem else "2 минуты"
        return False, f"⏳ <b>Кулдаун!</b> Подождите ещё <b>{remaining} сек.</b> (Ваш кулдаун: {cooldown_label})"
    return True, ""

@bot.message_handler(func=lambda m: m.text == "📤 Продать товар")
def start_add_ad(m):
    uid = m.from_user.id
    allowed, err = validate_ad_submission(uid)
    if not allowed:
        return safe_send_message(m.chat.id, err, reply_markup=kb_main_menu(uid))
    update_state(uid, posting_ad={"step": "category", "is_buy": False})
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    for cat in CATEGORIES:
        markup.add(types.KeyboardButton(cat))
    markup.row(types.KeyboardButton("⬅️ Назад"), types.KeyboardButton("❌ Отменить действие"))
    safe_send_message(m.chat.id, "📤 <b>Подача объявления о продаже</b>\n\nВыберите категорию:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📥 Скупить товар")
def start_add_buy_ad(m):
    uid = m.from_user.id
    allowed, err = validate_ad_submission(uid)
    if not allowed:
        return safe_send_message(m.chat.id, err, reply_markup=kb_main_menu(uid))
    update_state(uid, posting_ad={"step": "category", "is_buy": True})
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    for cat in CATEGORIES:
        markup.add(types.KeyboardButton(cat))
    markup.row(types.KeyboardButton("⬅️ Назад"), types.KeyboardButton("❌ Отменить действие"))
    safe_send_message(m.chat.id, "📥 <b>Подача объявления о скупке</b>\n\nВыберите категорию:", reply_markup=markup)

@bot.message_handler(func=lambda m: get_state(m.from_user.id).get("posting_ad", {}).get("step") == "category" and m.text in CATEGORIES)
def process_ad_category(m):
    uid = m.from_user.id
    cat = m.text
    st = get_state(uid)
    st["posting_ad"]["category"] = cat
    st["posting_ad"]["step"] = "text_or_photo"
    set_state(uid, st)
    safe_send_message(m.chat.id, "📝 Отправьте текст объявления и прикрепите фото (по желанию):", reply_markup=kb_cancel())

@bot.message_handler(content_types=["text", "photo"], func=lambda m: get_state(m.from_user.id).get("posting_ad", {}).get("step") == "text_or_photo")
def process_ad_content(m):
    uid = m.from_user.id
    st = get_state(uid)
    ad_data = st.get("posting_ad", {})
    clear_state(uid)

    allowed, err = validate_ad_submission(uid)
    if not allowed:
        return safe_send_message(m.chat.id, err, reply_markup=kb_main_menu(uid))

    text = m.text or m.caption
    if not text:
        return safe_send_message(m.chat.id, "⚠️ Текст объявления не может быть пустым.", reply_markup=kb_main_menu(uid))
    if not check_auto_moderation(text):
        return safe_send_message(m.chat.id, "🤬 Текст содержит запрещённые слова.", reply_markup=kb_main_menu(uid))

    photo = m.photo[-1].file_id if m.photo else None
    srv = get_user_server(uid)
    is_buy = ad_data.get("is_buy", False)
    category = ad_data.get("category", CATEGORIES[0])
    is_vip = 1 if is_user_premium(uid) else 0

    # Получаем UUID автора
    author_uuid = get_user_uuid_by_telegram_id(uid)
    if not author_uuid:
        return safe_send_message(m.chat.id, "Ошибка: пользователь не найден", reply_markup=kb_main_menu(uid))

    # Вставляем объявление в таблицу ads со статусом 'pending'
    new_ad = {
        "author_id": author_uuid,
        "author_username": m.from_user.username or str(uid),
        "server": srv,
        "category": category,
        "item_name": text[:100],
        "description": text,
        "price": 0,
        "images": photo,
        "is_vip": bool(is_vip),
        "mode": "sell" if not is_buy else "buy",
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "hidden": False
    }
    res = supabase.table("ads").insert(new_ad).execute()
    if not res.data:
        return safe_send_message(m.chat.id, "Ошибка при создании объявления", reply_markup=kb_main_menu(uid))
    post_id = res.data[0]["id"]

    set_user_last_ad_time(uid, time.time())

    # Уведомление админов
    admin_chats = get_admin_chat_ids()
    prefix = "скупки" if is_buy else "продажи"
    callback_acc = f"mod_acc_buy_{post_id}" if is_buy else f"mod_acc_{post_id}"
    callback_rej = f"mod_rej_buy_{post_id}" if is_buy else f"mod_rej_{post_id}"

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Одобрить", callback_data=callback_acc),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=callback_rej),
    )

    notif_text = f"🔔 <b>Новое объявление {prefix} (#{post_id}) на модерацию!</b>\n🌐 Сервер: {srv}\n👤 От: @{html.escape(m.from_user.username or str(uid))}\n\n{text}"

    for admin_id in admin_chats:
        try:
            if photo:
                bot.send_photo(admin_id, photo, caption=notif_text, reply_markup=markup)
            else:
                bot.send_message(admin_id, notif_text, reply_markup=markup)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")

    safe_send_message(m.chat.id, "✅ Ваше объявление отправлено на модерацию администраторам!", reply_markup=kb_main_menu(uid))

# ==========================================
# МОДЕРАЦИЯ
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("mod_acc_") or c.data.startswith("mod_rej_") or c.data.startswith("mod_acc_buy_") or c.data.startswith("mod_rej_buy_"))
def cb_moderate_post(call):
    if not is_admin_or_owner_id(call.from_user.id):
        try:
            return bot.answer_callback_query(call.id, "⛔ Нет прав!", show_alert=True)
        except:
            return

    data = call.data
    parts = data.split("_")
    is_buy_mod = "buy" in data
    action = parts[1]  # acc или rej
    pid = parts[-1]    # UUID

    # Получаем объявление из ads
    res = supabase.table("ads").select("*").eq("id", pid).execute()
    if not res.data:
        try:
            bot.answer_callback_query(call.id, "⚠️ Объявление не найдено.", show_alert=True)
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        return

    post = res.data[0]
    admin_uname = call.from_user.username or str(call.from_user.id)

    if action == "acc":
        # Одобряем: меняем статус и устанавливаем expires_at
        expires_at = (datetime.utcnow() + timedelta(hours=AD_EXPIRY_HOURS)).isoformat()
        supabase.table("ads").update({
            "status": "approved",
            "expires_at": expires_at
        }).eq("id", pid).execute()
        # Логируем
        supabase.table("moderator_logs").insert({
            "moderator_id": get_user_uuid_by_telegram_id(call.from_user.id),
            "moderator_username": admin_uname,
            "action": "approve_ad",
            "details": str(pid),
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        # Обновляем статистику редактора
        supabase.table("editor_stats").upsert({"username": admin_uname, "count": 1}).execute()
        try:
            safe_send_message(post["author_id"], f"✅ Ваше объявление (ID {pid}) одобрено и опубликовано!")
        except:
            pass
        try:
            bot.answer_callback_query(call.id, "✅ Одобрено!")
            bot.edit_message_caption(f"✅ <b>Одобрено администратором @{html.escape(admin_uname)}</b>\n\n{post['description']}", call.message.chat.id, call.message.message_id, reply_markup=None)
        except:
            pass
    else:
        # Отклоняем: меняем статус на deleted
        supabase.table("ads").update({"status": "deleted"}).eq("id", pid).execute()
        supabase.table("moderator_logs").insert({
            "moderator_id": get_user_uuid_by_telegram_id(call.from_user.id),
            "moderator_username": admin_uname,
            "action": "reject_ad",
            "details": str(pid),
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        try:
            safe_send_message(post["author_id"], f"❌ Ваше объявление (ID {pid}) отклонено модератором.")
        except:
            pass
        try:
            bot.answer_callback_query(call.id, "❌ Отклонено.")
            bot.edit_message_caption(f"❌ <b>Отклонено администратором @{html.escape(admin_uname)}</b>\n\n{post['description']}", call.message.chat.id, call.message.message_id, reply_markup=None)
        except:
            pass

# ==========================================
# АДМИН-ПАНЕЛЬ
# ==========================================
@bot.message_handler(func=lambda m: m.text == "👑 Админ-панель")
def admin_panel(m):
    uid = m.from_user.id
    if not is_admin_or_owner_id(uid):
        return safe_send_message(m.chat.id, "⛔ Доступ запрещён.")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("модерация продажи"), types.KeyboardButton("модерация скупки"))
    if is_owner(m.from_user):
        markup.row(types.KeyboardButton("рассылка"), types.KeyboardButton("📋 Логи чатов"))
        markup.row(types.KeyboardButton("🔨 Забанить игрока"), types.KeyboardButton("🔓 Разбанить игрока"))
        markup.row(types.KeyboardButton("👑 Добавить адм"), types.KeyboardButton("🚫 Снять с адм"))
    markup.row(types.KeyboardButton("⬅️ Назад"), types.KeyboardButton("❌ Отменить действие"))
    safe_send_message(m.chat.id, "👑 <b>Панель администратора / владельца:</b>", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "модерация продажи")
def show_pending_sales(m):
    if not is_admin_or_owner_id(m.from_user.id):
        return safe_send_message(m.chat.id, "⛔ Доступ запрещён.")
    res = supabase.table("ads").select("*").eq("status", "pending").eq("mode", "sell").limit(10).execute()
    posts = res.data
    if not posts:
        return safe_send_message(m.chat.id, "📭 Нет объявлений о продаже на модерации.")
    safe_send_message(m.chat.id, f"📋 <b>Очередь модерации продаж (найдено: {len(posts)}):</b>")
    for p in posts:
        pid = p["id"]
        text = p["description"]
        srv = p["server"]
        photo = p["images"]
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_acc_{pid}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_rej_{pid}"),
        )
        caption = f"📋 <b>Пост продажи #{pid}</b>\n🌐 Сервер: {srv}\n\n{text}"
        if photo:
            safe_send_photo(m.chat.id, photo, caption=caption, reply_markup=markup)
        else:
            safe_send_message(m.chat.id, caption, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "модерация скупки")
def show_pending_buys(m):
    if not is_admin_or_owner_id(m.from_user.id):
        return safe_send_message(m.chat.id, "⛔ Доступ запрещён.")
    res = supabase.table("ads").select("*").eq("status", "pending").eq("mode", "buy").limit(10).execute()
    posts = res.data
    if not posts:
        return safe_send_message(m.chat.id, "📭 Нет объявлений о скупке на модерации.")
    safe_send_message(m.chat.id, f"📋 <b>Очередь модерации скупки (найдено: {len(posts)}):</b>")
    for p in posts:
        pid = p["id"]
        text = p["description"]
        srv = p["server"]
        photo = p["images"]
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_acc_buy_{pid}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_rej_buy_{pid}"),
        )
        caption = f"📋 <b>Пост скупки #{pid}</b>\n🌐 Сервер: {srv}\n\n{text}"
        if photo:
            safe_send_photo(m.chat.id, photo, caption=caption, reply_markup=markup)
        else:
            safe_send_message(m.chat.id, caption, reply_markup=markup)

# ==========================================
# РАССЫЛКА, ЛОГИ, УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (ВЛАДЕЛЕЦ)
# ==========================================
@bot.message_handler(func=lambda m: m.text == "рассылка")
def start_broadcast(m):
    if not is_owner(m.from_user):
        return safe_send_message(m.chat.id, f"⛔ Только владелец (@{OWNER_USERNAME}).")
    update_state(m.from_user.id, broadcast_input=True)
    safe_send_message(m.chat.id, "📢 Введите текст или отправьте пост (с фото) для рассылки всем пользователям:", reply_markup=kb_cancel())

@bot.message_handler(content_types=["text", "photo"], func=lambda m: get_state(m.from_user.id).get("broadcast_input") is True)
def process_broadcast(m):
    uid = m.from_user.id
    clear_state(uid)
    if not is_owner(m.from_user):
        return safe_send_message(m.chat.id, "⛔ Доступ запрещён.")
    text = m.text or m.caption
    photo = m.photo[-1].file_id if m.photo else None

    # Получаем всех пользователей (их telegram_id)
    res = supabase.table("app_users").select("telegram_id").execute()
    users = [row["telegram_id"] for row in res.data if row["telegram_id"]]

    safe_send_message(m.chat.id, f"🚀 Начинаю рассылку для {len(users)} пользователей...")
    success = 0
    failed = 0
    for u_id in users:
        try:
            if photo:
                bot.send_photo(u_id, photo, caption=text, parse_mode="HTML")
            else:
                bot.send_message(u_id, text, parse_mode="HTML")
            success += 1
            time.sleep(0.04)
        except:
            failed += 1
    safe_send_message(m.chat.id, f"✅ <b>Рассылка завершена!</b>\n📤 Успешно: {success}\n❌ Ошибок: {failed}", reply_markup=kb_main_menu(uid))

@bot.message_handler(func=lambda m: m.text == "📋 Логи чатов")
def show_owner_logs_menu(m):
    if not is_owner(m.from_user) and not is_admin_or_owner_id(m.from_user.id):
        return safe_send_message(m.chat.id, f"⛔ Доступ только владельцу (@{OWNER_USERNAME}).")
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💬 Логи всех чатов (файлом)", callback_data="owner_view_chats"),
        types.InlineKeyboardButton("📢 Логи действий админов (файлом)", callback_data="owner_view_admin_ads"),
    )
    safe_send_message(m.chat.id, "📋 <b>Единый центр логов системы</b>\nВыберите раздел:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["owner_view_chats", "owner_view_admin_ads"])
def cb_owner_logs(call):
    if not is_owner(call.from_user) and not is_admin_or_owner_id(call.from_user.id):
        try:
            return bot.answer_callback_query(call.id, "⛔ Доступ запрещён.", show_alert=True)
        except:
            return
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

    if call.data == "owner_view_chats":
        res = supabase.table("chat_logs_history").select("*").order("timestamp", desc=True).limit(100).execute()
        logs = res.data
        log_text = "ИСТОРИЯ ОБЩЕНИЯ ИГРОКОВ В СДЕЛКАХ (последние 100)\n" + "="*50 + "\n\n"
        if logs:
            for l in logs:
                dt = datetime.fromtimestamp(l["timestamp"], ZoneInfo("Europe/Moscow")).strftime("%d.%m %H:%M:%S")
                log_text += f"[{dt} МСК] (От ID {l['sender_id']} -> К ID {l['receiver_id']}): {l['text']}\n"
        else:
            log_text += "История общения пуста."
        send_log_file(call.message.chat.id, "chat_history_logs.txt", log_text, caption="📁 <b>Файл истории переписок</b>")
    else:
        res = supabase.table("moderator_logs").select("*").order("created_at", desc=True).limit(100).execute()
        logs = res.data
        log_text = "ЛОГИ ДЕЙСТВИЙ АДМИНОВ\n" + "="*50 + "\n\n"
        if logs:
            for l in logs:
                dt = datetime.fromisoformat(l["created_at"]).astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m %H:%M:%S")
                log_text += f"[{dt} МСК] Администратор (@{l['moderator_username']}): {l['action']} | Цель: {l['details']}\n"
        else:
            log_text += "Логи пусты."
        send_log_file(call.message.chat.id, "admin_ads_action_logs.txt", log_text, caption="📁 <b>Файл логов действий админов</b>")

@bot.message_handler(func=lambda m: m.text in ["🔨 Забанить игрока", "🔓 Разбанить игрока", "👑 Добавить адм", "🚫 Снять с адм"])
def owner_action_start(m):
    if not is_owner(m.from_user):
        return safe_send_message(m.chat.id, f"⛔ Только владелец (@{OWNER_USERNAME}).")
    action_map = {
        "🔨 Забанить игрока": "ban",
        "🔓 Разбанить игрока": "unban",
        "👑 Добавить адм": "add_admin",
        "🚫 Снять с адм": "remove_admin"
    }
    action = action_map.get(m.text)
    update_state(m.from_user.id, owner_action_input=action)
    prompts = {
        "ban": "🔨 Введите User ID или @username игрока для блокировки:",
        "unban": "🔓 Введите User ID или @username игрока для разблокировки:",
        "add_admin": "👑 Введите User ID или @username пользователя для назначения администратором:",
        "remove_admin": "🚫 Введите User ID или @username администратора для снятия:"
    }
    safe_send_message(m.chat.id, prompts[action], reply_markup=kb_owner_input())

@bot.message_handler(func=lambda m: get_state(m.from_user.id).get("owner_action_input") is not None)
def process_owner_action(m):
    uid = m.from_user.id
    st = get_state(uid)
    action_type = st.get("owner_action_input")
    target_str = m.text.strip()
    clear_state(uid)

    if not is_owner(m.from_user):
        return safe_send_message(m.chat.id, "⛔ Доступ запрещён.")

    # Ищем пользователя по telegram_id или username
    target_telegram_id = None
    target_uuid = None
    target_uname = target_str.lstrip("@")
    if target_str.isdigit():
        target_telegram_id = int(target_str)
        target_uuid = get_user_uuid_by_telegram_id(target_telegram_id)
    else:
        # Ищем по username
        res = supabase.table("app_users").select("id, telegram_id").eq("username", target_uname).execute()
        if res.data:
            target_uuid = res.data[0]["id"]
            target_telegram_id = res.data[0].get("telegram_id")

    if action_type == "ban":
        if target_uuid:
            supabase.table("app_users").update({"banned": True}).eq("id", target_uuid).execute()
            supabase.table("bans").upsert({"target": str(target_telegram_id or target_str), "is_id": bool(target_telegram_id)}).execute()
            safe_send_message(m.chat.id, f"✅ Игрок <b>{html.escape(target_str)}</b> забанен.", reply_markup=kb_main_menu(uid))
            if target_telegram_id:
                try:
                    safe_send_message(target_telegram_id, "⛔ Вы были забанены администрацией.")
                except:
                    pass
        else:
            safe_send_message(m.chat.id, "⚠️ Пользователь не найден.")
    elif action_type == "unban":
        if target_uuid:
            supabase.table("app_users").update({"banned": False}).eq("id", target_uuid).execute()
            supabase.table("bans").delete().eq("target", str(target_telegram_id or target_str)).execute()
            safe_send_message(m.chat.id, f"✅ Игрок <b>{html.escape(target_str)}</b> разбанен.", reply_markup=kb_main_menu(uid))
        else:
            safe_send_message(m.chat.id, "⚠️ Пользователь не найден.")
    elif action_type == "add_admin":
        if not target_uuid:
            return safe_send_message(m.chat.id, "⚠️ Пользователь не найден. Пусть сначала запустит бота.", reply_markup=kb_main_menu(uid))
        supabase.table("app_users").update({"is_admin": True}).eq("id", target_uuid).execute()
        supabase.table("approved_admins").upsert({"user_id": target_uuid, "username": target_uname}).execute()
        safe_send_message(m.chat.id, f"👑 Пользователь @{target_uname} назначен администратором!", reply_markup=kb_main_menu(uid))
        if target_telegram_id:
            try:
                safe_send_message(target_telegram_id, "👑 Вам назначены права администратора в боте.")
            except:
                pass
    elif action_type == "remove_admin":
        if target_uuid:
            supabase.table("app_users").update({"is_admin": False}).eq("id", target_uuid).execute()
            supabase.table("approved_admins").delete().eq("user_id", target_uuid).execute()
        safe_send_message(m.chat.id, f"🚫 Администратор <b>{html.escape(target_str)}</b> снят.", reply_markup=kb_main_menu(uid))

# ==========================================
# МОИ ПУБЛИКАЦИИ
# ==========================================
@bot.message_handler(func=lambda m: m.text == "📋 Мои публикации")
def show_my_ads(m):
    uid = m.from_user.id
    srv = get_user_server(uid)
    user_uuid = get_user_uuid_by_telegram_id(uid)
    if not user_uuid:
        return safe_send_message(m.chat.id, "Ошибка: пользователь не найден")
    res = supabase.table("ads").select("*").eq("author_id", user_uuid).eq("server", srv).order("created_at", desc=True).execute()
    ads = res.data
    text = f"📋 <b>Ваши активные публикации на сервере {html.escape(srv)}:</b>\n\n"
    if not ads:
        text += "У вас нет объявлений."
    else:
        for a in ads:
            status_map = {"pending": "⏳ На модерации", "approved": "✅ Опубликовано", "deleted": "🗑 Удалено"}
            status_text = status_map.get(a["status"], a["status"])
            text += f"#{a['id']} {a['item_name']} — {format_price(a['price'])} — {status_text}\n"
    safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(uid))

# ==========================================
# ДРУГИЕ КНОПКИ (ЗАГЛУШКИ)
# ==========================================
@bot.message_handler(func=lambda m: m.text == "💱 Курс VC и калькулятор")
def show_vc_menu(m):
    safe_send_message(m.chat.id, "💱 Курс VC и калькулятор в разработке. Используйте мини-приложение.", reply_markup=kb_main_menu(m.from_user.id))

@bot.message_handler(func=lambda m: m.text == "❤️ Сохраненные")
def show_favorites(m):
    safe_send_message(m.chat.id, "❤️ <b>Сохранённые объявления:</b>\n\nСписок пуст.", reply_markup=kb_main_menu(m.from_user.id))

@bot.message_handler(func=lambda m: m.text == "🔍 Найти товар в базе")
def start_search(m):
    safe_send_message(m.chat.id, "🔍 <b>Поиск товара:</b> Используйте мини-приложение для полноценного поиска.", reply_markup=kb_main_menu(m.from_user.id))

@bot.message_handler(func=lambda m: m.text == "📊 Анализ цен на сервере")
def show_average_prices(m):
    safe_send_message(m.chat.id, "📊 Анализ цен в разработке.", reply_markup=kb_main_menu(m.from_user.id))

@bot.message_handler(func=lambda m: m.text == "💬 Связаться с менеджером")
def contact_manager(m):
    safe_send_message(m.chat.id, f"💬 Связаться с менеджером: @{MANAGER_USERNAME}", reply_markup=kb_main_menu(m.from_user.id))

@bot.message_handler(func=lambda m: m.text in CATEGORIES)
def show_category_ads(m):
    safe_send_message(m.chat.id, f"📦 Категория {m.text} — используйте мини-приложение для просмотра.", reply_markup=kb_main_menu(m.from_user.id))

# ==========================================
# ЗАПУСК
# ==========================================
if __name__ == "__main__":
    logger.info("Бот запущен (Supabase, UUID-версия)")
    bot.infinity_polling(skip_pending=True)
