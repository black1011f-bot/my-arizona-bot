# =========================================================
# БОТ ДЛЯ ОБЪЯВЛЕНИЙ ARIZONA RP (ФИНАЛЬНАЯ ВЕРСИЯ)
# Версия 2.0 — полный функционал
# =========================================================

import os
import sys
import time
import threading
import logging
import random
import re
import html
import io
import urllib.parse
import uuid
import traceback
import json
from datetime import datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo
from functools import lru_cache
from collections import defaultdict
import schedule
import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException
from supabase import create_client, Client
from flask import Flask, request

# =========================================================
# 1. КОНФИГУРАЦИЯ И ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ
# =========================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not all([TELEGRAM_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_KEY]):
    print("❌ Не заданы переменные окружения.")
    sys.exit(1)

# Константы
MANAGER_USERNAME = "bounqy31"
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

BAD_WORDS = ["хуй","хуе","хуя","хуи","пизд","еб","бля","сук","залуп","мраз",
             "ебан","долбоеб","сука","блять","ебать","хуесос","пидорас","пидар",
             "мразь","урод","чмо","шлюх","блядь","сукин","залупа","гандон",
             "ондон","дроч","ебуч","еблан","пиздюк","выбляд","samp-rp","advance",
             "Arizona V","Diamond","продажа вирт","продам вирты"]

RATE_LIMIT_SECONDS = 0.6
AD_EXPIRY_HOURS = 48
MAX_DESCRIPTION_LENGTH = 2000
MAX_IMAGES = 10

# =========================================================
# 2. ПОДКЛЮЧЕНИЕ К БАЗЕ И ЛОГИРОВАНИЕ
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=True, num_threads=4)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# =========================================================
# 3. ГЛОБАЛЬНЫЕ КЕШИ И СОСТОЯНИЯ (потокобезопасные)
# =========================================================
admin_cache = {}
user_cache = {}      # {telegram_id: {server, is_premium, last_ad_time, ...}}
state_lock = threading.Lock()
antispam_lock = threading.Lock()
user_last_message_time = {}
user_states = {}     # для многошаговых операций
user_chat_sessions = {}  # для обмена сообщениями между пользователями

CACHE_TTL = 300

def get_cached_admin(telegram_id):
    if telegram_id in admin_cache:
        entry = admin_cache[telegram_id]
        if time.time() - entry['time'] < CACHE_TTL:
            return entry['value']
    return None

def set_cached_admin(telegram_id, value):
    admin_cache[telegram_id] = {'value': value, 'time': time.time()}

def get_cached_user(telegram_id):
    if telegram_id in user_cache:
        entry = user_cache[telegram_id]
        if time.time() - entry['time'] < CACHE_TTL:
            return entry['value']
    return None

def set_cached_user(telegram_id, data):
    user_cache[telegram_id] = {'value': data, 'time': time.time()}

def invalidate_cache(telegram_id):
    if telegram_id in admin_cache:
        del admin_cache[telegram_id]
    if telegram_id in user_cache:
        del user_cache[telegram_id]

# =========================================================
# 4. РАБОТА С SUPABASE (RETRY, КЕШИРОВАНИЕ)
# =========================================================
def supabase_request_with_retry(func, max_retries=2, delay=0.5):
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Supabase failed: {e}")
                raise
            time.sleep(delay * (attempt + 1))

def get_user_uuid_by_telegram_id(telegram_id):
    try:
        res = supabase_request_with_retry(
            lambda: supabase.table("app_users").select("id").eq("telegram_id", telegram_id).execute()
        )
        if res and res.data:
            return res.data[0]["id"]
    except Exception as e:
        logger.error(f"get_user_uuid error: {e}")
    return None

