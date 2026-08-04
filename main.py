import os
import time
import threading
import logging
import sqlite3
import re
import html
import requests
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

# ==========================================
# ЛОГИРОВАНИЕ И КОНФИГУРАЦИЯ
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN = "8916669266:AAFall7GhTxs_ZAlMr4_d4W_XMZnunkY2NA"
YT_CHANNEL_URL = "https://youtube.com/@bounty_squad31"

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=20)

OWNER_USERNAME = "bounqy"
ADMIN_USERNAMES = {"bounqy31", "bounqy"}

DB_NAME = "smi_bot.db"
db_lock = threading.Lock()
state_lock = threading.Lock()

ADS_PER_PAGE = 5  

SERVERS = [
    "🔥 Phoenix", "🌴 Tucson", "🌵 Scottdale", "⚜️ Chandler", "❄️ Brainburg", "🌊 Yuma",
    "✨ Saint-Rose", "🏛 Mesa", "❤️ Red-Rock", "🍀 Surprise", "⚡️ Prescott", "🌲 Glendale",
    "👑 Kingman", "⚓️ Winslow", "🌴 Payson", "💎 Gilbert", "🔥 Show-Low", "🌴 Casa-Grande",
    "📜 Page", "☀️ Sun-City", "👑 Queen-Creek", "🌵 Sedona", "🎄 Holiday", "🍀 Wednesday",
    "⚡️ Yava", "🌌 Faraway", "🎁 Christmas", "🐝 Bumble Bee", "🪞 Mirage", "💖 Love",
    "📱 Mobile I", "📱 Mobile II", "📱 Mobile III"
]

CATEGORIES = [
    "💍 Аксессуары и вещи",
    "🚗 Транспорт и тюнинг",
    "👕 Скины и охранники",
    "🏠 Недвижимость и бизнесы",
    "📦 Ресурсы и материалы"
]

SYSTEM_NAV_BUTTONS = [
    "🔍 Найти товар в базе", "❤️ Сохраненные", "🔔 Уведомления о поиске",
    "📋 Мои публикации", "📊 Анализ цен на сервере", "📖 Справка и правила",
    "📤 Продать товар", "📥 Скупить товар", "💱 Курс VC и калькулятор", 
    "💎 VIP-статус", "🌐 Сменить игровой сервер", "👑 Админ-панель", 
    "📝 Стать редактором / админом", "❌ Отменить действие"
] + CATEGORIES + SERVERS

BAD_WORDS = [
    "хуй", "пизд", "еб", "бля", "сук", "залуп", "мраз", "ебан", "долбоеб", 
    "samp-rp", "advance", "Arizona V", "Diamond", "продажа вирт", "продам вирты"
]

# ==========================================
# ПОТОКОБЕЗОПАСНОЕ УПРАВЛЕНИЕ СОСТОЯНИЯМИ
# ==========================================
user_states = {}

def get_state(uid: int) -> dict:
    with state_lock:
        return user_states.get(uid, {}).copy()

def set_state(uid: int, data: dict):
    with state_lock:
        srv = user_states.get(uid, {}).get("server")
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
        if uid in user_states:
            srv = user_states[uid].get("server")
            user_states[uid] = {"server": srv} if srv else {}

# ==========================================
# БЕЗОПАСНАЯ ОТПРАВКА СООБЩЕНИЙ (HTML)
# ==========================================
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

# ==========================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
# ==========================================
def init_db():
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                server TEXT,
                category TEXT,
                text TEXT,
                photo TEXT,
                is_vip INTEGER,
                last_updated REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                server TEXT,
                category TEXT,
                text TEXT,
                photo TEXT,
                is_vip INTEGER,
                editing_by INTEGER,
                editing_since REAL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_buy_ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                server TEXT,
                category TEXT,
                text TEXT,
                photo TEXT,
                is_vip INTEGER,
                last_updated REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_buy_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                server TEXT,
                category TEXT,
                text TEXT,
                photo TEXT,
                is_vip INTEGER,
                editing_by INTEGER,
                editing_since REAL
            )
        ''')

        for tbl in ["active_ads", "pending_posts", "active_buy_ads", "pending_buy_posts"]:
            try:
                cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN is_edited INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('vc_rate', '95000')")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bans (
                target TEXT PRIMARY KEY,
                is_id INTEGER
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS editor_stats (
                username TEXT PRIMARY KEY,
                count INTEGER
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_data (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                last_ad_time REAL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_dialogs (
                buyer_id INTEGER,
                seller_id INTEGER,
                ad_id INTEGER,
                is_active INTEGER,
                PRIMARY KEY (buyer_id, seller_id, ad_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER,
                ad_id INTEGER,
                PRIMARY KEY (user_id, ad_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keyword_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                server TEXT,
                keyword TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seller_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER,
                buyer_id INTEGER,
                rating INTEGER,
                comment TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS premium_users (
                user_id INTEGER PRIMARY KEY,
                expires_at REAL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_chats (
                chat_id INTEGER PRIMARY KEY
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_apps (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                application_text TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS approved_admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT
            )
        ''')

        conn.commit()

init_db()

# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ И ВРЕМЯ ПО МСК
# ==========================================
def get_msk_time():
    try:
        return datetime.now(ZoneInfo("Europe/Moscow"))
    except Exception:
        return datetime.now()

def check_working_hours() -> bool:
    now_time = get_msk_time().time()
    return dtime(8, 0, 1) <= now_time <= dtime(22, 0, 1)

def background_cleanup_ads():
    last_cleaned_date = None
    while True:
        time.sleep(30)
        try:
            now_msk = get_msk_time()
            current_time = now_msk.time()
            current_date = now_msk.date()
            
            if current_time >= dtime(22, 0, 1) or current_time < dtime(8, 0, 1):
                if last_cleaned_date != current_date:
                    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
                        cur = conn.cursor()
                        cur.execute("DELETE FROM active_ads")
                        cur.execute("DELETE FROM active_buy_ads")
                        cur.execute("DELETE FROM pending_posts")
                        cur.execute("DELETE FROM pending_buy_posts")
                        conn.commit()
                    logger.info(f"Ночная очистка объявлений выполнена в {current_time} МСК.")
                    last_cleaned_date = current_date
        except Exception as e:
            logger.error(f"Ошибка фоновой ночной очистки: {e}")

threading.Thread(target=background_cleanup_ads, daemon=True).start()

# ==========================================
# ФОНОВАЯ ПРОВЕРКА YOUTUBE СТРИМОВ
# ==========================================
def background_youtube_stream_checker():
    last_live_id = None
    time.sleep(15)
    while True:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(f"{YT_CHANNEL_URL}/live", headers=headers, allow_redirects=True, timeout=15)
            final_url = resp.url
            
            if "/watch?v=" in final_url:
                video_id = final_url.split("v=")[1].split("&")[0]
                if video_id != last_live_id:
                    last_live_id = video_id
                    admin_chats = get_admin_chat_ids()
                    notif_text = (
                        "🔴 <b>ВНИМАНИЕ! СТРИМ НА YOUTUBE НАЧАЛСЯ!</b> 🎥\n\n"
                        "📡 Канал: <b>Bounty Squad</b>\n"
                        f"🔗 Ссылка: https://www.youtube.com/watch?v={video_id}"
                    )
                    for chat_id in admin_chats:
                        try:
                            safe_send_message(chat_id, notif_text)
                        except Exception as e:
                            logger.error(f"Не удалось отправить уведомление о стриме в чат {chat_id}: {e}")
            else:
                last_live_id = None
        except Exception as e:
            logger.error(f"Ошибка в фоновой проверке стримов YouTube: {e}")
        
        time.sleep(180)

threading.Thread(target=background_youtube_stream_checker, daemon=True).start()

def get_vc_rate() -> float:
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM bot_settings WHERE key = 'vc_rate'")
        row = cur.fetchone()
        return float(row[0]) if row else 95000.0

def set_vc_rate(rate: float):
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('vc_rate', ?)", (str(rate),))
        conn.commit()

def register_admin_chat(chat_id: int):
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO admin_chats (chat_id) VALUES (?)", (chat_id,))
        conn.commit()

def get_admin_chat_ids():
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT chat_id FROM admin_chats")
        return [row[0] for row in cur.fetchall()]

def get_all_admin_ids():
    admin_ids = set(get_admin_chat_ids())
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM approved_admins")
        for row in cur.fetchall():
            admin_ids.add(row[0])
    return list(admin_ids)

def is_user_premium(user_id: int) -> bool:
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT expires_at FROM premium_users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
    return bool(row and row[0] > time.time())

def get_seller_rating_info(seller_id: int) -> str:
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT AVG(rating), COUNT(rating) FROM seller_reviews WHERE seller_id = ?", (seller_id,))
        row = cur.fetchone()
    if not row or row[1] == 0:
        return "⭐ Нет оценок (0)"
    return f"⭐ {row[0]:.1f} / 5 (Отзывов: {row[1]})"

def check_auto_moderation(text: str) -> bool:
    if not text:
        return True
    lower_text = text.lower()
    for word in BAD_WORDS:
        if word in lower_text:
            return False
    return True

def get_user_last_ad_time(user_id):
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT last_ad_time FROM user_data WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else 0

def set_user_last_ad_time(user_id, t):
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO user_data (user_id, last_ad_time) VALUES (?, ?)", (user_id, t))
        conn.commit()

def register_user(user_id, username=None):
    uname = username.lstrip('@').lower() if username else None
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO user_data (user_id, username, last_ad_time) VALUES (?, ?, 0)", (user_id, uname))
        if uname:
            cur.execute("UPDATE user_data SET username = ? WHERE user_id = ?", (uname, user_id))
        conn.commit()

def is_banned(user) -> bool:
    if not user:
        return False
    uname = user.username.lower().lstrip('@') if user.username else ""
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM bans WHERE (is_id = 1 AND target = ?) OR (is_id = 0 AND target = ?)", 
                    (str(user.id), uname))
        res = cur.fetchone()
    return bool(res)

def is_owner(user) -> bool:
    return bool(user and user.username and user.username.lower() == OWNER_USERNAME.lower())

def is_admin_or_owner(user) -> bool:
    if not user: 
        return False
    if is_owner(user): 
        return True
    uname = user.username.lower().lstrip('@') if user.username else ""
    if uname in ADMIN_USERNAMES:
        return True
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM approved_admins WHERE user_id = ? OR LOWER(username) = ?", (user.id, uname))
        if cur.fetchone():
            return True
    return False

