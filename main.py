import os
import time
import threading
import logging
import sqlite3
import re
import html
from datetime import datetime, time as dtime
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

# Установка токена бота
TOKEN = "8916669266:AAE6lby6tObJLHyuGrHgeCaCLKFMQsTAKdI"

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
    "💍 Аксессуары",
    "🏎 Транспорт и Тюнинг",
    "🥼 Скины и Охранники",
    "🏡 Недвижимость и Бизнес",
    "📦 Ресурсы и Оружие"
]

SYSTEM_NAV_BUTTONS = [
    "🔍 Поиск по товарам", "❤️ Избранное", "🔔 Подписки на поиск",
    "📋 Мои объявления", "📊 Средние цены", "📊 Как работает бот",
    "🛒 Подать объявление о продаже", "💎 Премиум (VIP)", "🔄 Сменить сервер",
    "👑 Админ", "📝 Подать заявку на админа", "🚫 Отмена"
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
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
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

def verify_admin_callback(call) -> bool:
    if not is_admin_or_owner(call.from_user):
        try:
            bot.answer_callback_query(call.id, "⛔ Нет доступа к функциям СМИ!", show_alert=True)
        except Exception:
            pass
        return False
    return True

def check_working_hours() -> bool:
    now_time = datetime.now().time()
    return dtime(8, 0, 0) <= now_time <= dtime(22, 0, 0)

def clean_server_name(server: str) -> str:
    return server.split(' ', 1)[-1] if ' ' in server else server

def format_smi_post(server: str, category: str, text: str, player_username: str, editor_username: str, is_vip: bool = False, user_id: int = 0) -> str:
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

    return (
        f"{vip_header}"
        f"📰 | <b>[СМИ {clean_srv}] Объявление:</b> {prem_icon}\n"
        f"📞 <b>Контакт игрока:</b> {player_contact} | {rating_str}\n\n"
        f"{text_esc}\n\n"
        f"📂 <b>Раздел:</b> {cat_esc}\n"
        f"👨‍💻 <b>Отредактировал:</b> {editor_contact}"
    )

def background_cleanup_ads():
    while True:
        time.sleep(300)
        curr_t = time.time()
        try:
            with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
                cur = conn.cursor()
                expired_limit = curr_t - 86400  # Удаление объявлений старше 24 часов
                cur.execute("DELETE FROM active_ads WHERE last_updated < ?", (expired_limit,))
                conn.commit()
        except Exception as e:
            logger.error(f"Ошибка фоновой очистки: {e}")

threading.Thread(target=background_cleanup_ads, daemon=True).start()

# ==========================================
# КЛАВИАТУРЫ
# ==========================================
def kb_servers():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for i in range(0, len(SERVERS), 2): 
        m.add(*[types.KeyboardButton(s) for s in SERVERS[i:i+2]])
    m.add(types.KeyboardButton("📊 Как работает бот"), types.KeyboardButton("🛒 Подать объявление о продаже"))
    m.add(types.KeyboardButton("💎 Премиум (VIP)"), types.KeyboardButton("👑 Админ"))
    m.add(types.KeyboardButton("📝 Подать заявку на админа"))
    return m

def kb_main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("💍 Аксессуары", "🏎 Транспорт и Тюнинг")
    m.add("🥼 Скины и Охранники", "🏡 Недвижимость и Бизнес")
    m.add("📦 Ресурсы и Оружие")
    m.add("🔍 Поиск по товарам", "❤️ Избранное")
    m.add("🔔 Подписки на поиск", "📋 Мои объявления")
    m.add("📊 Средние цены", "📊 Как работает бот")
    m.add("🛒 Подать объявление о продаже", "💎 Премиум (VIP)")
    m.add("🔄 Сменить сервер", "👑 Админ")
    m.add("📝 Подать заявку на админа")
    return m

def kb_cancel():
    return types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("🚫 Отмена"))

def ikb_chat_controls(aid: int):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🛑 Завершить диалог", callback_data=f"stop_chat_{aid}"),
        types.InlineKeyboardButton("🔄 Возобновить / Начать заново", callback_data=f"resume_chat_{aid}")
    )
    return markup

def ikb_ad_actions(aid: int, is_fav: bool = False):
    markup = types.InlineKeyboardMarkup(row_width=2)
    fav_text = "❌ Убрать из избранного" if is_fav else "❤️ В избранное"
    markup.add(
        types.InlineKeyboardButton("✉️ Написать продавцу", callback_data=f"contact_seller_{aid}"),
        types.InlineKeyboardButton(fav_text, callback_data=f"fav_toggle_{aid}")
    )
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

    if msg.text == "🚫 Отмена" or msg.text.startswith('/'):
        return True

    if "admin_editing_pid" in st or "admin_editing_active_aid" in st or "applying_admin" in st:
        return False
        
    if "posting_ad" in st:
        step = st["posting_ad"].get("step")
        if step == "server" and msg.text in SERVERS:
            return False
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
    elif m.text == "🔄 Сменить сервер":
        change_server(m)
    elif m.text == "📊 Как работает бот":
        how_bot_works(m)
    elif m.text == "💎 Премиум (VIP)":
        info_premium(m)
    elif m.text == "📊 Средние цены":
        show_average_prices(m)
    elif m.text == "🛒 Подать объявление о продаже":
        start_add_ad(m)
    elif m.text == "🚫 Отмена":
        cancel_action(m)
    elif m.text == "📋 Мои объявления":
        show_my_ads(m)
    elif m.text == "❤️ Избранное":
        show_favorites(m)
    elif m.text == "🔍 Поиск по товарам":
        start_search(m)
    elif m.text == "🔔 Подписки на поиск":
        manage_subscriptions(m)
    elif m.text == "👑 Админ":
        admin_panel(m)
    elif m.text == "📝 Подать заявку на админа":
        start_admin_application(m)
    elif m.text in CATEGORIES:
        show_ads_category(m)
    elif m.text in SERVERS:
        select_srv(m)