def register_user(telegram_id, username):
    try:
        res = supabase.table("app_users").select("id").eq("telegram_id", telegram_id).execute()
        if res.data:
            supabase.table("app_users").update({"username": username or ""}).eq("telegram_id", telegram_id).execute()
            return res.data[0]["id"]
        fake_hash = "telegram_user_" + str(telegram_id) + "_" + uuid.uuid4().hex[:8]
        new_uuid = uuid.uuid4()
        supabase.table("app_users").insert({
            "id": str(new_uuid),
            "username": username or "",
            "password_hash": fake_hash,
            "telegram_id": telegram_id,
            "telegram_username": username or "",
            "server": SERVERS[0],
            "last_ad_time": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return str(new_uuid)
    except Exception as e:
        logger.error(f"register_user error: {e}")
        return None

def is_banned(user):
    if not user:
        return False
    try:
        uid = get_user_uuid_by_telegram_id(user.id)
        if uid:
            res = supabase.table("app_users").select("banned").eq("id", uid).execute()
            if res.data and res.data[0].get("banned"):
                return True
        res2 = supabase.table("bans").select("target").or_(f"target.eq.{user.id},target.eq.{user.username}").execute()
        return bool(res2.data)
    except:
        return False

def is_admin_or_owner_id(telegram_id):
    cached = get_cached_admin(telegram_id)
    if cached is not None:
        return cached
    try:
        uid = get_user_uuid_by_telegram_id(telegram_id)
        if not uid:
            set_cached_admin(telegram_id, False)
            return False
        res = supabase.table("app_users").select("username, is_admin").eq("id", uid).execute()
        if res.data:
            data = res.data[0]
            if data.get("username") and data["username"].lstrip("@") in ADMIN_USERNAMES:
                set_cached_admin(telegram_id, True)
                return True
            if data.get("is_admin"):
                set_cached_admin(telegram_id, True)
                return True
        res2 = supabase.table("approved_admins").select("user_id").eq("user_id", uid).execute()
        result = bool(res2.data)
        set_cached_admin(telegram_id, result)
        return result
    except:
        set_cached_admin(telegram_id, False)
        return False

def is_owner(user):
    if not user:
        return False
    if user.username and user.username.lstrip("@") == OWNER_USERNAME:
        return True
    try:
        uid = get_user_uuid_by_telegram_id(user.id)
        if uid:
            res = supabase.table("app_users").select("username").eq("id", uid).execute()
            if res.data and res.data[0].get("username", "").lstrip("@") == OWNER_USERNAME:
                return True
    except:
        pass
    return False

def get_owner_id():
    try:
        res = supabase.table("app_users").select("id").eq("username", OWNER_USERNAME).execute()
        if res.data:
            return res.data[0]["id"]
    except:
        pass
    return None

def get_admin_chat_ids():
    try:
        res = supabase.table("admin_chats").select("chat_id").execute()
        return [row["chat_id"] for row in res.data]
    except:
        return []

def register_admin_chat(chat_id):
    try:
        supabase.table("admin_chats").upsert({"chat_id": chat_id}).execute()
    except:
        pass

def get_user_last_ad_time(telegram_id):
    cached = get_cached_user(telegram_id)
    if cached and "last_ad_time" in cached:
        return cached["last_ad_time"]
    try:
        uid = get_user_uuid_by_telegram_id(telegram_id)
        if uid:
            res = supabase.table("app_users").select("last_ad_time").eq("id", uid).execute()
            if res.data:
                val = res.data[0].get("last_ad_time") or 0.0
                # обновить кеш
                cur = get_cached_user(telegram_id) or {}
                cur["last_ad_time"] = val
                set_cached_user(telegram_id, cur)
                return val
    except:
        pass
    return 0.0

def set_user_last_ad_time(telegram_id, t):
    try:
        uid = get_user_uuid_by_telegram_id(telegram_id)
        if uid:
            supabase.table("app_users").update({"last_ad_time": t}).eq("id", uid).execute()
            cur = get_cached_user(telegram_id) or {}
            cur["last_ad_time"] = t
            set_cached_user(telegram_id, cur)
    except:
        pass

def is_user_premium(telegram_id):
    cached = get_cached_user(telegram_id)
    if cached and "is_premium" in cached:
        return cached["is_premium"]
    try:
        uid = get_user_uuid_by_telegram_id(telegram_id)
        if not uid:
            return False
        now = time.time()
        res = supabase.table("premium_users").select("expires_at").eq("user_id", uid).execute()
        prem = False
        if res.data and res.data[0].get("expires_at", 0) > now:
            prem = True
        if not prem:
            try:
                res2 = supabase.table("user_settings").select("vip_subscription").eq("user_id", uid).execute()
                if res2.data and res2.data[0].get("vip_subscription"):
                    prem = True
            except:
                pass
        cur = get_cached_user(telegram_id) or {}
        cur["is_premium"] = prem
        set_cached_user(telegram_id, cur)
        return prem
    except:
        return False

def set_user_server(telegram_id, server):
    try:
        uid = get_user_uuid_by_telegram_id(telegram_id)
        if uid:
            supabase.table("app_users").update({"server": server}).eq("id", uid).execute()
            cur = get_cached_user(telegram_id) or {}
            cur["server"] = server
            set_cached_user(telegram_id, cur)
    except:
        pass

def get_user_server(telegram_id):
    cached = get_cached_user(telegram_id)
    if cached and "server" in cached:
        return cached["server"]
    try:
        uid = get_user_uuid_by_telegram_id(telegram_id)
        if uid:
            res = supabase.table("app_users").select("server").eq("id", uid).execute()
            if res.data and res.data[0].get("server"):
                srv = res.data[0]["server"]
                cur = get_cached_user(telegram_id) or {}
                cur["server"] = srv
                set_cached_user(telegram_id, cur)
                return srv
    except:
        pass
    return SERVERS[0]

def get_user_bonus_ads(telegram_id):
    """Возвращает количество доступных VIP-объявлений."""
    try:
        uid = get_user_uuid_by_telegram_id(telegram_id)
        if uid:
            res = supabase.table("user_bonuses").select("vip_ads_count").eq("user_id", uid).execute()
            if res.data:
                return res.data[0].get("vip_ads_count", 0)
    except:
        pass
    return 0

def decrement_bonus_ad(telegram_id):
    """Уменьшает счётчик бонусных объявлений на 1 (если >0)."""
    try:
        uid = get_user_uuid_by_telegram_id(telegram_id)
        if uid:
            res = supabase.table("user_bonuses").select("vip_ads_count").eq("user_id", uid).execute()
            if res.data:
                current = res.data[0].get("vip_ads_count", 0)
                if current > 0:
                    supabase.table("user_bonuses").update({"vip_ads_count": current - 1}).eq("user_id", uid).execute()
                    return True
    except:
        pass
    return False

# =========================================================
# 5. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================
def parse_flexible_price(text):
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
        except:
            cleaned = cleaned.replace(".", "")
    try:
        return int(float(cleaned) * multiplier)
    except:
        raise ValueError(f"Не удалось распознать цену: {text}")

def check_auto_moderation(text):
    t_lower = text.lower()
    for w in BAD_WORDS:
        if w in t_lower:
            return False
    return True

def is_flooding(user_id):
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
        logger.error(f"Ошибка отправки: {e}")
        return bot.send_message(chat_id, text, parse_mode=None, reply_markup=reply_markup)

def safe_send_photo(chat_id, photo, caption, parse_mode="HTML", reply_markup=None):
    try:
        return bot.send_photo(chat_id, photo, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)
    except ApiTelegramException as e:
        logger.error(f"Ошибка фото: {e}")
        return bot.send_photo(chat_id, photo, caption=caption, parse_mode=None, reply_markup=reply_markup)

def send_log_file(chat_id, filename, text_content, caption=None):
    file_bytes = io.BytesIO(text_content.encode("utf-8"))
    file_bytes.name = filename
    try:
        bot.send_document(chat_id, document=file_bytes, caption=caption, parse_mode="HTML")
    except:
        safe_send_message(chat_id, text_content[:4000])

def format_price(value):
    if not value:
        return "0"
    num = int(value)
    if num >= 1_000_000_000:
        return f"{num/1_000_000_000:.1f}ккк"
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}кк"
    if num >= 1_000:
        return f"{num/1_000:.1f}к"
    return str(num)

def get_msk_time():
    return datetime.now(ZoneInfo("Europe/Moscow"))

# =========================================================
# 6. КЛАВИАТУРЫ
# =========================================================
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

def kb_search_categories():
    m = types.InlineKeyboardMarkup(row_width=1)
    for cat in CATEGORIES:
        m.add(types.InlineKeyboardButton(cat, callback_data=f"search_cat_{cat}"))
    m.add(types.InlineKeyboardButton("🔍 Все категории", callback_data="search_all"))
    return m

# =========================================================
# 7. УПРАВЛЕНИЕ СОСТОЯНИЯМИ
# =========================================================
def get_state(uid):
    with state_lock:
        return user_states.get(uid, {}).copy()

def set_state(uid, data):
    with state_lock:
        user_states[uid] = data

def update_state(uid, **kwargs):
    with state_lock:
        if uid not in user_states:
            user_states[uid] = {}
        user_states[uid].update(kwargs)

def clear_state(uid):
    with state_lock:
        if uid in user_states:
            del user_states[uid]

# =========================================================
# 8. ОБРАБОТЧИКИ КОМАНД И КНОПОК
# =========================================================
@bot.message_handler(func=lambda m: is_flooding(m.from_user.id))
def handle_flood(m):
    safe_send_message(m.chat.id, "⚠️ <b>Слишком частые запросы!</b> Подождите немного.")

@bot.callback_query_handler(func=lambda c: is_flooding(c.from_user.id))
def handle_flood_callback(c):
    bot.answer_callback_query(c.id, "⚠️ Не так быстро! Подождите.", show_alert=False)

@bot.message_handler(func=lambda m: is_banned(m.from_user))
def blocked_user_message(m):
    safe_send_message(m.chat.id, "⛔ Вы заблокированы.", reply_markup=types.ReplyKeyboardRemove())

@bot.callback_query_handler(func=lambda c: is_banned(c.from_user))
def blocked_user_callback(c):
    bot.answer_callback_query(c.id, "⛔ Заблокированы!", show_alert=True)

# ---------- /start ----------
@bot.message_handler(commands=["start"])
def cmd_start(m):
    uid = m.from_user.id
    username = m.from_user.username or ""
    user_uuid = register_user(uid, username)
    if not user_uuid:
        safe_send_message(m.chat.id, "⚠️ Ошибка регистрации.")
        return
    set_user_server(uid, SERVERS[0])
    if is_banned(m.from_user):
        return safe_send_message(m.chat.id, "⛔ Вы заблокированы.", reply_markup=types.ReplyKeyboardRemove())

    # Реферальная ссылка
    args = m.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_tg = int(args[1].replace("ref_", ""))
            if referrer_tg != uid:
                referrer_uuid = get_user_uuid_by_telegram_id(referrer_tg)
                if referrer_uuid:
                    res = supabase.table("referrals").select("1").eq("referrer_id", referrer_uuid).eq("referred_id", uid).execute()
                    if not res.data:
                        supabase.table("referrals").insert({
                            "referrer_id": referrer_uuid,
                            "referred_id": uid,
                            "last_active_date": get_msk_time().strftime("%Y-%m-%d")
                        }).execute()
                        now_ts = time.time()
                        for target_tg_id in [referrer_tg, uid]:
                            target_uuid = get_user_uuid_by_telegram_id(target_tg_id)
                            if target_uuid:
                                res_prem = supabase.table("premium_users").select("expires_at").eq("user_id", target_uuid).execute()
                                base_exp = res_prem.data[0]["expires_at"] if res_prem.data and res_prem.data[0]["expires_at"] > now_ts else now_ts
                                new_exp = base_exp + 10*86400
                                supabase.table("premium_users").upsert({"user_id": target_uuid, "expires_at": new_exp}).execute()
                        safe_send_message(referrer_tg, "🎉 По вашей реферальной ссылке зарегистрировался друг! Вам и другу VIP на 10 дней!")
                        safe_send_message(uid, "🎁 Вы зарегистрировались по реферальной ссылке! Вам VIP на 10 дней!")
        except:
            pass

    text = (f"👋 Привет, <b>{html.escape(m.from_user.first_name)}</b>!\n"
            f"🤖 Неофициальный бот объявлений Arizona RP.\n"
            f"🌐 Текущий сервер: {get_user_server(uid)}\n"
            f"⚠️ Все сделки на ваш риск.\nВыберите раздел:")
    safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(uid))

