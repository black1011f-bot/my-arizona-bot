import os
import time
import threading
import logging
from datetime import datetime, time as dtime
import telebot
from telebot import types

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==========================================
# КОНФИГУРАЦИЯ И ТОКЕН
# ==========================================
TOKEN = os.getenv("BOT_TOKEN", "8916669266:AAGMsyFa-_OZBs8beZ7vIEi8bKX6uvRUrM8")
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=15)

OWNER_USERNAME = "bounqy"
ADMIN_USERNAMES = ["bounqy31", "bounqy"]

ADMIN_CHAT_IDS = set() 
MODERATION_CHAT_ID = int(os.getenv("MODERATION_CHAT_ID", "0"))

# Хранилища данных
user_states = {}
user_data = {}
active_ads = {}
pending_posts = {}
banned_users = set()
editor_stats = {} # { "username": approved_count }

ads_lock = threading.Lock()
moderation_counter = 0

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

PRO_TAGS = {
    "💍 Аксессуары": "а/с",
    "🏎 Транспорт и Тюнинг": "т/с",
    "🥼 Скины и Охранники": "с/к",
    "🏡 Недвижимость и Бизнес": "д/м",
    "📦 Ресурсы и Оружие": "р/с"
}

# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

def background_cleanup_ads():
    """Фоновая очистка старых объявлений."""
    while True:
        time.sleep(30)
        now = datetime.now()
        now_time = now.time()
        curr_t = time.time()

        is_night = now_time >= dtime(22, 0, 22) or now_time < dtime(8, 0, 0)
        is_morning_clean = dtime(8, 0, 0) <= now_time <= dtime(8, 5, 22)

        messages_to_delete = []

        with ads_lock:
            expired_ids = []
            for aid, data in list(active_ads.items()):
                if (curr_t - data.get("last_updated", 0) > 600) or is_night or is_morning_clean:
                    expired_ids.append(aid)

            for aid in expired_ids:
                msg_map = active_ads[aid].get("message_ids_map", {})
                for target_id, msg_id in list(msg_map.items()):
                    messages_to_delete.append((target_id, msg_id))
                del active_ads[aid]

        for target_id, msg_id in messages_to_delete:
            try:
                bot.delete_message(target_id, msg_id)
                time.sleep(0.04)
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение {msg_id}: {e}")

threading.Thread(target=background_cleanup_ads, daemon=True).start()

def is_owner(user):
    return user and user.username and user.username.lower() == OWNER_USERNAME.lower()

def is_admin_or_owner(user):
    if not user: 
        return False
    if is_owner(user): 
        return True
    if user.username:
        return user.username.lower() in [a.lower() for a in ADMIN_USERNAMES]
    return False

def register_admin(user, chat_id):
    if is_admin_or_owner(user):
        ADMIN_CHAT_IDS.add(chat_id)

def check_working_hours():
    now_time = datetime.now().time()
    if now_time < dtime(8, 0, 0) or now_time > dtime(22, 0, 22):
        return False
    return True

def format_smi_post(server, category, text, player_username, editor_username, is_vip=False):
    clean_server = server.replace('🔥 ', '').replace('🌴 ', '').replace('🌵 ', '').replace('⚜️ ', '').replace('❄️ ', '').replace('🌊 ', '').replace('✨ ', '').replace('🏛 ', '').replace('❤️ ', '').replace('🍀 ', '').replace('⚡️ ', '').replace('🌲 ', '').replace('👑 ', '').replace('⚓️ ', '').replace('💎 ', '').replace('📜 ', '').replace('☀️ ', '').replace('🎄 ', '').replace('🌌 ', '').replace('🎁 ', '').replace('🐝 ', '').replace('🪞 ', '').replace('💖 ', '').replace('📱 ', '')
    
    if is_vip:
        player_contact = "🛡️ [Контакт скрыт по желанию VIP]"
        vip_header = "👑 **[VIP ОБЪЯВЛЕНИЕ]**\n"
    else:
        player_contact = f"@{player_username}" if player_username and player_username != "Без юзернейма" else "Не указан"
        vip_header = ""

    editor_contact = f"@{editor_username}" if editor_username else "СМИ"

    return (
        f"{vip_header}"
        f"📰 | **[СМИ {clean_server}] Объявление:**\n"
        f"📞 **Контакт игрока:** {player_contact}\n\n"
        f"{text}\n\n"
        f"📂 **Раздел:** {category}\n"
        f"👨‍💻 **Отредактировал:** {editor_contact}"
    )