def is_admin_or_owner_id(user_id: int) -> bool:
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM approved_admins WHERE user_id = ?", (user_id,))
        if cur.fetchone():
            return True
        cur.execute("SELECT username FROM user_data WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if row and row[0] and row[0].lower() == OWNER_USERNAME.lower():
            return True
        cur.execute("SELECT 1 FROM admin_chats WHERE chat_id = ?", (user_id,))
        if cur.fetchone():
            return True
    return False

def verify_admin_callback(call) -> bool:
    if not is_admin_or_owner(call.from_user):
        try:
            bot.answer_callback_query(call.id, "⛔ Нет доступа к функциям СМИ!", show_alert=True)
        except Exception:
            pass
        return False
    return True

def clean_server_name(server: str) -> str:
    return server.split(' ', 1)[-1] if ' ' in server else server

def format_smi_post(server: str, category: str, text: str, player_username: str, editor_username: str, is_vip: bool = False, user_id: int = 0, is_buy: bool = False) -> str:
    clean_srv = html.escape(clean_server_name(server))
    cat_esc = html.escape(category)
    text_esc = html.escape(text)
    
    is_prem = is_user_premium(user_id) if user_id else False
    
    if is_vip:
        player_contact = "🛡️ <i>[Контакт скрыт по желанию VIP]</i>"
        vip_header = "👑 <b>[VIP ОБЪЯВЛЕНИЕ]</b>\n"
    else:
        p_uname = html.escape(player_username) if player_username and player_username != "Без юзернейма" else ""
        player_contact = f"@{p_uname}" if p_uname else "Не указан"
        vip_header = ""

    ed_uname = html.escape(editor_username) if editor_username else "СМИ"
    editor_contact = f"@{ed_uname}"
    prem_icon = "💎 " if is_prem else ""
    rating_str = get_seller_rating_info(user_id) if user_id else ""
    ad_type_label = "📥 <b>[СКУПКА]</b>" if is_buy else "📤 <b>[ПРОДАЖА]</b>"

    return (
        f"{vip_header}"
        f"📰 | <b>[СМИ {clean_srv}] Объявление:</b> {ad_type_label} {prem_icon}\n"
        f"📞 <b>Контакт:</b> {player_contact} | {rating_str}\n\n"
        f"{text_esc}\n\n"
        f"📂 <b>Раздел:</b> {cat_esc}\n"
        f"👨‍💻 <b>Отредактировал:</b> {editor_contact}"
    )

# ==========================================
# КЛАВИАТУРЫ
# ==========================================
def kb_servers():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for i in range(0, len(SERVERS), 2): 
        m.add(*[types.KeyboardButton(s) for s in SERVERS[i:i+2]])
    m.add(types.KeyboardButton("📖 Справка и правила"), types.KeyboardButton("📤 Продать товар"))
    m.add(types.KeyboardButton("📥 Скупить товар"), types.KeyboardButton("💱 Курс VC и калькулятор"))
    m.add(types.KeyboardButton("💎 VIP-статус"), types.KeyboardButton("👑 Админ-панель"))
    m.add(types.KeyboardButton("📝 Стать редактором / админом"))
    return m

def kb_main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("🌐 Сменить игровой сервер")
    m.add("💍 Аксессуары и вещи", "🚗 Транспорт и тюнинг")
    m.add("👕 Скины и охранники", "🏠 Недвижимость и бизнесы")
    m.add("📦 Ресурсы и материалы")
    m.add("📤 Продать товар", "📥 Скупить товар")
    m.add("💱 Курс VC и калькулятор")
    m.add("🔍 Найти товар в базе", "❤️ Сохраненные")
    m.add("🔔 Уведомления о поиске", "📋 Мои публикации")
    m.add("📊 Анализ цен на сервере")
    m.add("💎 VIP-статус")
    m.add("👑 Админ-панель", "📝 Стать редактором / админом")
    return m

def kb_cancel():
    return types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("❌ Отменить действие"))

def ikb_chat_controls(aid: int):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🛑 Завершить диалог", callback_data=f"stop_chat_{aid}"),
        types.InlineKeyboardButton("🔄 Возобновить / Начать заново", callback_data=f"resume_chat_{aid}")
    )
    return markup

def ikb_ad_actions(aid: int, is_fav: bool = False, user_id: int = 0, is_buy: bool = False):
    markup = types.InlineKeyboardMarkup(row_width=2)
    fav_text = "❌ Убрать из избранного" if is_fav else "❤️ В избранное"
    markup.add(
        types.InlineKeyboardButton("✉️ Написать автору", callback_data=f"contact_seller_{aid}"),
        types.InlineKeyboardButton(fav_text, callback_data=f"fav_toggle_{aid}")
    )
    if user_id and is_admin_or_owner_id(user_id):
        del_prefix = "admin_del_buy_" if is_buy else "admin_del_"
        markup.add(types.InlineKeyboardButton("🗑 Удалить (Админ)", callback_data=f"{del_prefix}{aid}"))
    return markup