# ---------- /help ----------
@bot.message_handler(commands=["help"])
def cmd_help(m):
    text = ("❓ <b>FAQ</b>\n\n"
            "1. Бот неофициальный.\n"
            "2. Продажа/скупка — кнопки в меню.\n"
            "3. Модерация занимает до 24 ч.\n"
            "4. VIP уменьшает кулдаун до 60 сек.\n"
            "5. Рефералы — VIP за приглашённых.\n"
            "6. Бонусы — ежедневный розыгрыш.\n"
            "7. По вопросам: @bounqy31")
    safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(m.from_user.id))

# ---------- Навигация ----------
@bot.message_handler(func=lambda m: m.text in ["❌ Отменить действие", "⬅️ Назад"])
def cancel_action(m):
    clear_state(m.from_user.id)
    safe_send_message(m.chat.id, "❌ Отменено.", reply_markup=kb_main_menu(m.from_user.id))

# ---------- Смена сервера ----------
@bot.message_handler(func=lambda m: m.text == "🌐 Сменить игровой сервер")
def change_server(m):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for i in range(0, len(SERVERS), 2):
        row = [types.KeyboardButton(s) for s in SERVERS[i:i+2]]
        markup.row(*row)
    markup.row(types.KeyboardButton("⬅️ Назад"), types.KeyboardButton("❌ Отменить действие"))
    safe_send_message(m.chat.id, "🌐 Выберите сервер:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in SERVERS)
def select_srv(m):
    set_user_server(m.from_user.id, m.text)
    safe_send_message(m.chat.id, f"✅ Сервер изменён на {html.escape(m.text)}", reply_markup=kb_main_menu(m.from_user.id))

# ---------- VIP ----------
@bot.message_handler(func=lambda m: m.text == "💎 VIP-статус")
def info_premium(m):
    uid = m.from_user.id
    is_prem = is_user_premium(uid)
    status = "✅ Активен" if is_prem else "❌ Неактивен"
    user_uuid = get_user_uuid_by_telegram_id(uid)
    if user_uuid:
        res = supabase.table("premium_users").select("expires_at").eq("user_id", user_uuid).execute()
        if res.data and res.data[0]["expires_at"] > time.time():
            exp_date = datetime.fromtimestamp(res.data[0]["expires_at"], ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M")
            status += f" (до {exp_date} МСК)"
    text = (f"💎 VIP-статус\nСтатус: {status}\n\n"
            "Преимущества:\n• Кулдаун 60 сек вместо 120\n• Приоритет\n\nКупить за Telegram Stars:")
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("👑 30 дней — 100 ⭐", callback_data="buy_vip_30"),
        types.InlineKeyboardButton("👑 Навсегда — 500 ⭐", callback_data="buy_vip_forever")
    )
    safe_send_message(m.chat.id, text, reply_markup=markup)

# ---------- Обработка платежей ----------
@bot.pre_checkout_query_handler(func=lambda query: True)
def handle_pre_checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    payload = message.successful_payment.invoice_payload
    uid = message.from_user.id
    user_uuid = get_user_uuid_by_telegram_id(uid)
    if not user_uuid:
        return
    now = time.time()
    if payload == "premium_30":
        days = 30
    else:
        days = 9999  # навсегда
    # Начисляем VIP
    res = supabase.table("premium_users").select("expires_at").eq("user_id", user_uuid).execute()
    base_exp = res.data[0]["expires_at"] if res.data and res.data[0]["expires_at"] > now else now
    new_exp = base_exp + days * 86400
    supabase.table("premium_users").upsert({"user_id": user_uuid, "expires_at": new_exp}).execute()
    # Обновляем кеш
    cur = get_cached_user(uid) or {}
    cur["is_premium"] = True
    set_cached_user(uid, cur)
    safe_send_message(message.chat.id, f"✅ VIP-статус активирован на {days} дней!")

@bot.callback_query_handler(func=lambda c: c.data in ["buy_vip_30", "buy_vip_forever"])
def cb_buy_vip(call):
    if call.data == "buy_vip_30":
        prices = [types.LabeledPrice("VIP 30 дней", 100)]
        payload = "premium_30"
        title = "VIP 30 дней"
        desc = "VIP на 30 дней"
    else:
        prices = [types.LabeledPrice("VIP навсегда", 500)]
        payload = "premium_forever"
        title = "VIP навсегда"
        desc = "Пожизненный VIP"
    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title=title,
            description=desc,
            invoice_payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="vip_sub"
        )
    except Exception as e:
        logger.error(f"Ошибка инвойса: {e}")

# ---------- Рефералы и бонусы ----------
@bot.message_handler(func=lambda m: m.text == "👥 Рефералы и Бонусы")
def show_ref_bonus_menu(m):
    uid = m.from_user.id
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{uid}"
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={urllib.parse.quote('Залетай в лучший бот объявлений Arizona RP!')}"

    user_uuid = get_user_uuid_by_telegram_id(uid)
    if not user_uuid:
        safe_send_message(m.chat.id, "Ошибка")
        return

    res = supabase.table("referrals").select("count", count="exact").eq("referrer_id", user_uuid).execute()
    ref_count = res.count or 0

    res_bonus = supabase.table("user_bonuses").select("*").eq("user_id", user_uuid).execute()
    bonus_row = res_bonus.data[0] if res_bonus.data else None
    last_claim_ts = bonus_row.get("last_claim_timestamp", 0.0) if bonus_row else 0.0
    vip_ads = bonus_row.get("vip_ads_count", 0) if bonus_row else 0

    current_ts = time.time()
    cooldown = 86400
    can_claim = (current_ts - last_claim_ts) >= cooldown
    remaining = int(cooldown - (current_ts - last_claim_ts)) if not can_claim else 0
    h = remaining // 3600
    m_rem = (remaining % 3600)//60

    text = (f"👥 Рефералы и Бонусы\n\n"
            f"Приглашайте друзей — получайте VIP на 10 дней!\n"
            f"🔗 Ссылка: <code>{ref_link}</code>\n"
            f"📊 Приглашено: {ref_count}\n"
            f"⭐ Бонусных VIP-объявлений: {vip_ads}\n"
            f"🎁 Ежедневный бонус (24ч):")
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("📤 Поделиться", url=share_url))
    if can_claim:
        markup.add(types.InlineKeyboardButton("🎁 Забрать бонус", callback_data="claim_daily_bonus"))
    else:
        markup.add(types.InlineKeyboardButton(f"⏳ Через {h}ч {m_rem}мин", callback_data="bonus_cooldown_alert"))
    safe_send_message(m.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["claim_daily_bonus", "bonus_cooldown_alert"])