# ==========================================
# ОСНОВНЫЕ КОМАНДЫ
# ==========================================
def cmd_start(m):
    register_user(m.from_user.id, m.from_user.username)
    
    if is_banned(m.from_user):
        return safe_send_message(m.chat.id, "⛔ Вы заблокированы в системе модерации.", reply_markup=types.ReplyKeyboardRemove())
        
    if is_admin_or_owner(m.from_user):
        register_admin_chat(m.chat.id)
    
    caption_text = (
        "🌟 <b>Приветствую тебя в официальном центре СМИ Arizona RP!</b> 📻\n\n"
        "Здесь ты сможешь быстро и безопасно подать объявление о покупке или продаже транспорта, "
        "аксессуаров, недвижимости, скинов и других ценных вещей на любом сервере проекта.\n\n"
        "⚠️ <b>Безопасность:</b> Бот и редакция <b>никогда</b> не запрашивают пароли от игровых аккаунтов, пин-коды и секретные данные!\n\n"
        "⏱ <b>Режим работы радиоцентра:</b> ежедневно с <b>08:00 до 22:00 МСК</b>.\n\n"
        "👇 <b>Для начала работы выбери свой игровой сервер ниже:</b>"
    )
    safe_send_message(m.chat.id, caption_text, reply_markup=kb_servers())

def cmd_help(m):
    help_text = (
        "🛠 <b>Помощь и часто задаваемые вопросы (FAQ)</b>\n\n"
        "❓ <b>1. Как подать объявление о продаже?</b>\n"
        "💡 <i>Выберите свой сервер в главном меню -> Нажмите кнопку «🛒 Подать объявление о продаже» -> Выберите категорию -> Введите описание товара и цену -> Прикрепите фото (по желанию) и отправьте на модерацию редакторам.</i>\n\n"
        "❓ <b>2. Сколько времени проверяются объявления?</b>\n"
        "💡 <i>Модерация объявлений осуществляется редакторами СМИ в рабочее время: ежедневно с <b>08:00 до 22:00 МСК</b>.</i>\n\n"
        "❓ <b>3. Что такое VIP-объявление и как его получить?</b>\n"
        "💡 <i>VIP-объявления публикуются с приоритетом и выделяются особым значком. Вы можете оформить статус VIP на 30 дней или разово через Telegram Stars (💎).</i>\n\n"
        "❓ <b>4. Как связаться с продавцом товара?</b>\n"
        "💡 <i>Под карточкой каждого опубликованного объявления есть кнопка «✉️ Написать продавцу». Нажав ее, вы сможете напрямую и безопасно пообщаться с владельцем товара прямо в боте.</i>\n\n"
        "❓ <b>5. Мое объявление отклонили, почему это произошло?</b>\n"
        "💡 <i>Возможно, текст нарушает правила редакции (содержит запрещенные слова, ненормативную лексику, рекламу посторонних сторонних ресурсов или неадекватную цену).</i>"
    )
    safe_send_message(m.chat.id, help_text, reply_markup=kb_main_menu())

def change_server(m):
    safe_send_message(m.chat.id, "👇 Выберите новый игровой сервер:", reply_markup=kb_servers())

def how_bot_works(m):
    text = (
        "📖 <b>Справочник: Как работает бот и радиоцентр</b>\n\n"
        "1. <b>Подача объявления:</b> Вы выбираете сервер, категорию, вводите текст товара и цену.\n"
        "2. <b>Проверка редакторами:</b> Редакторы СМИ проверяют текст в рабочие часы (08:00 - 22:00 МСК).\n"
        "3. <b>Публикация:</b> После одобрения объявление появляется в ленте сервера.\n"
        "4. <b>Связь:</b> Покупатель может безопасно написать продавцу через бота."
    )
    safe_send_message(m.chat.id, text)

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
    elif payload == "vip_single_ad_pub":
        st = get_state(uid)
        p_data = st.get("posting_ad")
        if p_data:
            p_data["is_vip"] = 1
            finish_posting(message.chat.id, uid, message.from_user.username, p_data.get("photo_id"))
        else:
            safe_send_message(message.chat.id, "✅ Оплата прошла, но данные сессии сбросились. Начните подачу заново.", reply_markup=kb_main_menu())

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
# ПОДАЧА И МОДЕРАЦИЯ ОБЪЯВЛЕНИЙ
# ==========================================
def start_add_ad(m):
    register_user(m.from_user.id, m.from_user.username)
    if is_banned(m.from_user):
        return safe_send_message(m.chat.id, "⛔ Вы заблокированы.", reply_markup=types.ReplyKeyboardRemove())
    
    if not check_working_hours():
        return safe_send_message(m.chat.id, "⏱ Радиоцентр закрыт! Режим работы: с 08:00 до 22:00 МСК.")

    uid = m.from_user.id
    last_t = get_user_last_ad_time(uid)
    if time.time() - last_t < 120 and not is_admin_or_owner(m.from_user):
        left = int(120 - (time.time() - last_t))
        return safe_send_message(m.chat.id, f"⏳ Подождите еще {left} сек. перед подачей нового объявления.")

    update_state(uid, posting_ad={"step": "server"})
    
    m_kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for s in SERVERS:
        m_kb.add(types.KeyboardButton(s))
    m_kb.add(types.KeyboardButton("🚫 Отмена"))
    
    safe_send_message(m.chat.id, "🏷 Выберите сервер для объявления:", reply_markup=m_kb)