def send_admins_notification_async(recipients, photo, f_text, counter):
    for target_id in recipients:
        try:
            if photo: 
                bot.send_photo(target_id, photo, caption=f_text, parse_mode="Markdown", reply_markup=ikb_moderation(counter))
            else: 
                bot.send_message(target_id, f_text, parse_mode="Markdown", reply_markup=ikb_moderation(counter))
            time.sleep(0.04)
        except Exception as e:
            logger.warning(f"Не удалось доставить уведомление админу {target_id}: {e}")

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

def ikb_moderation(pid):
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

def ikb_manage_active_ad(aid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✏️ Переписать", callback_data=f"reedit_active_{aid}"),
        types.InlineKeyboardButton("❌ Удалить", callback_data=f"del_active_{aid}")
    )
    return markup

# ==========================================
# ОБРАБОТКА КОМАНД
# ==========================================

@bot.message_handler(commands=['start'])
def cmd_start(m):
    if m.from_user.id in banned_users:
        return bot.send_message(m.chat.id, "⛔ Вы заблокированы в системе модерации.")
        
    register_admin(m.from_user, m.chat.id)
    text = (
        "👋 **Добро пожаловать в Торговый Помощник Arizona RP!** 🛒✨\n\n"
        "ℹ️ **ВАЖНОЕ ПРИМЕЧАНИЕ:**\n"
        "Мы — **НЕОФИЦИАЛЬНЫЙ** бот-помощник и площадка объявлений СМИ Arizona RP. "
        "Мы помогаем игрокам находить покупателей, свежие цены и редактировать объявления по правилам ПРО! 📰\n\n"
        "🛡️ **ПРАВИЛА БЕЗОПАСНОСТИ:**\n"
        "• 🔒 **Никогда и никому** не передавайте пароли, привязки или код безопасности от вашего игрового аккаунта!\n"
        "• 🤝 **Все сделки** совершайте **строго внутри игры** через трейд (`/trade`), Лавки на ЦР или Центр Обмена Имуществом.\n"
        "• ⚠️ Администрация бота **никогда не попросит** ваши личные данные от игры.\n\n"
        "👇 **Для начала работы выберите ваш сервер:**"
    )
    bot.send_message(m.chat.id, text, parse_mode="Markdown", reply_markup=kb_servers())

@bot.message_handler(commands=['help'])
def cmd_help(m):
    text = (
        "❓ **Вопросы / Помощь по использованию бота**\n\n"
        "🛠 **Как пользоваться ботом:**\n"
        "1️⃣ **Выбор сервера:** В самом начале выберите ваш игровой сервер Arizona RP.\n"
        "2️⃣ **Просмотр рынка:** Нажимайте на категории (*«💍 Аксессуары»*, *«🏎 Транспорт»* и т.д.), чтобы посмотреть свежие объявления от других игроков.\n"
        "3️⃣ **Подача объявления:**\n"
        "   • Нажмите **«🛒 Подать объявление о продаже»**.\n"
        "   • Выберите формат (Обычный или VIP ⭐).\n"
        "   • Выберите раздел товара.\n"
        "   • Напишите текст объявления (и прикрепите фото по желанию).\n"
        "   • Редакторы СМИ проверят его по правилам ПРО и опубликуют!\n\n"
        "⏱ **Режим работы СМИ:** Подача и публикация объявлений доступны ежедневно с **08:00 до 22:00 МСК**.\n\n"
        "🛡 **Безопасность:** Помните, что все сделки совершаются только в игре (`/trade`, лавки ЦР)."
    )
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📊 Откуда цены?")
def show_prices_info(m):
    text = (
        "📊 **Откуда мы берем цены?**\n\n"
        "Наш бот — это живой справочник рыночной экономики!\n\n"
        "🤝 **Только реальный рынок:** Все ценники формируются на основе реальных сделок.\n"
        "🚫 **Никакой отсебятины:** Все объявления проходят редактирование по ПРО СМИ."
    )
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