def cb_daily_bonus(call):
    uid = call.from_user.id
    user_uuid = get_user_uuid_by_telegram_id(uid)
    if not user_uuid:
        return bot.answer_callback_query(call.id, "Ошибка", show_alert=True)
    current_ts = time.time()
    cooldown = 86400
    res_bonus = supabase.table("user_bonuses").select("*").eq("user_id", user_uuid).execute()
    bonus_row = res_bonus.data[0] if res_bonus.data else None
    last_claim_ts = bonus_row.get("last_claim_timestamp", 0.0) if bonus_row else 0.0
    if current_ts - last_claim_ts < cooldown:
        remaining = int(cooldown - (current_ts - last_claim_ts))
        h = remaining//3600
        m = (remaining%3600)//60
        return bot.answer_callback_query(call.id, f"⏳ Осталось {h}ч {m}мин", show_alert=True)

    roll = random.randint(1,100)
    today_str = get_msk_time().strftime("%Y-%m-%d")
    if roll <= 5:
        # VIP на 13 дней
        res_prem = supabase.table("premium_users").select("expires_at").eq("user_id", user_uuid).execute()
        base_exp = res_prem.data[0]["expires_at"] if res_prem.data and res_prem.data[0]["expires_at"] > current_ts else current_ts
        new_exp = base_exp + 13*86400
        supabase.table("premium_users").upsert({"user_id": user_uuid, "expires_at": new_exp}).execute()
        msg = "🎉 Поздравляем! Вы выбили VIP на 13 дней!"
    else:
        if roll <= 35: ads_won = 1
        elif roll <= 60: ads_won = 2
        elif roll <= 80: ads_won = 3
        elif roll <= 92: ads_won = 4
        else: ads_won = 5
        current_ads = bonus_row.get("vip_ads_count", 0) if bonus_row else 0
        new_ads = current_ads + ads_won
        supabase.table("user_bonuses").upsert({
            "user_id": user_uuid,
            "last_claim_date": today_str,
            "last_claim_timestamp": current_ts,
            "vip_ads_count": new_ads,
            "vip_ads_expiry": current_ts + 86400
        }).execute()
        msg = f"🎁 Вы выбили {ads_won} VIP-объявлений!"
    supabase.table("user_bonuses").update({"last_claim_date": today_str, "last_claim_timestamp": current_ts}).eq("user_id", user_uuid).execute()
    bot.answer_callback_query(call.id, "🎉 Бонус получен!")
    safe_send_message(call.message.chat.id, msg)
    show_ref_bonus_menu(call.message)

# =========================================================
# 9. СОЗДАНИЕ ОБЪЯВЛЕНИЙ (ПОШАГОВОЕ) С ЦЕНОЙ И ФОТО
# =========================================================
def validate_ad_submission(telegram_id):
    now_msk = get_msk_time()
    current_time = now_msk.time()
    start = dtime(8,0,0); end = dtime(22,0,0)
    if not (start <= current_time <= end):
        return False, "❌ Объявления принимаются с 8:00 до 22:00 МСК."
    is_prem = is_user_premium(telegram_id)
    cooldown = 60 if is_prem else 120
    last = get_user_last_ad_time(telegram_id)
    elapsed = time.time() - last
    if elapsed < cooldown:
        remaining = int(cooldown - elapsed)
        return False, f"⏳ Кулдаун {remaining} сек. (Ваш кулдаун: {'1 мин' if is_prem else '2 мин'})"
    # Проверка бонусных объявлений
    bonus = get_user_bonus_ads(telegram_id)
    if bonus > 0:
        return True, ""  # можно использовать бонус
    return True, ""

@bot.message_handler(func=lambda m: m.text == "📤 Продать товар")
def start_add_ad(m):
    uid = m.from_user.id
    ok, msg = validate_ad_submission(uid)
    if not ok:
        return safe_send_message(m.chat.id, msg, reply_markup=kb_main_menu(uid))
    # Начинаем многошаговый процесс
    update_state(uid, {"ad_step": "category", "is_buy": False, "images": []})
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    for cat in CATEGORIES:
        markup.add(types.KeyboardButton(cat))
    markup.row(types.KeyboardButton("⬅️ Назад"), types.KeyboardButton("❌ Отменить действие"))
    safe_send_message(m.chat.id, "📤 <b>Продажа</b>\nВыберите категорию:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📥 Скупить товар")
def start_add_buy_ad(m):
    uid = m.from_user.id
    ok, msg = validate_ad_submission(uid)
    if not ok:
        return safe_send_message(m.chat.id, msg, reply_markup=kb_main_menu(uid))
    update_state(uid, {"ad_step": "category", "is_buy": True, "images": []})
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    for cat in CATEGORIES:
        markup.add(types.KeyboardButton(cat))
    markup.row(types.KeyboardButton("⬅️ Назад"), types.KeyboardButton("❌ Отменить действие"))
    safe_send_message(m.chat.id, "📥 <b>Скупка</b>\nВыберите категорию:", reply_markup=markup)

@bot.message_handler(func=lambda m: get_state(m.from_user.id).get("ad_step") == "category" and m.text in CATEGORIES)
def process_ad_category(m):
    uid = m.from_user.id
    cat = m.text
    update_state(uid, ad_step="price", category=cat)
    safe_send_message(m.chat.id, "💰 Введите цену (например, 150к, 2.5кк, 1ккк):", reply_markup=kb_cancel())

@bot.message_handler(func=lambda m: get_state(m.from_user.id).get("ad_step") == "price")
def process_ad_price(m):
    uid = m.from_user.id
    try:
        price = parse_flexible_price(m.text)
        if price < 0 or price > 10**12:
            raise ValueError
        update_state(uid, ad_step="name", price=price)
        safe_send_message(m.chat.id, "📝 Введите краткое название товара (до 100 символов):", reply_markup=kb_cancel())
    except:
        safe_send_message(m.chat.id, "⚠️ Некорректная цена. Попробуйте снова (например, 150к, 2.5кк):", reply_markup=kb_cancel())

@bot.message_handler(func=lambda m: get_state(m.from_user.id).get("ad_step") == "name")
def process_ad_name(m):
    uid = m.from_user.id
    name = m.text.strip()[:100]
    if not name:
        return safe_send_message(m.chat.id, "⚠️ Название не может быть пустым.")
    update_state(uid, ad_step="description", item_name=name)
    safe_send_message(m.chat.id, "📄 Введите описание (до 2000 символов). Можно добавить фото (до 10 шт.) на следующем шаге.", reply_markup=kb_cancel())

@bot.message_handler(content_types=["text", "photo"], func=lambda m: get_state(m.from_user.id).get("ad_step") == "description")
def process_ad_description(m):
    uid = m.from_user.id
    st = get_state(uid)
    if m.text:
        desc = m.text.strip()
        if len(desc) > MAX_DESCRIPTION_LENGTH:
            return safe_send_message(m.chat.id, f"⚠️ Описание слишком длинное (макс {MAX_DESCRIPTION_LENGTH} символов).")
        if not check_auto_moderation(desc):
            return safe_send_message(m.chat.id, "🤬 Обнаружены запрещённые слова.")
        update_state(uid, description=desc, ad_step="images")
        safe_send_message(m.chat.id, "📸 Отправьте фото (до 10 шт.) или нажмите «Готово», если фото не будет.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("✅ Готово (без фото)"), types.KeyboardButton("❌ Отменить действие")))
    elif m.photo:
        # Если пользователь отправил фото до описания — просим сначала описание
        safe_send_message(m.chat.id, "Сначала отправьте текстовое описание.")
    else:
        safe_send_message(m.chat.id, "Отправьте текст описания.")

@bot.message_handler(content_types=["photo"], func=lambda m: get_state(m.from_user.id).get("ad_step") == "images")
def process_ad_images(m):
    uid = m.from_user.id
    st = get_state(uid)
    images = st.get("images", [])
    if len(images) >= MAX_IMAGES:
        return safe_send_message(m.chat.id, f"⚠️ Максимум {MAX_IMAGES} фото.")
    file_id = m.photo[-1].file_id
    images.append(file_id)
    update_state(uid, images=images)
    safe_send_message(m.chat.id, f"✅ Фото добавлено ({len(images)}/{MAX_IMAGES}). Отправьте ещё или нажмите «Готово».", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("✅ Готово (без фото)"), types.KeyboardButton("❌ Отменить действие")))

