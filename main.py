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

# Вставьте сюда ваш полученный file_id видео (или оставьте пустым, пока не отправите боту видео)
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

        conn.commit()
        conn.close()

init_db()

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

def format_smi_post(server: str, category: str, text: str, player_username: str, editor_username: str, is_vip: bool = False) -> str:
    clean_srv = clean_server_name(server)
    if is_vip:
        player_contact = "🛡️ [Контакт скрыт по желанию VIP]"
        vip_header = "👑 **[VIP ОБЪЯВЛЕНИЕ]**\n"
    else:
        player_contact = f"@{player_username}" if player_username and player_username != "Без юзернейма" else "Не указан"
        vip_header = ""

    editor_contact = f"@{editor_username}" if editor_username else "СМИ"

    return (
        f"{vip_header}"
        f"📰 | **[СМИ {clean_srv}] Объявление:**\n"
        f"📞 **Контакт игрока:** {player_contact}\n\n"
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
    m.add(types.KeyboardButton("👑 Админ"))
    return m

def kb_main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("💍 Аксессуары", "🏎 Транспорт и Тюнинг")
    m.add("🥼 Скины и Охранники", "🏡 Недвижимость и Бизнес")
    m.add("📦 Ресурсы и Оружие")
    m.add("🔍 Поиск по товарам", "📋 Мои объявления")
    m.add("📊 Откуда цены?", "🛒 Подать объявление о продаже")
    m.add("🔄 Сменить сервер", "👑 Админ")
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
# ОСНОВНЫЕ КОМАНДЫ
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
        "Здесь вы можете быстро находить любые товары, отслеживать актуальные предложения и продавать своё имущество.\n\n"
        "📌 **Что умеет этот бот:**\n"
        "• 🛍 **Удобный каталог:** Просматривайте товары по разделам.\n"
        "• 🔍 **Быстрый поиск:** Находите нужные вещи по ключевым словам.\n"
        "• 📣 **Подача объявлений:** Отправляйте заявки редакторам СМИ прямо из чата.\n"
        "• ⭐ **VIP-публикация:** Закрепляйте объявления в топе списка.\n\n"
        "⏱ **Режим работы радиоцентра:** ежедневно с **08:00 до 22:00 МСК**.\n\n"
        "👇 **Для начала работы выберите ваш игровой сервер:**"
    )

    # Проверка: если вы указали реальный file_id видео, бот отправит его. Если нет — отправит текст.
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

    # Запасной вариант (если видео еще не настроено)
    bot.send_message(m.chat.id, caption_text, parse_mode="Markdown", reply_markup=kb_servers())

@bot.message_handler(commands=['help'])
def cmd_help(m):
    text = (
        "❓ **Помощь по использованию бота**\n\n"
        "1️⃣ Выберите игровой сервер.\n"
        "2️⃣ Выбирайте категории для просмотра активных объявлений.\n"
        "3️⃣ Подавайте объявления обычной или VIP публикацией (1 ⭐️ Stars).\n\n"
        "⏱ **График работы СМИ:** ежедневно с **08:00 до 22:00 МСК**."
    )
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📊 Откуда цены?")
def show_prices_info(m):
    bot.send_message(
        m.chat.id, 
        "📊 **Откуда мы берем цены?**\n\nВсе цены формируются на основе реальных сделок и проходят проверку СМИ.", 
        parse_mode="Markdown"
    )

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
            types.InlineKeyboardButton("🔨 Управление Банами", callback_data="manage_bans")
        )
        bot.send_message(
            m.chat.id, 
            f"⚙️ **Панель Редактора СМИ**\n📥 Заявок на проверку: **{pending_count} шт.**", 
            parse_mode="Markdown",
            reply_markup=markup
        )
    else:
        bot.send_message(m.chat.id, "⛔ У вас нет доступа к радиоцентру.")

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
        cur.execute("SELECT text, photo FROM active_ads WHERE server = ? AND LOWER(text) LIKE ?", (srv, f"%{query}%"))
        results = cur.fetchall()
        conn.close()

    if not results:
        return bot.send_message(m.chat.id, f"🔍 По запросу «**{query}**» объявлений не найдено.", parse_mode="Markdown", reply_markup=kb_main_menu())

    bot.send_message(m.chat.id, f"🔍 Найдено объявлений: **{len(results)} шт.** (Показ первых 10)", parse_mode="Markdown")
    for text, photo in results[:10]:
        if photo:
            bot.send_photo(m.chat.id, photo, caption=text, parse_mode="Markdown")
        else:
            bot.send_message(m.chat.id, text, parse_mode="Markdown")

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
# СОЗДАНИЕ И ПУБЛИКАЦИЯ ОБЪЯВЛЕНИЙ
# ==========================================