# ==========================================
# 👑 АДМИН-ПАНЕЛЬ, СТАТИСТИКА И БАНЫ
# ==========================================

@bot.message_handler(commands=['admin'])
@bot.message_handler(func=lambda msg: msg.text == "👑 Админ")
def cmd_admin(m):
    u = m.from_user
    register_admin(u, m.chat.id)
    if is_admin_or_owner(u):
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📝 Редакция объяв (Заявки игроков)", callback_data="show_pending_list"),
            types.InlineKeyboardButton("🗑 Активные объявления", callback_data="show_active_list"),
            types.InlineKeyboardButton("📊 Статистика редакторов", callback_data="show_editor_stats"),
            types.InlineKeyboardButton("🔨 Управление Банами", callback_data="manage_bans")
        )
        bot.send_message(
            m.chat.id, 
            f"⚙️ **Панель Редактора СМИ**\n"
            f"👤 Должность: {'Гл. Редактор (Владелец)' if is_owner(u) else 'Редактор (Админ)'}\n"
            f"📥 Заявок на проверку: **{len(pending_posts)} шт.**", 
            parse_mode="Markdown",
            reply_markup=markup
        )
    else:
        bot.send_message(m.chat.id, "⛔ У вас нет доступа к радиоцентру.")

@bot.message_handler(func=lambda msg: msg.text in SERVERS)
def select_srv(m):
    if m.from_user.id not in user_states:
        user_states[m.from_user.id] = {}
    user_states[m.from_user.id]["server"] = m.text
    bot.send_message(
        m.chat.id, 
        f"Сервер **{m.text}** выбран! Выберите нужную категорию или действие:", 
        parse_mode="Markdown", 
        reply_markup=kb_main_menu()
    )

@bot.message_handler(func=lambda msg: msg.text == "🔄 Сменить сервер")
def ch_srv(m): 
    bot.send_message(m.chat.id, "Выберите ваш сервер:", reply_markup=kb_servers())

@bot.message_handler(func=lambda msg: msg.text == "🚫 Отмена")
def cancel_all(m):
    user_states.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, "Действие отменено. Главное меню:", reply_markup=kb_main_menu())

# ==========================================
# 🔍 ПОИСК ПО КЛЮЧЕВЫМ СЛОВАМ
# ==========================================

@bot.message_handler(func=lambda msg: msg.text == "🔍 Поиск по товарам")
def start_search(m):
    uid = m.from_user.id
    srv = user_states.get(uid, {}).get("server")
    if not srv:
        return bot.send_message(m.chat.id, "⚠️ Сначала выберите сервер!", reply_markup=kb_servers())

    bot.send_message(m.chat.id, f"🔍 **Поиск по серверу [{srv}]**\n\nВведите название предмета или ключевое слово (например: *Нимб*, *+12*, *бизнес*):", parse_mode="Markdown", reply_markup=kb_cancel())
    bot.register_next_step_handler(m, process_search_query)