@bot.message_handler(func=lambda m: m.text == "✅ Готово (без фото)" and get_state(m.from_user.id).get("ad_step") == "images")
def finish_ad(m):
    uid = m.from_user.id
    st = get_state(uid)
    # Проверяем наличие обязательных полей
    if "description" not in st or "item_name" not in st or "price" not in st or "category" not in st:
        return safe_send_message(m.chat.id, "⚠️ Что-то пошло не так. Начните заново.", reply_markup=kb_main_menu(uid))
    # Проверяем кулдаун ещё раз
    ok, msg = validate_ad_submission(uid)
    if not ok:
        clear_state(uid)
        return safe_send_message(m.chat.id, msg, reply_markup=kb_main_menu(uid))

    # Создаём объявление
    srv = get_user_server(uid)
    is_buy = st.get("is_buy", False)
    images = st.get("images", [])
    images_json = json.dumps(images)  # сохраняем как JSON массив
    is_vip = 1 if is_user_premium(uid) else 0
    # Используем бонусное объявление, если есть
    used_bonus = False
    bonus = get_user_bonus_ads(uid)
    if bonus > 0 and not is_vip:
        # можно использовать бонус вместо VIP
        used_bonus = True
        decrement_bonus_ad(uid)
        is_vip = 1  # виртуально приравниваем к VIP (кулдаун уже проверен)

    author_uuid = get_user_uuid_by_telegram_id(uid)
    if not author_uuid:
        clear_state(uid)
        return safe_send_message(m.chat.id, "Ошибка пользователя.", reply_markup=kb_main_menu(uid))

    new_ad = {
        "author_id": author_uuid,
        "author_username": m.from_user.username or str(uid),
        "server": srv,
        "category": st["category"],
        "item_name": st["item_name"],
        "description": st["description"],
        "price": st["price"],
        "images": images_json,
        "is_vip": bool(is_vip),
        "mode": "sell" if not is_buy else "buy",
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hidden": False
    }
    res = supabase.table("ads").insert(new_ad).execute()
    if not res.data:
        clear_state(uid)
        return safe_send_message(m.chat.id, "Ошибка сохранения.", reply_markup=kb_main_menu(uid))
    post_id = res.data[0]["id"]

    set_user_last_ad_time(uid, time.time())

    # Уведомление админам
    admin_chats = get_admin_chat_ids()
    prefix = "скупки" if is_buy else "продажи"
    callback_acc = f"mod_acc_{post_id}" if not is_buy else f"mod_acc_buy_{post_id}"
    callback_rej = f"mod_rej_{post_id}" if not is_buy else f"mod_rej_buy_{post_id}"

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Одобрить", callback_data=callback_acc),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=callback_rej),
    )

    notif_text = f"🔔 Новое объявление {prefix} (#{post_id}) на модерацию!\n🌐 {srv}\n👤 @{html.escape(m.from_user.username or str(uid))}\n💰 {format_price(st['price'])}\n\n{st['description']}"
    for admin_id in admin_chats:
        try:
            if images:
                # Отправляем первое фото с подписью
                bot.send_photo(admin_id, images[0], caption=notif_text, reply_markup=markup)
                # Остальные фото отправляем без подписи
                for img in images[1:]:
                    bot.send_photo(admin_id, img)
            else:
                bot.send_message(admin_id, notif_text, reply_markup=markup)
        except Exception as e:
            logger.error(f"Не удалось уведомить админа {admin_id}: {e}")

    clear_state(uid)
    safe_send_message(m.chat.id, f"✅ Ваше объявление отправлено на модерацию. ID: {post_id}", reply_markup=kb_main_menu(uid))

# =========================================================
# 10. МОДЕРАЦИЯ (с комментарием при отклонении)
# =========================================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("mod_acc_") or c.data.startswith("mod_rej_") or c.data.startswith("mod_acc_buy_") or c.data.startswith("mod_rej_buy_"))
def cb_moderate_post(call):
    if not is_admin_or_owner_id(call.from_user.id):
        return bot.answer_callback_query(call.id, "⛔ Нет прав!", show_alert=True)

    data = call.data
    parts = data.split("_")
    is_buy = "buy" in data
    action = parts[1]
    pid = parts[-1]

    res = supabase.table("ads").select("*").eq("id", pid).execute()
    if not res.data:
        bot.answer_callback_query(call.id, "⚠️ Объявление не найдено.", show_alert=True)
        return

    post = res.data[0]
    admin_uname = call.from_user.username or str(call.from_user.id)

    if action == "acc":
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=AD_EXPIRY_HOURS)).isoformat()
        supabase.table("ads").update({"status": "approved", "expires_at": expires_at}).eq("id", pid).execute()
        supabase.table("moderator_logs").insert({
            "moderator_id": get_user_uuid_by_telegram_id(call.from_user.id),
            "moderator_username": admin_uname,
            "action": "approve_ad",
            "details": str(pid),
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        try:
            safe_send_message(post["author_id"], f"✅ Ваше объявление #{pid} одобрено!")
        except:
            pass
        bot.answer_callback_query(call.id, "✅ Одобрено")
        bot.edit_message_caption(f"✅ Одобрено @{html.escape(admin_uname)}\n\n{post['description']}", call.message.chat.id, call.message.message_id, reply_markup=None)
    else:
        # Отклонение с комментарием
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("Без комментария", callback_data=f"rej_no_comment_{pid}"))
        for reason in ["Неверная цена", "Некорректный сервер", "Нарушение правил", "Дубликат"]:
            markup.add(types.InlineKeyboardButton(reason, callback_data=f"rej_comment_{pid}_{reason}"))
        bot.send_message(call.message.chat.id, "Выберите причину отклонения или введите свой текст:", reply_markup=markup)
        bot.answer_callback_query(call.id)

# Обработка выбора причины отклонения
@bot.callback_query_handler(func=lambda c: c.data.startswith("rej_"))
def cb_reject_reason(call):
    if not is_admin_or_owner_id(call.from_user.id):
        return
    data = call.data
    if data.startswith("rej_no_comment_"):
        pid = data.replace("rej_no_comment_", "")
        reason = "Без комментария"
        finalize_reject(call, pid, reason)
    elif data.startswith("rej_comment_"):
        parts = data.split("_", 3)  # rej_comment_{pid}_{reason}
        pid = parts[2]
        reason = parts[3]
        finalize_reject(call, pid, reason)
    else:
        # Ожидаем текстовый комментарий от администратора
        bot.send_message(call.message.chat.id, "Введите текст причины отклонения:")
        # сохраняем pid в состоянии админа
        update_state(call.from_user.id, {"reject_pending": pid})
        bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: get_state(m.from_user.id).get("reject_pending") is not None)
def process_reject_comment(m):
    uid = m.from_user.id
    pid = get_state(uid).get("reject_pending")
    clear_state(uid)
    if not pid:
        return
    finalize_reject(m, pid, m.text)

