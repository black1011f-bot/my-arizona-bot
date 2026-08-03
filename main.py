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
bot = telebot.TeleBot(TOKEN)

OWNER_USERNAME = "bounqy"
ADMIN_USERNAMES = ["bounqy31", "bounqy"]

# Сюда можно вписать известные ID админов,
# а также бот сам сюда добавляет тех админов, кто написал /start или /admin
ADMIN_CHAT_IDS = set() 

MODERATION_CHAT_ID = int(os.getenv("MODERATION_CHAT_ID", "0"))

# Хранилища данных
user_states = {}
user_data = {}
active_ads = {}
pending_posts = {}
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
    """Фоновая очистка старых объявлений по таймеру и в ночное время."""
    while True:
        time.sleep(30)
        now = datetime.now()
        now_time = now.time()
        curr_t = time.time()

        is_night = now_time >= dtime(22, 0, 22) or now_time < dtime(8, 0, 0)
        is_morning_clean = dtime(8, 0, 0) <= now_time <= dtime(8, 5, 22)

        with ads_lock:
            expired_ids = []
            for aid, data in list(active_ads.items()):
                if (curr_t - data.get("last_updated", 0) > 600) or is_night or is_morning_clean:
                    expired_ids.append(aid)

            for aid in expired_ids:
                msg_map = active_ads[aid].get("message_ids_map", {})
                for target_id, msg_id in list(msg_map.items()):
                    try:
                        bot.delete_message(target_id, msg_id)
                    except Exception as e:
                        logger.warning(f"Не удалось удалить сообщение {msg_id}: {e}")
                del active_ads[aid]

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
    """Автоматически вносит админа в список получателей уведомлений."""
    if is_admin_or_owner(user):
        ADMIN_CHAT_IDS.add(chat_id)

def check_working_hours():
    now_time = datetime.now().time()
    if now_time < dtime(8, 0, 0) or now_time > dtime(22, 0, 22):
        return False
    return True

def format_smi_post(server, category, text, player_username, editor_username):
    """Форматирование финального объявления: сверху контакт игрока, снизу имя админа."""
    clean_server = server.replace('🔥 ', '').replace('🌴 ', '').replace('🌵 ', '').replace('⚜️ ', '').replace('❄️ ', '').replace('🌊 ', '').replace('✨ ', '').replace('🏛 ', '').replace('❤️ ', '').replace('🍀 ', '').replace('⚡️ ', '').replace('🌲 ', '').replace('👑 ', '').replace('⚓️ ', '').replace('💎 ', '').replace('📜 ', '').replace('☀️ ', '').replace('🎄 ', '').replace('🌌 ', '').replace('🎁 ', '').replace('🐝 ', '').replace('🪞 ', '').replace('💖 ', '').replace('📱 ', '')
    
    player_contact = f"@{player_username}" if player_username and player_username != "Без юзернейма" else "Не указан"
    editor_contact = f"@{editor_username}" if editor_username else "СМИ"

    return (
        f"📰 | **[СМИ {clean_server}] Объявление:**\n"
        f"📞 **Контакт игрока:** {player_contact}\n\n"
        f"{text}\n\n"
        f"📂 **Раздел:** {category}\n"
        f"👨‍💻 **Отредактировал:** {editor_contact}"
    )

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

def ikb_admin_select_cat():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for idx, cat in enumerate(CATEGORIES):
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"admin_select_cat_{idx}"))
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
    return markup

def ikb_manage_active_ad(aid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✏️ Переписать", callback_data=f"reedit_active_{aid}"),
        types.InlineKeyboardButton("❌ Удалить", callback_data=f"del_active_{aid}")
    )
    return markup

def ikb_admin_change_cat(pid):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for idx, cat in enumerate(CATEGORIES):
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"set_cat_{pid}_{idx}"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"back_to_mod_{pid}"))
    return markup

# ==========================================
# ОБРАБОТКА КОМАНД
# ==========================================

@bot.message_handler(commands=['start'])
def cmd_start(m):
    register_admin(m.from_user, m.chat.id)
    text = (
        "👋 **Привет!**\n"
        "Это торговый бот-помощник с редактором СМИ Arizona RP.\n\n"
        "👇 **Для старта:**\n"
        "Выбери нужный сервер из меню ниже!"
    )
    bot.send_message(m.chat.id, text, parse_mode="Markdown", reply_markup=kb_servers())

