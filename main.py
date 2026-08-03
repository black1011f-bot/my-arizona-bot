import os
import time
import threading
import logging
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

# Вставьте сюда ваш file_id приветственного видео в Telegram
WELCOME_VIDEO_ID = "YOUR_VIDEO_FILE_ID_HERE" 

# Хранилища данных (In-Memory)
user_states = {}
user_data = {}
active_ads = {}
pending_posts = {}
pending_ban_requests = {} 

# Быстрый O(1) поиск для блокировок
banned_ids = set()
banned_usernames = set()

editor_stats = {} 

ads_lock = threading.Lock()
moderation_counter = 0
ban_request_counter = 0

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
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ И ПРОВЕРКИ
# ==========================================

def is_banned(user) -> bool:
    """Мгновенная проверка блокировки пользователя (O(1))."""
    if not user:
        return False
    if user.id in banned_ids:
        return True
    if user.username and user.username.lower().lstrip('@') in banned_usernames:
        return True
    return False

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
    """Хелпер проверки админ-прав для каллбэков."""
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
    """Фоновая очистка просроченных объявлений."""
    while True:
        time.sleep(60)
        now_time = datetime.now().time()
        curr_t = time.time()

        is_night = now_time >= dtime(22, 0, 0) or now_time < dtime(8, 0, 0)
        is_morning_clean = dtime(8, 0, 0) <= now_time <= dtime(8, 5, 0)

        messages_to_delete = []

        with ads_lock:
            expired_ids = [
                aid for aid, data in active_ads.items()
                if (curr_t - data.get("last_updated", 0) > 600) or is_night or is_morning_clean
            ]

            for aid in expired_ids:
                msg_map = active_ads[aid].get("message_ids_map", {})
                for target_id, msg_id in msg_map.items():
                    messages_to_delete.append((target_id, msg_id))
                del active_ads[aid]

        for target_id, msg_id in messages_to_delete:
            try:
                bot.delete_message(target_id, msg_id)
                time.sleep(0.02)
            except Exception:
                pass

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

def ikb_manage_active_ad(aid: int):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("❌ Удалить", callback_data=f"del_active_{aid}"))
    return markup

# ==========================================
# ОСНОВНЫЕ КОМАНДЫ (С ВИДЕО-ПРИВЕТСТВИЕМ)
# ==========================================

