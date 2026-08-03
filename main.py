import os
import time
import threading
import logging
import sqlite3
import re
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

TOKEN = os.getenv("BOT_TOKEN", "8916669266:AAEKhCxOrvEsz1RgwNdOZinC7X7vKbJ_CLg")
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
    "👑 Админ", "🚫 Отмена"
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
        user_states[uid] = data

def update_state(uid: int, **kwargs):
    with state_lock:
        if uid not in user_states:
            user_states[uid] = {}
        user_states[uid].update(kwargs)

def clear_state(uid: int):
    with state_lock:
        user_states.pop(uid, None)

# ==========================================
# БЕЗОПАСНАЯ ОТПРАВКА СООБЩЕНИЙ
# ==========================================
def safe_send_message(chat_id, text, parse_mode="Markdown", reply_markup=None):
    try:
        return bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)
    except ApiTelegramException:
        return bot.send_message(chat_id, text, parse_mode=None, reply_markup=reply_markup)

def safe_send_photo(chat_id, photo, caption, parse_mode="Markdown", reply_markup=None):
    try:
        return bot.send_photo(chat_id, photo, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)
    except ApiTelegramException:
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

        conn.commit()

init_db()

# ==========================================
# ВСПАМОГАТЕЛЬНЫЕ ФУНКЦИИ
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
    return bool(user.username and user.username.lower() in ADMIN_USERNAMES)

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
    clean_srv = clean_server_name(server)
    is_prem = is_user_premium(user_id) if user_id else False
    
    if is_vip:
        player_contact = "🛡️ [Контакт скрыт по желанию VIP]"
        vip_header = "👑 **[VIP ОБЪЯВЛЕНИЕ]**\n"
    else:
        player_contact = f"@{player_username}" if player_username and player_username != "Без юзернейма" else "Не указан"
        vip_header = ""

    editor_contact = f"@{editor_username}" if editor_username else "СМИ"
    prem_icon = "💎 " if is_prem else ""
    rating_str = get_seller_rating_info(user_id) if user_id else ""

    return (
        f"{vip_header}"
        f"📰 | **[СМИ {clean_srv}] Объявление:** {prem_icon}\n"
        f"📞 **Контакт игрока:** {player_contact} | {rating_str}\n\n"
        f"{text}\n\n"
        f"📂 **Раздел:** {category}\n"
        f"👨‍💻 **Отредактировал:** {editor_contact}"
    )

def background_cleanup_ads():
    while True:
        time.sleep(300)
        now_time = datetime.now().time()
        curr_t = time.time()

        is_morning_clean = dtime(8, 0, 0) <= now_time <= dtime(8, 5, 0)

        try:
            with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
                cur = conn.cursor()
                if is_morning_clean:
                    cur.execute("DELETE FROM active_ads")
                else:
                    expired_limit = curr_t - 600
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
# МИДДЛВЕЙР СБРОСА СОСТОЯНИЙ ПРИ НАЖАТИИ СИСТЕМНЫХ КНОПОК
# ==========================================
@bot.message_handler(func=lambda msg: msg.text in SYSTEM_NAV_BUTTONS or msg.text.startswith('/'), priority=10)
def handle_navigation_override(m):
    clear_state(m.from_user.id)
    
    # Редирект на нужные функции
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
    elif m.text in CATEGORIES:
        show_ads_category(m)
    elif m.text in SERVERS:
        select_srv(m)

# ==========================================
# ОСНОВНЫЕ КОМАНДЫ И НАВИГАЦИЯ
# ==========================================
def cmd_start(m):
    if is_banned(m.from_user):
        return safe_send_message(m.chat.id, "⛔ Вы заблокированы в системе модерации.")
        
    if is_admin_or_owner(m.from_user):
        register_admin_chat(m.chat.id)
    
    caption_text = (
        "👋 **Добро пожаловать в неофициальный бот СМИ Arizona RP!**\n\n"
        "⚠️ **Важная информация:** Мы являемся фанатским неофициальным проектом, созданным обычным игроком. "
        "**Мы никогда не просим у вас пароль от аккаунта, пин-коды, рег. данные и другие секретные сведения!** Никогда и никому не сообщайте их.\n\n"
        "⏱ **Режим работы радиоцентра:** ежедневно с **08:00 до 22:00 МСК**.\n\n"
        "👇 **Для начала работы выберите ваш игровой сервер:**"
    )
    safe_send_message(m.chat.id, caption_text, reply_markup=kb_servers())