@bot.message_handler(func=lambda msg: msg.text == "📊 Откуда цены?")
def show_prices_info(m):
    text = (
        "📊 **Откуда мы берем цены?**\n\n"
        "Наш бот — это живой справочник рыночной экономики!\n\n"
        "🤝 **Только реальный рынок:** Все ценники формируются на основе реальных сделок.\n"
        "🚫 **Никакой отсебятины:** Все объявления проходят редактирование по ПРО СМИ."
    )
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['admin'])
@bot.message_handler(func=lambda msg: msg.text == "👑 Админ")
def cmd_admin(m):
    u = m.from_user
    register_admin(u, m.chat.id)
    if is_admin_or_owner(u):
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📋 Ожидающие заявки СМИ", callback_data="show_pending_list"),
            types.InlineKeyboardButton("📰 Объявление СМИ (Прямой эфир)", callback_data="admin_smi_ad"),
            types.InlineKeyboardButton("🗑 Активные объявления (Удалить/Изменить)", callback_data="show_active_list")
        )
        bot.send_message(
            m.chat.id, 
            f"⚙️ **Панель Редактора СМИ**\n"
            f"Должность: {'Гл. Редактор (Владелец)' if is_owner(u) else 'Редактор (Админ)'}\n"
            f"🔔 Статус рассылки админам: **Активен**", 
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
# ПОДАЧА ОБЪЯВЛЕНИЯ ИГРОКОМ И РАССЫЛКА АДМИНАМ
# ==========================================

@bot.message_handler(func=lambda msg: msg.text == "🛒 Подать объявление о продаже")
def start_ad_creation(m):
    if not check_working_hours():
        return bot.send_message(m.chat.id, "❌ Радиоцентр закрыт! Подача объявлений с 22:00 до 08:00 МСК заблокирована.")
    
    uid = m.from_user.id
    if uid in user_data and "last_ad_time" in user_data[uid]:
        if time.time() - user_data[uid]["last_ad_time"] < 600:
            remaining = int(600 - (time.time() - user_data[uid]["last_ad_time"]))
            return bot.send_message(
                m.chat.id, 
                f"❌ Кулдаун! Подождите {remaining // 60} мин. {remaining % 60} сек. перед отправкой следующего объявления."
            )

    if uid not in user_states or "server" not in user_states[uid]:
        return bot.send_message(m.chat.id, "⚠️ Сначала выберите сервер из главного меню!", reply_markup=kb_servers())

    bot.send_message(
        m.chat.id,
        f"🌐 **Сервер:** {user_states[uid].get('server')}\n\n👇 **Шаг 1 из 2:** Выберите раздел товара:",
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
        "👇 **Шаг 2 из 2:** Отправьте описание предмета (и при желании фото).\n"
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

    if uid not in user_data: 
        user_data[uid] = {}
    user_data[uid]["last_ad_time"] = time.time()

    moderation_counter += 1
    uname = m.from_user.username or "Без юзернейма"
    
    pending_posts[moderation_counter] = {
        "user_id": uid, 
        "username": uname, 
        "photo": photo, 
        "text": text or "Без описания", 
        "category": category, 
        "server": server_name
    }

    f_text = (
        f"🚨 **НОВОЕ ОБЪЯВЛЕНИЕ НА МОДЕРАЦИЮ #{moderation_counter}!**\n\n"
        f"🌐 **Сервер:** {server_name}\n"
        f"📂 **Категория:** {category}\n"
        f"👤 **От игрока:** @{uname} (ID: `{uid}`)\n\n"
        f"📥 **Текст игрока:**\n`{text or 'Без описания'}`"
    )

    # -------------------------------------------------------------
    # РАССЫЛКА УВЕДОМЛЕНИЯ ВСЕМ АДМИНАМ В ЛС
    # -------------------------------------------------------------
    recipients = set(ADMIN_CHAT_IDS)
    if MODERATION_CHAT_ID != 0:
        recipients.add(MODERATION_CHAT_ID)

    # Если ни один админ ещё не писал боту, отправляем автору для теста
    if not recipients:
        recipients.add(m.chat.id)

    for target_id in recipients:
        try:
            if photo: 
                bot.send_photo(target_id, photo, caption=f_text, parse_mode="Markdown", reply_markup=ikb_moderation(moderation_counter))
            else: 
                bot.send_message(target_id, f_text, parse_mode="Markdown", reply_markup=ikb_moderation(moderation_counter))
        except Exception as e:
            logger.warning(f"Не удалось доставить уведомление админу {target_id}: {e}")

    bot.send_message(m.chat.id, "✅ **Ваше объявление отправлено редакторам СМИ!**\nОжидайте модерации.", reply_markup=kb_main_menu())

# ==========================================
# ОБРАБОТКА ИНЛАЙН-КНОПОК И МОДЕРАЦИИ
# ==========================================

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    global pending_posts
    data = call.data
    u = call.from_user
    register_admin(u, call.message.chat.id)

    if data == "show_active_list":
        if not is_admin_or_owner(u):
            return bot.answer_callback_query(call.id, "⛔ Нет доступа!", show_alert=True)

        bot.answer_callback_query(call.id)
        with ads_lock:
            if not active_ads:
                return bot.send_message(call.message.chat.id, "📂 В данный момент активных объявлений нет.")

            bot.send_message(call.message.chat.id, f"📋 **Все активные объявления ({len(active_ads)} шт.):**", parse_mode="Markdown")
            for aid, ad in list(active_ads.items()):
                info = f"🆔 **Объявление #{aid}**\n🌐 Сервер: {ad['server']}\n📂 Раздел: {ad['category']}\n\n{ad['text']}"
                if ad.get("photo"):
                    bot.send_photo(call.message.chat.id, ad["photo"], caption=info, parse_mode="Markdown", reply_markup=ikb_manage_active_ad(aid))
                else:
                    bot.send_message(call.message.chat.id, info, parse_mode="Markdown", reply_markup=ikb_manage_active_ad(aid))

    elif data.startswith("del_active_"):
        aid = int(data.split('_')[2])
        if not is_admin_or_owner(u):
            return bot.answer_callback_query(call.id, "⛔ Нет прав!", show_alert=True)

        with ads_lock:
            if aid in active_ads:
                del active_ads[aid]
                bot.answer_callback_query(call.id, f"Объявление #{aid} удалено!")
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
            f"💡 **Рекомендуемый тег:** `{pro_tag}`\n"
            f"📝 **Введите отредактированный вариант по ПРО:**\n"
            f"• *Продам {pro_tag} \"Название\". Цена: 10.000.000$*"
        )
        return bot.send_message(call.message.chat.id, instructions, parse_mode="Markdown", reply_markup=kb_cancel())

    elif data.startswith("edit_cat_"):
        pid = int(data.split('_')[2])
        if not is_admin_or_owner(u): 
            return bot.answer_callback_query(call.id, "⛔ Доступ только для СМИ!", show_alert=True)
        
        bot.answer_callback_query(call.id)
        if call.message.caption:
            bot.edit_message_caption("Выберите новый раздел:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=ikb_admin_change_cat(pid))
        else:
            bot.edit_message_text("Выберите новый раздел:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=ikb_admin_change_cat(pid))

    elif data.startswith("set_cat_"):
        parts = data.split('_')
        pid, cat_idx = int(parts[2]), int(parts[3])
        new_category = CATEGORIES[cat_idx]

        if pid in pending_posts:
            pending_posts[pid]["category"] = new_category

        bot.answer_callback_query(call.id, f"Категория изменена на: {new_category}")
        
        if pid in pending_posts:
            post = pending_posts[pid]
            f_text = (
                f"🚨 **Заявка на редактирование #{pid}**\n"
                f"🌐 **Сервер:** {post['server']}\n"
                f"📂 **Категория:** {post['category']} (Изменено)\n"
                f"👤 **От игрока:** @{post['username']}\n\n"
                f"📥 **Текст:**\n{post['text']}"
            )
            if call.message.caption:
                bot.edit_message_caption(f_text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=ikb_moderation(pid))
            else:
                bot.edit_message_text(f_text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=ikb_moderation(pid))

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
        p_text = format_smi_post(post['server'], post['category'], post['text'], post['username'], editor_uname)
        
        with ads_lock:
            active_ads[pid] = {
                "text": p_text, 
                "photo": post["photo"], 
                "server": post["server"],
                "category": post["category"],
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

    elif data == "show_pending_list":
        bot.answer_callback_query(call.id, f"Заявок в очереди СМИ: {len(pending_posts)}", show_alert=True)

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
            f"🚨 **Заявка в СМИ #{pid} (Отредактировано)**\n"
            f"🌐 **Сервер:** {post['server']}\n"
            f"📂 **Категория:** {post['category']}\n"
            f"👤 **От игрока:** @{post['username']}\n\n"
            f"✍️ **Готовый текст по ПРО:**\n{post['text']}"
        )
        bot.send_message(m.chat.id, f"✅ Текст отредактирован!\n\n{f_text}", parse_mode="Markdown", reply_markup=ikb_moderation(pid))
    else:
        bot.send_message(m.chat.id, "❌ Заявка не найдена.", reply_markup=kb_main_menu())

# ==========================================
# ПРОСМОТР ОБЪЯВЛЕНИЙ ПО КАТЕГОРИЯМ
# ==========================================

@bot.message_handler(func=lambda msg: msg.text in CATEGORIES)
def show_ads(m):
    uid = m.from_user.id
    srv = user_states.get(uid, {}).get("server", "Не выбран")
    cat_name = m.text
    
    with ads_lock: 
        ads_list = [ad for ad in active_ads.values() if ad.get("category") == cat_name and ad.get("server") == srv]
    
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
    print("🚀 Радиоцентр запущен!")
    bot.infinity_polling(skip_pending=True)
