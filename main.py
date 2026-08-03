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
            CREATE TABLE IF NOT EXISTS bans (
                target TEXT PRIMARY KEY,
                is_id INTEGER
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

def register_admin(user, chat_id: int):
    if user and (user.username and user.username.lower() in ADMIN_USERNAMES or user.username.lower() == OWNER_USERNAME.lower()):
        ADMIN_CHAT_IDS.add(chat_id)

def clean_server_name(server: str) -> str:
    return server.split(' ', 1)[-1] if ' ' in server else server

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

def ikb_chat_controls(aid: int):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🛑 Завершить диалог", callback_data=f"stop_chat_{aid}"),
        types.InlineKeyboardButton("🔄 Возобновить / Начать заново", callback_data=f"resume_chat_{aid}")
    )
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
        "👋 ДОБРО ПОЖАЛОВАТЬ В ЦЕНТР ЦЕН!\n"
        "Здесь ты узнаешь все актуальные цены ARIZONA RP!\n\n"
        "⏱ Режим работы радиоцентра: ежедневно с 08:00 до 22:00 МСК.\n\n"
        "👇 Для начала работы выберите ваш игровой сервер:"
    )
    bot.send_message(m.chat.id, caption_text, reply_markup=kb_servers())

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

    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO active_dialogs (buyer_id, seller_id, ad_id, is_active) VALUES (?, ?, ?, 1)", (buyer_id, seller_id, aid))
        conn.commit()
        conn.close()

    bot.answer_callback_query(call.id)
    
    safe_preview = (ad_text[:47] + "...") if len(ad_text) > 50 else ad_text
    user_states[buyer_id] = {
        "messaging_seller": True,
        "seller_id": seller_id,
        "ad_id": aid,
        "ad_info": f"[{server}] {category}: {safe_preview}"
    }

    bot.send_message(
        call.message.chat.id,
        "✍️ **Связь с продавцом через бота**\n\n"
        "Отправьте ваше сообщение. Вы можете в любой момент завершить или возобновить диалог кнопками ниже.",
        parse_mode="Markdown",
        reply_markup=ikb_chat_controls(aid)
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("stop_chat_"))
def cb_stop_chat(call):
    aid = int(call.data.split("_")[2])
    uid = call.from_user.id
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("UPDATE active_dialogs SET is_active = 0 WHERE buyer_id = ? AND ad_id = ?", (uid, aid))
        conn.commit()
        conn.close()

    bot.answer_callback_query(call.id, "🛑 Диалог завершен!")
    bot.send_message(call.message.chat.id, "❌ Диалог с продавцом приостановлен.", reply_markup=ikb_chat_controls(aid))

@bot.callback_query_handler(func=lambda c: c.data.startswith("resume_chat_"))
def cb_resume_chat(call):
    aid = int(call.data.split("_")[2])
    uid = call.from_user.id
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("UPDATE active_dialogs SET is_active = 1 WHERE buyer_id = ? AND ad_id = ?", (uid, aid))
        conn.commit()
        conn.close()

    bot.answer_callback_query(call.id, "🔄 Диалог возобновлен!")
    bot.send_message(call.message.chat.id, "✅ Диалог возобновлен! Можете продолжать общение.", reply_markup=ikb_chat_controls(aid))

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states and user_states[msg.from_user.id].get("messaging_seller"))
def process_message_to_seller(m):
    uid = m.from_user.id
    state_data = user_states[uid]
    aid = state_data.get("ad_id")
    seller_id = state_data.get("seller_id")

    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT is_active FROM active_dialogs WHERE buyer_id = ? AND ad_id = ?", (uid, aid))
        row = cur.fetchone()
        conn.close()

    if not row or row[0] == 0:
        return bot.send_message(m.chat.id, "⚠️ Диалог завершен. Нажмите кнопку возобновления.")

    forward_text = (
        f"📩 Сообщение по объявлению!\n\n"
        f"📌 Товар ID: {aid}\n"
        f"💬 Текст:\n{m.text}"
    )

    try:
        bot.send_message(seller_id, forward_text, reply_markup=ikb_chat_controls(aid))
        bot.send_message(m.chat.id, "✅ Сообщение доставлено продавцу!", reply_markup=ikb_chat_controls(aid))
    except Exception as e:
        logger.error(f"Ошибка доставки продавцу: {e}")
        bot.send_message(m.chat.id, "❌ Не удалось доставить сообщение.")

# ==========================================
# КАТЕГОРИИ И СЕРВЕРА
# ==========================================

@bot.message_handler(func=lambda msg: msg.text in CATEGORIES)
def show_ads_category(m):
    cat_idx = CATEGORIES.index(m.text)
    render_category_page(m, m.from_user.id, cat_idx, page=0)

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

    for aid, seller_uid, text, photo in all_ads[:ADS_PER_PAGE]:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✉️ Написать продавцу", callback_data=f"contact_seller_{aid}"))
        if photo:
            bot.send_photo(message.chat.id, photo, caption=text, reply_markup=markup)
        else:
            bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in SERVERS)
def select_srv(m):
    user_states.setdefault(m.from_user.id, {})["server"] = m.text
    bot.send_message(m.chat.id, f"Сервер **{m.text}** выбран!", parse_mode="Markdown", reply_markup=kb_main_menu())

# ==========================================
# ЗАПУСК БОТА
# ==========================================
if __name__ == '__main__':
    try:
        bot.remove_webhook()
    except Exception:
        pass

    logger.info("🚀 Бот СМИ успешно запущен!")
    bot.infinity_polling(skip_pending=True)