def cmd_help(m):
    help_text = (
        "🛠 **Помощь и часто задаваемые вопросы (FAQ)**\n\n"
        "❓ **1. Как подать объявление?**\n"
        "• Выберите свой сервер в главном меню.\n"
        "• Нажмите кнопку «🛒 Подать объявление о продаже».\n"
        "• Выберите категорию, введите текст товара/цену и прикрепите фото (или пропустите его).\n"
        "• Выберите формат (обычное или VIP) — после этого объявление отправится на проверку редакторам.\n\n"
        "❓ **2. Сколько времени проверяется объявление?**\n"
        "• Модерация объявлений редакторами происходит в рабочие часы радиоцентра: с **08:00 до 22:00 МСК**.\n\n"
        "❓ **3. Что делать, если не работает какая-то кнопка или бот завис?**\n"
        "• Попробуйте перезапустить бот командой /start.\n"
        "• Если проблема сохраняется, обратитесь в наше сообщество ВК: **@bountyarz**.\n\n"
        "❓ **4. Безопасно ли использовать бот?**\n"
        "• Да. Бот создан игроками для игроков. Мы **никогда** не запрашиваем личные данные от аккаунтов."
    )
    safe_send_message(m.chat.id, help_text, reply_markup=kb_main_menu())

def change_server(m):
    safe_send_message(m.chat.id, "👇 Выберите новый игровой сервер:", reply_markup=kb_servers())

def how_bot_works(m):
    text = (
        "📖 **Справочник: Как работает бот и радиоцентр**\n\n"
        "1. **Подача объявления:** Вы выбираете свой сервер, категорию, вводите текст товара и цену. Объявление отправляется на модерацию редакторам.\n"
        "2. **Проверка редакторами:** Редакторы СМИ проверяют текст на ошибки и соответствие правилам (в рабочие часы с 08:00 до 22:00 МСК).\n"
        "3. **Публикация:** После одобрения объявление появляется в ленте выбранного сервера.\n"
        "4. **Связь с продавцом:** Нажав на кнопку под товаром, покупатель может безопасно написать продавцу прямо через бота.\n"
        "5. **Избранное и Подписки:** Вы можете добавлять товары в избранное или настраивать ключевые слова для уведомлений."
    )
    safe_send_message(m.chat.id, text)

def info_premium(m):
    is_prem = is_user_premium(m.from_user.id)
    status_text = "✅ **Ваш VIP-статус активен!**" if is_prem else "❌ **У вас нет активного VIP-статуса.**"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Купить VIP (10 Звезд / 30 дней)", pay=True, callback_data="buy_vip_stars"))

    text = (
        f"💎 **Премиум-статус (VIP) в боте**\n\n"
        f"{status_text}\n\n"
        "Преимущества VIP статуса:\n"
        "• Значок премиум-аккаунта в ваших объявлениях\n"
        "• Приоритетное размещение товаров\n"
        "• Увеличенные лимиты и расширенные возможности поиска\n\n"
        "Стоимость: **10 Telegram Stars** на 30 дней."
    )
    safe_send_message(m.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "buy_vip_stars")
def send_invoice_vip(call):
    prices = [types.LabeledPrice(label="VIP Статус на 30 дней", amount=10)]
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
            finish_posting(message, p_data.get("photo_id"))
        else:
            safe_send_message(message.chat.id, "✅ Оплата прошла, но данные сессии сбросились. Начните подачу заново.", reply_markup=kb_main_menu())

