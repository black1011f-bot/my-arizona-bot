import os
import time
import threading
import logging
import sqlite3
from datetime import datetime, time as dtime
import telebot
from telebot import types

# ==========================================
# ЛОГИРОВАНИЕ И КОНФИГУРАЦИЯ
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN", "8916669266:AAGMsyFa-_OZBs8beZ7vIEi8bKX6uvRUrM8")
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=20)

OWNER_USERNAME = "bounqy"
ADMIN_USERNAMES = {"bounqy31", "bounqy"}

ADMIN_CHAT_IDS = set() 
MODERATION_CHAT_ID = int(os.getenv("MODERATION_CHAT_ID", "0"))

WELCOME_VIDEO_ID = "YOUR_VIDEO_FILE_ID_HERE" 

DB_NAME = "smi_bot.db"
db_lock = threading.Lock()

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

# Список запрещенных слов для автомодерации (мат, оскорбления, сторонние проекты)
BAD_WORDS = [
    "хуй", "пизд", "еб", "бля", "сук", "залуп", "мраз", "ебан", "долбоеб", 
    "samp-rp", "advance", "Arizona V", "Diamond", "продажа вирт", "продам вирты"
]

# ==========================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ (SQLite)
# ==========================================
def init_db():
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
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
                is_vip INTEGER
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
            CREATE TABLE IF NOT EXISTS pending_bans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                admin_username TEXT,
                target TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_message_limits (
                user_id INTEGER PRIMARY KEY,
                msg_count INTEGER,
                last_reset_date TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                sender_id INTEGER,
                sender_username TEXT,
                recipient_id INTEGER,
                message_text TEXT
            )
        ''')

        # 1. Избранное
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER,
                ad_id INTEGER,
                PRIMARY KEY (user_id, ad_id)
            )
        ''')

        # 2. Подписка на ключевые слова (Умный поиск)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keyword_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                server TEXT,
                keyword TEXT
            )
        ''')

        # 3. Отзывы и рейтинг продавцов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seller_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER,
                buyer_id INTEGER,
                rating INTEGER,
                comment TEXT
            )
        ''')

        # 4. Премиум-подписка
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS premium_users (
                user_id INTEGER PRIMARY KEY,
                expires_at REAL
            )
        ''')

        conn.commit()
        conn.close()

init_db()

def is_user_premium(user_id: int) -> bool:
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT expires_at FROM premium_users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        if row and row[0] > time.time():
            return True
        return False

def get_seller_rating_info(seller_id: int) -> str:
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT AVG(rating), COUNT(rating) FROM seller_reviews WHERE seller_id = ?", (seller_id,))
        row = cur.fetchone()
        conn.close()
    if not row or row[1] == 0:
        return "⭐ Нет оценок (0)"
    avg_rating, count = row[0], row[1]
    return f"⭐ {avg_rating:.1f} / 5 (Отзывов: {count})"

def check_auto_moderation(text: str) -> bool:
    if not text:
        return True
    lower_text = text.lower()
    for word in BAD_WORDS:
        if word in lower_text:
            return False
    return True

def get_user_last_ad_time(user_id):
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT last_ad_time FROM user_data WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else 0

def set_user_last_ad_time(user_id, t):
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO user_data (user_id, last_ad_time) VALUES (?, ?)", (user_id, t))
        conn.commit()
        conn.close()

def is_banned(user) -> bool:
    if not user:
        return False
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM bans WHERE (is_id = 1 AND target = ?) OR (is_id = 0 AND target = ?)", 
                    (str(user.id), user.username.lower().lstrip('@') if user.username else ""))
        res = cur.fetchone()
        conn.close()
    return bool(res)

def is_owner(user) -> bool:
    return bool(user and user.username and user.username.lower() == OWNER_USERNAME.lower())

def is_admin_or_owner(user) -> bool:
    if not user: 
        return False
    if is_owner(user): 
        return True
    return bool(user.username and user.username.lower() in ADMIN_USERNAMES)

def register_admin(user, chat_id: int):
    if is_admin_or_owner(user):
        ADMIN_CHAT_IDS.add(chat_id)

def verify_admin_callback(call) -> bool:
    if not is_admin_or_owner(call.from_user):
        bot.answer_callback_query(call.id, "⛔ Нет доступа к функциям СМИ!", show_alert=True)
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
        time.sleep(60)
        now_time = datetime.now().time()
        curr_t = time.time()

        is_night = now_time >= dtime(22, 0, 0) or now_time < dtime(8, 0, 0)
        is_morning_clean = dtime(8, 0, 0) <= now_time <= dtime(8, 5, 0)

        with db_lock:
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            if is_night or is_morning_clean:
                cur.execute("DELETE FROM active_ads")
            else:
                expired_limit = curr_t - 600
                cur.execute("DELETE FROM active_ads WHERE last_updated < ?", (expired_limit,))
            conn.commit()
            conn.close()

threading.Thread(target=background_cleanup_ads, daemon=True).start()

def background_reset_limits_task():
    while True:
        now = datetime.now()
        target_time = now.replace(hour=22, minute=0, second=22, microsecond=0)
        if now >= target_time:
            from datetime import timedelta
            target_time += timedelta(days=1)
        
        sleep_seconds = (target_time - datetime.now()).total_seconds()
        time.sleep(max(1, sleep_seconds))
        
        with db_lock:
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("DELETE FROM daily_message_limits")
            conn.commit()
            conn.close()
        logger.info("🔄 Лимиты сообщений успешно обновлены (сброшены) в 22:00:22!")

threading.Thread(target=background_reset_limits_task, daemon=True).start()

def send_admins_notification_async(recipients: set, photo, f_text: str, counter: int):
    for target_id in recipients:
        try:
            if photo: 
                bot.send_photo(target_id, photo, caption=f_text, parse_mode="Markdown", reply_markup=ikb_moderation(counter))
            else: 
                bot.send_message(target_id, f_text, parse_mode="Markdown", reply_markup=ikb_moderation(counter))
            time.sleep(0.03)
        except Exception as e:
            logger.warning(f"Ошибка доставки уведомления админу {target_id}: {e}")

# ==========================================
# КЛАВИАТУРЫ
# ==========================================

def kb_servers():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for i in range(0, len(SERVERS), 2): 
        m.add(*[types.KeyboardButton(s) for s in SERVERS[i:i+2]])
    m.add(types.KeyboardButton("📊 Откуда цены?"), types.KeyboardButton("🛒 Подать объявление о продаже"))
    m.add(types.KeyboardButton("💎 Премиум (VIP)"), types.KeyboardButton("👑 Админ"))
    return m

def kb_main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("💍 Аксессуары", "🏎 Транспорт и Тюнинг")
    m.add("🥼 Скины и Охранники", "🏡 Недвижимость и Бизнес")
    m.add("📦 Ресурсы и Оружие")
    m.add("🔍 Поиск по товарам", "❤️ Избранное")
    m.add("🔔 Подписки на поиск", "📋 Мои объявления")
    m.add("📊 Откуда цены?", "🛒 Подать объявление о продаже")
    m.add("💎 Премиум (VIP)", "🔄 Сменить сервер")
    m.add("👑 Админ")
    return m

def kb_cancel():
    return types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("🚫 Отмена"))

def ikb_user_categories():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for idx, cat in enumerate(CATEGORIES):
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"user_select_cat_{idx}"))
    return markup

def ikb_vip_choice():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("⭐ Подать как VIP (1 ⭐️ Telegram Star)", callback_data="type_ad_vip"))
    markup.add(types.InlineKeyboardButton("📝 Обычное объявление (Бесплатно)", callback_data="type_ad_std"))
    return markup

def ikb_moderation(pid: int):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📝 Редактировать (ПРО)", callback_data=f"edit_text_{pid}"),
        types.InlineKeyboardButton("📁 Раздел", callback_data=f"edit_cat_{pid}")
    )
    markup.add(
        types.InlineKeyboardButton("✅ Одобрить и Опубликовать", callback_data=f"owner_approve_{pid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{pid}")
    )
    markup.add(
        types.InlineKeyboardButton("🔨 Заблокировать автора", callback_data=f"ban_author_{pid}")
    )
    return markup

def ikb_reject_reasons(pid: int):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("❌ Нарушение ПРО", callback_data=f"do_reject_{pid}_pro"),
        types.InlineKeyboardButton("❌ Некорректная цена", callback_data=f"do_reject_{pid}_price"),
        types.InlineKeyboardButton("❌ Нецензурная лексика", callback_data=f"do_reject_{pid}_mat"),
        types.InlineKeyboardButton("🔙 Назад к заявке", callback_data=f"back_to_post_{pid}")
    )
    return markup

def ikb_manage_active_ad(aid: int):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("❌ Удалить", callback_data=f"del_active_{aid}"))
    return markup

# ==========================================
# ОСНОВНЫЕ КОМАНДЫ И МЕНЮ
# ==========================================

user_states = {}

@bot.message_handler(commands=['start'])
def cmd_start(m):
    if is_banned(m.from_user):
        return bot.send_message(m.chat.id, "⛔ Вы заблокированы в системе модерации.")
        
    register_admin(m.from_user, m.chat.id)
    
    caption_text = (
        "👋 **ДОБРО ПОЖАЛОВАТЬ В ЦЕНТР ЦЕН!**\n"
        "Здесь ты узнаешь все актуальные цены ARIZONA RP обновляются каждый день!\n\n"
        "Ваш персональный радиоцентр и торговая площадка прямо в Telegram! "
        "Доступны избранное, подписки на редкие товары, система отзывов и премиум-статус.\n\n"
        "⏱ **Режим работы радиоцентра:** ежедневно с **08:00 до 22:00 МСК**.\n\n"
        "👇 **Для начала работы выберите ваш игровой сервер:**"
    )

    if WELCOME_VIDEO_ID and WELCOME_VIDEO_ID != "YOUR_VIDEO_FILE_ID_HERE":
        try:
            bot.send_video(
                m.chat.id, 
                WELCOME_VIDEO_ID, 
                caption=caption_text, 
                parse_mode="Markdown", 
                reply_markup=kb_servers()
            )
            return
        except Exception as e:
            logger.warning(f"Не удалось отправить видео по ID, отправляем текст: {e}")

    bot.send_message(m.chat.id, caption_text, parse_mode="Markdown", reply_markup=kb_servers())

@bot.message_handler(commands=['help'])
def cmd_help(m):
    text = (
        "❓ **Помощь по использованию бота**\n\n"
        "1️⃣ Выберите игровой сервер.\n"
        "2️⃣ Просматривайте каталог или используйте поиск и избранное.\n"
        "3️⃣ Подписывайтесь на ключевые слова, чтобы не пропустить нужный товар.\n"
        "4️⃣ Оценивайте продавцов после сделки!\n\n"
        "⏱ **График работы СМИ:** ежедневно с **08:00 до 22:00 МСК**."
    )
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['chatlogs'])
def cmd_chatlogs(m):
    if not is_owner(m.from_user):
        return bot.send_message(m.chat.id, "⛔ Эта команда доступна только владельцу бота.")

    log_file_path = "chat_history_logs.txt"
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT timestamp, sender_id, sender_username, recipient_id, message_text FROM chat_logs ORDER BY id DESC LIMIT 1000")
        rows = cur.fetchall()
        conn.close()

    with open(log_file_path, "w", encoding="utf-8") as f:
        f.write("=== ЛОГИ ЧАТОВ СВЯЗИ С ПРОДАВЦАМИ ===\n\n")
        for row in rows:
            ts, s_id, s_uname, r_id, text = row
            f.write(f"[{ts}] От: @{s_uname} (ID: {s_id}) -> Получателю (ID: {r_id})\nТекст: {text}\n{'-'*40}\n")

    with open(log_file_path, "rb") as f:
        bot.send_document(m.chat.id, f, caption="📂 **Логи последних сообщений в чатах:**", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📊 Откуда цены?")
def show_prices_info(m):
    text = (
        "📊 **Откуда берутся цены в нашем боте?**\n\n"
        "👥 **Помощь игроков:** Все цены и актуальная информация формируются благодаря вам! Игроки активно отправляют свои продажи, фиксируют изменения рынка и помогают находить выгодные лавки на сервере.\n\n"
        "📰 **Работа СМИ:** Редакторы радиоцентра проверяют поступающие данные, отсеивают фейки и поддерживают актуальность каталога, чтобы вы всегда знали реальную стоимость имущества."
    )
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

# ==========================================
# МОДУЛЬ ПРЕМИУМ-ПОДПИСКИ И РАЗБАНА (Telegram Stars)
# ==========================================

@bot.message_handler(func=lambda msg: msg.text == "💎 Премиум (VIP)")
def show_premium_info(m):
    uid = m.from_user.id
    is_prem = is_user_premium(uid)
    is_user_banned = is_banned(m.from_user)
    
    status_str = "🟢 **У вас активен Премиум-статус!**" if is_prem else "🔴 **Премиум-статус не активен.**"
    
    text = (
        f"💎 **Магазин услуг и Премиум-подписки**\n\n"
        f"{status_str}\n\n"
        f"**Что дает Premium:**\n"
        f"• 🚫 **Без кулдауна** на подачу обычных объявлений (можно выкладывать без ожидания 10 минут).\n"
        f"• 📈 **Увеличенный лимит сообщений** продавцам (1000 сообщений в день вместо 300).\n"
        f"• ✨ **Эксклюзивный значок 💎** возле вашего имени во всех опубликованных объявлениях.\n\n"
        f"💰 **Стоимость Премиума:** 20 ⭐️ Telegram Stars (на 30 дней).\n"
    )
    if is_user_banned:
        text += f"🔨 **Разбан аккаунта:** 150 ⭐️ Telegram Stars."
    
    markup = types.InlineKeyboardMarkup()
    if not is_prem:
        markup.add(types.InlineKeyboardButton("💳 Купить Премиум на 30 дней (20 ⭐️)", callback_data="buy_premium_30"))
    if is_user_banned:
        markup.add(types.InlineKeyboardButton("🔓 Разблокировать аккаунт (150 ⭐️)", callback_data="buy_unban_150"))
    
    bot.send_message(m.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "buy_premium_30")
def cb_buy_premium(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    try:
        bot.send_invoice(
            call.message.chat.id,
            title="💎 Премиум-подписка на 30 дней",
            description="Снятие кулдаунов, лимит 1000 сообщений и значок 💎 в объявлениях",
            invoice_payload=f"premium_sub_{uid}_{int(time.time())}",
            provider_token="",
            currency="XTR",
            prices=[types.LabeledPrice(label="Премиум 30 дней", amount=20)]
        )
    except Exception as e:
        logger.error(f"Ошибка отправки инвойса: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "buy_unban_150")
def cb_buy_unban(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    try:
        bot.send_invoice(
            call.message.chat.id,
            title="🔓 Разбан аккаунта в боте",
            description="Снятие блокировки и восстановление доступа к функционалу бота",
            invoice_payload=f"unban_sub_{uid}_{int(time.time())}",
            provider_token="",
            currency="XTR",
            prices=[types.LabeledPrice(label="Разбан аккаунта", amount=150)]
        )
    except Exception as e:
        logger.error(f"Ошибка отправки инвойса на разбан: {e}")

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def process_successful_payment(m):
    uid = m.from_user.id
    payload = m.successful_payment.invoice_payload
    
    if "premium_sub" in payload:
        expires_at = time.time() + (30 * 24 * 60 * 60) # 30 дней
        with db_lock:
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO premium_users (user_id, expires_at) VALUES (?, ?)", (uid, expires_at))
            conn.commit()
            conn.close()
        bot.send_message(m.chat.id, "🎉 **Поздравляем! Премиум-подписка успешно активирована на 30 дней!** 💎", parse_mode="Markdown", reply_markup=kb_main_menu())
    elif "unban_sub" in payload:
        with db_lock:
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("DELETE FROM bans WHERE target = ? OR target = ?", (str(uid), m.from_user.username.lower() if m.from_user.username else ""))
            conn.commit()
            conn.close()
        bot.send_message(m.chat.id, "🎉 **Оплата прошла успешно! Вы были разблокированы в системе.**", parse_mode="Markdown", reply_markup=kb_main_menu())
    elif "vip_ad" in payload:
        vip_data = user_states.get(uid, {}).get("pending_vip_data")
        bot.send_message(m.chat.id, "🎉 **Оплата 1 ⭐️ прошла успешно!** VIP-объявление отправлено СМИ.")
        if vip_data:
            finalize_ad_submission(
                m.chat.id, uid, 
                vip_data["photo"], vip_data["text"], 
                vip_data["category"], vip_data["server"], 
                is_vip=True
            )

# ==========================================
# МОДУЛЬ ИЗБРАННОГО
# ==========================================

@bot.callback_query_handler(func=lambda c: c.data.startswith("fav_add_"))
def cb_fav_add(call):
    aid = int(call.data.split("_")[2])
    uid = call.from_user.id
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO favorites (user_id, ad_id) VALUES (?, ?)", (uid, aid))
        conn.commit()
        conn.close()
    
    bot.answer_callback_query(call.id, "❤️ Товар добавлен в избранное!")

@bot.message_handler(func=lambda msg: msg.text == "❤️ Избранное")
def show_favorites(m):
    uid = m.from_user.id
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("""
            SELECT a.id, a.server, a.category, a.text, a.photo 
            FROM favorites f JOIN active_ads a ON f.ad_id = a.id 
            WHERE f.user_id = ?
        """, (uid,))
        ads = cur.fetchall()
        conn.close()

    if not ads:
        return bot.send_message(m.chat.id, "❤️ В вашем избранном пока ничего нет.", reply_markup=kb_main_menu())

    bot.send_message(m.chat.id, f"❤️ **Ваше избранное ({len(ads)} шт.):**", parse_mode="Markdown")
    for aid, server, category, text, photo in ads:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✉️ Написать продавцу", callback_data=f"contact_seller_{aid}"),
            types.InlineKeyboardButton("❌ Убрать из избранного", callback_data=f"fav_del_{aid}")
        )
        info = f"🌐 Сервер: {server}\n📂 Раздел: {category}\n\n{text}"
        if photo:
            bot.send_photo(m.chat.id, photo, caption=info, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(m.chat.id, info, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("fav_del_"))
def cb_fav_del(call):
    aid = int(call.data.split("_")[2])
    uid = call.from_user.id
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("DELETE FROM favorites WHERE user_id = ? AND ad_id = ?", (uid, aid))
        conn.commit()
        conn.close()
    bot.answer_callback_query(call.id, "🗑 Удалено из избранного!")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

# ==========================================
# МОДУЛЬ ПОДПИСОК НА КЛЮЧЕВЫЕ СЛОВА
# ==========================================

@bot.message_handler(func=lambda msg: msg.text == "🔔 Подписки на поиск")
def manage_subscriptions(m):
    uid = m.from_user.id
    srv = user_states.get(uid, {}).get("server", "Phoenix")
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT id, keyword FROM keyword_subscriptions WHERE user_id = ? AND server = ?", (uid, srv))
        subs = cur.fetchall()
        conn.close()

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Добавить ключевое слово", callback_data="sub_add_keyword"))
    
    text = f"🔔 **Ваши подписки на поиск [{srv}]:**\n\n"
    if subs:
        for sid, kw in subs:
            text += f"• `{kw}`\n"
            markup.add(types.InlineKeyboardButton(f"❌ Удалить: {kw}", callback_data=f"sub_del_{sid}"))
    else:
        text += "У вас нет активных подписок на этом сервере."

    bot.send_message(m.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "sub_add_keyword")
def cb_sub_add(call):
    bot.answer_callback_query(call.id)
    user_states.setdefault(call.from_user.id, {})["awaiting_keyword"] = True
    bot.send_message(call.message.chat.id, "Введите слово или фразу для отслеживания (например: `Шар` или `Нимб`):", parse_mode="Markdown", reply_markup=kb_cancel())

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states and user_states[msg.from_user.id].get("awaiting_keyword"))
def process_keyword_sub(m):
    uid = m.from_user.id
    user_states[uid].pop("awaiting_keyword", None)
    if m.text == "🚫 Отмена":
        return bot.send_message(m.chat.id, "Отменено.", reply_markup=kb_main_menu())
    
    kw = m.text.strip().lower()
    srv = user_states.get(uid, {}).get("server", "Phoenix")

    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("INSERT INTO keyword_subscriptions (user_id, server, keyword) VALUES (?, ?, ?)", (uid, srv, kw))
        conn.commit()
        conn.close()

    bot.send_message(m.chat.id, f"✅ Успешно! Как только появится объявление со словом **«{kw}»** на сервере **{srv}**, мы пришлем вам уведомление.", parse_mode="Markdown", reply_markup=kb_main_menu())

@bot.callback_query_handler(func=lambda c: c.data.startswith("sub_del_"))
def cb_sub_del(call):
    sid = int(call.data.split("_")[2])
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("DELETE FROM keyword_subscriptions WHERE id = ?", (sid,))
        conn.commit()
        conn.close()
    bot.answer_callback_query(call.id, "🗑 Подписка удалена!")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

def check_keyword_notifications(server: str, text: str, aid: int):
    lower_text = text.lower()
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT user_id, keyword FROM keyword_subscriptions WHERE server = ?", (server,))
        subs = cur.fetchall()
        conn.close()

    notified_users = set()
    for user_id, kw in subs:
        if kw in lower_text and user_id not in notified_users:
            notified_users.add(user_id)
            try:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("✉️ Написать продавцу", callback_data=f"contact_seller_{aid}"))
                bot.send_message(
                    user_id,
                    f"🔔 **Найден товар по вашей подписке (`{kw}`)!**\n\n{text}",
                    parse_mode="Markdown",
                    reply_markup=markup
                )
            except Exception:
                pass

# ==========================================
# СИСТЕМА РЕЙТИНГА И ОТЗЫВОВ ПРОДАВЦОВ
# ==========================================

@bot.callback_query_handler(func=lambda c: c.data.startswith("rate_seller_"))
def cb_rate_seller(call):
    parts = call.data.split("_")
    seller_id = int(parts[2])
    aid = int(parts[3])
    buyer_id = call.from_user.id

    if seller_id == buyer_id:
        return bot.answer_callback_query(call.id, "⚠️ Вы не можете оценивать сами себя!", show_alert=True)

    user_states[buyer_id] = {"rating_seller_id": seller_id, "rating_aid": aid}
    bot.answer_callback_query(call.id)
    
    markup = types.InlineKeyboardMarkup(row_width=5)
    markup.add(
        types.InlineKeyboardButton("⭐ 1", callback_data="do_rate_1"),
        types.InlineKeyboardButton("⭐ 2", callback_data="do_rate_2"),
        types.InlineKeyboardButton("⭐ 3", callback_data="do_rate_3"),
        types.InlineKeyboardButton("⭐ 4", callback_data="do_rate_4"),
        types.InlineKeyboardButton("⭐ 5", callback_data="do_rate_5")
    )
    bot.send_message(call.message.chat.id, "⭐ Выберите оценку для продавца от 1 до 5 звезд:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("do_rate_"))
def cb_do_rate(call):
    score = int(call.data.split("_")[2])
    buyer_id = call.from_user.id
    st = user_states.get(buyer_id, {})
    seller_id = st.get("rating_seller_id")

    if not seller_id:
        return bot.answer_callback_query(call.id, "Сессия оценки истекла.", show_alert=True)

    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("INSERT INTO seller_reviews (seller_id, buyer_id, rating) VALUES (?, ?, ?)", (seller_id, buyer_id, score))
        conn.commit()
        conn.close()

    bot.answer_callback_query(call.id, f"✅ Спасибо! Вы поставили оценку ⭐ {score}")
    try:
        bot.edit_message_text("✅ Оценка успешно сохранена!", chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.send_message(seller_id, f"⭐ Вам оставили новую оценку: **{score} / 5 звезд**!", parse_mode="Markdown")
    except Exception:
        pass
    user_states.pop(buyer_id, None)

# ==========================================
# ПОИСК И МОИ ОБЪЯВЛЕНИЯ
# ==========================================

@bot.message_handler(func=lambda msg: msg.text == "🔍 Поиск по товарам")
def start_search(m):
    srv = user_states.get(m.from_user.id, {}).get("server")
    if not srv:
        return bot.send_message(m.chat.id, "⚠️ Сначала выберите сервер!", reply_markup=kb_servers())

    bot.send_message(m.chat.id, f"🔍 **Поиск по серверу [{srv}]**\nВведите ключевое слово:", parse_mode="Markdown", reply_markup=kb_cancel())
    bot.register_next_step_handler(m, process_search_query)

def process_search_query(m):
    if m.text == "🚫 Отмена":
        return bot.send_message(m.chat.id, "Поиск отменен.", reply_markup=kb_main_menu())

    query = m.text.lower().strip()
    srv = user_states.get(m.from_user.id, {}).get("server", "Phoenix")

    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT id, user_id, text, photo FROM active_ads WHERE server = ? AND LOWER(text) LIKE ?", (srv, f"%{query}%"))
        results = cur.fetchall()
        conn.close()

    if not results:
        return bot.send_message(m.chat.id, f"🔍 По запросу «**{query}**» объявлений не найдено.", parse_mode="Markdown", reply_markup=kb_main_menu())

    bot.send_message(m.chat.id, f"🔍 Найдено объявлений: **{len(results)} шт.**", parse_mode="Markdown")
    for aid, seller_uid, text, photo in results[:10]:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✉️ Написать продавцу", callback_data=f"contact_seller_{aid}"),
            types.InlineKeyboardButton("❤️ В избранное", callback_data=f"fav_add_{aid}"),
            types.InlineKeyboardButton("⭐ Оценить продавца", callback_data=f"rate_seller_{seller_uid}_{aid}")
        )

        if photo:
            bot.send_photo(m.chat.id, photo, caption=text, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(m.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📋 Мои объявления")
def show_my_ads(m):
    uid = m.from_user.id

    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT id, server, category, text, photo FROM active_ads WHERE user_id = ?", (uid,))
        user_ads = cur.fetchall()
        conn.close()

    if not user_ads:
        return bot.send_message(m.chat.id, "📋 У вас нет активных объявлений.", reply_markup=kb_main_menu())

    bot.send_message(m.chat.id, f"📋 **Ваши активные объявления ({len(user_ads)} шт.):**", parse_mode="Markdown")
    for aid, server, category, text, photo in user_ads:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Продано (Удалить)", callback_data=f"user_delete_self_{aid}"))
        
        info = f"🌐 Сервер: {server}\n📂 Раздел: {category}\n\n{text}"
        if photo:
            bot.send_photo(m.chat.id, photo, caption=info, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(m.chat.id, info, parse_mode="Markdown", reply_markup=markup)

# ==========================================
# СВЯЗЬ С ПРОДАВЦОМ
# ==========================================

@bot.callback_query_handler(func=lambda c: c.data.startswith("contact_seller_"))
def cb_contact_seller(call):
    aid = int(call.data.split("_")[2])
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT user_id, server, category, text FROM active_ads WHERE id = ?", (aid,))
        ad = cur.fetchone()
        conn.close()

    if not ad:
        return bot.answer_callback_query(call.id, "❌ Это объявление уже неактивно или удалено.", show_alert=True)

    seller_id, server, category, ad_text = ad
    buyer_id = call.from_user.id

    if seller_id == buyer_id:
        return bot.answer_callback_query(call.id, "⚠️ Вы не можете написать самому себе!", show_alert=True)

    bot.answer_callback_query(call.id)
    
    user_states[buyer_id] = {
        "messaging_seller": True,
        "seller_id": seller_id,
        "ad_info": f"[{server}] {category}: {ad_text[:50]}..."
    }

    bot.send_message(
        call.message.chat.id,
        "✍️ **Связь с продавцом через бота**\n\n"
        "Отправьте ваше сообщение или вопрос. Лимиты:\n"
        "• Обычный аккаунт: до 300 сообщений в день.\n"
        "• Премиум аккаунт 💎: до 1000 сообщений в день.\n\n"
        "Для выхода нажмите кнопку ниже.",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("🚫 Отмена связи"))
    )

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states and user_states[msg.from_user.id].get("messaging_seller"))
def process_message_to_seller(m):
    uid = m.from_user.id
    state_data = user_states[uid]

    if m.text == "🚫 Отмена связи":
        user_states.pop(uid, None)
        return bot.send_message(m.chat.id, "❌ Переписка с продавцом отменена.", reply_markup=kb_main_menu())

    is_prem = is_user_premium(uid)
    max_limit = 1000 if is_prem else 300

    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT msg_count FROM daily_message_limits WHERE user_id = ?", (uid,))
        row = cur.fetchone()
        current_count = row[0] if row else 0

        if current_count >= max_limit:
            conn.close()
            return bot.send_message(
                m.chat.id, 
                f"❌ Вы исчерпали лимит из **{max_limit} сообщений** на сегодня.", 
                parse_mode="Markdown"
            )

        cur.execute("INSERT OR REPLACE INTO daily_message_limits (user_id, msg_count) VALUES (?, ?)", (uid, current_count + 1))
        
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sender_uname = m.from_user.username or m.from_user.first_name
        cur.execute("""
            INSERT INTO chat_logs (timestamp, sender_id, sender_username, recipient_id, message_text)
            VALUES (?, ?, ?, ?, ?)
        """, (timestamp_str, uid, sender_uname, state_data.get("seller_id"), m.text))
        
        conn.commit()
        conn.close()

    seller_id = state_data.get("seller_id")
    ad_info = state_data.get("ad_info")
    buyer_username = f"@{m.from_user.username}" if m.from_user.username else f"ID: `{m.from_user.id}`"

    forward_text = (
        f"📩 **Вам сообщение по объявлению!**\n\n"
        f"📌 **Товар:** {ad_info}\n"
        f"👤 **Покупатель:** {buyer_username}\n\n"
        f"💬 **Текст сообщения:**\n{m.text}"
    )

    try:
        bot.send_message(seller_id, forward_text, parse_mode="Markdown")
        for adm_chat in ADMIN_CHAT_IDS:
            try:
                bot.send_message(adm_chat, f"🕵️‍♂️ **[ЛОГ ЧАТА]** От @{sender_uname} к `{seller_id}`:\n{m.text}", parse_mode="Markdown")
            except Exception:
                pass

        remaining_msgs = max_limit - (current_count + 1)
        bot.send_message(
            m.chat.id, 
            f"✅ **Сообщение отправлено!** (Осталось лимита: {remaining_msgs}/{max_limit})", 
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки продавцу: {e}")
        bot.send_message(m.chat.id, "❌ Не удалось доставить сообщение продавцу.", reply_markup=kb_main_menu())
        user_states.pop(uid, None)

# ==========================================
# СОЗДАНИЕ И ПУБЛИКАЦИЯ ОБЪЯВЛЕНИЙ
# ==========================================

@bot.message_handler(func=lambda msg: msg.text == "🛒 Подать объявление о продаже")
def start_ad_creation(m):
    if is_banned(m.from_user):
        return bot.send_message(m.chat.id, "⛔ Вы заблокированы в системе модерации. Вы можете разблокировать аккаунт через меню «💎 Премиум (VIP)» за 150 ⭐️.")

    if not check_working_hours():
        return bot.send_message(m.chat.id, "❌ Радиоцентр закрыт! Подача объявлений доступна с 08:00 до 22:00 МСК.")

    uid = m.from_user.id
    if uid not in user_states or "server" not in user_states[uid]:
        return bot.send_message(m.chat.id, "⚠️ Сначала выберите сервер из меню!", reply_markup=kb_servers())

    bot.send_message(
        m.chat.id,
        "⭐ **Выберите формат подачи:**\n\n"
        "• **Обычное:** Бесплатно, с кулдауном 10 минут (у Премиум-пользователей кулдаун отсутствует!).\n"
        "• **VIP (1 ⭐️ Star):** Закреп в топе категории + скрытие контакта.",
        reply_markup=ikb_vip_choice()
    )

@bot.callback_query_handler(func=lambda call: call.data in ["type_ad_vip", "type_ad_std"])
def select_ad_type(call):
    uid = call.from_user.id
    user_states.setdefault(uid, {"server": "Phoenix"})

    is_vip = (call.data == "type_ad_vip")

    if not is_vip and not is_user_premium(uid):
        last_time = get_user_last_ad_time(uid)
        elapsed = time.time() - last_time
        if elapsed < 600:
            remaining = int(600 - elapsed)
            return bot.answer_callback_query(
                call.id, 
                f"❌ Кулдаун! Подождите {remaining // 60} мин. {remaining % 60} сек. (Купите Премиум, чтобы убрать кулдаун!)", 
                show_alert=True
            )

    user_states[uid]["is_vip"] = is_vip
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        f"🌐 **Сервер:** {user_states[uid].get('server')}\n"
        f"Тип: {'⭐ VIP (1 Star)' if is_vip else '📝 Обычное'}\n\n"
        f"👇 Выберите раздел товара:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="Markdown",
        reply_markup=ikb_user_categories()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("user_select_cat_"))
def process_user_cat_choice(call):
    uid = call.from_user.id
    cat_idx = int(call.data.split("_")[3])
    selected_cat = CATEGORIES[cat_idx]

    user_states.setdefault(uid, {"server": "Phoenix"})["selected_category"] = selected_cat

    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        f"✅ Раздел: **{selected_cat}**\n\n👇 Отправьте описание (и фото по желанию):",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="Markdown"
    )
    bot.send_message(call.message.chat.id, "Ожидаю описание...", reply_markup=kb_cancel())
    bot.register_next_step_handler(call.message, process_sub)

def process_sub(m):
    uid = m.from_user.id

    if m.text == "🚫 Отмена":
        return bot.send_message(m.chat.id, "Отменено.", reply_markup=kb_main_menu())
    
    photo = m.photo[-1].file_id if m.photo else None
    text = m.caption or m.text

    if not photo and not text:
        bot.send_message(m.chat.id, "❌ Отправьте текст или фото с текстом.")
        return bot.register_next_step_handler(m, process_sub)

    # 🤖 АВТОМОДЕРАЦИЯ (Фильтр мата и ссылок)
    if not check_auto_moderation(text):
        return bot.send_message(
            m.chat.id, 
            "🤖 **Автомодерация отклонила объявление!**\n\n"
            "В вашем тексте найдены запрещенные слова (мат, оскорбления или сторонние ссылки). Исправьте текст и отправьте снова.", 
            parse_mode="Markdown", 
            reply_markup=kb_main_menu()
        )

    server_name = user_states.get(uid, {}).get("server", "Phoenix")
    category = user_states.get(uid, {}).get("selected_category", CATEGORIES[0])
    is_vip = user_states.get(uid, {}).get("is_vip", False)

    if is_vip:
        try:
            bot.send_invoice(
                m.chat.id,
                title="👑 VIP-Объявление в СМИ",
                description="Топ категории + Скрытие контакта",
                invoice_payload=f"vip_ad_{uid}_{int(time.time())}",
                provider_token="",
                currency="XTR",
                prices=[types.LabeledPrice(label="VIP Объявление", amount=1)]
            )
            user_states[uid]["pending_vip_data"] = {
                "photo": photo, "text": text, "category": category, "server": server_name
            }
            return
        except Exception as e:
            logger.error(f"Ошибка инвойса VIP: {e}")

    finalize_ad_submission(m, uid, photo, text, category, server_name, is_vip=False)

def finalize_ad_submission(m_or_chat_id, uid: int, photo, text: str, category: str, server_name: str, is_vip: bool = False):
    if not is_vip:
        set_user_last_ad_time(uid, time.time())

    if isinstance(m_or_chat_id, types.Message):
        uname = m_or_chat_id.from_user.username or "Без юзернейма"
        chat_id = m_or_chat_id.chat.id
    else:
        chat_id = m_or_chat_id
        try:
            chat_obj = bot.get_chat(uid)
            uname = chat_obj.username or "Без юзернейма"
        except Exception:
            uname = "Без юзернейма"

    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pending_posts (user_id, username, server, category, text, photo, is_vip)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (uid, uname, server_name, category, text or "Без описания", photo, 1 if is_vip else 0))
        moderation_counter = cur.lastrowid
        conn.commit()
        conn.close()

    f_text = (
        f"🚨 **НОВОЕ {'👑 VIP' if is_vip else ''} ОБЪЯВЛЕНИЕ #{moderation_counter}!**\n\n"
        f"🌐 **Сервер:** {server_name}\n"
        f"📂 **Категория:** {category}\n"
        f"👤 **От игрока:** @{uname} (ID: `{uid}`)\n\n"
        f"📥 **Текст игрока:**\n`{text or 'Без описания'}`"
    )

    recipients = set(ADMIN_CHAT_IDS)
    if MODERATION_CHAT_ID != 0:
        recipients.add(MODERATION_CHAT_ID)
    if not recipients:
        recipients.add(chat_id)

    threading.Thread(
        target=send_admins_notification_async, 
        args=(recipients, photo, f_text, moderation_counter), 
        daemon=True
    ).start()

    bot.send_message(chat_id, "✅ **Объявление отправлено на модерацию СМИ!**", reply_markup=kb_main_menu())

# ==========================================
# МОДУЛЬ АДМИНИСТРИРОВАНИЯ И РАССЫЛКИ
# ==========================================

@bot.message_handler(commands=['send'])
def cmd_broadcast(m):
    if not is_owner(m.from_user):
        return bot.send_message(m.chat.id, "⛔ Только для владельца бота.")
    
    text_to_send = m.text.replace("/send", "").strip()
    if not text_to_send:
        return bot.send_message(m.chat.id, "⚠️ Укажите текст рассылки после команды `/send`.", parse_mode="Markdown")

    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT user_id FROM user_data")
        users = [row[0] for row in cur.fetchall()]
        conn.close()

    success_count = 0
    bot.send_message(m.chat.id, f"🚀 Начинаю рассылку для {len(users)} пользователей...")

    for uid in users:
        try:
            bot.send_message(uid, f"📢 **Объявление / Новость:**\n\n{text_to_send}", parse_mode="Markdown")
            success_count += 1
            time.sleep(0.04)
        except Exception:
            pass

    bot.send_message(m.chat.id, f"✅ Рассылка завершена! Успешно доставлено: {success_count}/{len(users)}")

@bot.message_handler(commands=['stats'])
@bot.message_handler(func=lambda msg: msg.text == "📈 Статистика")
def cmd_stats(m):
    if not is_admin_or_owner(m.from_user):
        return bot.send_message(m.chat.id, "⛔ Нет доступа.")

    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT user_id) FROM user_data")
        total_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM active_ads")
        active_ads_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM pending_posts")
        pending_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM premium_users")
        prem_count = cur.fetchone()[0]
        conn.close()

    text = (
        f"📈 **Расширенная статистика бота:**\n\n"
        f"👥 Всего пользователей: **{total_users}**\n"
        f"💎 Активных Премиум-подписок: **{prem_count}**\n"
        f"📂 Активных объявлений в ленте: **{active_ads_count}**\n"
        f"📥 Заявок на модерации: **{pending_count}**"
    )
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states and user_states[msg.from_user.id].get("awaiting_ban_target"))
def process_ban_target_input(m):
    uid = m.from_user.id
    user_states[uid].pop("awaiting_ban_target", None)

    if m.text == "🚫 Отмена":
        return bot.send_message(m.chat.id, "Подача заявки отменена.", reply_markup=kb_main_menu())

    target = m.text.strip()
    admin_uname = m.from_user.username or m.from_user.first_name

    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("INSERT INTO pending_bans (admin_id, admin_username, target) VALUES (?, ?, ?)", (uid, admin_uname, target))
        req_id = cur.lastrowid
        conn.commit()
        conn.close()

    req_text = (
        f"🚨 **ЗАЯВКА НА БАН #{req_id}**\n\n"
        f"👨‍💻 **От админа:** @{admin_uname} (ID: `{uid}`)\n"
        f"🎯 **Цель (Юзернейм / ID):** `{target}`\n\n"
        f"Подтвердите или отклоните запрос на блокировку:"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Одобрить и забанить", callback_data=f"approve_ban_{req_id}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_ban_{req_id}")
    )

    recipients = set(ADMIN_CHAT_IDS)
    if MODERATION_CHAT_ID != 0:
        recipients.add(MODERATION_CHAT_ID)
    if not recipients:
        recipients.add(m.chat.id)

    for target_chat in recipients:
        try:
            bot.send_message(target_chat, req_text, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            pass

    bot.send_message(m.chat.id, f"✅ **Заявка на бан #{req_id} отправлена на утверждение!**", reply_markup=kb_main_menu())

@bot.message_handler(commands=['admin'])
@bot.message_handler(func=lambda msg: msg.text == "👑 Админ")
def cmd_admin(m):
    u = m.from_user
    register_admin(u, m.chat.id)
    if is_admin_or_owner(u):
        with db_lock:
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM pending_posts")
            pending_count = cur.fetchone()[0]
            conn.close()

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📝 Редакция объяв (Заявки)", callback_data="show_pending_list"),
            types.InlineKeyboardButton("🗑 Активные объявления", callback_data="show_active_list"),
            types.InlineKeyboardButton("📊 Статистика редакторов", callback_data="show_editor_stats"),
            types.InlineKeyboardButton("📈 Расширенная статистика", callback_data="show_extended_stats"),
            types.InlineKeyboardButton("🔨 Управление Банами", callback_data="manage_bans")
        )
        if is_owner(u):
            markup.add(types.InlineKeyboardButton("📂 Выгрузить логи чатов", callback_data="owner_get_logs"))

        bot.send_message(
            m.chat.id, 
            f"⚙️ **Панель Редактора СМИ**\n📥 Заявок на проверку: **{pending_count} шт.**", 
            parse_mode="Markdown",
            reply_markup=markup
        )
    else:
        bot.send_message(m.chat.id, "⛔ У вас нет доступа к радиоцентру.")

@bot.callback_query_handler(func=lambda c: c.data == "show_extended_stats")
def cb_show_ext_stats(call):
    if not verify_admin_callback(call): return
    bot.answer_callback_query(call.id)
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT user_id) FROM user_data")
        total_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM active_ads")
        active_ads_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM premium_users")
        prem_count = cur.fetchone()[0]
        conn.close()

    text = (
        f"📈 **Расширенная статистика:**\n\n"
        f"👥 Всего пользователей: **{total_users}**\n"
        f"💎 Премиум пользователей: **{prem_count}**\n"
        f"📂 Активных объявлений: **{active_ads_count}**"
    )
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "owner_get_logs")
def cb_owner_get_logs(call):
    if not is_owner(call.from_user):
        return bot.answer_callback_query(call.id, "⛔ Только для владельца!", show_alert=True)
    bot.answer_callback_query(call.id)
    
    log_file_path = "chat_history_logs.txt"
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT timestamp, sender_id, sender_username, recipient_id, message_text FROM chat_logs ORDER BY id DESC LIMIT 1000")
        rows = cur.fetchall()
        conn.close()

    with open(log_file_path, "w", encoding="utf-8") as f:
        f.write("=== ЛОГИ ЧАТОВ СВЯЗИ С ПРОДАВЦАМИ ===\n\n")
        for row in rows:
            ts, s_id, s_uname, r_id, text = row
            f.write(f"[{ts}] От: @{s_uname} (ID: {s_id}) -> Получателю (ID: {r_id})\nТекст: {text}\n{'-'*40}\n")

    with open(log_file_path, "rb") as f:
        bot.send_document(call.message.chat.id, f, caption="📂 **Логи последних сообщений в чатах:**", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text in SERVERS)
def select_srv(m):
    user_states.setdefault(m.from_user.id, {})["server"] = m.text
    bot.send_message(m.chat.id, f"Сервер **{m.text}** выбран!", parse_mode="Markdown", reply_markup=kb_main_menu())

@bot.message_handler(func=lambda msg: msg.text == "🔄 Сменить сервер")
def ch_srv(m): 
    bot.send_message(m.chat.id, "Выберите ваш сервер:", reply_markup=kb_servers())

@bot.message_handler(func=lambda msg: msg.text == "🚫 Отмена")
def cancel_all(m):
    user_states.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, "Действие отменено.", reply_markup=kb_main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "show_pending_list")
def cb_show_pending(call):
    if not verify_admin_callback(call): return
    bot.answer_callback_query(call.id)
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT id, user_id, username, server, category, text, photo, is_vip FROM pending_posts")
        posts = cur.fetchall()
        conn.close()

    if not posts:
        return bot.send_message(call.message.chat.id, "📥 **Заявок пока нет.**")

    for pid, uid, uname, server, category, text, photo, is_vip in posts:
        f_text = (
            f"🚨 **Заявка #{pid} {'👑 [VIP]' if is_vip else ''}**\n"
            f"🌐 **Сервер:** {server}\n"
            f"📂 **Категория:** {category}\n"
            f"👤 **От игрока:** @{uname} (ID: `{uid}`)\n\n"
            f"📥 **Текст:**\n`{text}`"
        )
        if photo:
            bot.send_photo(call.message.chat.id, photo, caption=f_text, parse_mode="Markdown", reply_markup=ikb_moderation(pid))
        else:
            bot.send_message(call.message.chat.id, f_text, parse_mode="Markdown", reply_markup=ikb_moderation(pid))

@bot.callback_query_handler(func=lambda c: c.data == "show_active_list")
def cb_show_active(call):
    if not verify_admin_callback(call): return
    bot.answer_callback_query(call.id)
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT id, server, text, photo FROM active_ads LIMIT 10")
        ads = cur.fetchall()
        conn.close()

    if not ads:
        return bot.send_message(call.message.chat.id, "📂 Активных объявлений нет.")

    for aid, server, text, photo in ads:
        info = f"🆔 **Объявление #{aid}**\n🌐 Сервер: {server}\n\n{text}"
        if photo:
            bot.send_photo(call.message.chat.id, photo, caption=info, parse_mode="Markdown", reply_markup=ikb_manage_active_ad(aid))
        else:
            bot.send_message(call.message.chat.id, info, parse_mode="Markdown", reply_markup=ikb_manage_active_ad(aid))

@bot.callback_query_handler(func=lambda c: c.data == "show_editor_stats")
def cb_show_stats(call):
    if not verify_admin_callback(call): return
    bot.answer_callback_query(call.id)
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT username, count FROM editor_stats ORDER BY count DESC")
        stats = cur.fetchall()
        conn.close()

    stats_text = "📊 **Статистика Редакторов:**\n\n"
    for idx, (ed_name, count) in enumerate(stats, 1):
        stats_text += f"{idx}. @{ed_name} — **{count} шт.**\n"
    bot.send_message(call.message.chat.id, stats_text if stats else "Статистика пуста.", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "manage_bans")
def cb_manage_bans(call):
    if not verify_admin_callback(call): return
    bot.answer_callback_query(call.id)
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM bans")
        total_banned = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM pending_bans")
        pending_bans_count = cur.fetchone()[0]
        conn.close()

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🚫 Подать заявку на бан", callback_data="create_ban_req"),
        types.InlineKeyboardButton("📜 Список забаненных", callback_data="list_banned_users")
    )
    bot.send_message(
        call.message.chat.id, 
        f"🔨 **Управление банами**\n\nВсего в бане: **{total_banned}**\nОжидают решения: **{pending_bans_count}**", 
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda c: c.data == "create_ban_req")
def cb_create_ban_req(call):
    if not verify_admin_callback(call): return
    bot.answer_callback_query(call.id)
    user_states.setdefault(call.from_user.id, {})["awaiting_ban_target"] = True

    bot.send_message(
        call.message.chat.id,
        "🔨 **Подача заявки на бан**\n\nВведите `@username` или `ID` пользователя, которого нужно заблокировать:",
        parse_mode="Markdown",
        reply_markup=kb_cancel()
    )

@bot.callback_query_handler(func=lambda c: c.data == "list_banned_users")
def cb_list_banned(call):
    if not verify_admin_callback(call): return
    bot.answer_callback_query(call.id)

    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT target, is_id FROM bans")
        bans = cur.fetchall()
        conn.close()

    if not bans:
        return bot.send_message(call.message.chat.id, "📜 Список заблокированных пользователей пуст.")

    b_list = [f"• {'ID' if is_id else 'User'}: `{target}`" for target, is_id in bans]
    bot.send_message(call.message.chat.id, "📜 **Список заблокированных:**\n\n" + "\n".join(b_list), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("approve_ban_"))
def cb_approve_ban(call):
    if not verify_admin_callback(call): return
    req_id = int(call.data.split('_')[2])
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT admin_id, target FROM pending_bans WHERE id = ?", (req_id,))
        row = cur.fetchone()
        if row:
            admin_id, target = row
            cur.execute("DELETE FROM pending_bans WHERE id = ?", (req_id,))
            is_id = 1 if target.isdigit() else 0
            cur.execute("INSERT OR IGNORE INTO bans (target, is_id) VALUES (?, ?)", (target, is_id))
            conn.commit()
        conn.close()

    if not row:
        return bot.answer_callback_query(call.id, "Заявка не найдена.", show_alert=True)

    bot.answer_callback_query(call.id, "✅ Бан одобрен!")
    try:
        bot.edit_message_text(
            f"✅ **ЗАЯВКА НА БАН #{req_id} ОДОБРЕНА!**\n\n🎯 Нарушитель `{target}` заблокирован.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
    except Exception:
        pass
    try:
        bot.send_message(admin_id, f"🎉 Ваша заявка на бан `{target}` (Заявка #{req_id}) была **ОДОБРЕНА**!")
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("reject_ban_"))
def cb_reject_ban(call):
    if not verify_admin_callback(call): return
    req_id = int(call.data.split('_')[2])
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT admin_id, target FROM pending_bans WHERE id = ?", (req_id,))
        row = cur.fetchone()
        if row:
            admin_id, target = row
            cur.execute("DELETE FROM pending_bans WHERE id = ?", (req_id,))
            conn.commit()
        conn.close()

    if not row:
        return bot.answer_callback_query(call.id, "Заявка не найдена.", show_alert=True)

    bot.answer_callback_query(call.id, "❌ Бан отклонен.")
    try:
        bot.edit_message_text(
            f"❌ **ЗАЯВКА НА БАН #{req_id} ОТКЛОНЕНА**\n\n🎯 Отклонен бан для: `{target}`",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
    except Exception:
        pass
    try:
        bot.send_message(admin_id, f"❌ Ваша заявка на бан `{target}` (Заявка #{req_id}) была **ОТКЛОНЕНА**.")
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("ban_author_"))
def cb_ban_author(call):
    if not verify_admin_callback(call): return
    pid = int(call.data.split('_')[2])
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM pending_posts WHERE id = ?", (pid,))
        row = cur.fetchone()
        if row:
            target_uid = row[0]
            cur.execute("DELETE FROM pending_posts WHERE id = ?", (pid,))
            cur.execute("INSERT OR IGNORE INTO bans (target, is_id) VALUES (?, 1)", (str(target_uid),))
            conn.commit()
        conn.close()

    bot.answer_callback_query(call.id, "Автор забанен!", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith("user_delete_self_") or c.data.startswith("del_active_"))
def cb_delete_ad(call):
    aid = int(call.data.split('_')[-1])
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("DELETE FROM active_ads WHERE id = ?", (aid,))
        conn.commit()
        conn.close()

    bot.answer_callback_query(call.id, "✅ Удалено!")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_text_"))
def cb_edit_text(call):
    if not verify_admin_callback(call): return
    pid = int(call.data.split('_')[2])
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT text FROM pending_posts WHERE id = ?", (pid,))
        row = cur.fetchone()
        conn.close()

    text = row[0] if row else ""
    user_states[call.from_user.id] = {"editing": pid}
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"✏️ **Редактирование заявки #{pid}:**\n`{text}`", parse_mode="Markdown", reply_markup=kb_cancel())

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states and "editing" in user_states[msg.from_user.id])
def process_editing(m):
    uid = m.from_user.id
    pid = user_states[uid].pop("editing", None)

    if pid:
        with db_lock:
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("UPDATE pending_posts SET text = ? WHERE id = ?", (m.text, pid))
            conn.commit()
            conn.close()

        bot.send_message(m.chat.id, f"✅ Отредактировано:\n\n{m.text}", parse_mode="Markdown", reply_markup=ikb_moderation(pid))

@bot.callback_query_handler(func=lambda c: c.data.startswith("reject_") and not c.data.startswith("reject_ban_") and not c.data.startswith("do_reject_"))
def cb_ask_reject_reason(call):
    if not verify_admin_callback(call): return
    pid = int(call.data.split('_')[1])
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=ikb_reject_reasons(pid))
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("back_to_post_"))
def cb_back_to_post(call):
    if not verify_admin_callback(call): return
    pid = int(call.data.split('_')[3])
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=ikb_moderation(pid))
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("do_reject_"))
def cb_do_reject(call):
    if not verify_admin_callback(call): return
    parts = call.data.split('_')
    pid = int(parts[2])
    reason_code = parts[3]

    reasons_map = {
        "pro": "Нарушение ПРО (Правил редактирования объявлений)",
        "price": "Указана некорректная цена товара",
        "mat": "Использование нецензурной лексики"
    }
    reason_text = reasons_map.get(reason_code, "Нарушение правил подачи")

    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT user_id, text FROM pending_posts WHERE id = ?", (pid,))
        row = cur.fetchone()
        if row:
            user_id, text = row
            cur.execute("DELETE FROM pending_posts WHERE id = ?", (pid,))
            conn.commit()
        conn.close()

    bot.answer_callback_query(call.id, "Заявка отклонена!")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

    if row:
        try:
            bot.send_message(
                user_id, 
                f"❌ **Ваше объявление было отклонено редактором СМИ!**\n\n📌 **Причина:** {reason_text}\n\n*Текст заявки:* `{text}`", 
                parse_mode="Markdown"
            )
        except Exception:
            pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("owner_approve_"))
def cb_approve_post(call):
    if not verify_admin_callback(call): return
    pid = int(call.data.split('_')[2])
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT user_id, username, server, category, text, photo, is_vip FROM pending_posts WHERE id = ?", (pid,))
        row = cur.fetchone()
        if row:
            user_id, username, server, category, text, photo, is_vip = row
            cur.execute("DELETE FROM pending_posts WHERE id = ?", (pid,))
            conn.commit()
        conn.close()

    if not row:
        return bot.answer_callback_query(call.id, "Заявка не найдена.")

    editor_uname = call.from_user.username or call.from_user.first_name
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO editor_stats (username, count) VALUES (?, COALESCE((SELECT count FROM editor_stats WHERE username = ?), 0) + 1)", (editor_uname, editor_uname))
        conn.commit()
        conn.close()

    p_text = format_smi_post(
        server, category, text, 
        username, editor_uname, is_vip=bool(is_vip), user_id=user_id
    )
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO active_ads (user_id, server, category, text, photo, is_vip, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, server, category, p_text, photo, is_vip, time.time()))
        new_aid = cur.lastrowid
        conn.commit()
        conn.close()
    
    # Проверяем совпадения по подпискам на ключевые слова
    check_keyword_notifications(server, p_text, new_aid)

    bot.answer_callback_query(call.id, "Опубликовано!")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

    try:
        bot.send_message(user_id, f"🎉 **Ваше объявление опубликовано!**\n\n{p_text}", parse_mode="Markdown")
    except Exception:
        pass

@bot.message_handler(content_types=['video'])
def get_video_id(m):
    bot.reply_to(m, f"📋 **Скопируйте этот file_id и вставьте в переменную WELCOME_VIDEO_ID в коде:**\n\n`{m.video.file_id}`", parse_mode="Markdown")

# ==========================================
# ПРОСМОТР ОБЪЯВЛЕНИЙ ПО КАТЕГОРИЯМ
# ==========================================

@bot.message_handler(func=lambda msg: msg.text in CATEGORIES)
def show_ads_category(m):
    cat_idx = CATEGORIES.index(m.text)
    render_category_page(m, m.from_user.id, cat_idx, page=0)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cat_page_"))
def cb_cat_page(call):
    parts = call.data.split("_")
    cat_idx, page = int(parts[2]), int(parts[3])
    render_category_page(call.message, call.from_user.id, cat_idx, page)

def render_category_page(message, user_id: int, cat_idx: int, page: int = 0):
    cat_name = CATEGORIES[cat_idx]
    srv = user_states.get(user_id, {}).get("server", "Phoenix")

    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT id, user_id, text, photo FROM active_ads WHERE category = ? AND server = ? ORDER BY is_vip DESC, id DESC", (cat_name, srv))
        all_ads = cur.fetchall()
        conn.close()

    if not all_ads:
        return bot.send_message(message.chat.id, f"📊 Раздел: **{cat_name}** [{srv}]\nОбъявлений пока нет.", parse_mode="Markdown", reply_markup=kb_main_menu())

    total_pages = (len(all_ads) + ADS_PER_PAGE - 1) // ADS_PER_PAGE
    start_idx = page * ADS_PER_PAGE
    page_ads = all_ads[start_idx:start_idx + ADS_PER_PAGE]

    bot.send_message(message.chat.id, f"📻 **Газета [{srv}] — {cat_name}** (Стр. {page + 1}/{total_pages}):", parse_mode="Markdown")

    for aid, seller_uid, text, photo in page_ads:
        try:
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✉️ Написать продавцу", callback_data=f"contact_seller_{aid}"),
                types.InlineKeyboardButton("❤️ В избранное", callback_data=f"fav_add_{aid}"),
                types.InlineKeyboardButton("⭐ Оценить продавца", callback_data=f"rate_seller_{seller_uid}_{aid}")
            )

            if photo:
                bot.send_photo(message.chat.id, photo, caption=text, parse_mode="Markdown", reply_markup=markup)
            else:
                bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            pass

    markup = types.InlineKeyboardMarkup()
    buttons = []
    if page > 0:
        buttons.append(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"cat_page_{cat_idx}_{page - 1}"))
    if page < total_pages - 1:
        buttons.append(types.InlineKeyboardButton("Вперед ➡️", callback_data=f"cat_page_{cat_idx}_{page + 1}"))
    
    if buttons:
        markup.add(*buttons)
        bot.send_message(message.chat.id, f"📑 Страница {page + 1} из {total_pages}", reply_markup=markup)

# ==========================================
# ЗАПУСК БОТА
# ==========================================

if __name__ == '__main__':
    try:
        bot.remove_webhook()
    except Exception:
        pass

    logger.info("🚀 Бот СМИ со всеми функциями запущен!")
    bot.infinity_polling(skip_pending=True)