def process_search_query(m):
    if m.text == "🚫 Отмена":
        return bot.send_message(m.chat.id, "Поиск отменен.", reply_markup=kb_main_menu())

    query = m.text.lower().strip()
    uid = m.from_user.id
    srv = user_states.get(uid, {}).get("server", "Phoenix")

    results = []
    with ads_lock:
        for aid, ad in active_ads.items():
            if ad.get("server") == srv and query in ad.get("text", "").lower():
                results.append(ad)

    if not results:
        return bot.send_message(m.chat.id, f"🔍 По запросу «**{query}**» объявлений не найдено.", parse_mode="Markdown", reply_markup=kb_main_menu())

    bot.send_message(m.chat.id, f"🔍 Найдено объявлений: **{len(results)} шт.**", parse_mode="Markdown")
    for ad in results:
        if ad.get("photo"):
            bot.send_photo(m.chat.id, ad["photo"], caption=ad["text"], parse_mode="Markdown")
        else:
            bot.send_message(m.chat.id, ad["text"], parse_mode="Markdown")

# ==========================================
# 📋 УПРАВЛЕНИЕ СВОИМИ ОБЪЯВЛЕНИЯМИ
# ==========================================

@bot.message_handler(func=lambda msg: msg.text == "📋 Мои объявления")
def show_my_ads(m):
    uid = m.from_user.id
    user_ads = []

    with ads_lock:
        for aid, ad in active_ads.items():
            if ad.get("user_id") == uid:
                user_ads.append((aid, ad))

    if not user_ads:
        return bot.send_message(m.chat.id, "📋 У вас пока нет активных опубликованных объявлений.", reply_markup=kb_main_menu())

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
# ПОДАЧА ОБЪЯВЛЕНИЯ ИГРОКОМ (ОБЫЧНОЕ / VIP)
# ==========================================

@bot.message_handler(func=lambda msg: msg.text == "🛒 Подать объявление о продаже")
def start_ad_creation(m):
    uid = m.from_user.id
    if uid in banned_users:
        return bot.send_message(m.chat.id, "⛔ Вы заблокированы в системе модерации.")

    if not check_working_hours():
        return bot.send_message(m.chat.id, "❌ Радиоцентр закрыт! Подача объявлений с 22:00 до 08:00 МСК заблокирована.")

    if uid not in user_states or "server" not in user_states[uid]:
        return bot.send_message(m.chat.id, "⚠️ Сначала выберите сервер из главного меню!", reply_markup=kb_servers())

    bot.send_message(
        m.chat.id,
        "⭐ **Выберите формат подачи объявления:**\n\n"
        "• **Обычное:** Бесплатно, отправляется в общую ленту.\n"
        "• **VIP (1 ⭐️ Stars):** Закрепляется **в самом верху** категории + Контакт автоматически скрыт!\n"
        "*(На VIP-объявления кулдаун не распространяется)*",
        reply_markup=ikb_vip_choice()
    )

@bot.callback_query_handler(func=lambda call: call.data in ["type_ad_vip", "type_ad_std"])
def select_ad_type(call):
    uid = call.from_user.id
    if uid not in user_states:
        user_states[uid] = {"server": "Phoenix"}

    is_vip = (call.data == "type_ad_vip")

    # Кулдаун проверяется ТОЛЬКО для обычных объявлений!
    if not is_vip:
        if uid in user_data and "last_ad_time" in user_data[uid]:
            elapsed = time.time() - user_data[uid]["last_ad_time"]
            if elapsed < 600:
                remaining = int(600 - elapsed)
                bot.answer_callback_query(
                    call.id, 
                    f"❌ Кулдаун! Подождите {remaining // 60} мин. {remaining % 60} сек. перед обычным объявлением.", 
                    show_alert=True
                )
                return

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

    if uid not in user_states:
        user_states[uid] = {"server": "Phoenix"}

    user_states[uid]["selected_category"] = selected_cat

    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        f"✅ Выбран раздел: **{selected_cat}**\n\n"
        "👇 Отправьте описание предмета (и при желании фото).\n"
        "💡 *Пример: Продам машинку на ПУ (+12). Цена: 25кк*",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="Markdown"
    )
    bot.send_message(call.message.chat.id, "Ожидаю описание предмета...", reply_markup=kb_cancel())
    bot.register_next_step_handler(call.message, process_sub)