@bot.message_handler(commands=['start'])
def cmd_start(m):
    if is_banned(m.from_user):
        return bot.send_message(m.chat.id, "⛔ Вы заблокированы в системе модерации.")
        
    register_admin(m.from_user, m.chat.id)
    
    caption_text = (
        "👋 **Добро пожаловать в Торговый Помощник СМИ Arizona RP!** 🛒✨\n\n"
        "Ваш персональный радиоцентр и торговая площадка прямо в Telegram! "
        "Здесь вы можете быстро находить любые товары, отслеживать актуальные предложения и продавать своё имущество.\n\n"
        "📌 **Что умеет этот бот:**\n"
        "• 🛍 **Удобный каталог:** Просматривайте товары по разделам (авто, аксессуары, недвижимость).\n"
        "• 🔍 **Быстрый поиск:** Находите нужные вещи по ключевым словам за секунды.\n"
        "• 📣 **Подача объявлений:** Отправляйте заявки редакторам СМИ прямо из чата.\n"
        "• ⭐ **VIP-публикация:** Закрепляйте объявления в топе списка и скрывайте контакты.\n"
        "• 📋 **Мои объявления:** Легко управляйте активными публикациями и удаляйте проданное.\n\n"
        "⏱ **Режим работы радиоцентра:** ежедневно с **08:00 до 22:00 МСК**.\n\n"
        "👇 **Для начала работы выберите ваш игровой сервер:**"
    )

    try:
        # Отправка видео с приветствием по file_id
        bot.send_video(
            m.chat.id, 
            WELCOME_VIDEO_ID, 
            caption=caption_text, 
            parse_mode="Markdown", 
            reply_markup=kb_servers()
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить приветственное видео (проверьте WELCOME_VIDEO_ID): {e}")
        # Запасной вариант: обычное текстовое приветствие
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
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📝 Редакция объяв (Заявки)", callback_data="show_pending_list"),
            types.InlineKeyboardButton("🗑 Активные объявления", callback_data="show_active_list"),
            types.InlineKeyboardButton("📊 Статистика редакторов", callback_data="show_editor_stats"),
            types.InlineKeyboardButton("🔨 Управление Банами", callback_data="manage_bans")
        )
        bot.send_message(
            m.chat.id, 
            f"⚙️ **Панель Редактора СМИ**\n📥 Заявок на проверку: **{len(pending_posts)} шт.**", 
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

    results = []
    with ads_lock:
        for ad in active_ads.values():
            if ad.get("server") == srv and query in ad.get("text", "").lower():
                results.append(ad)

    if not results:
        return bot.send_message(m.chat.id, f"🔍 По запросу «**{query}**» объявлений не найдено.", parse_mode="Markdown", reply_markup=kb_main_menu())

    bot.send_message(m.chat.id, f"🔍 Найдено объявлений: **{len(results)} шт.** (Показ первых 10)", parse_mode="Markdown")
    for ad in results[:10]:
        if ad.get("photo"):
            bot.send_photo(m.chat.id, ad["photo"], caption=ad["text"], parse_mode="Markdown")
        else:
            bot.send_message(m.chat.id, ad["text"], parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📋 Мои объявления")
def show_my_ads(m):
    uid = m.from_user.id
    user_ads = []

    with ads_lock:
        for aid, ad in active_ads.items():
            if ad.get("user_id") == uid:
                user_ads.append((aid, ad))

    if not user_ads:
        return bot.send_message(m.chat.id, "📋 У вас нет активных объявлений.", reply_markup=kb_main_menu())

    bot.send_message(m.chat.id, f"📋 **Ваши активные объявления ({len(user_ads)} шт.):**", parse_mode="Markdown")
    for aid, ad in user_ads:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Продано (Удалить)", callback_data=f"user_delete_self_{aid}"))
        
        info = f"🌐 Сервер: {ad['server']}\n📂 Раздел: {ad['category']}\n\n{ad['text']}"
        if ad.get("photo"):
            bot.send_photo(m.chat.id, ad["photo"], caption=info, parse_mode="Markdown", reply_markup=markup)
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
        if uid in user_data and "last_ad_time" in user_data[uid]:
            elapsed = time.time() - user_data[uid]["last_ad_time"]
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
    global moderation_counter

    if not is_vip:
        user_data.setdefault(uid, {})["last_ad_time"] = time.time()

    moderation_counter += 1
    
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

    pending_posts[moderation_counter] = {
        "user_id": uid, 
        "username": uname, 
        "photo": photo, 
        "text": text or "Без описания", 
        "category": category, 
        "server": server_name,
        "is_vip": is_vip
    }

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
# ОПЛАТА TELEGRAM STARS (VIP)
# ==========================================

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
# ПОДАЧА И ОБРАБОТКА ЗАЯВОК НА БАН
# ==========================================

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states and user_states[msg.from_user.id].get("awaiting_ban_target"))
def process_ban_target_input(m):
    uid = m.from_user.id
    user_states[uid].pop("awaiting_ban_target", None)

    if m.text == "🚫 Отмена":
        return bot.send_message(m.chat.id, "Подача заявки отменена.", reply_markup=kb_main_menu())

    target = m.text.strip()
    global ban_request_counter
    ban_request_counter += 1
    req_id = ban_request_counter

    admin_uname = m.from_user.username or m.from_user.first_name

    pending_ban_requests[req_id] = {
        "admin_id": uid,
        "admin_username": admin_uname,
        "target": target
    }

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

# ==========================================
# МОДУЛЬНЫЕ CALLBACK-ХЭНДЛЕРЫ (АДМИН/МОДЕРАЦИЯ)
# ==========================================

@bot.callback_query_handler(func=lambda c: c.data == "show_pending_list")
def cb_show_pending(call):
    if not verify_admin_callback(call): return
    bot.answer_callback_query(call.id)
    if not pending_posts:
        return bot.send_message(call.message.chat.id, "📥 **Заявок пока нет.**")

    for pid, post in list(pending_posts.items()):
        f_text = (
            f"🚨 **Заявка #{pid} {'👑 [VIP]' if post.get('is_vip') else ''}**\n"
            f"🌐 **Сервер:** {post['server']}\n"
            f"📂 **Категория:** {post['category']}\n"
            f"👤 **От игрока:** @{post['username']} (ID: `{post['user_id']}`)\n\n"
            f"📥 **Текст:**\n`{post['text']}`"
        )
        if post.get("photo"):
            bot.send_photo(call.message.chat.id, post["photo"], caption=f_text, parse_mode="Markdown", reply_markup=ikb_moderation(pid))
        else:
            bot.send_message(call.message.chat.id, f_text, parse_mode="Markdown", reply_markup=ikb_moderation(pid))

@bot.callback_query_handler(func=lambda c: c.data == "show_active_list")
def cb_show_active(call):
    if not verify_admin_callback(call): return
    bot.answer_callback_query(call.id)
    with ads_lock:
        if not active_ads:
            return bot.send_message(call.message.chat.id, "📂 Активных объявлений нет.")

        for aid, ad in list(active_ads.items())[:10]:
            info = f"🆔 **Объявление #{aid}**\n🌐 Сервер: {ad['server']}\n\n{ad['text']}"
            if ad.get("photo"):
                bot.send_photo(call.message.chat.id, ad["photo"], caption=info, parse_mode="Markdown", reply_markup=ikb_manage_active_ad(aid))
            else:
                bot.send_message(call.message.chat.id, info, parse_mode="Markdown", reply_markup=ikb_manage_active_ad(aid))

@bot.callback_query_handler(func=lambda c: c.data == "show_editor_stats")
def cb_show_stats(call):
    if not verify_admin_callback(call): return
    bot.answer_callback_query(call.id)
    stats_text = "📊 **Статистика Редакторов:**\n\n"
    for idx, (ed_name, count) in enumerate(sorted(editor_stats.items(), key=lambda x: x[1], reverse=True), 1):
        stats_text += f"{idx}. @{ed_name} — **{count} шт.**\n"
    bot.send_message(call.message.chat.id, stats_text if editor_stats else "Статистика пуста.", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "manage_bans")
def cb_manage_bans(call):
    if not verify_admin_callback(call): return
    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🚫 Подать заявку на бан", callback_data="create_ban_req"),
        types.InlineKeyboardButton("📜 Список забаненных", callback_data="list_banned_users")
    )
    total_banned = len(banned_ids) + len(banned_usernames)
    bot.send_message(
        call.message.chat.id, 
        f"🔨 **Управление банами**\n\nВсего в бане: **{total_banned}**\nОжидают решения: **{len(pending_ban_requests)}**", 
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
        "🔨 **Подача заявки на бан**\n\nВведите `@username` или `ID` (номер аккаунта) пользователя, которого нужно заблокировать:",
        parse_mode="Markdown",
        reply_markup=kb_cancel()
    )