# ==========================================
# ПЕРЕХВАТЧИК ДЛЯ ЗАБЛОКИРОВАННЫХ ПОЛЬЗОВАТЕЛЕЙ
# ==========================================
@bot.message_handler(func=lambda m: is_banned(m.from_user))
def blocked_user_message(m):
    safe_send_message(
        m.chat.id, 
        "⛔ <b>Вы заблокированы в системе модерации.</b> Ваши кнопки отключены, и доступ к функциям бота ограничен.", 
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.callback_query_handler(func=lambda c: is_banned(c.from_user))
def blocked_user_callback(c):
    try:
        bot.answer_callback_query(c.id, "⛔ Вы заблокированы в системе и не можете использовать бота!", show_alert=True)
    except Exception:
        pass

# ==========================================
# УМНЫЙ МИДДЛВЕЙР НАВИГАЦИИ
# ==========================================
def should_override_nav(msg):
    if not msg.text: 
        return False
        
    uid = msg.from_user.id
    st = get_state(uid)

    if msg.text == "❌ Отменить действие" or msg.text.startswith('/'):
        return True

    if "admin_editing_pid" in st or "admin_editing_buy_pid" in st or "admin_editing_active_aid" in st or "applying_admin" in st or "vc_setting_rate" in st or "vc_calc_step" in st or "vc_conv_input" in st or "admin_action" in st or "editing_active_ad_id" in st:
        return False
        
    if "posting_ad" in st or "posting_buy_ad" in st:
        p_key = "posting_ad" if "posting_ad" in st else "posting_buy_ad"
        step = st[p_key].get("step")
        if step == "category" and msg.text in CATEGORIES:
            return False

    return msg.text in SYSTEM_NAV_BUTTONS

@bot.message_handler(func=should_override_nav)
def handle_navigation_override(m):
    clear_state(m.from_user.id)
    
    if m.text == '/start':
        cmd_start(m)
    elif m.text == '/help':
        cmd_help(m)
    elif m.text == "🌐 Сменить игровой сервер":
        change_server(m)
    elif m.text == "📖 Справка и правила":
        how_bot_works(m)
    elif m.text == "💎 VIP-статус":
        info_premium(m)
    elif m.text == "📊 Анализ цен на сервере":
        show_average_prices(m)
    elif m.text == "📤 Продать товар":
        start_add_ad(m)
    elif m.text == "📥 Скупить товар":
        start_add_buy_ad(m)
    elif m.text == "💱 Курс VC и калькулятор":
        show_vc_menu(m)
    elif m.text == "❌ Отменить действие":
        cancel_action(m)
    elif m.text == "📋 Мои публикации":
        show_my_ads(m)
    elif m.text == "❤️ Сохраненные":
        show_favorites(m)
    elif m.text == "🔍 Найти товар в базе":
        start_search(m)
    elif m.text == "🔔 Уведомления о поиске":
        manage_subscriptions(m)
    elif m.text == "👑 Админ-панель":
        admin_panel(m)
    elif m.text == "📝 Стать редактором / админом":
        start_admin_application(m)
    elif m.text in CATEGORIES:
        if get_state(m.from_user.id).get("viewing_buy_categories"):
            show_buy_ads_category(m)
        else:
            show_ads_category(m)
    elif m.text in SERVERS:
        select_srv(m)

# ==========================================
# ОСНОВНЫЕ КОМАНДЫ
# ==========================================
@bot.message_handler(commands=['start'])
def cmd_start(m):
    register_user(m.from_user.id, m.from_user.username)
    
    if is_banned(m.from_user):
        return safe_send_message(m.chat.id, "⛔ Вы заблокированы в системе модерации.", reply_markup=types.ReplyKeyboardRemove())
        
    if is_admin_or_owner(m.from_user):
        register_admin_chat(m.chat.id)
    
    caption_text = (
        "🌟 <b>Привет! Обратите внимание: мы не официальный бот</b>, а независимый помощник для игроков Arizona RP. "
        "Мы помогаем игрокам находить аксессуары, транспорт, недвижимость и другие ценные вещи, а также следить за экономикой и курсами.\n\n"
        "🔒 <b>Безопасность:</b> Мы <b>никогда</b> не просим пароли от игровых аккаунтов или личные данные!\n\n"
        "⏱ <b>Режим работы радиоцентра:</b> ежедневно с <b>08:00:01 до 22:00:01 МСК</b>.\n\n"
        "👇 <b>Для начала работы выберите свой игровой сервер ниже:</b>"
    )
    safe_send_message(m.chat.id, caption_text, reply_markup=kb_servers())

@bot.message_handler(commands=['help'])
def cmd_help(m):
    help_text = (
        "🛠 <b>Помощь, правила и расширенный FAQ</b>\n\n"
        "❓ <b>1. Как подать объявление о продаже или скупке?</b>\n"
        "💡 <i>Выберите нужный игровой сервер в главном меню -> Нажмите «📤 Продать товар» или «📥 Скупить товар» -> Выберите категорию -> Введите товар, цену и условия -> Отправьте на модерацию редакторам.</i>\n\n"
        "❓ <b>2. Сколько времени модераторы проверяют заявки?</b>\n"
        "💡 <i>Обычно проверка занимает от силы пару минут, если редактора находятся в сети. Вы получите уведомление в чат сразу после публикации или отклонения объявления.</i>\n\n"
        "❓ <b>3. Как изменить или удалить уже опубликованное объявление?</b>\n"
        "💡 <i>В личном кабинете или разделе управления объявлениями вы можете в любой момент снять товар с публикации, изменить цену или обновить описание.</i>\n\n"
        "❓ <b>4. Как работает калькулятор Vice City и конвертер валют?</b>\n"
        "💡 <i>В разделе «💱 Курс VC и калькулятор» можно мгновенно переводить вирты в VC-баксы по актуальному курсу, а также рассчитывать выгоду перелетов и чистую прибыль с учетом комиссий.</i>\n\n"
        "❓ <b>5. Как безопасно связаться с продавцом или покупателем?</b>\n"
        "💡 <i>Под карточкой каждого активного объявления есть кнопка «✉️ Написать автору». Она открывает защищенный внутренний чат для обсуждения всех деталей сделки.</i>\n\n"
        "❓ <b>6. Каковы главные правила подачи объявлений и модерации?</b>\n"
        "💡 <i>Запрещено указывать нереалистичные цены, использовать нецензурную лексику, рекламировать сторонние ресурсы или нарушать правила проекта. Нарушители могут получить бан в боте.</i>\n\n"
        "❓ <b>7. Что делать, если мое объявление отклонили?</b>\n"
        "💡 <i>В системном уведомлении об отклонении всегда указана причина. Чаще всего это опечатки, отсутствие конкретики или нарушение правил. Просто исправьте текст и отправьте его повторно.</i>\n\n"
        "❓ <b>8. Куда обращаться при обнаружении багов или технических неполадок?</b>\n"
        "💡 <i>Если бот завис, работает некорректно или вы нашли ошибку, обязательно напишите об этом в наше официальное сообщество ВКонтакте: <b>@bountyarz</b>. Наша команда оперативно всё проверит!</i>\n\n"
        "⏱ <b>Дополнительная информация:</b> Радиоцентр и редакция работают ежедневно с <b>08:00:01 до 22:00:01 МСК</b>."
    )
    safe_send_message(m.chat.id, help_text, reply_markup=kb_main_menu())

def change_server(m):
    safe_send_message(m.chat.id, "👇 Выберите новый игровой сервер:", reply_markup=kb_servers())

def select_srv(m):
    srv = m.text
    update_state(m.from_user.id, server=srv)
    safe_send_message(m.chat.id, f"✅ Игровой сервер установлен: <b>{html.escape(srv)}</b>", reply_markup=kb_main_menu())

def how_bot_works(m):
    text = (
        "📖 <b>Справочник: Как работает бот и радиоцентр</b>\n\n"
        "1. <b>Подача объявления:</b> Выбирается тип (продажа/скупка), сервер, категория и текст.\n"
        "2. <b>Проверка редакторами:</b> Редакторы проверяют материалы с 08:00:01 до 22:00:01 МСК.\n"
        "3. <b>Публикация:</b> Одобренное объявление уходит в ленту.\n"
        "4. <b>Инструменты VC:</b> Полноценный курс, конвертер и калькулятор прибыли для перекупщиков."
    )
    safe_send_message(m.chat.id, text)

# ==========================================
# ПОДАЧА ЗАЯВКИ НА ПОСТ РЕДАКТОРА (ARIZONA RP STYLE)
# ==========================================
def start_admin_application(m):
    uid = m.from_user.id
    if is_admin_or_owner(m.from_user):
        return safe_send_message(m.chat.id, "👑 Вы уже являетесь администратором / владельцем бота!", reply_markup=kb_main_menu())
    
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM admin_apps WHERE user_id = ?", (uid,))
        if cur.fetchone():
            return safe_send_message(m.chat.id, "⏳ Ваша заявка на пост редактора уже находится на рассмотрении руководства.", reply_markup=kb_main_menu())

    update_state(uid, applying_admin="waiting_text")
    safe_send_message(
        m.chat.id,
        "📝 <b>Электронное заявление на пост редактора СМИ (Arizona RP Style)</b>\n\n"
        "Пожалуйста, заполните заявку в свободной форме. Укажите:\n"
        "• Ваш игровой ник и сервер\n"
        "• Ваш возраст и часовой пояс\n"
        "• Опыт работы в СМИ / почему хотите занять этот пост\n\n"
        "<i>Отправьте ваш текст ответным сообщением в чат:</i>",
        reply_markup=kb_cancel()
    )

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("applying_admin") == "waiting_text")
def process_admin_application(m):
    uid = m.from_user.id
    uname = m.from_user.username or "Без юзернейма"
    app_text = m.text.strip()
    clear_state(uid)

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO admin_apps (user_id, username, application_text) VALUES (?, ?, ?)", (uid, uname, app_text))
        conn.commit()

    safe_send_message(m.chat.id, "✅ Ваша заявка на пост редактора успешно отправлена владельцу @bounqy и редакции! Ожидайте рассмотрения.", reply_markup=kb_main_menu())

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Принять (Назначить админом)", callback_data=f"accept_admin_app_{uid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_admin_app_{uid}")
    )

    notif_text = (
        "📝 <b>Новая заявка на пост редактора / администратора!</b>\n\n"
        f"👤 Кандидат: @{html.escape(uname)} (ID: <code>{uid}</code>)\n\n"
        f"📄 <b>Текст заявки:</b>\n{html.escape(app_text)}"
    )

    admin_recipients = get_all_admin_ids()
    for chat_id in admin_recipients:
        try:
            safe_send_message(chat_id, notif_text, reply_markup=markup)
        except Exception as e:
            logger.error(f"Не удалось отправить заявку админу {chat_id}: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("accept_admin_app_") or c.data.startswith("reject_admin_app_"))
def cb_handle_admin_app(call):
    if not is_owner(call.from_user) and not is_admin_or_owner(call.from_user):
        try:
            bot.answer_callback_query(call.id, "⛔ У вас нет прав для рассмотрения заявок!", show_alert=True)
        except Exception:
            pass
        return

    is_accept = "accept_admin_app_" in call.data
    prefix = "accept_admin_app_" if is_accept else "reject_admin_app_"
    target_uid = int(call.data.replace(prefix, ""))

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT username FROM admin_apps WHERE user_id = ?", (target_uid,))
        row = cur.fetchone()
        target_uname = row[0] if row else "user"
        cur.execute("DELETE FROM admin_apps WHERE user_id = ?", (target_uid,))
        
        if is_accept:
            cur.execute("INSERT OR IGNORE INTO approved_admins (user_id, username) VALUES (?, ?)", (target_uid, target_uname))
        conn.commit()

    try:
        bot.answer_callback_query(call.id, "✅ Заявка принята!" if is_accept else "❌ Заявка отклонена!")
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
    except Exception:
        pass

    if is_accept:
        safe_send_message(target_uid, "🎉 <b>Поздравляем! Ваша заявка на пост редактора одобрена владелицем @bounqy!</b> Теперь вам доступны функции модерации и админ-панель.", reply_markup=kb_main_menu())
        try:
            safe_send_message(call.message.chat.id, f"✅ Кандидат @{html.escape(target_uname)} успешно назначен редактором/администратором.")
        except Exception:
            pass
    else:
        safe_send_message(target_uid, "❌ К сожалению, ваша заявка на пост редактора была отклонена руководящим составом.")
        try:
            safe_send_message(call.message.chat.id, f"❌ Заявка кандидата @{html.escape(target_uname)} отклонена.")
        except Exception:
            pass

def info_premium(m):
    is_prem = is_user_premium(m.from_user.id)
    status_text = "✅ <b>Ваш VIP-статус активен!</b>" if is_prem else "❌ <b>У вас нет активного VIP-статуса.</b>"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Купить VIP (50 Звезд / 30 дней)", pay=True, callback_data="buy_vip_stars"))

    text = (
        f"💎 <b>Премиум-статус (VIP) в боте</b>\n\n"
        f"{status_text}\n\n"
        "Преимущества VIP статуса:\n"
        "• Значок премиум-аккаунта в ваших объявлениях\n"
        "• Приоритетное размещение товаров\n\n"
        "Стоимость: <b>50 Telegram Stars</b> на 30 дней."
    )
    safe_send_message(m.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "buy_vip_stars")
def send_invoice_vip(call):
    prices = [types.LabeledPrice(label="VIP Статус на 30 дней", amount=50)]
    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title="Премиум-статус VIP",
            description="Покупка VIP статуса в боте СМИ на 30 дней",
            invoice_payload="vip_subscription_30_days",
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="buy_vip"
        )
    except Exception as e:
        try:
            bot.answer_callback_query(call.id, f"Ошибка создания счета: {e}", show_alert=True)
        except Exception:
            pass

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    try:
        bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    except Exception:
        pass

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    payload = message.successful_payment.invoice_payload
    uid = message.from_user.id
    if payload == "vip_subscription_30_days":
        expires = time.time() + 30 * 86400
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO premium_users (user_id, expires_at) VALUES (?, ?)", (uid, expires))
            conn.commit()
        safe_send_message(message.chat.id, "🎉 Поздравляем! Вы успешно приобрели VIP-статус на 30 дней!", reply_markup=kb_main_menu())
    elif payload == "vip_single_ad_pub" or payload == "vip_single_buy_pub":
        st = get_state(uid)
        p_data = st.get("posting_ad") or st.get("posting_buy_ad")
        if p_data:
            p_data["is_vip"] = 1
            is_buy_flag = "posting_buy_ad" in st
            finish_posting(message.chat.id, uid, message.from_user.username, p_data.get("photo_id"), is_buy=is_buy_flag)
        else:
            safe_send_message(message.chat.id, "✅ Оплата прошла, но данные сессии сбросились. Начните заново.", reply_markup=kb_main_menu())