def finalize_reject(sender, pid, reason):
    # sender может быть call или message
    chat_id = sender.chat.id if hasattr(sender, 'chat') else sender.message.chat.id
    user_id = sender.from_user.id
    # Получаем объявление
    res = supabase.table("ads").select("*").eq("id", pid).execute()
    if not res.data:
        safe_send_message(chat_id, "Объявление не найдено.")
        return
    post = res.data[0]
    supabase.table("ads").update({"status": "deleted"}).eq("id", pid).execute()
    supabase.table("moderator_logs").insert({
        "moderator_id": get_user_uuid_by_telegram_id(user_id),
        "moderator_username": sender.from_user.username or str(user_id),
        "action": "reject_ad",
        "details": f"{pid}: {reason}",
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()
    try:
        safe_send_message(post["author_id"], f"❌ Ваше объявление #{pid} отклонено. Причина: {reason}")
    except:
        pass
    safe_send_message(chat_id, f"❌ Объявление #{pid} отклонено с причиной: {reason}")
    # Попытка обновить исходное сообщение админа
    try:
        bot.edit_message_caption(f"❌ Отклонено @{html.escape(sender.from_user.username or str(user_id))}\nПричина: {reason}\n\n{post['description']}", chat_id, sender.message.message_id, reply_markup=None)
    except:
        pass

# ---------- Модерация по кнопке в админ-панели ----------
@bot.message_handler(func=lambda m: m.text == "модерация продажи")
def show_pending_sales(m):
    if not is_admin_or_owner_id(m.from_user.id):
        return safe_send_message(m.chat.id, "⛔ Доступ запрещён.")
    res = supabase.table("ads").select("*").eq("status", "pending").eq("mode", "sell").limit(10).execute()
    posts = res.data
    if not posts:
        return safe_send_message(m.chat.id, "📭 Нет продаж на модерации.")
    for p in posts:
        pid = p["id"]
        caption = f"📋 Пост продажи #{pid}\n🌐 {p['server']}\n💰 {format_price(p['price'])}\n\n{p['description']}"
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_acc_{pid}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_rej_{pid}"),
        )
        images = json.loads(p["images"]) if p["images"] else []
        if images:
            safe_send_photo(m.chat.id, images[0], caption, reply_markup=markup)
        else:
            safe_send_message(m.chat.id, caption, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "модерация скупки")
def show_pending_buys(m):
    if not is_admin_or_owner_id(m.from_user.id):
        return safe_send_message(m.chat.id, "⛔ Доступ запрещён.")
    res = supabase.table("ads").select("*").eq("status", "pending").eq("mode", "buy").limit(10).execute()
    posts = res.data
    if not posts:
        return safe_send_message(m.chat.id, "📭 Нет скупки на модерации.")
    for p in posts:
        pid = p["id"]
        caption = f"📋 Пост скупки #{pid}\n🌐 {p['server']}\n💰 {format_price(p['price'])}\n\n{p['description']}"
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_acc_buy_{pid}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_rej_buy_{pid}"),
        )
        images = json.loads(p["images"]) if p["images"] else []
        if images:
            safe_send_photo(m.chat.id, images[0], caption, reply_markup=markup)
        else:
            safe_send_message(m.chat.id, caption, reply_markup=markup)

# =========================================================
# 11. АДМИН-ПАНЕЛЬ (расширенная)
# =========================================================
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
        markup.row(types.KeyboardButton("📊 Статистика модераторов"))
    markup.row(types.KeyboardButton("⬅️ Назад"), types.KeyboardButton("❌ Отменить действие"))
    safe_send_message(m.chat.id, "👑 Админ-панель", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "рассылка")
def start_broadcast(m):
    if not is_owner(m.from_user):
        return safe_send_message(m.chat.id, "⛔ Только владелец.")
    update_state(m.from_user.id, broadcast_input=True)
    safe_send_message(m.chat.id, "📢 Введите текст или отправьте пост для рассылки:", reply_markup=kb_cancel())

@bot.message_handler(content_types=["text", "photo"], func=lambda m: get_state(m.from_user.id).get("broadcast_input") is True)
def process_broadcast(m):
    uid = m.from_user.id
    clear_state(uid)
    if not is_owner(m.from_user):
        return
    text = m.text or m.caption
    photo = m.photo[-1].file_id if m.photo else None
    res = supabase.table("app_users").select("telegram_id").execute()
    users = [row["telegram_id"] for row in res.data if row["telegram_id"]]
    safe_send_message(m.chat.id, f"🚀 Начинаю рассылку для {len(users)} пользователей...")
    success = failed = 0
    for u_id in users:
        try:
            if photo:
                bot.send_photo(u_id, photo, caption=text, parse_mode="HTML")
            else:
                bot.send_message(u_id, text, parse_mode="HTML")
            success += 1
            time.sleep(0.05)
        except:
            failed += 1
    safe_send_message(m.chat.id, f"✅ Рассылка завершена! Успешно: {success}, Ошибок: {failed}", reply_markup=kb_main_menu(uid))