# ==========================================
# СРЕДНИЕ ЦЕНЫ
# ==========================================
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
            f"📊 На сервере **{srv}** пока недостаточно данных для расчета средних цен.", 
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

    report = f"📊 **Динамические средние цены на сервере {srv}:**\n\n"
    
    for cat in CATEGORIES:
        prices = category_prices[cat]
        if prices:
            avg_val = sum(prices) / len(prices)
            min_val = min(prices)
            max_val = max(prices)
            
            report += f"📂 **{cat}**:\n"
            report += f"• Средняя цена: **{format_price(avg_val)}**\n"
            report += f"• Диапазон: от {format_price(min_val)} до {format_price(max_val)}\n"
            report += f"• Учтено объявлений: {len(prices)}\n\n"
        else:
            report += f"📂 **{cat}**:\n• *Нет данных о ценах*\n\n"

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
    if is_banned(m.from_user):
        return safe_send_message(m.chat.id, "⛔ Вы заблокированы.")
    
    if not check_working_hours():
        return safe_send_message(m.chat.id, "⏱ Радиоцентр закрыт! Режим работы: с 08:00 до 22:00 МСК.")

    uid = m.from_user.id
    last_t = get_user_last_ad_time(uid)
    if time.time() - last_t < 120 and not is_admin_or_owner(m.from_user):
        left = int(120 - (time.time() - last_t))
        return safe_send_message(m.chat.id, f"⏳ Подождите еще {left} сек. перед подачей нового объявления.")

    set_state(uid, {"posting_ad": {"step": "server"}})
    
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

def m_is_in_posting(uid, step):
    st = get_state(uid)
    return "posting_ad" in st and st["posting_ad"].get("step") == step

@bot.message_handler(func=lambda msg: m_is_in_posting(msg.from_user.id, "server"))
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

@bot.message_handler(func=lambda msg: m_is_in_posting(msg.from_user.id, "category"))
def process_post_category(m):
    cat = m.text
    if cat not in CATEGORIES:
        return safe_send_message(m.chat.id, "⚠️ Выберите категорию из предложенных вариантов.")
    
    uid = m.from_user.id
    st = get_state(uid)
    p_data = st.get("posting_ad", {})
    p_data["category"] = cat
    p_data["step"] = "text"
    set_state(uid, {"posting_ad": p_data})

    safe_send_message(m.chat.id, "✍️ Введите текст объявления (описание товара, цену и условия):", reply_markup=kb_cancel())