def show_average_prices(m):
    uid = m.from_user.id
    srv = get_state(uid).get("server", "Phoenix")

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT category, text FROM active_ads WHERE server = ?", (srv,))
        ads = cur.fetchall()

    if not ads:
        return safe_send_message(
            m.chat.id, 
            f"📊 На сервере <b>{html.escape(srv)}</b> пока недостаточно данных для расчета средних цен.", 
            reply_markup=kb_main_menu()
        )

    category_prices = {cat: [] for cat in CATEGORIES}

    for cat, text in ads:
        if cat in category_prices:
            numbers = re.findall(r'\d+', text.replace(',', '').replace('.', ''))
            for num_str in numbers:
                val = int(num_str)
                if 100 <= val <= 1000000000:
                    category_prices[cat].append(val)

    report = f"📊 <b>Динамические средние цены на сервере {html.escape(srv)}:</b>\n\n"
    
    for cat in CATEGORIES:
        prices = category_prices[cat]
        if prices:
            avg_val = sum(prices) / len(prices)
            min_val = min(prices)
            max_val = max(prices)
            
            report += f"📂 <b>{cat}</b>:\n"
            report += f"• Средняя цена: <b>{format_price(avg_val)}</b>\n"
            report += f"• Диапазон: от {format_price(min_val)} до {format_price(max_val)}\n"
            report += f"• Учтено объявлений: {len(prices)}\n\n"
        else:
            report += f"📂 <b>{cat}</b>:\n• <i>Нет данных о ценах</i>\n\n"

    safe_send_message(m.chat.id, report, reply_markup=kb_main_menu())

def format_price(val: float) -> str:
    if val >= 1_000_000_000:
        return f"{val / 1_000_000_000:.1f}ккк (млрд)"
    elif val >= 1_000_000:
        return f"{val / 1_000_000:.1f}кк (млн)"
    elif val >= 1_000:
        return f"{val / 1_000:.1f}к (тыс)"
    return f"{int(val)}"

# ==========================================
# КАЛЬКУЛЯТОР И КУРС VICE CITY (VC)
# ==========================================
def show_vc_menu(m):
    rate = get_vc_rate()
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💱 Конвертер валют (Вирты ⇄ VC)", callback_data="vc_conv_start"),
        types.InlineKeyboardButton("📈 Калькулятор выгоды перекупа", callback_data="vc_calc_start"),
    )
    if is_admin_or_owner(m.from_user):
        markup.add(types.InlineKeyboardButton("⚙️ Изменить курс VC (Админ)", callback_data="vc_set_rate_start"))

    text = (
        f"💱 <b>Финансовый центр Vice City & Экономика Arizona</b>\n\n"
        f"📊 Текущий установленный курс:\n"
        f"• <b>1 VC Dollar = {format_price(rate)} вирт</b>\n\n"
        f"Выберите необходимый инструмент ниже:"
    )
    safe_send_message(m.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "vc_conv_start")
def cb_vc_conv_start(call):
    uid = call.from_user.id
    update_state(uid, vc_conv_input=True)
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    safe_send_message(
        call.message.chat.id, 
        "💱 <b>Конвертер валют VC:</b>\n\n"
        "Отправьте сумму для перевода.\n"
        "• Чтобы перевести <i>вирты в VC</i>, просто отправьте число вирт (например: <code>15000000</code> или <code>50кк</code>).\n"
        "• Чтобы перевести <i>VC в вирты</i>, добавьте суффикс vc (например: <code>450vc</code>).",
        reply_markup=kb_cancel()
    )

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("vc_conv_input"))
def process_vc_conversion(m):
    uid = m.from_user.id
    clear_state(uid)
    text = m.text.strip().lower()
    rate = get_vc_rate()

    try:
        if "vc" in text:
            val_str = re.sub(r'[^0-9.]', '', text)
            vc_val = float(val_str)
            reg_val = vc_val * rate
            result_text = (
                f"💱 <b>Результат конвертации:</b>\n\n"
                f"💎 <b>{vc_val:,.1f} VC</b> = 💵 <b>{format_price(reg_val)} вирт</b>\n"
                f"<i>(Курс: 1 VC = {format_price(rate)} вирт)</i>"
            )
        else:
            multiplier = 1
            clean_text = text.replace(',', '.')
            if "ккк" in clean_text or "млрд" in clean_text:
                multiplier = 1_000_000_000
                clean_text = re.sub(r'[^0-9.]', '', clean_text)
            elif "кк" in clean_text or "млн" in clean_text:
                multiplier = 1_000_000
                clean_text = re.sub(r'[^0-9.]', '', clean_text)
            elif "к" in clean_text or "тыс" in clean_text:
                multiplier = 1_000
                clean_text = re.sub(r'[^0-9.]', '', clean_text)
            else:
                clean_text = re.sub(r'[^0-9.]', '', clean_text)

            val = float(clean_text) * multiplier
            vc_res = val / rate
            result_text = (
                f"💱 <b>Результат конвертации:</b>\n\n"
                f"💵 <b>{format_price(val)} вирт</b> = 💎 <b>{vc_res:,.2f} VC</b>\n"
                f"<i>(Курс: 1 VC = {format_price(rate)} вирт)</i>"
            )
        safe_send_message(m.chat.id, result_text, reply_markup=kb_main_menu())
    except Exception as e:
        safe_send_message(m.chat.id, "⚠️ Неверный формат числа. Попробуйте снова через меню конвертера.", reply_markup=kb_main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "vc_calc_start")
def cb_vc_calc_start(call):
    uid = call.from_user.id
    update_state(uid, vc_calc_step="server_price")
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    safe_send_message(
        call.message.chat.id,
        "📈 <b>Калькулятор выгоды перекупщика (Перелет на Vice City)</b>\n\n"
        "Шаг 1 из 2: Введите цену товара на <b>вашем сервере</b> (в виртах, например: <code>45000000</code> или <code>45кк</code>):",
        reply_markup=kb_cancel()
    )

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("vc_calc_step") == "server_price")
def process_calc_server_price(m):
    uid = m.from_user.id
    text = m.text.strip().lower()
    try:
        multiplier = 1
        clean_text = text.replace(',', '.')
        if "ккк" in clean_text or "млрд" in clean_text:
            multiplier = 1_000_000_000
            clean_text = re.sub(r'[^0-9.]', '', clean_text)
        elif "кк" in clean_text or "млн" in clean_text:
            multiplier = 1_000_000
            clean_text = re.sub(r'[^0-9.]', '', clean_text)
        elif "к" in clean_text or "тыс" in clean_text:
            multiplier = 1_000
            clean_text = re.sub(r'[^0-9.]', '', clean_text)
        else:
            clean_text = re.sub(r'[^0-9.]', '', clean_text)

        server_price = float(clean_text) * multiplier
        update_state(uid, vc_calc_server_price=server_price, vc_calc_step="vc_price")

        safe_send_message(
            m.chat.id,
            "📈 Шаг 2 из 2: Введите цену продажи этого же товара на <b>Vice City</b> (в VC долл., например: <code>550</code>):",
            reply_markup=kb_cancel()
        )
    except Exception:
        safe_send_message(m.chat.id, "⚠️ Ошибка ввода суммы. Введите число (например, 50кк или 50000000):", reply_markup=kb_cancel())

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("vc_calc_step") == "vc_price")
def process_calc_vc_price(m):
    uid = m.from_user.id
    st = get_state(uid)
    server_price = st.get("vc_calc_server_price", 0)
    clear_state(uid)

    try:
        vc_price = float(re.sub(r'[^0-9.]', '', m.text.replace(',', '.')))
        rate = get_vc_rate()

        vc_price_in_reg = vc_price * rate
        profit_reg = vc_price_in_reg - server_price
        
        flight_cost = 500_000
        net_profit = profit_reg - flight_cost

        status_emoji = "🟢 <b>ВЫГОДНО!</b>" if net_profit > 0 else "🔴 <b>НЕ ВЫГОДНО (В МИНУСЕ)</b>"

        report = (
            f"📊 <b>Анализ выгоды перелета на Vice City:</b>\n\n"
            f"• Цена на вашем сервере: <b>{format_price(server_price)}</b>\n"
            f"• Цена на Vice City: <b>{vc_price:,.1f} VC</b> ({format_price(vc_price_in_reg)})\n"
            f"• Расходы на перелет/комиссию: ~{format_price(flight_cost)}\n\n"
            f"💰 Чистая прибыль: <b>{format_price(net_profit)}</b>\n"
            f"{status_emoji}"
        )
        safe_send_message(m.chat.id, report, reply_markup=kb_main_menu())
    except Exception:
        safe_send_message(m.chat.id, "⚠️ Ошибка ввода цены на VC. Попробуйте заново через меню калькулятора.", reply_markup=kb_main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "vc_set_rate_start")
def cb_vc_set_rate_start(call):
    if not verify_admin_callback(call):
        return
    uid = call.from_user.id
    update_state(uid, vc_setting_rate=True)
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    safe_send_message(call.message.chat.id, "⚙️ Введите новый актуальный курс 1 VC в виртах (например: <code>95000</code>):", reply_markup=kb_cancel())

@bot.message_handler(func=lambda msg: "vc_setting_rate" in get_state(msg.from_user.id))
def process_set_vc_rate(m):
    if not is_admin_or_owner(m.from_user):
        clear_state(m.from_user.id)
        return
    uid = m.from_user.id
    clear_state(uid)

    try:
        new_rate = float(re.sub(r'[^0-9.]', '', m.text.replace(',', '.')))
        if new_rate <= 0:
            raise ValueError()
        set_vc_rate(new_rate)
        safe_send_message(m.chat.id, f"✅ Курс успешно обновлен! Теперь 1 VC = <b>{format_price(new_rate)} вирт</b>.", reply_markup=kb_main_menu())
    except Exception:
        safe_send_message(m.chat.id, "⚠️ Ошибка. Введите положительное число (например, 95000).", reply_markup=kb_main_menu())

# ==========================================
# ПОДАЧА И МОДЕРАЦИЯ ОБЪЯВЛЕНИЙ
# ==========================================
def start_add_ad(m):
    _start_posting_flow(m, is_buy=False)

def start_add_buy_ad(m):
    _start_posting_flow(m, is_buy=True)

def _start_posting_flow(m, is_buy: bool):
    register_user(m.from_user.id, m.from_user.username)
    if is_banned(m.from_user):
        return safe_send_message(m.chat.id, "⛔ Вы заблокированы.", reply_markup=types.ReplyKeyboardRemove())
    
    if not check_working_hours():
        return safe_send_message(m.chat.id, "⏱ Радиоцентр закрыт! Режим работы: с 08:00:01 до 22:00:01 МСК.")

    uid = m.from_user.id
    last_t = get_user_last_ad_time(uid)
    
    if not is_admin_or_owner(m.from_user) and not is_user_premium(uid):
        if time.time() - last_t < 120:
            left = int(120 - (time.time() - last_t))
            return safe_send_message(m.chat.id, f"⏳ КД 2 минуты! Подождите еще {left} сек. перед подачей нового объявления.")

    srv = get_state(uid).get("server", "Phoenix")
    state_key = "posting_buy_ad" if is_buy else "posting_ad"
    update_state(uid, **{state_key: {"step": "category", "server": srv, "is_buy": is_buy}})
    
    m_kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for c in CATEGORIES:
        m_kb.add(types.KeyboardButton(c))
    m_kb.add(types.KeyboardButton("❌ Отменить действие"))
    
    ad_type_str = "скупку" if is_buy else "продажу"
    safe_send_message(m.chat.id, f"📂 Выберите категорию товара для объявления на <b>{ad_type_str}</b> (сервер: <b>{html.escape(srv)}</b>):", reply_markup=m_kb)