@bot.message_handler(func=lambda m: m.text == "📋 Логи чатов")
def show_owner_logs_menu(m):
    if not is_owner(m.from_user) and not is_admin_or_owner_id(m.from_user.id):
        return safe_send_message(m.chat.id, "⛔ Доступ только владельцу.")
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💬 Логи чатов", callback_data="owner_view_chats"),
        types.InlineKeyboardButton("📢 Логи админов", callback_data="owner_view_admin_ads"),
        types.InlineKeyboardButton("📈 Статистика модераторов", callback_data="owner_stats_mods"),
    )
    safe_send_message(m.chat.id, "📋 Логи системы:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("owner_"))
def cb_owner_logs(call):
    if not is_owner(call.from_user) and not is_admin_or_owner_id(call.from_user.id):
        return bot.answer_callback_query(call.id, "⛔ Нет прав", show_alert=True)
    bot.answer_callback_query(call.id)
    if call.data == "owner_view_chats":
        res = supabase.table("chat_logs_history").select("*").order("timestamp", desc=True).limit(100).execute()
        logs = res.data
        text = "ИСТОРИЯ ЧАТОВ (последние 100)\n" + "="*50 + "\n"
        for l in logs:
            dt = datetime.fromtimestamp(l["timestamp"], ZoneInfo("Europe/Moscow")).strftime("%d.%m %H:%M:%S")
            text += f"[{dt} МСК] {l['sender_id']} -> {l['receiver_id']}: {l['text']}\n"
        send_log_file(call.message.chat.id, "chat_logs.txt", text, caption="📁 История чатов")
    elif call.data == "owner_view_admin_ads":
        res = supabase.table("moderator_logs").select("*").order("created_at", desc=True).limit(100).execute()
        logs = res.data
        text = "ЛОГИ АДМИНОВ\n" + "="*50 + "\n"
        for l in logs:
            dt = datetime.fromisoformat(l["created_at"]).astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m %H:%M:%S")
            text += f"[{dt} МСК] @{l['moderator_username']}: {l['action']} | {l['details']}\n"
        send_log_file(call.message.chat.id, "admin_logs.txt", text, caption="📁 Логи админов")
    elif call.data == "owner_stats_mods":
        res = supabase.table("moderator_logs").select("moderator_username, action").execute()
        data = res.data
        stats = {}
        for row in data:
            uname = row["moderator_username"]
            action = row["action"]
            if uname not in stats:
                stats[uname] = {"approve":0, "reject":0}
            if "approve" in action:
                stats[uname]["approve"] += 1
            elif "reject" in action:
                stats[uname]["reject"] += 1
        text = "СТАТИСТИКА МОДЕРАТОРОВ\n" + "="*50 + "\n"
        for uname, vals in stats.items():
            text += f"@{uname}: одобрено {vals['approve']}, отклонено {vals['reject']}\n"
        safe_send_message(call.message.chat.id, text)

# ---------- Управление игроками и админами ----------
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
    action = action_map[m.text]
    update_state(m.from_user.id, owner_action_input=action)
    prompts = {
        "ban": "🔨 Введите User ID или @username для бана:",
        "unban": "🔓 Введите User ID или @username для разбана:",
        "add_admin": "👑 Введите User ID или @username для назначения админом:",
        "remove_admin": "🚫 Введите User ID или @username для снятия:"
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

    target_telegram_id = None
    target_uuid = None
    target_uname = target_str.lstrip("@")
    if target_str.isdigit():
        target_telegram_id = int(target_str)
        target_uuid = get_user_uuid_by_telegram_id(target_telegram_id)
    else:
        res = supabase.table("app_users").select("id, telegram_id").eq("username", target_uname).execute()
        if res.data:
            target_uuid = res.data[0]["id"]
            target_telegram_id = res.data[0].get("telegram_id")

    if action_type == "ban":
        if target_uuid:
            supabase.table("app_users").update({"banned": True}).eq("id", target_uuid).execute()
            supabase.table("bans").upsert({"target": str(target_telegram_id or target_str), "is_id": bool(target_telegram_id)}).execute()
            safe_send_message(m.chat.id, f"✅ Игрок {html.escape(target_str)} забанен.", reply_markup=kb_main_menu(uid))
            if target_telegram_id:
                safe_send_message(target_telegram_id, "⛔ Вы забанены.")
            invalidate_cache(target_telegram_id)
        else:
            safe_send_message(m.chat.id, "⚠️ Пользователь не найден.")
    elif action_type == "unban":
        if target_uuid:
            supabase.table("app_users").update({"banned": False}).eq("id", target_uuid).execute()
            supabase.table("bans").delete().eq("target", str(target_telegram_id or target_str)).execute()
            safe_send_message(m.chat.id, f"✅ {html.escape(target_str)} разбанен.", reply_markup=kb_main_menu(uid))
            invalidate_cache(target_telegram_id)
        else:
            safe_send_message(m.chat.id, "⚠️ Пользователь не найден.")
    elif action_type == "add_admin":
        if not target_uuid:
            return safe_send_message(m.chat.id, "⚠️ Пользователь не найден.", reply_markup=kb_main_menu(uid))
        supabase.table("app_users").update({"is_admin": True}).eq("id", target_uuid).execute()
        supabase.table("approved_admins").upsert({"user_id": target_uuid, "username": target_uname}).execute()
        safe_send_message(m.chat.id, f"👑 @{target_uname} назначен админом!", reply_markup=kb_main_menu(uid))
        if target_telegram_id:
            safe_send_message(target_telegram_id, "👑 Вам назначены права администратора.")
        invalidate_cache(target_telegram_id)
    elif action_type == "remove_admin":
        if target_uuid:
            supabase.table("app_users").update({"is_admin": False}).eq("id", target_uuid).execute()
            supabase.table("approved_admins").delete().eq("user_id", target_uuid).execute()
        safe_send_message(m.chat.id, f"🚫 Администратор {html.escape(target_str)} снят.", reply_markup=kb_main_menu(uid))
        invalidate_cache(target_telegram_id)

# =========================================================
# 12. МОИ ПУБЛИКАЦИИ (с возможностью удалить/редактировать)
# =========================================================
@bot.message_handler(func=lambda m: m.text == "📋 Мои публикации")
def show_my_ads(m):
    uid = m.from_user.id
    srv = get_user_server(uid)
    user_uuid = get_user_uuid_by_telegram_id(uid)
    if not user_uuid:
        return safe_send_message(m.chat.id, "Ошибка")
    res = supabase.table("ads").select("*").eq("author_id", user_uuid).eq("server", srv).order("created_at", desc=True).execute()
    ads = res.data
    if not ads:
        return safe_send_message(m.chat.id, "📭 У вас нет объявлений на этом сервере.", reply_markup=kb_main_menu(uid))
    # Показываем по одному с кнопками
    for ad in ads[:10]:
        status_map = {"pending":"⏳ На модерации", "approved":"✅ Опубликовано", "deleted":"🗑 Удалено"}
        status_text = status_map.get(ad["status"], ad["status"])
        caption = f"#{ad['id']} <b>{ad['item_name']}</b>\n💰 {format_price(ad['price'])}\n{status_text}\n{ad['description'][:300]}..."
        markup = types.InlineKeyboardMarkup(row_width=2)
        if ad["status"] == "pending":
            markup.add(types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_ad_{ad['id']}"))
            markup.add(types.InlineKeyboardButton("🗑 Удалить", callback_data=f"del_ad_{ad['id']}"))
        elif ad["status"] == "approved":
            markup.add(types.InlineKeyboardButton("🗑 Удалить", callback_data=f"del_ad_{ad['id']}"))
        else:
            markup.add(types.InlineKeyboardButton("Удалено", callback_data="noop"))
        images = json.loads(ad["images"]) if ad["images"] else []
        if images:
            safe_send_photo(m.chat.id, images[0], caption, reply_markup=markup)
        else:
            safe_send_message(m.chat.id, caption, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_ad_"))
def cb_delete_ad(call):
    uid = call.from_user.id
    pid = call.data.replace("del_ad_", "")
    # Проверяем, что объявление принадлежит пользователю
    user_uuid = get_user_uuid_by_telegram_id(uid)
    if not user_uuid:
        return bot.answer_callback_query(call.id, "Ошибка", show_alert=True)
    res = supabase.table("ads").select("author_id").eq("id", pid).execute()
    if not res.data or res.data[0]["author_id"] != user_uuid:
        return bot.answer_callback_query(call.id, "⛔ Не ваше объявление.", show_alert=True)
    supabase.table("ads").update({"status": "deleted"}).eq("id", pid).execute()
    bot.answer_callback_query(call.id, "🗑 Объявление удалено.")
    bot.edit_message_caption(call.message.caption + "\n\n🗑 Удалено вами.", call.message.chat.id, call.message.message_id, reply_markup=None)

@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_ad_"))
def cb_edit_ad(call):
    uid = call.from_user.id
    pid = call.data.replace("edit_ad_", "")
    user_uuid = get_user_uuid_by_telegram_id(uid)
    if not user_uuid:
        return bot.answer_callback_query(call.id, "Ошибка", show_alert=True)
    res = supabase.table("ads").select("author_id, status").eq("id", pid).execute()
    if not res.data or res.data[0]["author_id"] != user_uuid:
        return bot.answer_callback_query(call.id, "⛔ Не ваше объявление.", show_alert=True)
    if res.data[0]["status"] != "pending":
        return bot.answer_callback_query(call.id, "⛔ Можно редактировать только на модерации.", show_alert=True)
    # Начинаем процесс редактирования (можно упрощённо — пересоздать)
    # Удаляем старое, создаём новое с теми же данными
    # Для простоты — предлагаем удалить и создать заново
    supabase.table("ads").update({"status": "deleted"}).eq("id", pid).execute()
    bot.answer_callback_query(call.id, "✅ Старое объявление удалено. Создайте новое через меню.")
    safe_send_message(call.message.chat.id, "Вы можете подать новое объявление через «📤 Продать товар» или «📥 Скупить товар».")

# =========================================================
# 13. ПОИСК ТОВАРА (с фильтрами)
# =========================================================
@bot.message_handler(func=lambda m: m.text == "🔍 Найти товар в базе")
def start_search(m):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔍 Поиск по ключевому слову", callback_data="search_keyword"),
        types.InlineKeyboardButton("📂 По категориям", callback_data="search_categories")
    )
    safe_send_message(m.chat.id, "🔍 Выберите способ поиска:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["search_keyword", "search_categories"])
def cb_search_choose(c):
    if c.data == "search_keyword":
        bot.answer_callback_query(c.id)
        update_state(c.from_user.id, search_step="keyword")
        safe_send_message(c.message.chat.id, "🔍 Введите ключевое слово для поиска (до 50 символов):", reply_markup=kb_cancel())
    else:
        bot.answer_callback_query(c.id)
        markup = kb_search_categories()
        safe_send_message(c.message.chat.id, "📂 Выберите категорию:", reply_markup=markup)

@bot.message_handler(func=lambda m: get_state(m.from_user.id).get("search_step") == "keyword")
def process_search_keyword(m):
    uid = m.from_user.id
    keyword = m.text.strip()
    clear_state(uid)
    if len(keyword) < 2:
        return safe_send_message(m.chat.id, "⚠️ Слишком короткий запрос.")
    srv = get_user_server(uid)
    # Ищем в описании и названии
    res = supabase.table("ads").select("*").eq("server", srv).eq("status", "approved").ilike("item_name", f"%{keyword}%").execute()
    ads = res.data
    if not ads:
        res2 = supabase.table("ads").select("*").eq("server", srv).eq("status", "approved").ilike("description", f"%{keyword}%").execute()
        ads = res2.data
    if not ads:
        return safe_send_message(m.chat.id, "🔍 Ничего не найдено.", reply_markup=kb_main_menu(uid))
    # Показываем первые 5
    for ad in ads[:5]:
        caption = f"#{ad['id']} <b>{ad['item_name']}</b>\n💰 {format_price(ad['price'])}\n{ad['description'][:300]}..."
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📩 Связаться с автором", callback_data=f"contact_{ad['author_id']}_{ad['id']}"))
        images = json.loads(ad["images"]) if ad["images"] else []
        if images:
            safe_send_photo(m.chat.id, images[0], caption, reply_markup=markup)
        else:
            safe_send_message(m.chat.id, caption, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("search_cat_"))
def cb_search_category(c):
    cat = c.data.replace("search_cat_", "")
    uid = c.from_user.id
    srv = get_user_server(uid)
    res = supabase.table("ads").select("*").eq("server", srv).eq("status", "approved").eq("category", cat).execute()
    ads = res.data
    if not ads:
        return bot.answer_callback_query(c.id, "В этой категории нет объявлений.", show_alert=True)
    for ad in ads[:5]:
        caption = f"#{ad['id']} <b>{ad['item_name']}</b>\n💰 {format_price(ad['price'])}\n{ad['description'][:300]}..."
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📩 Связаться", callback_data=f"contact_{ad['author_id']}_{ad['id']}"))
        images = json.loads(ad["images"]) if ad["images"] else []
        if images:
            safe_send_photo(c.message.chat.id, images[0], caption, reply_markup=markup)
        else:
            safe_send_message(c.message.chat.id, caption, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "search_all")
def cb_search_all(c):
    uid = c.from_user.id
    srv = get_user_server(uid)
    res = supabase.table("ads").select("*").eq("server", srv).eq("status", "approved").order("created_at", desc=True).limit(10).execute()
    ads = res.data
    if not ads:
        return bot.answer_callback_query(c.id, "Нет объявлений.", show_alert=True)
    for ad in ads:
        caption = f"#{ad['id']} <b>{ad['item_name']}</b>\n💰 {format_price(ad['price'])}\n{ad['description'][:300]}..."
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📩 Связаться", callback_data=f"contact_{ad['author_id']}_{ad['id']}"))
        images = json.loads(ad["images"]) if ad["images"] else []
        if images:
            safe_send_photo(c.message.chat.id, images[0], caption, reply_markup=markup)
        else:
            safe_send_message(c.message.chat.id, caption, reply_markup=markup)

# =========================================================
# 14. ЧАТ МЕЖДУ ПОЛЬЗОВАТЕЛЯМИ (связь с автором)
# =========================================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("contact_"))
def cb_contact_author(c):
    parts = c.data.split("_")
    author_uuid = parts[1]
    ad_id = parts[2]
    # Получаем telegram_id автора
    res = supabase.table("app_users").select("telegram_id").eq("id", author_uuid).execute()
    if not res.data:
        return bot.answer_callback_query(c.id, "Автор не найден.", show_alert=True)
    author_tg = res.data[0]["telegram_id"]
    if not author_tg:
        return bot.answer_callback_query(c.id, "У автора нет Telegram ID.", show_alert=True)
    # Создаём сессию чата
    uid = c.from_user.id
    session_id = f"{uid}_{author_tg}_{ad_id}"
    user_chat_sessions[session_id] = {"buyer": uid, "seller": author_tg, "ad_id": ad_id}
    # Отправляем сообщение автору
    safe_send_message(author_tg, f"🔔 Пользователь @{c.from_user.username or str(uid)} хочет связаться с вами по объявлению #{ad_id}.\nВы можете ответить ему в этом чате. (Ваши сообщения будут пересылаться ему, а его — вам.)")
    safe_send_message(uid, f"💬 Вы начали диалог с автором объявления #{ad_id}. Пишите в этот чат, и ваши сообщения будут пересылаться.")
    bot.answer_callback_query(c.id, "Чат открыт! Проверьте личные сообщения.")

# Перехватываем сообщения для пересылки между участниками чата
@bot.message_handler(func=lambda m: m.chat.type == "private" and m.text and not m.text.startswith("/") and not any(key in m.text for key in ["📤", "📥", "👥", "💎", "🔍", "🌐", "⬅️", "❌"]))
def forward_chat_messages(m):
    uid = m.from_user.id
    # Проверяем, есть ли активная сессия
    for session_id, data in list(user_chat_sessions.items()):
        if data["buyer"] == uid or data["seller"] == uid:
            other = data["seller"] if data["buyer"] == uid else data["buyer"]
            # Пересылаем сообщение другому участнику
            try:
                bot.send_message(other, f"💬 Сообщение от @{m.from_user.username or str(uid)}:\n{m.text}")
                # Сохраняем в историю
                supabase.table("chat_logs_history").insert({
                    "sender_id": uid,
                    "receiver_id": other,
                    "text": m.text,
                    "timestamp": time.time()
                }).execute()
            except Exception as e:
                safe_send_message(uid, f"⚠️ Не удалось отправить сообщение: {e}")
            return
    # Если нет активного чата, игнорируем

# =========================================================
# 15. ФОНОВЫЕ ЗАДАЧИ (удаление просрочек, сгорание бонусов)
# =========================================================
def background_jobs():
    while True:
        try:
            # Удаляем просроченные объявления
            now = datetime.now(timezone.utc).isoformat()
            res = supabase.table("ads").select("id, author_id, expires_at").eq("status", "approved").lt("expires_at", now).execute()
            for ad in res.data:
                supabase.table("ads").update({"status": "deleted"}).eq("id", ad["id"]).execute()
                # Уведомляем автора
                author_tg = supabase.table("app_users").select("telegram_id").eq("id", ad["author_id"]).execute()
                if author_tg.data and author_tg.data[0]["telegram_id"]:
                    safe_send_message(author_tg.data[0]["telegram_id"], f"⏰ Ваше объявление #{ad['id']} истекло и удалено.")
            # Сгорание бонусных VIP-объявлений (раз в сутки убираем по 1)
            # Эту логику вынесем в отдельную функцию, вызываемую раз в день
        except Exception as e:
            logger.error(f"Ошибка в background_jobs: {e}")
        time.sleep(3600)  # раз в час

def daily_bonus_decay():
    # Уменьшаем счётчик бонусов у всех пользователей на 1, если >0
    try:
        res = supabase.table("user_bonuses").select("user_id, vip_ads_count").execute()
        for row in res.data:
            if row["vip_ads_count"] > 0:
                new_val = row["vip_ads_count"] - 1
                supabase.table("user_bonuses").update({"vip_ads_count": new_val}).eq("user_id", row["user_id"]).execute()
    except Exception as e:
        logger.error(f"Ошибка daily_bonus_decay: {e}")

def schedule_daily():
    # Запускаем ежедневно в 00:00 МСК
    schedule.every().day.at("00:00").do(daily_bonus_decay)
    while True:
        schedule.run_pending()
        time.sleep(60)

# Запускаем фоновые потоки
threading.Thread(target=background_jobs, daemon=True).start()
threading.Thread(target=schedule_daily, daemon=True).start()

# =========================================================
# 16. ЗАПУСК FLASK + БОТА
# =========================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!", 200

@app.route('/health')
def health():
    # Проверка соединения с Supabase
    try:
        supabase.table("app_users").select("count", count="exact").limit(1).execute()
        return "OK", 200
    except:
        return "DB error", 500

def run_bot():
    logger.info("Запуск бота (версия 2.0)")
    try:
        bot.remove_webhook()
    except:
        pass
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=10)
        except ApiTelegramException as e:
            if e.result_json and e.result_json.get('error_code') == 409:
                logger.error("Конфликт 409 — другой экземпляр бота. Выход.")
                os._exit(0)
            else:
                logger.error(f"Polling error: {e}")
                time.sleep(5)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Запуск Flask на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