def cancel_action(m):
    uid = m.from_user.id
    st = get_state(uid)
    
    pid = st.get("admin_editing_pid")
    if pid:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE pending_posts SET editing_by = 0, editing_since = 0 WHERE id = ?", (pid,))
            conn.commit()

    clear_state(uid)
    safe_send_message(m.chat.id, "❌ Действие отменено.", reply_markup=kb_main_menu())

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("posting_ad", {}).get("step") == "server")
def process_post_server(m):
    srv = m.text
    if srv not in SERVERS:
        return safe_send_message(m.chat.id, "⚠️ Выберите сервер из списка с помощью кнопок.")
    
    uid = m.from_user.id
    update_state(uid, posting_ad={"server": srv, "step": "category"})

    m_kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for c in CATEGORIES:
        m_kb.add(types.KeyboardButton(c))
    m_kb.add(types.KeyboardButton("🚫 Отмена"))

    safe_send_message(m.chat.id, "📂 Выберите категорию товара:", reply_markup=m_kb)

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("posting_ad", {}).get("step") == "category")
def process_post_category(m):
    cat = m.text
    if cat not in CATEGORIES:
        return safe_send_message(m.chat.id, "⚠️ Выберите категорию из предложенных вариантов.")
    
    uid = m.from_user.id
    st = get_state(uid)
    p_data = st.get("posting_ad", {})
    p_data["category"] = cat
    p_data["step"] = "text"
    update_state(uid, posting_ad=p_data)

    safe_send_message(m.chat.id, "✍️ Введите текст объявления (описание товара, цену и условия):", reply_markup=kb_cancel())

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("posting_ad", {}).get("step") == "text")
def process_post_text(m):
    text = m.text
    if not check_auto_moderation(text):
        return safe_send_message(m.chat.id, "⚠️ Текст содержит запрещенные слова или ссылки. Пожалуйста, исправьте его.")

    uid = m.from_user.id
    st = get_state(uid)
    p_data = st.get("posting_ad", {})
    p_data["text"] = text
    p_data["step"] = "photo"
    update_state(uid, posting_ad=p_data)

    safe_send_message(m.chat.id, "🖼 Отправьте фотографию товара или нажмите «Пропустить»:", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Пропустить", "🚫 Отмена"))

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("posting_ad", {}).get("step") == "photo" and msg.text == "Пропустить")
def process_post_no_photo(m):
    ask_vip_choice(m, None)

@bot.message_handler(content_types=['photo'], func=lambda msg: get_state(msg.from_user.id).get("posting_ad", {}).get("step") == "photo")
def process_post_photo(m):
    photo_id = m.photo[-1].file_id
    ask_vip_choice(m, photo_id)