@bot.message_handler(func=lambda msg: msg.text == "🛒 Подать объявление о продаже")
def start_ad_creation(m):
    if is_banned(m.from_user):
        return bot.send_message(m.chat.id, "⛔ Вы заблокированы в системе модерации.")

    if not check_working_hours():
        return bot.send_message(m.chat.id, "❌ Радиоцентр закрыт! Подача объявлений доступна с 08:00 до 22:00 МСК.")

    uid = m.from_user.id
    if uid not in user_states or "server" not in user_states[uid]:
        return bot.send_message(m.chat.id, "⚠️ Сначала выберите сервер из меню!", reply_markup=kb_servers())

    bot.send_message(
        m.chat.id,
        "⭐ **Выберите формат подачи:**\n\n"
        "• **Обычное:** Бесплатно, с кулдауном 10 минут.\n"
        "• **VIP (1 ⭐️ Star):** Без кулдауна, скрывает контакт, всегда **вверху списка**!",
        reply_markup=ikb_vip_choice()
    )

@bot.callback_query_handler(func=lambda call: call.data in ["type_ad_vip", "type_ad_std"])
def select_ad_type(call):
    uid = call.from_user.id
    user_states.setdefault(uid, {"server": "Phoenix"})

    is_vip = (call.data == "type_ad_vip")

    if not is_vip:
        last_time = get_user_last_ad_time(uid)
        elapsed = time.time() - last_time
        if elapsed < 600:
            remaining = int(600 - elapsed)
            return bot.answer_callback_query(
                call.id, 
                f"❌ Кулдаун! Подождите {remaining // 60} мин. {remaining % 60} сек.", 
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
            logger.error(f"Ошибка вызова счета Stars: {e}")

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

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def process_successful_payment(m):
    uid = m.from_user.id
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
# МОДУЛЬ АДМИНИСТРИРОВАНИЯ И БАНОВ
# ==========================================

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
        username, editor_uname, is_vip=bool(is_vip)
    )
    
    with db_lock:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO active_ads (user_id, server, category, text, photo, is_vip, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, server, category, p_text, photo, is_vip, time.time()))
        conn.commit()
        conn.close()
    
    bot.answer_callback_query(call.id, "Опубликовано!")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

    try:
        bot.send_message(user_id, f"🎉 **Ваше объявление опубликовано!**\n\n{p_text}", parse_mode="Markdown")
    except Exception:
        pass

# ==========================================
# АВТО-ПОЛУЧЕНИЕ FILE_ID ВИДЕО
# ==========================================
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
        cur.execute("SELECT text, photo FROM active_ads WHERE category = ? AND server = ? ORDER BY is_vip DESC, id DESC", (cat_name, srv))
        all_ads = cur.fetchall()
        conn.close()

    if not all_ads:
        return bot.send_message(message.chat.id, f"📊 Раздел: **{cat_name}** [{srv}]\nОбъявлений пока нет.", parse_mode="Markdown", reply_markup=kb_main_menu())

    total_pages = (len(all_ads) + ADS_PER_PAGE - 1) // ADS_PER_PAGE
    start_idx = page * ADS_PER_PAGE
    page_ads = all_ads[start_idx:start_idx + ADS_PER_PAGE]

    bot.send_message(message.chat.id, f"📻 **Газета [{srv}] — {cat_name}** (Стр. {page + 1}/{total_pages}):", parse_mode="Markdown")

    for text, photo in page_ads:
        try:
            if photo:
                bot.send_photo(message.chat.id, photo, caption=text, parse_mode="Markdown")
            else:
                bot.send_message(message.chat.id, text, parse_mode="Markdown")
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

    logger.info("🚀 Бот СМИ запущен!")
    bot.infinity_polling(skip_pending=True)