@bot.callback_query_handler(func=lambda c: c.data == "list_banned_users")
def cb_list_banned(call):
    if not verify_admin_callback(call): return
    bot.answer_callback_query(call.id)

    if not banned_ids and not banned_usernames:
        return bot.send_message(call.message.chat.id, "📜 Список заблокированных пользователей пуст.")

    b_list = [f"• ID: `{i}`" for i in banned_ids] + [f"• User: `@{u}`" for u in banned_usernames]
    bot.send_message(call.message.chat.id, "📜 **Список заблокированных:**\n\n" + "\n".join(b_list), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("approve_ban_"))
def cb_approve_ban(call):
    if not verify_admin_callback(call): return
    req_id = int(call.data.split('_')[2])
    
    if req_id not in pending_ban_requests:
        return bot.answer_callback_query(call.id, "Заявка не найдена или обработана.", show_alert=True)

    req = pending_ban_requests.pop(req_id)
    target = req["target"]

    if target.isdigit():
        banned_ids.add(int(target))
    else:
        banned_usernames.add(target.lstrip('@').lower())

    bot.answer_callback_query(call.id, "✅ Бан одобрен!")

    try:
        bot.edit_message_text(
            f"✅ **ЗАЯВКА НА БАН #{req_id} ОДОБРЕНА!**\n\n🎯 Нарушитель `{target}` заблокирован.\n👨‍⚖️ **Одобрил:** @{call.from_user.username or call.from_user.first_name}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
    except Exception:
        pass

    try:
        bot.send_message(req["admin_id"], f"🎉 Ваша заявка на бан `{target}` (Заявка #{req_id}) была **ОДОБРЕНА**!")
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("reject_ban_"))
def cb_reject_ban(call):
    if not verify_admin_callback(call): return
    req_id = int(call.data.split('_')[2])
    
    if req_id not in pending_ban_requests:
        return bot.answer_callback_query(call.id, "Заявка не найдена.", show_alert=True)

    req = pending_ban_requests.pop(req_id)
    bot.answer_callback_query(call.id, "❌ Бан отклонен.")

    try:
        bot.edit_message_text(
            f"❌ **ЗАЯВКА НА БАН #{req_id} ОТКЛОНЕНА**\n\n🎯 Отклонен бан для: `{req['target']}`\n👨‍⚖️ **Отклонил:** @{call.from_user.username or call.from_user.first_name}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
    except Exception:
        pass

    try:
        bot.send_message(req["admin_id"], f"❌ Ваша заявка на бан `{req['target']}` (Заявка #{req_id}) была **ОТКЛОНЕНА**.")
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("ban_author_"))
def cb_ban_author(call):
    if not verify_admin_callback(call): return
    pid = int(call.data.split('_')[2])
    if pid in pending_posts:
        target_uid = pending_posts[pid]["user_id"]
        banned_ids.add(target_uid)
        pending_posts.pop(pid, None)
        bot.answer_callback_query(call.id, f"Автор {target_uid} забанен!", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith("user_delete_self_") or c.data.startswith("del_active_"))