def process_sub(m):
    global moderation_counter
    uid = m.from_user.id

    if m.text == "🚫 Отмена":
        return bot.send_message(m.chat.id, "Отменено.", reply_markup=kb_main_menu())
    
    photo = m.photo[-1].file_id if m.photo else None
    text = m.caption or m.text

    if not photo and not text:
        bot.send_message(m.chat.id, "❌ Сообщение пустое. Отправьте текст объявления.")
        return bot.register_next_step_handler(m, process_sub)

    if uid not in user_states or "selected_category" not in user_states[uid]:
        return bot.send_message(m.chat.id, "⚠️ Произошла ошибка. Попробуйте еще раз.", reply_markup=kb_main_menu())

    server_name = user_states[uid].get("server", "Phoenix")
    category = user_states[uid].get("selected_category", CATEGORIES[0])
    is_vip = user_states[uid].get("is_vip", False)

    # Если выбрана VIP публикация — отправляем счет на 1 Telegram Star
    if is_vip:
        try:
            prices = [types.LabeledPrice(label="VIP Объявление", amount=1)]
            bot.send_invoice(
                m.chat.id,
                title="👑 VIP-Объявление в СМИ",
                description="Поднятие в топ категории + Скрытие контакта",
                invoice_payload=f"vip_ad_payload_{uid}_{int(time.time())}",
                provider_token="",
                currency="XTR",
                prices=prices
            )
            # Сохраняем временные данные до оплаты
            user_states[uid]["pending_vip_data"] = {
                "photo": photo, "text": text, "category": category, "server": server_name
            }
            return
        except Exception as e:
            logger.error(f"Ошибка вызова счета Stars: {e}")
            bot.send_message(m.chat.id, "⚠️ Ошибка вызова оплаты Stars. Подаем как обычное объявление.")

    finalize_ad_submission(m, uid, photo, text, category, server_name, is_vip=False)

def finalize_ad_submission(m_or_chat_id, uid, photo, text, category, server_name, is_vip=False):
    global moderation_counter

    # Кулдаун обновляем ТОЛЬКО для обычных объявлений
    if not is_vip:
        if uid not in user_data: 
            user_data[uid] = {}
        user_data[uid]["last_ad_time"] = time.time()

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

    bot.send_message(chat_id, "✅ **Ваше объявление отправлено редакторам СМИ!**\nОжидайте модерации.", reply_markup=kb_main_menu())

# ==========================================
# ⭐️ ОПЛАТА TELEGRAM STARS (VIP)
# ==========================================

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def process_successful_payment(m):
    uid = m.from_user.id
    vip_data = user_states.get(uid, {}).get("pending_vip_data")
    
    try:
        bot.send_message(
            m.chat.id,
            f"🎉 **Оплата 1 ⭐️ прошла успешно!** Ваше VIP-объявление передано редакторам."
        )
        logger.info(f"Игрок @{m.from_user.username} ({uid}) оплатил 1 ⭐️ Telegram Star для VIP.")
    except Exception as e:
        logger.warning(f"Ошибка отправки сообщения об оплате: {e}")

    if vip_data:
        finalize_ad_submission(
            m.chat.id, uid, 
            vip_data["photo"], vip_data["text"], 
            vip_data["category"], vip_data["server"], 
            is_vip=True
        )