@bot.message_handler(func=lambda msg: m_is_in_posting(msg.from_user.id, "text"))
def process_post_text(m):
    text = m.text
    if not check_auto_moderation(text):
        return safe_send_message(m.chat.id, "⚠️ Текст содержит запрещенные слова или ссылки. Пожалуйста, исправьте его.")

    uid = m.from_user.id
    st = get_state(uid)
    p_data = st.get("posting_ad", {})
    p_data["text"] = text
    p_data["step"] = "photo"
    set_state(uid, {"posting_ad": p_data})

    safe_send_message(m.chat.id, "🖼 Отправьте фотографию товара или нажмите «Пропустить»:", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Пропустить", "🚫 Отмена"))

@bot.message_handler(func=lambda msg: m_is_in_posting(msg.from_user.id, "photo") and msg.text == "Пропустить")
def process_post_no_photo(m):
    ask_vip_choice(m, None)

@bot.message_handler(content_types=['photo'], func=lambda msg: m_is_in_posting(msg.from_user.id, "photo"))
def process_post_photo(m):
    photo_id = m.photo[-1].file_id
    ask_vip_choice(m, photo_id)

def ask_vip_choice(m, photo_id):
    uid = m.from_user.id
    st = get_state(uid)
    p_data = st.get("posting_ad", {})
    p_data["photo_id"] = photo_id
    set_state(uid, {"posting_ad": p_data})

    markup = types.InlineKeyboardMarkup(row_width=1)
    if is_user_premium(uid):
        markup.add(types.InlineKeyboardButton("👑 Опубликовать как VIP (Бесплатно по VIP)", callback_data="post_as_vip_free"))
    else:
        markup.add(types.InlineKeyboardButton("💎 Подать как VIP-объявление (1 Звезда)", pay=True, callback_data="buy_single_vip_star"))
    markup.add(types.InlineKeyboardButton("📄 Опубликовать как обычное (бесплатно)", callback_data="post_as_regular"))

    safe_send_message(m.chat.id, "💎 **Выберите формат публикации вашего объявления:**", reply_markup=markup)

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
    finish_posting(call.message, p_data.get("photo_id"))

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

def finish_posting(m, photo_id):
    uid = m.from_user.id if hasattr(m, "from_user") and m.from_user else m.chat.id
    chat_id = m.chat.id if hasattr(m, "chat") else uid
    
    st = get_state(uid)
    p_data = st.get("posting_ad")
    if not p_data:
        return

    srv = p_data["server"]
    cat = p_data["category"]
    text = p_data["text"]
    is_vip = p_data.get("is_vip", 0)

    uname = m.from_user.username if (hasattr(m, "from_user") and m.from_user and m.from_user.username) else "Без юзернейма"

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO pending_posts (user_id, username, server, category, text, photo, is_vip, editing_by, editing_since)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
        ''', (uid, uname, srv, cat, text, photo_id, is_vip))
        pid = cur.lastrowid
        conn.commit()

    clear_state(uid)
    set_user_last_ad_time(uid, time.time())

    safe_send_message(chat_id, "✅ Объявление отправлено на модерацию редакторам!", reply_markup=kb_main_menu())

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_accept_{pid}"),
        types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"mod_edit_{pid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_reject_{pid}")
    )

    preview = format_smi_post(srv, cat, text, uname, uname if uname != "Без юзернейма" else "", is_vip, uid)
    
    admin_chats = get_admin_chat_ids()
    for admin_chat_id in admin_chats:
        if photo_id:
            safe_send_photo(admin_chat_id, photo_id, caption=f"📥 **Новое объявление на модерацию (ID: {pid}):**\n\n{preview}", reply_markup=markup)
        else:
            safe_send_message(admin_chat_id, f"📥 **Новое объявление на модерацию (ID: {pid}):**\n\n{preview}", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("mod_"))
def callback_moderation(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if not verify_admin_callback(call):
        return

    parts = call.data.split("_")
    action = parts[1]
    pid = int(parts[2])
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

        set_state(admin_id, {"admin_editing_pid": pid, "edit_start_time": curr_time})
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
        types.InlineKeyboardButton("✅ Опубликовать отредактированное", callback_data=f"mod_publish_edited_{pid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_reject_{pid}")
    )

    if photo_id:
        safe_send_photo(m.chat.id, photo_id, caption=f"✏️ **Отредактированное объявление (ID: {pid}):**\n\n{preview}", reply_markup=markup)
    else:
        safe_send_message(m.chat.id, f"✏️ **Отредактированное объявление (ID: {pid}):**\n\n{preview}", reply_markup=markup)

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

    text_msg = "📋 **Ваши объявления:**\n\n⏳ **1. В очереди модерации:**\n"
    text_msg += "• Нет объявлений.\n\n" if not pending else "".join([f"• [{srv}] {cat}: {text[:30]}...\n" for aid, srv, cat, text, photo in pending]) + "\n"
    
    text_msg += "✅ **2. Опубликованные:**\n"
    text_msg += "• Нет активных объявлений." if not active else "".join([f"• [{srv}] {cat}: {text[:30]}...\n" for aid, srv, cat, text, photo in active])

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

    safe_send_message(m.chat.id, "❤️ **Ваши сохраненные объявления:**")
    for aid, srv, cat, text, photo in favs:
        markup = ikb_ad_actions(aid, is_fav=True)
        if photo:
            safe_send_photo(m.chat.id, photo, caption=text, reply_markup=markup)
        else:
            safe_send_message(m.chat.id, text, reply_markup=markup)

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
    set_state(m.from_user.id, {"searching": True})
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
        return safe_send_message(m.chat.id, f"🔍 По запросу «{query}» ничего не найдено.", reply_markup=kb_main_menu())

    safe_send_message(m.chat.id, f"🔍 Результаты поиска по запросу «{query}» [{srv}]:")
    for aid, srv_name, cat, text, photo in results:
        markup = ikb_ad_actions(aid, is_fav=False)
        if photo:
            safe_send_photo(m.chat.id, photo, caption=text, reply_markup=markup)
        else:
            safe_send_message(m.chat.id, text, reply_markup=markup)

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

    safe_send_message(m.chat.id, "🔔 **Ваши подписки на ключевые слова:**", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "add_sub_start")
def cb_add_sub_start(call):
    set_state(call.from_user.id, {"adding_sub": True})
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

    safe_send_message(m.chat.id, f"✅ Подписка на слово «{kw}» создана!", reply_markup=kb_main_menu())

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
            safe_send_message(uid, f"🔔 **Найдено по вашей подписке «{kw}»!**\n\n{text}")

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
    
    set_state(buyer_id, {"active_chat_with": seller_id, "ad_id": aid})
    safe_send_message(buyer_id, "✍️ **Связь с продавцом установлена.** Напишите ваше сообщение (можно прикрепить фото):", reply_markup=ikb_chat_controls(aid))

@bot.callback_query_handler(func=lambda c: c.data.startswith("reply_buyer_"))
def cb_reply_buyer(call):
    parts = call.data.split("_")
    buyer_id = int(parts[2])
    aid = int(parts[3])
    seller_id = call.from_user.id

    set_state(seller_id, {"active_chat_with": buyer_id, "ad_id": aid})
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    safe_send_message(seller_id, "✍️ **Режим ответа покупателю включен.** Введите ваше сообщение:", reply_markup=ikb_chat_controls(aid))

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

    header = f"📩 **Новое сообщение по объявлению #{aid}:**\n\n"
    try:
        if m.content_type == 'photo':
            photo_id = m.photo[-1].file_id
            caption = header + (m.caption if m.caption else "")
            safe_send_photo(target_id, photo_id, caption=caption, reply_markup=reply_markup)
        else:
            safe_send_message(target_id, header + m.text, reply_markup=reply_markup)
            
        safe_send_message(uid, "✅ Сообщение успешно отправлено!")
    except Exception as e:
        logger.error(f"Ошибка пересылки сообщения в чате: {e}")
        safe_send_message(uid, "❌ Не удалось доставить сообщение. Возможно, пользователь заблокировал бота.")

# ==========================================
# АДМИН-ПАНЕЛЬ
# ==========================================
def admin_panel(m):
    if not is_admin_or_owner(m.from_user):
        return safe_send_message(m.chat.id, "⛔ У вас нет доступа к админ-панели.")

    register_admin_chat(m.chat.id)

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Статистика редакторов", callback_data="admin_stats"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("🚫 Забанить", callback_data="admin_ban"),
        types.InlineKeyboardButton("🟢 Разбанить", callback_data="admin_unban")
    )
    safe_send_message(m.chat.id, "👑 **Панель управления администратора:**", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_stats")
def cb_admin_stats(call):
    if not verify_admin_callback(call):
        return

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT username, count FROM editor_stats ORDER BY count DESC LIMIT 10")
        stats = cur.fetchall()

    text = "📊 **Статистика работы редакторов:**\n\n" + ("Пока нет данных." if not stats else "\n".join([f"• @{uname}: отредактировано постов — **{cnt}**" for uname, cnt in stats]))
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    safe_send_message(call.message.chat.id, text)

@bot.callback_query_handler(func=lambda c: c.data == "admin_ban")
def cb_admin_ban(call):
    if not is_owner(call.from_user):
        try:
            return bot.answer_callback_query(call.id, "⛔ Заблокировать может только владелец бота!", show_alert=True)
        except Exception:
            return
    
    set_state(call.from_user.id, {"admin_action": "ban"})
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    safe_send_message(call.message.chat.id, "🚫 Введите username (без @) или ID пользователя:", reply_markup=kb_cancel())

@bot.callback_query_handler(func=lambda c: c.data == "admin_unban")
def cb_admin_unban(call):
    if not is_owner(call.from_user):
        try:
            return bot.answer_callback_query(call.id, "⛔ Разблокировать может только владелец бота!", show_alert=True)
        except Exception:
            return
    
    set_state(call.from_user.id, {"admin_action": "unban"})
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    safe_send_message(call.message.chat.id, "🟢 Введите username (без @) или ID для разблокировки:", reply_markup=kb_cancel())

@bot.callback_query_handler(func=lambda c: c.data == "admin_broadcast")
def cb_admin_broadcast(call):
    if not verify_admin_callback(call):
        return
    set_state(call.from_user.id, {"admin_action": "broadcast"})
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    safe_send_message(call.message.chat.id, "📢 Введите текст массовой рассылки:", reply_markup=kb_cancel())

@bot.message_handler(func=lambda msg: "admin_action" in get_state(msg.from_user.id))
def process_admin_input(m):
    if not is_admin_or_owner(m.from_user):
        return
    
    uid = m.from_user.id
    st = get_state(uid)
    action = st.get("admin_action")
    clear_state(uid)
    val = m.text.strip()

    if action in ["ban", "unban"]:
        if not is_owner(m.from_user):
            return safe_send_message(m.chat.id, "⛔ Только владелец может выполнять это действие.")
        target = val.lstrip('@').lower()
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            if action == "ban":
                is_id = 1 if val.isdigit() else 0
                cur.execute("INSERT OR REPLACE INTO bans (target, is_id) VALUES (?, ?)", (target, is_id))
                msg_txt = f"✅ Пользователь `{target}` заблокирован."
            else:
                cur.execute("DELETE FROM bans WHERE target = ?", (target,))
                msg_txt = f"✅ Пользователь `{target}` разблокирован."
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
                safe_send_message(u_id, f"📢 **Сообщение от администрации:**\n\n{val}")
                success += 1
            except Exception:
                pass
        safe_send_message(m.chat.id, f"✅ Рассылка завершена. Доставлено: {success} пользователям.", reply_markup=kb_main_menu())

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
        return safe_send_message(chat_id, f"📊 Раздел: **{cat_name}** [{srv}]\nОбъявлений пока нет.", reply_markup=kb_main_menu())

    total_ads = len(all_ads)
    start_idx = page * ADS_PER_PAGE
    end_idx = start_idx + ADS_PER_PAGE
    page_ads = all_ads[start_idx:end_idx]

    if not page_ads:
        return safe_send_message(chat_id, "📄 На этой странице больше нет объявлений.", reply_markup=kb_main_menu())

    safe_send_message(chat_id, f"📂 **Раздел:** {cat_name} [{srv}] (Страница {page + 1}):")

    for aid, seller_uid, text, photo in page_ads:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM favorites WHERE user_id = ? AND ad_id = ?", (user_id, aid))
            is_fav = bool(cur.fetchone())

        markup = ikb_ad_actions(aid, is_fav=is_fav)
        if photo:
            safe_send_photo(chat_id, photo, caption=text, reply_markup=markup)
        else:
            safe_send_message(chat_id, text, reply_markup=markup)

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
    safe_send_message(m.chat.id, f"Сервер **{m.text}** выбран!", reply_markup=kb_main_menu())

# ==========================================
# ЗАПУСК БОТА
# ==========================================
if __name__ == '__main__':
    try:
        bot.remove_webhook()
    except Exception:
        pass

    logger.info("🚀 Бот обновлен и запущен с исправленной системой кнопок!")
    bot.infinity_polling(skip_pending=True)