def cb_delete_ad(call):
    aid = int(call.data.split('_')[-1])
    with ads_lock:
        if aid in active_ads:
            del active_ads[aid]
            bot.answer_callback_query(call.id, "✅ Удалено!")
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_text_"))
def cb_edit_text(call):
    if not verify_admin_callback(call): return
    pid = int(call.data.split('_')[2])
    post = pending_posts.get(pid, {})
    user_states[call.from_user.id] = {"editing": pid}
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"✏️ **Редактирование заявки #{pid}:**\n`{post.get('text', '')}`", parse_mode="Markdown", reply_markup=kb_cancel())

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states and "editing" in user_states[msg.from_user.id])
def process_editing(m):
    uid = m.from_user.id
    pid = user_states[uid].pop("editing", None)

    if pid and pid in pending_posts:
        pending_posts[pid]["text"] = m.text
        bot.send_message(m.chat.id, f"✅ Отредактировано:\n\n{m.text}", parse_mode="Markdown", reply_markup=ikb_moderation(pid))

@bot.callback_query_handler(func=lambda c: c.data.startswith("owner_approve_"))
def cb_approve_post(call):
    if not verify_admin_callback(call): return
    pid = int(call.data.split('_')[2])
    if pid not in pending_posts: 
        return bot.answer_callback_query(call.id, "Заявка не найдена.")

    post = pending_posts.pop(pid)
    editor_uname = call.from_user.username or call.from_user.first_name
    editor_stats[editor_uname] = editor_stats.get(editor_uname, 0) + 1

    p_text = format_smi_post(
        post['server'], post['category'], post['text'], 
        post['username'], editor_uname, is_vip=post.get("is_vip", False)
    )
    
    with ads_lock:
        active_ads[pid] = {
            "user_id": post["user_id"],
            "text": p_text, 
            "photo": post["photo"], 
            "server": post["server"],
            "category": post["category"],
            "is_vip": post.get("is_vip", False),
            "last_updated": time.time(),
            "message_ids_map": {}
        }
    
    bot.answer_callback_query(call.id, "Опубликовано!")
    try:
        bot.send_message(post["user_id"], f"🎉 **Ваше объявление опубликовано!**\n\n{p_text}", parse_mode="Markdown")
    except Exception:
        pass

# ==========================================
# ВРЕМЕННЫЙ ХЕНДЛЕР ДЛЯ ПОЛУЧЕНИЯ FILE_ID ВИДЕО
# ==========================================
@bot.message_handler(content_types=['video'])
def get_video_id(m):
    bot.reply_to(m, f"📋 **File ID этого видео:**\n`{m.video.file_id}`", parse_mode="Markdown")

# ==========================================
# ПРОСМОТР ОБЪЯВЛЕНИЙ ПО КАТЕГОРИЯМ (ПАГИНАЦИЯ)
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

    with ads_lock:
        vip_ads = [ad for ad in active_ads.values() if ad.get("category") == cat_name and ad.get("server") == srv and ad.get("is_vip")]
        std_ads = [ad for ad in active_ads.values() if ad.get("category") == cat_name and ad.get("server") == srv and not ad.get("is_vip")]
        all_ads = vip_ads + std_ads

    if not all_ads:
        return bot.send_message(message.chat.id, f"📊 Раздел: **{cat_name}** [{srv}]\nОбъявлений пока нет.", parse_mode="Markdown", reply_markup=kb_main_menu())

    total_pages = (len(all_ads) + ADS_PER_PAGE - 1) // ADS_PER_PAGE
    start_idx = page * ADS_PER_PAGE
    page_ads = all_ads[start_idx:start_idx + ADS_PER_PAGE]

    bot.send_message(message.chat.id, f"📻 **Газета [{srv}] — {cat_name}** (Стр. {page + 1}/{total_pages}):", parse_mode="Markdown")

    for ad in page_ads:
        try:
            if ad.get("photo"):
                bot.send_photo(message.chat.id, ad["photo"], caption=ad['text'], parse_mode="Markdown")
            else:
                bot.send_message(message.chat.id, ad['text'], parse_mode="Markdown")
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

    logger.info("🚀 Высокопроизводительный бот СМИ запущен с видео-приветствием!")
    bot.infinity_polling(skip_pending=True)