def ask_vip_choice(m, photo_id):
    uid = m.from_user.id
    st = get_state(uid)
    p_data = st.get("posting_ad", {})
    p_data["photo_id"] = photo_id
    update_state(uid, posting_ad=p_data)

    markup = types.InlineKeyboardMarkup(row_width=1)
    if is_user_premium(uid):
        markup.add(types.InlineKeyboardButton("👑 Опубликовать как VIP (Бесплатно по VIP)", callback_data="post_as_vip_free"))
    else:
        markup.add(types.InlineKeyboardButton("💎 Подать как VIP-объявление (1 Звезда)", pay=True, callback_data="buy_single_vip_star"))
    markup.add(types.InlineKeyboardButton("📄 Опубликовать как обычное (бесплатно)", callback_data="post_as_regular"))

    safe_send_message(m.chat.id, "💎 <b>Выберите формат публикации вашего объявления:</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["post_as_vip_free", "post_as_regular"])
def callback_publish_choice(call):
    uid = call.from_user.id
    st = get_state(uid)
    p_data = st.get("posting_ad")
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if not p_data:
        return safe_send_message(call.message.chat.id, "⚠️ Данные объявления устарели. Начните подачу заново.", reply_markup=kb_main_menu())

    is_vip = 1 if call.data == "post_as_vip_free" else 0
    p_data["is_vip"] = is_vip
    finish_posting(call.message.chat.id, uid, call.from_user.username, p_data.get("photo_id"))

@bot.callback_query_handler(func=lambda c: c.data == "buy_single_vip_star")
def callback_buy_single_vip(call):
    prices = [types.LabeledPrice(label="VIP Объявление (разовое)", amount=1)]
    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title="Разовое VIP-объявление",
            description="Публикация объявления с VIP-статусом за 1 Telegram Star",
            invoice_payload="vip_single_ad_pub",
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

def finish_posting(chat_id: int, user_id: int, username: str, photo_id: str):
    st = get_state(user_id)
    p_data = st.get("posting_ad")
    if not p_data:
        return

    srv = p_data["server"]
    cat = p_data["category"]
    text = p_data["text"]
    is_vip = p_data.get("is_vip", 0)

    uname = username if username else "Без юзернейма"

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO pending_posts (user_id, username, server, category, text, photo, is_vip, editing_by, editing_since)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
        ''', (user_id, uname, srv, cat, text, photo_id, is_vip))
        pid = cur.lastrowid
        conn.commit()

    clear_state(user_id)
    set_user_last_ad_time(user_id, time.time())

    safe_send_message(chat_id, "✅ Объявление отправлено на модерацию редакторам!", reply_markup=kb_main_menu())

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_accept_{pid}"),
        types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"mod_edit_{pid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_reject_{pid}")
    )

    preview = format_smi_post(srv, cat, text, uname, uname if uname != "Без юзернейма" else "", is_vip, user_id)
    
    admin_chats = get_admin_chat_ids()
    for admin_chat_id in admin_chats:
        if photo_id:
            safe_send_photo(admin_chat_id, photo_id, caption=f"📥 <b>Новое объявление на модерацию (ID: {pid}):</b>\n\n{preview}", reply_markup=markup)
        else:
            safe_send_message(admin_chat_id, f"📥 <b>Новое объявление на модерацию (ID: {pid}):</b>\n\n{preview}", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("mod_"))
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

        final_text = format_smi_post(srv, cat, text, uname, editor_uname, is_vip, user_id)
        markup = ikb_ad_actions(aid, is_fav=False)

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

@bot.message_handler(func=lambda msg: "admin_editing_pid" in get_state(msg.from_user.id))
def process_admin_edit_text(m):
    if not is_admin_or_owner(m.from_user):
        return
    
    uid = m.from_user.id
    st = get_state(uid)
    start_t = st.get("edit_start_time", 0)

    if time.time() - start_t > 720:
        clear_state(uid)
        return safe_send_message(m.chat.id, "⌛ Время редактирования истекло (более 12 минут).", reply_markup=kb_main_menu())

    pid = st["admin_editing_pid"]
    new_text = m.text.strip()
    clear_state(uid)

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE pending_posts SET text = ?, editing_by = 0, editing_since = 0 WHERE id = ?", (new_text, pid))
        cur.execute("SELECT user_id, username, server, category, text, photo, is_vip FROM pending_posts WHERE id = ?", (pid,))
        post = cur.fetchone()
        conn.commit()

    if not post:
        return safe_send_message(m.chat.id, "❌ Ошибка: объявление не найдено.", reply_markup=kb_main_menu())

    user_id, uname, srv, cat, text, photo_id, is_vip = post
    editor_uname = m.from_user.username or "Админ"
    preview = format_smi_post(srv, cat, text, uname, editor_uname, is_vip, user_id)

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Опубликовать", callback_data=f"mod_publish_edited_{pid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_reject_{pid}")
    )

    if photo_id:
        safe_send_photo(m.chat.id, photo_id, caption=f"✏️ <b>Отредактированное объявление (ID: {pid}):</b>\n\n{preview}", reply_markup=markup)
    else:
        safe_send_message(m.chat.id, f"✏️ <b>Отредактированное объявление (ID: {pid}):</b>\n\n{preview}", reply_markup=markup)


# ==========================================
# МОИ ОБЪЯВЛЕНИЯ
# ==========================================
def show_my_ads(m):
    uid = m.from_user.id
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, server, category, text, photo FROM pending_posts WHERE user_id = ?", (uid,))
        pending = cur.fetchall()
        cur.execute("SELECT id, server, category, text, photo FROM active_ads WHERE user_id = ?", (uid,))
        active = cur.fetchall()

    text_msg = "📋 <b>Ваши объявления:</b>\n\n⏳ <b>1. В очереди модерации:</b>\n"
    text_msg += "• Нет объявлений.\n\n" if not pending else "".join([f"• [{html.escape(srv)}] {html.escape(cat)}: {html.escape(text[:30])}...\n" for aid, srv, cat, text, photo in pending]) + "\n"
    
    text_msg += "✅ <b>2. Опубликованные:</b>\n"
    text_msg += "• Нет активных объявлений." if not active else "".join([f"• [{html.escape(srv)}] {html.escape(cat)}: {html.escape(text[:30])}...\n" for aid, srv, cat, text, photo in active])

    markup = types.InlineKeyboardMarkup(row_width=1)
    for aid, srv, cat, text, photo in pending:
        markup.add(types.InlineKeyboardButton(f"❌ Отменить ожидающее (ID {aid})", callback_data=f"cancel_pending_{aid}"))
    for aid, srv, cat, text, photo in active:
        markup.add(types.InlineKeyboardButton(f"🗑 Удалить активное (ID {aid})", callback_data=f"cancel_active_{aid}"))

    safe_send_message(m.chat.id, text_msg, reply_markup=markup if (pending or active) else kb_main_menu())

@bot.callback_query_handler(func=lambda c: c.data.startswith("cancel_pending_"))
def cb_cancel_pending(call):
    aid = int(call.data.split("_")[2])
    uid = call.from_user.id
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM pending_posts WHERE id = ? AND user_id = ?", (aid, uid))
        conn.commit()
    try:
        bot.answer_callback_query(call.id, "❌ Вы успешно отменили объявление!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("cancel_active_"))
def cb_cancel_active(call):
    aid = int(call.data.split("_")[2])
    uid = call.from_user.id
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM active_ads WHERE id = ? AND user_id = ?", (aid, uid))
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
        markup = ikb_ad_actions(aid, is_fav=True)
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
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=ikb_ad_actions(aid, is_fav=new_fav))
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
        cur.execute("SELECT id, server, category, text, photo FROM active_ads WHERE server = ? AND LOWER(text) LIKE ? ORDER BY id DESC LIMIT 10", (srv, f"%{query}%"))
        results = cur.fetchall()

    if not results:
        return safe_send_message(m.chat.id, f"🔍 По запросу «{html.escape(query)}» ничего не найдено.", reply_markup=kb_main_menu())

    safe_send_message(m.chat.id, f"🔍 Результаты поиска по запросу «{html.escape(query)}» [{html.escape(srv)}]:")
    for aid, srv_name, cat, text, photo in results:
        markup = ikb_ad_actions(aid, is_fav=False)
        fmt_text = html.escape(text)
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
def process_add_subscription(m):
    uid = m.from_user.id
    kw = m.text.strip()
    srv = get_state(uid).get("server", "Phoenix")
    clear_state(uid)

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO keyword_subscriptions (user_id, server, keyword) VALUES (?, ?, ?)", (uid, srv, kw))
        conn.commit()

    safe_send_message(m.chat.id, f"✅ Подписка на слово «{html.escape(kw)}» создана!", reply_markup=kb_main_menu())

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_sub_"))
def cb_del_sub(call):
    sub_id = int(call.data.split("_")[2])
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM keyword_subscriptions WHERE id = ?", (sub_id,))
        conn.commit()
    try:
        bot.answer_callback_query(call.id, "✅ Подписка удалена!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

def check_keyword_subscriptions(server: str, text: str):
    lower_text = text.lower()
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, keyword FROM keyword_subscriptions WHERE server = ?", (server,))
        subs = cur.fetchall()

    for uid, kw in subs:
        if kw.lower() in lower_text:
            safe_send_message(uid, f"🔔 <b>Найдено по вашей подписке «{html.escape(kw)}»!</b>\n\n{html.escape(text)}")

# ==========================================
# ЧАТ МЕЖДУ ПОКУПАТЕЛЕМ И ПРОДАВЦОМ
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("contact_seller_"))
def cb_contact_seller(call):
    aid = int(call.data.split("_")[2])
    buyer_id = call.from_user.id

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, server, category, text FROM active_ads WHERE id = ?", (aid,))
        ad = cur.fetchone()

    try:
        if not ad:
            return bot.answer_callback_query(call.id, "❌ Объявление удалено или неактивно.", show_alert=True)

        seller_id, server, category, ad_text = ad
        if seller_id == buyer_id:
            return bot.answer_callback_query(call.id, "⚠️ Вы не можете написать самому себе!", show_alert=True)

        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO active_dialogs (buyer_id, seller_id, ad_id, is_active) VALUES (?, ?, ?, 1)", (buyer_id, seller_id, aid))
            conn.commit()

        bot.answer_callback_query(call.id)
    except Exception:
        pass
    
    update_state(buyer_id, active_chat_with=seller_id, ad_id=aid)
    safe_send_message(buyer_id, "✍️ <b>Связь с продавцом установлена.</b> Напишите ваше сообщение (можно прикрепить фото):", reply_markup=ikb_chat_controls(aid))

@bot.callback_query_handler(func=lambda c: c.data.startswith("reply_buyer_"))
def cb_reply_buyer(call):
    parts = call.data.split("_")
    buyer_id = int(parts[2])
    aid = int(parts[3])
    seller_id = call.from_user.id

    update_state(seller_id, active_chat_with=buyer_id, ad_id=aid)
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    safe_send_message(seller_id, "✍️ <b>Режим ответа покупателю включен.</b> Введите ваше сообщение:", reply_markup=ikb_chat_controls(aid))

@bot.callback_query_handler(func=lambda c: c.data.startswith("stop_chat_"))
def cb_stop_chat(call):
    aid = int(call.data.split("_")[2])
    uid = call.from_user.id
    
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE active_dialogs SET is_active = 0 WHERE ad_id = ? AND (buyer_id = ? OR seller_id = ?)", (aid, uid, uid))
        conn.commit()

    clear_state(uid)
    try:
        bot.answer_callback_query(call.id, "🛑 Диалог завершен!")
    except Exception:
        pass
    safe_send_message(call.message.chat.id, "❌ Диалог приостановлен.", reply_markup=kb_main_menu())

@bot.callback_query_handler(func=lambda c: c.data.startswith("resume_chat_"))
def cb_resume_chat(call):
    aid = int(call.data.split("_")[2])
    try:
        bot.answer_callback_query(call.id, "🔄 Диалог возобновлен!")
    except Exception:
        pass
    safe_send_message(call.message.chat.id, "✅ Напишите ваше сообщение пользователю:")

@bot.message_handler(content_types=['text', 'photo'], func=lambda msg: "active_chat_with" in get_state(msg.from_user.id))
def process_dialog_message(m):
    uid = m.from_user.id
    st = get_state(uid)
    target_id = st.get("active_chat_with")
    aid = st.get("ad_id")

    if not target_id:
        clear_state(uid)
        return

    reply_markup = types.InlineKeyboardMarkup()
    reply_markup.add(
        types.InlineKeyboardButton("💬 Ответить", callback_data=f"reply_buyer_{uid}_{aid}"),
        types.InlineKeyboardButton("🛑 Завершить", callback_data=f"stop_chat_{aid}")
    )

    header = f"📩 <b>Новое сообщение по объявлению #{aid}:</b>\n\n"
    try:
        if m.content_type == 'photo':
            photo_id = m.photo[-1].file_id
            caption = header + html.escape(m.caption if m.caption else "")
            safe_send_photo(target_id, photo_id, caption=caption, reply_markup=reply_markup)
        else:
            safe_send_message(target_id, header + html.escape(m.text), reply_markup=reply_markup)
            
        safe_send_message(uid, "✅ Сообщение успешно отправлено!")
    except Exception as e:
        logger.error(f"Ошибка пересылки сообщения в чате: {e}")
        safe_send_message(uid, "❌ Не удалось доставить сообщение. Возможно, пользователь заблокировал бота.")


# ==========================================
# ЗАЯВКА НА АДМИНА
# ==========================================
def start_admin_application(m):
    register_user(m.from_user.id, m.from_user.username)
    if is_banned(m.from_user):
        return safe_send_message(m.chat.id, "⛔ Вы заблокированы.", reply_markup=types.ReplyKeyboardRemove())
    
    if is_admin_or_owner(m.from_user):
        return safe_send_message(m.chat.id, "👑 Вы уже являетесь администратором бота!", reply_markup=kb_main_menu())

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM admin_apps WHERE user_id = ?", (m.from_user.id,))
        if cur.fetchone():
            return safe_send_message(m.chat.id, "⏳ Вы уже подали заявку на администратора. Ожидайте рассмотрения владельцем (@bounqy).", reply_markup=kb_main_menu())

    update_state(m.from_user.id, applying_admin=True)
    safe_send_message(
        m.chat.id, 
        "📝 <b>Подача заявки на пост администратора:</b>\n\n"
        "Расскажите о себе в свободной форме (укажите ваш возраст, игровой опыт, почему хотите стать редактором/админом и сколько времени готовы уделять):\n\n"
        "👇 <i>Отправьте ваш текст ответным сообщением:</i>", 
        reply_markup=kb_cancel()
    )

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("applying_admin"))
def process_admin_application_text(m):
    uid = m.from_user.id
    clear_state(uid)
    text = m.text.strip()
    uname = m.from_user.username or "Без юзернейма"

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO admin_apps (user_id, username, application_text) VALUES (?, ?, ?)", (uid, uname, text))
        conn.commit()

    safe_send_message(m.chat.id, "✅ Ваша заявка на администратора успешно отправлена владельцу (@bounqy) на рассмотрение!", reply_markup=kb_main_menu())

    # Рассылка уведомления владельцу и в админ-чаты с кнопками Принять/Отклонить
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Принять заявку", callback_data=f"app_accept_{uid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"app_reject_{uid}")
    )

    app_msg = (
        f"🚨 <b>Новая заявка на администратора!</b>\n\n"
        f"👤 <b>Кандидат:</b> @{html.escape(uname)} (ID: <code>{uid}</code>)\n\n"
        f"💬 <b>Текст заявки:</b>\n{html.escape(text)}"
    )

    admin_chats = get_admin_chat_ids()
    for chat_id in admin_chats:
        safe_send_message(chat_id, app_msg, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("app_accept_") or c.data.startswith("app_reject_"))
def callback_admin_app_decision(call):
    # Строгое требование: принимать или отклонять заявку может только владелец (@bounqy)
    if not is_owner(call.from_user):
        try:
            return bot.answer_callback_query(call.id, "⛔ Принимать или отклонять заявки на администратора может исключительно владелец бота (@bounqy)!", show_alert=True)
        except Exception:
            return

    parts = call.data.split("_")
    action = parts[1] # accept или reject
    target_uid = int(parts[2])

    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT username FROM admin_apps WHERE user_id = ?", (target_uid,))
        row = cur.fetchone()
        target_uname = row[0] if row else ""
        cur.execute("DELETE FROM admin_apps WHERE user_id = ?", (target_uid,))
        
        if action == "accept":
            cur.execute("INSERT OR IGNORE INTO approved_admins (user_id, username) VALUES (?, ?)", (target_uid, target_uname))
        conn.commit()

    if action == "accept":
        try:
            safe_send_message(
                target_uid, 
                "🎉 <b>Поздравляем! Ваша заявка на администратора была принята владельцем (@bounqy)!</b>\n\n"
                "Вам открыт доступ к панели управления и функциям модерации.", 
                reply_markup=kb_main_menu()
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление пользователю {target_uid}: {e}")

        safe_send_message(call.message.chat.id, f"✅ Вы успешно приняли заявку пользователя ID: <code>{target_uid}</code>. Права администратора выданы.")
    else:
        try:
            safe_send_message(target_uid, "❌ К сожалению, ваша заявка на пост администратора была отклонена владельцем.")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление пользователю {target_uid}: {e}")

        safe_send_message(call.message.chat.id, f"❌ Заявка пользователя ID: <code>{target_uid}</code> отклонена.")

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass


# ==========================================
# АДМИН-ПАНЕЛЬ (Строго контролируется владельцем @bounqy)
# ==========================================
def admin_panel(m):
    if not is_admin_or_owner(m.from_user):
        return safe_send_message(m.chat.id, "⛔ У вас нет доступа к админ-панели.")

    register_admin_chat(m.chat.id)

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Статистика редакторов", callback_data="admin_stats"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("🛠 Управление объявлениями", callback_data="admin_manage_ad")
    )
    # Только владелец (@bounqy) имеет полный доступ к управлению статусами блокировок/админки
    if is_owner(m.from_user):
        markup.add(
            types.InlineKeyboardButton("🚫 Забанить / Убрать админа", callback_data="admin_ban"),
            types.InlineKeyboardButton("🟢 Разбанить / Назначить", callback_data="admin_unban")
        )
    safe_send_message(m.chat.id, "👑 <b>Панель управления администратора:</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_stats")
def cb_admin_stats(call):
    if not verify_admin_callback(call): return
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT username, count FROM editor_stats ORDER BY count DESC LIMIT 10")
        stats = cur.fetchall()

    text = "📊 <b>Статистика работы редакторов:</b>\n\n" + ("Пока нет данных." if not stats else "\n".join([f"• @{html.escape(uname)}: отредактировано постов — <b>{cnt}</b>" for uname, cnt in stats]))
    try: bot.answer_callback_query(call.id)
    except: pass
    safe_send_message(call.message.chat.id, text)

@bot.callback_query_handler(func=lambda c: c.data == "admin_ban")
def cb_admin_ban(call):
    if not is_owner(call.from_user):
        try: return bot.answer_callback_query(call.id, "⛔ Это действие доступно исключительно владельцу бота (@bounqy)!", show_alert=True)
        except: return
    update_state(call.from_user.id, admin_action="ban")
    try: bot.answer_callback_query(call.id)
    except: pass
    safe_send_message(call.message.chat.id, "🚫 Введите username (без @) или ID пользователя для блокировки / снятия прав:", reply_markup=kb_cancel())

@bot.callback_query_handler(func=lambda c: c.data == "admin_unban")
def cb_admin_unban(call):
    if not is_owner(call.from_user):
        try: return bot.answer_callback_query(call.id, "⛔ Принимать на админку и разблокировать может исключительно владелец бота (@bounqy)!", show_alert=True)
        except: return
    update_state(call.from_user.id, admin_action="unban")
    try: bot.answer_callback_query(call.id)
    except: pass
    safe_send_message(call.message.chat.id, "🟢 Введите username (без @) или ID для разблокировки / приема на админку:", reply_markup=kb_cancel())

@bot.callback_query_handler(func=lambda c: c.data == "admin_broadcast")
def cb_admin_broadcast(call):
    if not verify_admin_callback(call): return
    update_state(call.from_user.id, admin_action="broadcast")
    try: bot.answer_callback_query(call.id)
    except: pass
    safe_send_message(call.message.chat.id, "📢 Введите текст массовой рассылки:", reply_markup=kb_cancel())

@bot.callback_query_handler(func=lambda c: c.data == "admin_manage_ad")
def cb_admin_manage_ad(call):
    if not verify_admin_callback(call): return
    try: bot.answer_callback_query(call.id)
    except: pass
    
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, server, category, text, photo FROM active_ads ORDER BY id DESC LIMIT 10")
        ads = cur.fetchall()
        
    if not ads:
        return safe_send_message(call.message.chat.id, "📭 Нет активных объявлений для управления.", reply_markup=kb_main_menu())
        
    safe_send_message(call.message.chat.id, "🛠 <b>Управление активными объявлениями (последние 10):</b>")
    for aid, srv, cat, text, photo in ads:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_del_ad_{aid}"),
            types.InlineKeyboardButton("✏️ Изменить текст", callback_data=f"adm_edit_ad_{aid}")
        )
        preview = f"<b>ID: {aid}</b> | [{srv}] {cat}\n{text[:120]}..."
        if photo:
            safe_send_photo(call.message.chat.id, photo, caption=preview, reply_markup=markup)
        else:
            safe_send_message(call.message.chat.id, preview, reply_markup=markup)

@bot.message_handler(func=lambda msg: "admin_action" in get_state(msg.from_user.id))
def process_admin_input(m):
    if not is_admin_or_owner(m.from_user): return
    
    uid = m.from_user.id
    st = get_state(uid)
    action = st.get("admin_action")
    clear_state(uid)
    val = m.text.strip()

    if action in ["ban", "unban"]:
        if not is_owner(m.from_user):
            return safe_send_message(m.chat.id, "⛔ Ошибка доступа! Принимать на админку и управлять блокировками может исключительно владелец (@bounqy).")
        target = val.lstrip('@').lower()
        
        target_uid = None
        if target.isdigit():
            target_uid = int(target)
        else:
            with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
                cur = conn.cursor()
                cur.execute("SELECT user_id FROM user_data WHERE LOWER(username) = ?", (target,))
                row = cur.fetchone()
                if row:
                    target_uid = row[0]
                else:
                    cur.execute("SELECT user_id FROM pending_posts WHERE LOWER(username) = ? LIMIT 1", (target,))
                    row2 = cur.fetchone()
                    if row2:
                        target_uid = row2[0]

        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            if action == "ban":
                is_id = 1 if target.isdigit() else 0
                cur.execute("INSERT OR REPLACE INTO bans (target, is_id) VALUES (?, ?)", (target, is_id))
                cur.execute("DELETE FROM approved_admins WHERE user_id = ? OR LOWER(username) = ?", (target_uid or 0, target))
                msg_txt = f"✅ Пользователь <code>{html.escape(target)}</code> заблокирован / снят с прав владельцем (@bounqy)."
                if target_uid:
                    try:
                        safe_send_message(
                            target_uid, 
                            "⛔ <b>Вы были заблокированы владельцем бота.</b> Ваши кнопки отключены, доступ к функциям ограничен.", 
                            reply_markup=types.ReplyKeyboardRemove()
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить уведомление о бане пользователю {target_uid}: {e}")
            else:
                cur.execute("DELETE FROM bans WHERE target = ?", (target,))
                if target_uid:
                    cur.execute("INSERT OR IGNORE INTO approved_admins (user_id, username) VALUES (?, ?)", (target_uid, target))
                msg_txt = f"✅ Пользователь <code>{html.escape(target)}</code> успешно принят на админку / разблокирован владельцем (@bounqy)."
                if target_uid:
                    try:
                        safe_send_message(
                            target_uid, 
                            "✅ <b>Ваш статус был обновлен владельцем (@bounqy)!</b> Доступ и клавиатура восстановлены.", 
                            reply_markup=kb_main_menu()
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить уведомление пользователю {target_uid}: {e}")
            conn.commit()
        safe_send_message(m.chat.id, msg_txt, reply_markup=kb_main_menu())

    elif action == "broadcast":
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT user_id FROM user_data")
            users = cur.fetchall()

        success = 0
        for (u_id,) in users:
            try:
                safe_send_message(u_id, f"📢 <b>Сообщение от администрации:</b>\n\n{html.escape(val)}")
                success += 1
            except: pass
        safe_send_message(m.chat.id, f"✅ Рассылка завершена. Доставлено: {success} пользователям.", reply_markup=kb_main_menu())

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_del_ad_"))
def cb_adm_del_ad(call):
    if not verify_admin_callback(call): return
    aid = int(call.data.split("_")[3])
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM active_ads WHERE id = ?", (aid,))
        conn.commit()
    try:
        bot.answer_callback_query(call.id, "✅ Объявление удалено.")
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_edit_ad_"))
def cb_adm_edit_ad(call):
    if not verify_admin_callback(call): 
        return
    aid = int(call.data.split("_")[3])
    update_state(call.from_user.id, admin_editing_active_aid=aid)
    try: bot.answer_callback_query(call.id)
    except: pass
    safe_send_message(call.message.chat.id, f"✏️ Введите новый текст для объявления #{aid}:", reply_markup=kb_cancel())

@bot.message_handler(func=lambda msg: "admin_editing_active_aid" in get_state(msg.from_user.id))
def process_admin_edit_active(m):
    if not is_admin_or_owner(m.from_user): 
        clear_state(m.from_user.id)
        return safe_send_message(m.chat.id, "⛔ У вас нет прав на редактирование объявлений.")
        
    uid = m.from_user.id
    st = get_state(uid)
    aid = st["admin_editing_active_aid"]
    clear_state(uid)
    
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE active_ads SET text = ? WHERE id = ?", (m.text, aid))
        conn.commit()
        
    safe_send_message(m.chat.id, f"✅ Текст объявления #{aid} успешно изменен!", reply_markup=kb_main_menu())


# ==========================================
# ПРОСМОТР КАТЕГОРИЙ С ПАГИНАЦИЕЙ
# ==========================================
def show_ads_category(m):
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
        return safe_send_message(chat_id, f"📊 Раздел: <b>{html.escape(cat_name)}</b> [{html.escape(srv)}]\nОбъявлений пока нет.", reply_markup=kb_main_menu())

    total_ads = len(all_ads)
    start_idx = page * ADS_PER_PAGE
    end_idx = start_idx + ADS_PER_PAGE
    page_ads = all_ads[start_idx:end_idx]

    if not page_ads:
        return safe_send_message(chat_id, "📄 На этой странице больше нет объявлений.", reply_markup=kb_main_menu())

    safe_send_message(chat_id, f"📂 <b>Раздел:</b> {html.escape(cat_name)} [{html.escape(srv)}] (Страница {page + 1}):")

    for aid, seller_uid, text, photo in page_ads:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM favorites WHERE user_id = ? AND ad_id = ?", (user_id, aid))
            is_fav = bool(cur.fetchone())

        markup = ikb_ad_actions(aid, is_fav=is_fav)
        fmt_text = html.escape(text)
        if photo:
            safe_send_photo(chat_id, photo, caption=fmt_text, reply_markup=markup)
        else:
            safe_send_message(chat_id, fmt_text, reply_markup=markup)

    nav_markup = types.InlineKeyboardMarkup(row_width=2)
    nav_btns = []
    if page > 0:
        nav_btns.append(types.InlineKeyboardButton("⏮ Назад", callback_data=f"cat_page_{cat_idx}_{page - 1}"))
    if end_idx < total_ads:
        nav_btns.append(types.InlineKeyboardButton("Вперед ⏭", callback_data=f"cat_page_{cat_idx}_{page + 1}"))
    
    if nav_btns:
        nav_markup.add(*nav_btns)
        safe_send_message(chat_id, f"📑 Страница {page + 1} из {(total_ads + ADS_PER_PAGE - 1) // ADS_PER_PAGE}:", reply_markup=nav_markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cat_page_"))
def cb_category_page(call):
    parts = call.data.split("_")
    cat_idx = int(parts[2])
    page = int(parts[3])
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    render_category_page(call.message.chat.id, call.from_user.id, cat_idx, page=page)

def select_srv(m):
    update_state(m.from_user.id, server=m.text)
    safe_send_message(m.chat.id, f"Сервер <b>{html.escape(m.text)}</b> выбран!", reply_markup=kb_main_menu())

# ==========================================
# ЗАПУСК БОТА
# ==========================================
if __name__ == '__main__':
    try:
        bot.remove_webhook()
    except Exception:
        pass

    logger.info("🚀 Бот полностью обновлен и запущен!")
    bot.infinity_polling(skip_pending=True)