# ==========================================
# ОБРАБОТКА ИНЛАЙН-КНОПОК И МОДЕРАЦИИ
# ==========================================

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    global pending_posts, banned_users
    data = call.data
    u = call.from_user
    register_admin(u, call.message.chat.id)

    if data == "show_pending_list":
        if not is_admin_or_owner(u):
            return bot.answer_callback_query(call.id, "⛔ Нет доступа!", show_alert=True)

        bot.answer_callback_query(call.id)
        if not pending_posts:
            return bot.send_message(call.message.chat.id, "📥 **Очередь СМИ пуста!** Новых заявок от игроков пока нет.")

        bot.send_message(call.message.chat.id, f"📝 **Очередь на редакцию ({len(pending_posts)} шт.):**", parse_mode="Markdown")
        
        for pid, post in list(pending_posts.items()):
            f_text = (
                f"🚨 **Заявка #{pid} {'👑 [VIP]' if post.get('is_vip') else ''}**\n"
                f"🌐 **Сервер:** {post['server']}\n"
                f"📂 **Категория:** {post['category']}\n"
                f"👤 **От игрока:** @{post['username']} (ID: `{post['user_id']}`)\n\n"
                f"📥 **Текст игрока:**\n`{post['text']}`"
            )
            if post.get("photo"):
                bot.send_photo(call.message.chat.id, post["photo"], caption=f_text, parse_mode="Markdown", reply_markup=ikb_moderation(pid))
            else:
                bot.send_message(call.message.chat.id, f_text, parse_mode="Markdown", reply_markup=ikb_moderation(pid))

    elif data == "show_active_list":
        if not is_admin_or_owner(u):
            return bot.answer_callback_query(call.id, "⛔ Нет доступа!", show_alert=True)

        bot.answer_callback_query(call.id)
        with ads_lock:
            if not active_ads:
                return bot.send_message(call.message.chat.id, "📂 В данный момент опубликованных объявлений нет.")

            bot.send_message(call.message.chat.id, f"📋 **Опубликованные объявления ({len(active_ads)} шт.):**", parse_mode="Markdown")
            for aid, ad in list(active_ads.items()):
                info = f"🆔 **Объявление #{aid}**\n🌐 Сервер: {ad['server']}\n📂 Раздел: {ad['category']}\n\n{ad['text']}"
                if ad.get("photo"):
                    bot.send_photo(call.message.chat.id, ad["photo"], caption=info, parse_mode="Markdown", reply_markup=ikb_manage_active_ad(aid))
                else:
                    bot.send_message(call.message.chat.id, info, parse_mode="Markdown", reply_markup=ikb_manage_active_ad(aid))

    elif data == "show_editor_stats":
        if not is_admin_or_owner(u):
            return bot.answer_callback_query(call.id, "⛔ Нет доступа!", show_alert=True)

        bot.answer_callback_query(call.id)
        stats_text = "📊 **Статистика Редакторов СМИ:**\n\n"
        if not editor_stats:
            stats_text += "Пока ни один редактор не проверил объявления."
        else:
            sorted_stats = sorted(editor_stats.items(), key=lambda x: x[1], reverse=True)
            for idx, (ed_name, count) in enumerate(sorted_stats, 1):
                stats_text += f"{idx}. @{ed_name} — **{count} шт.** проверено\n"

        stats_text += f"\n📂 Всего активных объявлений в боте: **{len(active_ads)}**"
        bot.send_message(call.message.chat.id, stats_text, parse_mode="Markdown")

    elif data == "manage_bans":
        if not is_admin_or_owner(u):
            return bot.answer_callback_query(call.id, "⛔ Нет доступа!", show_alert=True)

        bot.answer_callback_query(call.id)
        ban_text = f"🔨 **Список заблокированных пользователей ({len(banned_users)}):**\n"
        for b_id in banned_users:
            ban_text += f"• ID: `{b_id}`\n"
        ban_text += "\nЧтобы забанить автора, используйте кнопку в карточке заявки."
        bot.send_message(call.message.chat.id, ban_text, parse_mode="Markdown")

    elif data.startswith("ban_author_"):
        pid = int(data.split('_')[2])
        if not is_admin_or_owner(u):
            return bot.answer_callback_query(call.id, "⛔ Нет прав!", show_alert=True)

        if pid in pending_posts:
            target_uid = pending_posts[pid]["user_id"]
            banned_users.add(target_uid)
            pending_posts.pop(pid, None)
            bot.answer_callback_query(call.id, f"Пользователь {target_uid} заблокирован!", show_alert=True)
            try:
                bot.edit_message_caption("🔨 Автор заблокирован, заявка удалена.", chat_id=call.message.chat.id, message_id=call.message.message_id)
            except Exception:
                pass

    elif data.startswith("user_delete_self_"):
        aid = int(data.split('_')[3])
        with ads_lock:
            if aid in active_ads and active_ads[aid].get("user_id") == call.from_user.id:
                del active_ads[aid]
                bot.answer_callback_query(call.id, "✅ Объявление удалено!")
                try:
                    bot.delete_message(call.message.chat.id, call.message.message_id)
                except Exception:
                    pass
            else:
                bot.answer_callback_query(call.id, "Объявление не найдено.", show_alert=True)

    elif data.startswith("del_active_"):
        aid = int(data.split('_')[2])
        if not is_admin_or_owner(u):
            return bot.answer_callback_query(call.id, "⛔ Нет прав!", show_alert=True)

        with ads_lock:
            if aid in active_ads:
                player_id = active_ads[aid].get("user_id")
                del active_ads[aid]
                bot.answer_callback_query(call.id, f"Объявление #{aid} удалено!")
                
                if player_id:
                    try:
                        bot.send_message(
                            player_id, 
                            f"🗑️ **Ваше объявление (#{aid}) было удалено редактором СМИ.**", 
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось отправить сообщение {player_id}: {e}")

                try:
                    bot.delete_message(call.message.chat.id, call.message.message_id)
                except Exception:
                    pass
            else:
                bot.answer_callback_query(call.id, "Объявление уже не существует.", show_alert=True)

    elif data.startswith("edit_text_"):
        pid = int(data.split('_')[2])
        if not is_admin_or_owner(u): 
            return bot.answer_callback_query(call.id, "⛔ Доступ только для СМИ!", show_alert=True)
        
        post = pending_posts.get(pid, {})
        category = post.get("category", "")
        pro_tag = PRO_TAGS.get(category, "т/с")
        
        user_states[u.id] = {"editing": pid}
        bot.answer_callback_query(call.id)
        
        instructions = (
            f"✏️ **Редактирование заявки #{pid} по ПРО**\n\n"
            f"👤 **Продавец:** @{post.get('username', 'Игрок')}\n"
            f"📥 **Текст игрока:** `{post.get('text', '')}`\n\n"
            f"💡 **Тег раздела:** `{pro_tag}`\n"
            f"📝 **Введите отредактированный вариант по ПРО:**\n"
            f"• *Продам {pro_tag} \"Название\". Цена: 10.000.000$*"
        )
        return bot.send_message(call.message.chat.id, instructions, parse_mode="Markdown", reply_markup=kb_cancel())

    elif data.startswith("owner_approve_"):
        pid = int(data.split('_')[2])
        if not is_admin_or_owner(u): 
            return bot.answer_callback_query(call.id, "⛔ Только для СМИ!", show_alert=True)
        if pid not in pending_posts: 
            return bot.answer_callback_query(call.id, "Заявка не найдена.")
        if not check_working_hours(): 
            return bot.answer_callback_query(call.id, "❌ Эфиры после 22:00 заблокированы!", show_alert=True)

        post = pending_posts.pop(pid)
        editor_uname = u.username or u.first_name
        
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
                "editor": f"@{editor_uname}", 
                "last_updated": time.time(), 
                "subscribers": set(), 
                "message_ids_map": {}
            }
        
        bot.answer_callback_query(call.id, "Опубликовано!")
        status_text = f"✅ Одобрено и опубликовано в разделе {post['category']}!\nРедактор: @{editor_uname}\nID: #{pid}"
        
        if call.message.caption:
            bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=status_text, reply_markup=ikb_manage_active_ad(pid))
        else:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=status_text, reply_markup=ikb_manage_active_ad(pid))
        
        try: 
            bot.send_message(post["user_id"], f"🎉 **Ваше объявление прошло проверку ПРО и опубликовано в боте!**\n\n{p_text}", parse_mode="Markdown")
        except Exception: 
            pass

    elif data.startswith("reject_"):
        pid = int(data.split('_')[1])
        if not is_admin_or_owner(u): 
            return bot.answer_callback_query(call.id, "⛔ Нет прав.", show_alert=True)
        if pid in pending_posts:
            p_info = pending_posts.pop(pid)
            bot.answer_callback_query(call.id, "Отклонено.")
            try:
                if call.message.caption:
                    bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption="❌ Отклонено (Нарушение ПРО)", reply_markup=None)
                else:
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="❌ Отклонено (Нарушение ПРО)", reply_markup=None)
                bot.send_message(p_info["user_id"], "❌ Ваше объявление было отклонено редактором СМИ (Нарушение ПРО).")
            except Exception: 
                pass

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states and "editing" in user_states[msg.from_user.id])
def process_editing(m):
    uid = m.from_user.id
    pid = user_states[uid].get("editing")
    user_states[uid].pop("editing", None)
    
    if m.text == "🚫 Отмена":
        return bot.send_message(m.chat.id, "Отменено.", reply_markup=kb_main_menu())

    if pid in pending_posts:
        pending_posts[pid]["text"] = m.text
        post = pending_posts[pid]
        f_text = (
            f"🚨 **Заявка от игрока #{pid} (Отредактировано)**\n"
            f"🌐 **Сервер:** {post['server']}\n"
            f"📂 **Категория:** {post['category']}\n"
            f"👤 **От игрока:** @{post['username']}\n\n"
            f"✍️ **Готовый текст по ПРО:**\n{post['text']}"
        )
        bot.send_message(m.chat.id, f"✅ Текст отредактирован!\n\n{f_text}", parse_mode="Markdown", reply_markup=ikb_moderation(pid))
    else:
        bot.send_message(m.chat.id, "❌ Заявка не найдена.", reply_markup=kb_main_menu())