def cancel_action(m):
    uid = m.from_user.id
    st = get_state(uid)
    
    pid = st.get("admin_editing_pid") or st.get("admin_editing_buy_pid")
    if pid:
        table_name = "pending_buy_posts" if "admin_editing_buy_pid" in st else "pending_posts"
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute(f"UPDATE {table_name} SET editing_by = 0, editing_since = 0 WHERE id = ?", (pid,))
            conn.commit()

    clear_state(uid)
    safe_send_message(m.chat.id, "❌ Действие отменено.", reply_markup=kb_main_menu())

@bot.message_handler(func=lambda msg: "posting_ad" in get_state(msg.from_user.id) or "posting_buy_ad" in get_state(msg.from_user.id), content_types=['text', 'photo'])
def process_posting_flow(m):
    uid = m.from_user.id
    st = get_state(uid)
    is_buy = "posting_buy_ad" in st
    p_key = "posting_buy_ad" if is_buy else "posting_ad"
    p_data = st.get(p_key, {})
    step = p_data.get("step")

    if step == "category":
        if m.content_type != 'text':
            return safe_send_message(m.chat.id, "⚠️ Пожалуйста, выберите категорию с помощью кнопок ниже.")
        cat = m.text
        if cat not in CATEGORIES:
            return safe_send_message(m.chat.id, "⚠️ Выберите категорию из предложенных вариантов.")
        p_data["category"] = cat
        p_data["step"] = "text"
        update_state(uid, **{p_key: p_data})
        
        prompt_text = "✍️ Введите текст объявления о скупке (что скупаете, бюджет и условия) <b>или сразу отправьте фотографию с описанием</b>:" if is_buy else "✍️ Введите текст объявления о продаже (описание товара, цену и условия) <b>или сразу отправьте фотографию с описанием</b>:"
        return safe_send_message(m.chat.id, prompt_text, reply_markup=kb_cancel())

    elif step == "text":
        text = ""
        photo_id = None

        if m.content_type == 'photo':
            photo_id = m.photo[-1].file_id
            text = m.caption if m.caption else "Товар по фотографии"
        elif m.content_type == 'text':
            text = m.text
        else:
            return safe_send_message(m.chat.id, "⚠️ Пожалуйста, отправьте текст объявления или фото с описанием.")

        if not check_auto_moderation(text):
            return safe_send_message(m.chat.id, "⚠️ Текст содержит запрещенные слова или ссылки. Пожалуйста, исправьте его.")
        
        p_data["text"] = text
        p_data["photo_id"] = photo_id
        update_state(uid, **{p_key: p_data})
        
        ask_vip_choice_generic(m, photo_id)

def ask_vip_choice_generic(m, photo_id):
    uid = m.from_user.id
    st = get_state(uid)
    is_buy = "posting_buy_ad" in st
    p_key = "posting_buy_ad" if is_buy else "posting_ad"
    p_data = st.get(p_key, {})
    p_data["photo_id"] = photo_id
    update_state(uid, **{p_key: p_data})

    markup = types.InlineKeyboardMarkup(row_width=1)
    callback_suffix = "_buy" if is_buy else ""
    if is_user_premium(uid):
        markup.add(types.InlineKeyboardButton(f"👑 Опубликовать как VIP (Бесплатно)", callback_data=f"post_as_vip_free{callback_suffix}"))
    else:
        markup.add(types.InlineKeyboardButton(f"💎 Подать как VIP-объявление (1 Звезда)", pay=True, callback_data=f"buy_single_vip_star{callback_suffix}"))
    markup.add(types.InlineKeyboardButton(f"📄 Опубликовать как обычное (бесплатно)", callback_data=f"post_as_regular{callback_suffix}"))

    safe_send_message(m.chat.id, "💎 <b>Выберите формат публикации вашего объявления:</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["post_as_vip_free", "post_as_regular", "post_as_vip_free_buy", "post_as_regular_buy"])
def callback_publish_choice(call):
    uid = call.from_user.id
    st = get_state(uid)
    is_buy = "_buy" in call.data
    p_key = "posting_buy_ad" if is_buy else "posting_ad"
    p_data = st.get(p_key)
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if not p_data:
        return safe_send_message(call.message.chat.id, "⚠️ Данные объявления устарели. Начните подачу заново.", reply_markup=kb_main_menu())

    is_vip = 1 if "vip_free" in call.data else 0
    p_data["is_vip"] = is_vip
    finish_posting(call.message.chat.id, uid, call.from_user.username, p_data.get("photo_id"), is_buy=is_buy)

@bot.callback_query_handler(func=lambda c: c.data in ["buy_single_vip_star", "buy_single_vip_star_buy"])
def callback_buy_single_vip(call):
    is_buy = "_buy" in call.data
    payload = "vip_single_buy_pub" if is_buy else "vip_single_ad_pub"
    prices = [types.LabeledPrice(label="VIP Объявление (разовое)", amount=1)]
    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title="Разовое VIP-объявление",
            description="Публикация объявления с VIP-статусом за 1 Telegram Star",
            invoice_payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="buy_single_vip"
        )
    except Exception as e:
        try:
            bot.answer_callback_query(call.id, f"Ошибка создания счета: {e}", show_alert=True)
        except Exception:
            pass

def finish_posting(chat_id: int, user_id: int, username: str, photo_id: str, is_buy: bool):
    st = get_state(user_id)
    p_key = "posting_buy_ad" if is_buy else "posting_ad"
    p_data = st.get(p_key)
    if not p_data:
        return

    srv = p_data["server"]
    cat = p_data["category"]
    text = p_data["text"]
    is_vip = p_data.get("is_vip", 0)
    uname = username if username else "Без юзернейма"

    table_name = "pending_buy_posts" if is_buy else "pending_posts"

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute(f'''
            INSERT INTO {table_name} (user_id, username, server, category, text, photo, is_vip, editing_by, editing_since, is_edited)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
        ''', (user_id, uname, srv, cat, text, photo_id, is_vip))
        pid = cur.lastrowid
        conn.commit()

    clear_state(user_id)
    set_user_last_ad_time(user_id, time.time())

    type_title = "скупку" if is_buy else "продажу"
    safe_send_message(chat_id, f"✅ Объявление на <b>{type_title}</b> отправлено на модерацию редакторам!", reply_markup=kb_main_menu())

    action_prefix = "mod_buy_" if is_buy else "mod_"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Одобрить", callback_data=f"{action_prefix}accept_{pid}"),
        types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"{action_prefix}edit_{pid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"{action_prefix}reject_{pid}")
    )

    preview = format_smi_post(srv, cat, text, uname, uname if uname != "Без юзернейма" else "", is_vip, user_id, is_buy=is_buy)
    
    admin_recipients = get_all_admin_ids()
    for admin_chat_id in admin_recipients:
        try:
            if photo_id:
                safe_send_photo(admin_chat_id, photo_id, caption=(f"📥 <b>Новая заявка на скупку (ID: {pid}):</b>\n\n{preview}" if is_buy else f"📥 <b>Новая заявка на продажу (ID: {pid}):</b>\n\n{preview}"), reply_markup=markup)
            else:
                safe_send_message(admin_chat_id, (f"📥 <b>Новая заявка на скупку (ID: {pid}):</b>\n\n{preview}" if is_buy else f"📥 <b>Новая заявка на продажу (ID: {pid}):</b>\n\n{preview}"), reply_markup=markup)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin_chat_id}: {e}")

# ==========================================
# ОБРАБОТЧИКИ МОДЕРАЦИИ
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data == "admin_edit_ads_menu")
def cb_admin_edit_ads_menu(call):
    if not verify_admin_callback(call):
        return
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, server, category, text FROM pending_posts")
        pending = cur.fetchall()
        cur.execute("SELECT id, server, category, text FROM pending_buy_posts")
        pending_buy = cur.fetchall()

    if not pending and not pending_buy:
        return safe_send_message(call.message.chat.id, "📭 В данный момент нет объявлений на модерации для редактирования.")

    markup = types.InlineKeyboardMarkup(row_width=1)
    for pid, srv, cat, text in pending:
        markup.add(types.InlineKeyboardButton(f"📤 [Продажа | {srv}] ID {pid}: {text[:25]}...", callback_data=f"mod_edit_{pid}"))
    for pid, srv, cat, text in pending_buy:
        markup.add(types.InlineKeyboardButton(f"📥 [Скупка | {srv}] ID {pid}: {text[:25]}...", callback_data=f"mod_buy_edit_{pid}"))

    safe_send_message(call.message.chat.id, "✏️ <b>Выберите объявление для проверки и редактирования:</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("mod_buy_"))
def callback_buy_moderation(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if not verify_admin_callback(call):
        return

    raw_action = call.data.replace("mod_buy_", "")
    try:
        action, pid_str = raw_action.rsplit("_", 1)
        pid = int(pid_str)
    except ValueError:
        return safe_send_message(call.message.chat.id, "⚠️ Ошибка в формате данных модерации.")

    admin_id = call.from_user.id
    curr_time = time.time()

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, username, server, category, text, photo, is_vip, editing_by, editing_since FROM pending_buy_posts WHERE id = ?", (pid,))
        post = cur.fetchone()

    if not post:
        return safe_send_message(call.message.chat.id, "⚠️ Объявление уже обработано или удалено.")

    user_id, uname, srv, cat, text, photo_id, is_vip, editing_by, editing_since = post

    if editing_by != 0 and (curr_time - editing_since) > 720:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE pending_buy_posts SET editing_by = 0, editing_since = 0 WHERE id = ?", (pid,))
            conn.commit()
        editing_by = 0

    if action == "edit":
        if editing_by != 0 and editing_by != admin_id:
            return safe_send_message(call.message.chat.id, "⛔ Это объявление уже редактирует другой администратор!")
        
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE pending_buy_posts SET editing_by = ?, editing_since = ? WHERE id = ?", (admin_id, curr_time, pid))
            conn.commit()

        update_state(admin_id, admin_editing_buy_pid=pid, edit_start_time=curr_time)
        safe_send_message(call.message.chat.id, f"✏️ Введите новый текст для скупкы (ID: {pid}). У вас есть 12 минут:", reply_markup=kb_cancel())
        return

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM pending_buy_posts WHERE id = ?", (pid,))
        conn.commit()

    editor_uname = call.from_user.username or "Админ"

    if action in ["accept", "publish_edited"]:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO active_buy_ads (user_id, server, category, text, photo, is_vip, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, srv, cat, text, photo_id, is_vip, time.time()))
            aid = cur.lastrowid
            cur.execute("INSERT INTO editor_stats (username, count) VALUES (?, 1) ON CONFLICT(username) DO UPDATE SET count = count + 1", (editor_uname,))
            conn.commit()

        safe_send_message(user_id, "🎉 Ваше объявление о скупке успешно опубликовано!")

        final_text = format_smi_post(srv, cat, text, uname, editor_uname, is_vip, user_id, is_buy=True)
        markup = ikb_ad_actions(aid, is_fav=False, user_id=admin_id, is_buy=True)

        if photo_id:
            safe_send_photo(call.message.chat.id, photo_id, caption=final_text, reply_markup=markup)
        else:
            safe_send_message(call.message.chat.id, final_text, reply_markup=markup)
            
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

    elif action == "reject":
        safe_send_message(user_id, "❌ Ваше объявление о скупке было отклонено редактором.")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("mod_") and not c.data.startswith("mod_buy_"))