# ==========================================
# 💍 ПРОСМОТР ОБЪЯВЛЕНИЙ (С VIP ВВЕРХУ)
# ==========================================

@bot.message_handler(func=lambda msg: msg.text in CATEGORIES)
def show_ads(m):
    uid = m.from_user.id
    srv = user_states.get(uid, {}).get("server", "Не выбран")
    cat_name = m.text
    
    with ads_lock: 
        vip_ads = [ad for ad in active_ads.values() if ad.get("category") == cat_name and ad.get("server") == srv and ad.get("is_vip")]
        std_ads = [ad for ad in active_ads.values() if ad.get("category") == cat_name and ad.get("server") == srv and not ad.get("is_vip")]
        
        ads_list = vip_ads + std_ads
    
    if not ads_list:
        return bot.send_message(m.chat.id, f"📊 **Раздел:** {cat_name}\n🌐 **Сервер:** {srv}\n\nВ этом разделе пока нет объявлений.", parse_mode="Markdown", reply_markup=kb_main_menu())

    bot.send_message(m.chat.id, f"📻 **Газета СМИ [{srv}]**\n📂 **Раздел:** {cat_name}\n\n🛒 **Объявления:**", parse_mode="Markdown", reply_markup=kb_main_menu())
    for ad in ads_list:
        try:
            if ad.get("photo"): 
                sent = bot.send_photo(m.chat.id, ad["photo"], caption=ad['text'], parse_mode="Markdown")
            else: 
                sent = bot.send_message(m.chat.id, ad['text'], parse_mode="Markdown")
            with ads_lock:
                ad.setdefault("subscribers", set()).add(m.chat.id)
                ad.setdefault("message_ids_map", {})[m.chat.id] = sent.message_id
        except Exception as e:
            logger.warning(f"Ошибка вывода: {e}")

if __name__ == '__main__':
    try:
        bot.remove_webhook()
    except Exception:
        pass

    try:
        bot.set_my_commands([
            types.BotCommand("start", "Начать"),
            types.BotCommand("help", "Вопросы/помощь")
        ])
    except Exception as e:
        logger.warning(f"Не удалось установить команды Telegram: {e}")

    print("🚀 Радиоцентр запущен!")
    bot.infinity_polling(skip_pending=True)