def callback_moderation(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if not verify_admin_callback(call):
        return

    raw_action = call.data.replace("mod_", "")
    try:
        action, pid_str = raw_action.rsplit("_", 1)
        pid = int(pid_str)
    except ValueError:
        return safe_send_message(call.message.chat.id, "⚠️ Ошибка в формате данных модерации.")

    admin_id = call.from_user.id
    curr_time = time.time()

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, username, server, category, text, photo, is_vip, editing_by, editing_since FROM pending_posts WHERE id = ?", (pid,))
        post = cur.fetchone()

    if not post:
        return safe_send_message(call.message.chat.id, "⚠️ Объявление уже обработано или удалено.")

    user_id, uname, srv, cat, text, photo_id, is_vip, editing_by, editing_since = post

    if editing_by != 0 and (curr_time - editing_since) > 720:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE pending_posts SET editing_by = 0, editing_since = 0 WHERE id = ?", (pid,))
            conn.commit()
        editing_by = 0

    if action == "edit":
        if editing_by != 0 and editing_by != admin_id:
            return safe_send_message(call.message.chat.id, "⛔ Это объявление уже редактирует другой администратор!")
        
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE pending_posts SET editing_by = ?, editing_since = ? WHERE id = ?", (admin_id, curr_time, pid))
            conn.commit()

        update_state(admin_id, admin_editing_pid=pid, edit_start_time=curr_time)
        safe_send_message(call.message.chat.id, f"✏️ Введите новый текст и цену для объявления (ID: {pid}). У вас есть 12 минут:", reply_markup=kb_cancel())
        return

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM pending_posts WHERE id = ?", (pid,))
        conn.commit()

    editor_uname = call.from_user.username or "Админ"

    if action in ["accept", "publish_edited"]:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO active_ads (user_id, server, category, text, photo, is_vip, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, srv, cat, text, photo_id, is_vip, time.time()))
            aid = cur.lastrowid
            cur.execute("INSERT INTO editor_stats (username, count) VALUES (?, 1) ON CONFLICT(username) DO UPDATE SET count = count + 1", (editor_uname,))
            conn.commit()

        safe_send_message(user_id, "🎉 Ваше объявление успешно прошло модерацию и было опубликовано!")

        final_text = format_smi_post(srv, cat, text, uname, editor_uname, is_vip, user_id, is_buy=False)
        markup = ikb_ad_actions(aid, is_fav=False, user_id=admin_id, is_buy=False)

        if photo_id:
            safe_send_photo(call.message.chat.id, photo_id, caption=final_text, reply_markup=markup)
        else:
            safe_send_message(call.message.chat.id, final_text, reply_markup=markup)
            
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

        check_keyword_subscriptions(srv, text)

    elif action == "reject":
        safe_send_message(user_id, "❌ Ваше объявление было отклонено редактором.")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

@bot.message_handler(func=lambda msg: "admin_editing_pid" in get_state(msg.from_user.id) or "admin_editing_buy_pid" in get_state(msg.from_user.id))
def process_admin_edit_text(m):
    if not is_admin_or_owner(m.from_user):
        return
    
    uid = m.from_user.id
    st = get_state(uid)
    start_t = st.get("edit_start_time", 0)

    if time.time() - start_t > 720:
        clear_state(uid)
        return safe_send_message(m.chat.id, "⌛ Время редактирования истекло (более 12 минут).", reply_markup=kb_main_menu())

    is_buy = "admin_editing_buy_pid" in st
    pid = st.get("admin_editing_buy_pid") if is_buy else st.get("admin_editing_pid")
    new_text = m.text.strip()
    clear_state(uid)

    table_name = "pending_buy_posts" if is_buy else "pending_posts"

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE {table_name} SET text = ?, is_edited = 1, editing_by = 0, editing_since = 0 WHERE id = ?", (new_text, pid))
        cur.execute(f"SELECT user_id, username, server, category, text, photo, is_vip FROM {table_name} WHERE id = ?", (pid,))
        post = cur.fetchone()
        conn.commit()

    if not post:
        return safe_send_message(m.chat.id, "❌ Ошибка: объявление не найдено.", reply_markup=kb_main_menu())

    user_id, uname, srv, cat, text, photo_id, is_vip = post
    
    try:
        safe_send_message(user_id, f"✏️ <b>Ваше объявление (ID: {pid}) было отредактировано редактором:</b>\n\n<i>{html.escape(new_text)}</i>\n\nОно ожидает финальной публикации.")
    except Exception:
        pass

    editor_uname = m.from_user.username or "Админ"
    preview = format_smi_post(srv, cat, text, uname, editor_uname, is_vip, user_id, is_buy=is_buy)

    action_prefix = "mod_buy_" if is_buy else "mod_"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Опубликовать", callback_data=f"{action_prefix}publish_edited_{pid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"{action_prefix}reject_{pid}")
    )

    if photo_id:
        safe_send_photo(m.chat.id, photo_id, caption=f"✏️ <b>Отредактированное объявление (ID: {pid}):</b>\n\n{preview}", reply_markup=markup)
    else:
        safe_send_message(m.chat.id, f"✏️ <b>Отредактированное объявление (ID: {pid}):</b>\n\n{preview}", reply_markup=markup)

# ==========================================
# УДАЛЕНИЕ АКТИВНЫХ ОБЪЯВЛЕНИЙ АДМИНИСТРАТОРОМ
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_del_") or c.data.startswith("admin_del_buy_"))
def cb_admin_delete_active_ad(call):
    if not verify_admin_callback(call):
        return
    is_buy = "admin_del_buy_" in call.data
    prefix = "admin_del_buy_" if is_buy else "admin_del_"
    aid = int(call.data.replace(prefix, ""))
    table_name = "active_buy_ads" if is_buy else "active_ads"

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {table_name} WHERE id = ?", (aid,))
        conn.commit()

    try:
        bot.answer_callback_query(call.id, "🗑 Объявление успешно удалено администратором!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

# ==========================================
# ПРОСМОТР ПРОДАЖ И СКУПКИ
# ==========================================
def show_ads_category(m):
    update_state(m.from_user.id, viewing_buy_categories=False)
    cat_idx = CATEGORIES.index(m.text)
    render_category_page(m.chat.id, m.from_user.id, cat_idx, page=0)

def render_category_page(chat_id: int, user_id: int, cat_idx: int, page: int = 0):
    cat_name = CATEGORIES[cat_idx]
    srv = get_state(user_id).get("server", "Phoenix")

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, user_id, text, photo FROM active_ads WHERE category = ? AND server = ? ORDER BY is_vip DESC, id DESC", (cat_name, srv))
        all_ads = cur.fetchall()

    if not all_ads:
        return safe_send_message(chat_id, f"📤 Продажа | Раздел: <b>{html.escape(cat_name)}</b> [{html.escape(srv)}]\nОбъявлений о продаже пока нет.", reply_markup=kb_main_menu())

    total_ads = len(all_ads)
    start_idx = page * ADS_PER_PAGE
    end_idx = start_idx + ADS_PER_PAGE
    page_ads = all_ads[start_idx:end_idx]

    if not page_ads:
        return safe_send_message(chat_id, "📄 На этой странице больше нет объявлений.", reply_markup=kb_main_menu())

    safe_send_message(chat_id, f"📤 <b>Продажа | Раздел:</b> {html.escape(cat_name)} [{html.escape(srv)}] (Страница {page + 1}):")

    for aid, seller_uid, text, photo in page_ads:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM favorites WHERE user_id = ? AND ad_id = ?", (user_id, aid))
            is_fav = bool(cur.fetchone())

        markup = ikb_ad_actions(aid, is_fav=is_fav, user_id=user_id, is_buy=False)
        fmt_text = html.escape(text)
        if photo:
            safe_send_photo(chat_id, photo, caption=fmt_text, reply_markup=markup)
        else:
            safe_send_message(chat_id, fmt_text, reply_markup=markup)

    nav_markup = types.InlineKeyboardMarkup(row_width=2)
    nav_btns = []
    if page > 0:
        nav_btns.append(types.InlineKeyboardButton("⏮ Назад", callback_data=f"sale_page_{cat_idx}_{page - 1}"))
    if end_idx < total_ads:
        nav_btns.append(types.InlineKeyboardButton("Вперед ⏭", callback_data=f"sale_page_{cat_idx}_{page + 1}"))
    
    if nav_btns:
        nav_markup.add(*nav_btns)
        safe_send_message(chat_id, f"📑 Страница {page + 1} из {(total_ads + ADS_PER_PAGE - 1) // ADS_PER_PAGE}:", reply_markup=nav_markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("sale_page_"))
def cb_sale_category_page(call):
    parts = call.data.split("_")
    cat_idx = int(parts[2])
    page = int(parts[3])
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    render_category_page(call.message.chat.id, call.from_user.id, cat_idx, page=page)

def show_buy_ads_category(m):
    update_state(m.from_user.id, viewing_buy_categories=True)
    cat_idx = CATEGORIES.index(m.text)
    render_buy_category_page(m.chat.id, m.from_user.id, cat_idx, page=0)

def render_buy_category_page(chat_id: int, user_id: int, cat_idx: int, page: int = 0):
    cat_name = CATEGORIES[cat_idx]
    srv = get_state(user_id).get("server", "Phoenix")

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, user_id, text, photo FROM active_buy_ads WHERE category = ? AND server = ? ORDER BY is_vip DESC, id DESC", (cat_name, srv))
        all_ads = cur.fetchall()

    if not all_ads:
        return safe_send_message(chat_id, f"📥 Скупка | Раздел: <b>{html.escape(cat_name)}</b> [{html.escape(srv)}]\nОбъявлений о скупке пока нет.", reply_markup=kb_main_menu())

    total_ads = len(all_ads)
    start_idx = page * ADS_PER_PAGE
    end_idx = start_idx + ADS_PER_PAGE
    page_ads = all_ads[start_idx:end_idx]

    if not page_ads:
        return safe_send_message(chat_id, "📄 На этой странице больше нет объявлений.", reply_markup=kb_main_menu())

    safe_send_message(chat_id, f"📥 <b>Скупка | Раздел:</b> {html.escape(cat_name)} [{html.escape(srv)}] (Страница {page + 1}):")

    for aid, seller_uid, text, photo in page_ads:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM favorites WHERE user_id = ? AND ad_id = ?", (user_id, aid))
            is_fav = bool(cur.fetchone())

        markup = ikb_ad_actions(aid, is_fav=is_fav, user_id=user_id, is_buy=True)
        fmt_text = html.escape(text)
        if photo:
            safe_send_photo(chat_id, photo, caption=fmt_text, reply_markup=markup)
        else:
            safe_send_message(chat_id, fmt_text, reply_markup=markup)

    nav_markup = types.InlineKeyboardMarkup(row_width=2)
    nav_btns = []
    if page > 0:
        nav_btns.append(types.InlineKeyboardButton("⏮ Назад", callback_data=f"buy_page_{cat_idx}_{page - 1}"))
    if end_idx < total_ads:
        nav_btns.append(types.InlineKeyboardButton("Вперед ⏭", callback_data=f"buy_page_{cat_idx}_{page + 1}"))
    
    if nav_btns:
        nav_markup.add(*nav_btns)
        safe_send_message(chat_id, f"📑 Страница {page + 1} из {(total_ads + ADS_PER_PAGE - 1) // ADS_PER_PAGE}:", reply_markup=nav_markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_page_"))
def cb_buy_category_page(call):
    parts = call.data.split("_")
    cat_idx = int(parts[2])
    page = int(parts[3])
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    render_buy_category_page(call.message.chat.id, call.from_user.id, cat_idx, page=page)

# ==========================================
# МОИ ОБЪЯВЛЕНИЯ
# ==========================================
def show_my_ads(m):
    uid = m.from_user.id
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, server, category, text, is_edited FROM pending_posts WHERE user_id = ?", (uid,))
            pending = cur.fetchall()
            cur.execute("SELECT id, server, category, text, is_edited FROM active_ads WHERE user_id = ?", (uid,))
            active = cur.fetchall()
            cur.execute("SELECT id, server, category, text, is_edited FROM pending_buy_posts WHERE user_id = ?", (uid,))
            pending_buy = cur.fetchall()
            cur.execute("SELECT id, server, category, text, is_edited FROM active_buy_ads WHERE user_id = ?", (uid,))
            active_buy = cur.fetchall()
        except sqlite3.OperationalError:
            cur.execute("SELECT id, server, category, text FROM pending_posts WHERE user_id = ?", (uid,))
            pending = [(r[0], r[1], r[2], r[3], 0) for r in cur.fetchall()]
            cur.execute("SELECT id, server, category, text FROM active_ads WHERE user_id = ?", (uid,))
            active = [(r[0], r[1], r[2], r[3], 0) for r in cur.fetchall()]
            cur.execute("SELECT id, server, category, text FROM pending_buy_posts WHERE user_id = ?", (uid,))
            pending_buy = [(r[0], r[1], r[2], r[3], 0) for r in cur.fetchall()]
            cur.execute("SELECT id, server, category, text FROM active_buy_ads WHERE user_id = ?", (uid,))
            active_buy = [(r[0], r[1], r[2], r[3], 0) for r in cur.fetchall()]

    text_msg = "📋 <b>Ваши объявления и их статусы:</b>\n\n⏳ <b>1. Ожидают модерации:</b>\n"
    total_count = len(pending) + len(active) + len(pending_buy) + len(active_buy)
    
    if not pending and not pending_buy:
        text_msg += "• Нет объявлений в очереди.\n\n"
    else:
        for aid, srv, cat, text, is_ed in pending:
            ed_label = " <i>(✏️ Отредактировано)</i>" if is_ed else ""
            text_msg += f"• [Продажа | {html.escape(srv)}] {html.escape(cat)}{ed_label}: {html.escape(text[:22])}...\n"
        for aid, srv, cat, text, is_ed in pending_buy:
            ed_label = " <i>(✏️ Отредактировано)</i>" if is_ed else ""
            text_msg += f"• [Скупка | {html.escape(srv)}] {html.escape(cat)}{ed_label}: {html.escape(text[:22])}...\n"
        text_msg += "\n"
    
    text_msg += "✅ <b>2. Опубликованные:</b>\n"
    if not active and not active_buy:
        text_msg += "• Нет активных объявлений."
    else:
        for aid, srv, cat, text, is_ed in active:
            ed_label = " <i>(✏️ Отредактировано)</i>" if is_ed else ""
            text_msg += f"• [Продажа | {html.escape(srv)}] {html.escape(cat)}{ed_label}: {html.escape(text[:22])}...\n"
        for aid, srv, cat, text, is_ed in active_buy:
            ed_label = " <i>(✏️ Отредактировано)</i>" if is_ed else ""
            text_msg += f"• [Скупка | {html.escape(srv)}] {html.escape(cat)}{ed_label}: {html.escape(text[:22])}...\n"

    markup = types.InlineKeyboardMarkup(row_width=1)
    for aid, srv, cat, text, _ in pending:
        markup.add(types.InlineKeyboardButton(f"❌ Отменить мод. продажи (ID {aid})", callback_data=f"cancel_pending_{aid}"))
    for aid, srv, cat, text, _ in pending_buy:
        markup.add(types.InlineKeyboardButton(f"❌ Отменить мод. скупки (ID {aid})", callback_data=f"cancel_pending_buy_{aid}"))
    for aid, srv, cat, text, _ in active:
        markup.add(types.InlineKeyboardButton(f"🗑 Удалить активную продажу (ID {aid})", callback_data=f"cancel_active_{aid}"))
    for aid, srv, cat, text, _ in active_buy:
        markup.add(types.InlineKeyboardButton(f"🗑 Удалить активную скупку (ID {aid})", callback_data=f"cancel_active_buy_{aid}"))

    safe_send_message(m.chat.id, text_msg, reply_markup=markup if total_count > 0 else kb_main_menu())

@bot.callback_query_handler(func=lambda c: c.data.startswith("cancel_pending_") or c.data.startswith("cancel_pending_buy_"))
def cb_cancel_pending(call):
    is_buy = "buy" in call.data
    prefix = "cancel_pending_buy_" if is_buy else "cancel_pending_"
    aid = int(call.data.replace(prefix, ""))
    uid = call.from_user.id
    table_name = "pending_buy_posts" if is_buy else "pending_posts"

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {table_name} WHERE id = ? AND user_id = ?", (aid, uid))
        conn.commit()
    try:
        bot.answer_callback_query(call.id, "❌ Объявление отменено!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("cancel_active_") or c.data.startswith("cancel_active_buy_"))
def cb_cancel_active(call):
    is_buy = "buy" in call.data
    prefix = "cancel_active_buy_" if is_buy else "cancel_active_"
    aid = int(call.data.replace(prefix, ""))
    uid = call.from_user.id
    table_name = "active_buy_ads" if is_buy else "active_ads"

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {table_name} WHERE id = ? AND user_id = ?", (aid, uid))
        conn.commit()
    try:
        bot.answer_callback_query(call.id, "✅ Объявление удалено из ленты!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

# ==========================================
# ИЗБРАННОЕ И ПОИСК
# ==========================================
def show_favorites(m):
    uid = m.from_user.id
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute('''
            SELECT a.id, a.server, a.category, a.text, a.photo 
            FROM favorites f JOIN active_ads a ON f.ad_id = a.id 
            WHERE f.user_id = ?
        ''', (uid,))
        favs = cur.fetchall()

    if not favs:
        return safe_send_message(m.chat.id, "❤️ Ваш список избранного пуст.", reply_markup=kb_main_menu())

    safe_send_message(m.chat.id, "❤️ <b>Ваши сохраненные объявления:</b>")
    for aid, srv, cat, text, photo in favs:
        markup = ikb_ad_actions(aid, is_fav=True, user_id=uid, is_buy=False)
        fmt_text = html.escape(text)
        if photo:
            safe_send_photo(m.chat.id, photo, caption=fmt_text, reply_markup=markup)
        else:
            safe_send_message(m.chat.id, fmt_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("fav_toggle_"))
def cb_fav_toggle(call):
    aid = int(call.data.split("_")[2])
    uid = call.from_user.id

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM favorites WHERE user_id = ? AND ad_id = ?", (uid, aid))
        exists = cur.fetchone()
        
        if exists:
            cur.execute("DELETE FROM favorites WHERE user_id = ? AND ad_id = ?", (uid, aid))
            msg_alert = "❌ Удалено из избранного!"
            new_fav = False
        else:
            cur.execute("INSERT OR IGNORE INTO favorites (user_id, ad_id) VALUES (?, ?)", (uid, aid))
            msg_alert = "❤️ Добавлено в избранное!"
            new_fav = True
        conn.commit()

    try:
        bot.answer_callback_query(call.id, msg_alert)
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=ikb_ad_actions(aid, is_fav=new_fav, user_id=uid, is_buy=False))
    except Exception:
        pass

def start_search(m):
    update_state(m.from_user.id, searching=True)
    safe_send_message(m.chat.id, "🔍 Введите ключевое слово для поиска:", reply_markup=kb_cancel())

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("searching"))
def process_search_query(m):
    query = m.text.lower()
    uid = m.from_user.id
    srv = get_state(uid).get("server", "Phoenix")
    clear_state(uid)

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, server, category, text, photo FROM active_ads WHERE server = ? AND LOWER(text) LIKE ? ORDER BY id DESC LIMIT 5", (srv, f"%{query}%"))
        results = cur.fetchall()
        cur.execute("SELECT id, server, category, text, photo FROM active_buy_ads WHERE server = ? AND LOWER(text) LIKE ? ORDER BY id DESC LIMIT 5", (srv, f"%{query}%"))
        results_buy = cur.fetchall()

    if not results and not results_buy:
        return safe_send_message(m.chat.id, f"🔍 По запросу «{html.escape(query)}» ничего не найдено.", reply_markup=kb_main_menu())

    safe_send_message(m.chat.id, f"🔍 Результаты поиска по запросу «{html.escape(query)}» [{html.escape(srv)}]:")
    
    for aid, srv_name, cat, text, photo in results:
        markup = ikb_ad_actions(aid, is_fav=False, user_id=uid, is_buy=False)
        fmt_text = f"📤 <b>[Продажа]</b>\n" + html.escape(text)
        if photo:
            safe_send_photo(m.chat.id, photo, caption=fmt_text, reply_markup=markup)
        else:
            safe_send_message(m.chat.id, fmt_text, reply_markup=markup)

    for aid, srv_name, cat, text, photo in results_buy:
        markup = ikb_ad_actions(aid, is_fav=False, user_id=uid, is_buy=True)
        fmt_text = f"📥 <b>[Скупка]</b>\n" + html.escape(text)
        if photo:
            safe_send_photo(m.chat.id, photo, caption=fmt_text, reply_markup=markup)
        else:
            safe_send_message(m.chat.id, fmt_text, reply_markup=markup)

def manage_subscriptions(m):
    uid = m.from_user.id
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, server, keyword FROM keyword_subscriptions WHERE user_id = ?", (uid,))
        subs = cur.fetchall()

    markup = types.InlineKeyboardMarkup(row_width=1)
    for sub_id, srv, kw in subs:
        markup.add(types.InlineKeyboardButton(f"❌ Удалить: [{srv}] {kw}", callback_data=f"del_sub_{sub_id}"))
    markup.add(types.InlineKeyboardButton("➕ Добавить новую подписку", callback_data="add_sub_start"))

    safe_send_message(m.chat.id, "🔔 <b>Ваши подписки на ключевые слова:</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "add_sub_start")
def cb_add_sub_start(call):
    update_state(call.from_user.id, adding_sub=True)
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    safe_send_message(call.message.chat.id, "🔔 Введите ключевое слово для подписки:", reply_markup=kb_cancel())

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("adding_sub"))
def process_add_sub(m):
    uid = m.from_user.id
    kw = m.text.lower().strip()
    srv = get_state(uid).get("server", "Phoenix")
    clear_state(uid)

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM keyword_subscriptions WHERE user_id = ?", (uid,))
        if cur.fetchone()[0] >= 3:
            return safe_send_message(m.chat.id, "⚠️ Достигнут лимит (максимум 3 подписки).", reply_markup=kb_main_menu())
        cur.execute("INSERT INTO keyword_subscriptions (user_id, server, keyword) VALUES (?, ?, ?)", (uid, srv, kw))
        conn.commit()

    safe_send_message(m.chat.id, f"✅ Вы подписались на уведомления по слову «<b>{html.escape(kw)}</b>» на сервере {html.escape(srv)}.", reply_markup=kb_main_menu())

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_sub_"))
def cb_del_sub(call):
    sub_id = int(call.data.replace("del_sub_", ""))
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM keyword_subscriptions WHERE id = ? AND user_id = ?", (sub_id, call.from_user.id))
        conn.commit()
    try:
        bot.answer_callback_query(call.id, "❌ Подписка удалена!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

def check_keyword_subscriptions(srv: str, text: str):
    t_lower = text.lower()
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, keyword FROM keyword_subscriptions WHERE server = ?", (srv,))
        for uid, kw in cur.fetchall():
            if kw in t_lower:
                safe_send_message(uid, f"🔔 <b>Уведомление!</b>\nНа сервере {html.escape(srv)} появилось новое объявление с ключевым словом «<b>{html.escape(kw)}</b>». Проверьте последние обновления!")

# ==========================================
# ЧАТЫ И КОНТАКТЫ
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("contact_seller_"))
def cb_contact_seller(call):
    aid = int(call.data.replace("contact_seller_", ""))
    buyer_id = call.from_user.id
    
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, text, server, photo FROM active_ads WHERE id = ?", (aid,))
        seller = cur.fetchone()
        
    if not seller:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("SELECT user_id, text, server, photo FROM active_buy_ads WHERE id = ?", (aid,))
            seller = cur.fetchone()

    if not seller:
        return safe_send_message(call.message.chat.id, "⚠️ Объявление уже удалено или неактуально.")

    seller_id, text, srv, photo_id = seller

    if buyer_id == seller_id:
        return safe_send_message(call.message.chat.id, "⚠️ Вы не можете начать диалог с самим собой.")

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT is_active FROM active_dialogs WHERE (buyer_id = ? AND seller_id = ?) OR (buyer_id = ? AND seller_id = ?)", (buyer_id, seller_id, seller_id, buyer_id))
        dialog = cur.fetchone()

    if dialog and dialog[0] == 1:
        return safe_send_message(call.message.chat.id, "ℹ️ У вас уже есть активный диалог с этим пользователем. Напишите ему в чат!")
    elif dialog and dialog[0] == 0:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE active_dialogs SET is_active = 1 WHERE (buyer_id = ? AND seller_id = ?) OR (buyer_id = ? AND seller_id = ?)", (buyer_id, seller_id, seller_id, buyer_id))
            conn.commit()
    else:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO active_dialogs (buyer_id, seller_id, ad_id, is_active) VALUES (?, ?, ?, 1)", (buyer_id, seller_id, aid))
            conn.commit()

    safe_send_message(buyer_id, f"✉️ <b>Диалог начат!</b>\nПо объявлению: {html.escape(text[:30])}...\nВсе сообщения, отправленные сюда, будут перенаправляться собеседнику, пока вы не завершите диалог.", reply_markup=ikb_chat_controls(aid))
    safe_send_message(seller_id, f"✉️ <b>С вами хотят связаться по объявлению!</b>\n\n{html.escape(text[:50])}...\nНапишите ответное сообщение в этот чат.", reply_markup=ikb_chat_controls(aid))

@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/') and m.text not in SYSTEM_NAV_BUTTONS)
def forward_dialog_message(m):
    uid = m.from_user.id
    st = get_state(uid)
    if any(k in st for k in ["posting_ad", "posting_buy_ad", "searching", "adding_sub", "vc_setting_rate", "vc_calc_step", "vc_conv_input", "admin_editing_pid", "admin_editing_buy_pid", "applying_admin"]):
        return

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT buyer_id, seller_id, ad_id FROM active_dialogs WHERE (buyer_id = ? OR seller_id = ?) AND is_active = 1", (uid, uid))
        row = cur.fetchone()

    if not row:
        return

    buyer_id, seller_id, ad_id = row
    target_id = seller_id if uid == buyer_id else buyer_id

    try:
        sender_name = html.escape(m.from_user.first_name or "Пользователь")
        if m.content_type == 'photo':
            safe_send_photo(target_id, m.photo[-1].file_id, caption=f"💬 <b>Сообщение от {sender_name}:</b>\n{html.escape(m.caption or '')}", reply_markup=ikb_chat_controls(ad_id))
        elif m.content_type == 'text':
            safe_send_message(target_id, f"💬 <b>Сообщение от {sender_name}:</b>\n{html.escape(m.text)}", reply_markup=ikb_chat_controls(ad_id))
    except Exception as e:
        logger.error(f"Ошибка пересылки сообщения в диалоге: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("stop_chat_") or c.data.startswith("resume_chat_"))
def cb_chat_control(call):
    is_stop = "stop_chat_" in call.data
    aid = int(call.data.replace("stop_chat_" if is_stop else "resume_chat_", ""))
    uid = call.from_user.id
    new_status = 0 if is_stop else 1

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE active_dialogs SET is_active = ? WHERE ad_id = ? AND (buyer_id = ? OR seller_id = ?)", (new_status, aid, uid, uid))
        conn.commit()

    try:
        bot.answer_callback_query(call.id, "🛑 Диалог завершен!" if is_stop else "🔄 Диалог возобновлен!")
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=ikb_chat_controls(aid))
    except Exception:
        pass

# ==========================================
# АДМИН-ПАНЕЛЬ
# ==========================================
def admin_panel(m):
    if not is_admin_or_owner(m.from_user):
        return safe_send_message(m.chat.id, "⛔ У вас нет доступа к админ-панели.")
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("✏️ Меню редактирования модерации", callback_data="admin_edit_ads_menu"),
        types.InlineKeyboardButton("📊 Статистика редакторов", callback_data="admin_stats"),
        types.InlineKeyboardButton("⚙️ Управление курсом VC", callback_data="vc_set_rate_start")
    )
    safe_send_message(m.chat.id, "👑 <b>Панель администратора:</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_stats")
def cb_admin_stats(call):
    if not verify_admin_callback(call):
        return
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT username, count FROM editor_stats ORDER BY count DESC LIMIT 10")
        stats = cur.fetchall()

    if not stats:
        return safe_send_message(call.message.chat.id, "📊 Статистика редакторов пуста.")

    text = "📊 <b>Топ редакторов по публикациям:</b>\n\n"
    for uname, count in stats:
        text += f"• @{html.escape(uname)} — <b>{count}</b> объявл.\n"

    safe_send_message(call.message.chat.id, text)

# ==========================================
# ЗАПУСК БОТА
# ==========================================
if __name__ == '__main__':
    logger.info("Бот успешно запущен и ожидает сообщения")
    bot.infinity_polling(skip_pending=True)
