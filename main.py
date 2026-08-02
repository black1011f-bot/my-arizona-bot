import os
import time
import threading
from datetime import datetime, time as dtime
import telebot
from telebot import types

# Инициализация бота с обновленным токеном
TOKEN = "8962696714:AAH5dYsLqlAqoLdVr5-sJH35OJnw1ttgpJ0"
bot = telebot.TeleBot(TOKEN)

# Данные пользователей и настройки
user_states = {}        # Хранит состояние FSM пользователя
user_data = {}          # Временное хранилище данных (для создания объявлений и т.д.)

# Временное хранилище активных объявлений для таймера (10 минут) и рассылки
# Структура: ad_id: { "text": str, "chat_id": int, "message_id": int, "editor": str, "last_updated": float, "photo": str, "subscribers": set, "message_ids_map": dict }
active_ads = {}
ads_lock = threading.Lock()

# Главный владелец и модераторы
OWNER_USERNAME = "bounqy"
ADMIN_USERNAMES = ["bounqy31", "bounqy"] 

# ID чата модерации
MODERATION_CHAT_ID = -1001234567890

# База данных админов по серверам в памяти
admins = {
    "server_1": set(),
    "server_2": set()
}

# Временное хранилище для заявок на продажу
pending_posts = {}
moderation_counter = 0

# Список всех серверов Arizona RP
SERVERS = [
    "🔥 Phoenix", "🌴 Tucson", "🌵 Scottdale", "⚜️ Chandler",
    "❄️ Brainburg", "🌊 Yuma", "✨ Saint-Rose", "🏛 Mesa",
    "❤️ Red-Rock", "🍀 Surprise", "⚡️ Prescott", "🌲 Glendale",
    "👑 Kingman", "⚓️ Winslow", "🌴 Payson", "💎 Gilbert",
    "🔥 Show-Low", "🌴 Casa-Grande", "📜 Page", "☀️ Sun-City",
    "👑 Queen-Creek", "🌵 Sedona", "🎄 Holiday", "🍀 Wednesday",
    "⚡️ Yava", "🌌 Faraway", "🎁 Christmas", "🐝 Bumble Bee",
    "🪞 Mirage", "💖 Love", "📱 Mobile I", "📱 Mobile II", "📱 Mobile III"
]

# ----------------- ФОНОВЫЙ ПОТОК ОЧИСТКИ И ПРОВЕРКИ ВРЕМЕНИ (08:00 - 22:00) -----------------

def background_cleanup_ads():
    """Фоновый поток: удаляет объявления при неактивности (10 минут) либо если наступило время вне лимита (вне интервала 08:00 - 22:00)."""
    while True:
        time.sleep(30)  # Проверка каждые 30 секунд
        current_time = time.time()
        now = datetime.now()
        current_time_obj = now.time()
        
        # Разрешенный интервал с 08:00 до 22:00
        start_allowed = dtime(8, 0)
        end_allowed = dtime(22, 0)
        
        # Проверяем, находимся ли мы вне разрешенного времени (ночью с 22:00 до 08:00)
        is_outside_working_hours = not (start_allowed <= current_time_obj <= end_allowed)

        with ads_lock:
            expired_ads = []
            for ad_id, data in active_ads.items():
                # Условие 1: Прошло более 10 минут с последнего обновления
                # Условие 2: Наступило время после 22:00 или до 08:00 (ночное удаление)
                if (current_time - data["last_updated"] > 600) or is_outside_working_hours:
                    expired_ads.append(ad_id)

            for ad_id in expired_ads:
                data = active_ads[ad_id]
                # Удаляем у всех пользователей и из канала, куда рассылалось объявление
                for sub_chat_id, msg_id in list(data.get("message_ids_map", {}).items()):
                    try:
                        bot.delete_message(sub_chat_id, msg_id)
                    except Exception as e:
                        print(f"Ошибка при удалении объявления #{ad_id} у чата {sub_chat_id}: {e}")
                
                del active_ads[ad_id]
                print(f"Объявление #{ad_id} удалено (причина: истекли 10 минут неактивности либо наступило время вне лимита 08:00-22:00).")

# Запуск фонового потока
cleanup_thread = threading.Thread(target=background_cleanup_ads, daemon=True)
cleanup_thread.start()

# ----------------- ВСПОМОГАТЕЛЬНЫЕ ПРОВЕРКИ -----------------

def is_owner(user):
    return user.username and user.username.lower() == OWNER_USERNAME.lower()

def is_admin_or_owner(user):
    if not user:
        return False
    return is_owner(user) or (user.username and user.username.lower() in [adm.lower() for adm in ADMIN_USERNAMES])

def is_server_admin(user_id, server_key):
    return user_id in admins.get(server_key, set())

# ----------------- КЛАВИАТУРЫ -----------------

def get_servers_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for i in range(0, len(SERVERS), 2):
        pair = SERVERS[i:i+2]
        markup.add(*[types.KeyboardButton(s) for s in pair])
    markup.add(types.KeyboardButton("🛒 Подать объявление о продаже"), types.KeyboardButton("⚙️ Панель администратора"))
    return markup

def get_categories_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("💍 Аксы"),
        types.KeyboardButton("🏎 Все авто,воздушные,водные,тюнинг")
    )
    markup.add(
        types.KeyboardButton("🥼 Скины и Охранники"),
        types.KeyboardButton("🏡 Дома и Бизнесы")
    )
    markup.add(
        types.KeyboardButton("📦 Ресурсы и Оружие")
    )
    markup.add(types.KeyboardButton("🛒 Подать объявление о продаже"), types.KeyboardButton("⚙️ Панель администратора"))
    markup.add(types.KeyboardButton("🔄 Сменить сервер"))
    return markup

def get_cancel_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🚫 Отмена"))
    return markup

def get_admin_item_types_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🚗 Продажа машины"),
        types.KeyboardButton("💍 Продажа акса")
    )
    markup.add(
        types.KeyboardButton("🥼 Продажа скина"),
        types.KeyboardButton("🏡 Продажа недвижимости")
    )
    markup.add(types.KeyboardButton("🚫 Отмена"))
    return markup

def get_admin_servers_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for i in range(0, len(SERVERS), 2):
        pair = SERVERS[i:i+2]
        markup.add(*[types.KeyboardButton(s) for s in pair])
    markup.add(types.KeyboardButton("🚫 Отмена"))
    return markup


# ----------------- ОБРАБОТЧИКИ КОМАНД И МЕНЮ -----------------

@bot.message_handler(commands=['start'])
def start_command(message):
    welcome_text = (
        "👇 НАЖМИ И ВЫБЕРИ СВОЙ СЕРВЕР 👇\n\n"
        "👋 Привет! Это неофициальный бот с ценами для Arizona RP!\n\n"
        "🎯 Выбирай сервер из списка и узнавай актуальные цены с ЦР и АБ.\n\n"
        "🛡 Безопасность:\n"
        "• Мы НИКОГДА не просим пароли, пин-коды или данные от аккаунта!\n"
        "• Бот абсолютно бесплатный — мы НЕ просим деньги за работу.\n\n"
        "📢 Наш Telegram-канал: @Bounty_Squad31\n\n"
        "❤️ Спасибо, что используешь нашего бота! Удачных сделок!"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_servers_keyboard())

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if is_admin_or_owner(message.from_user):
        bot.send_message(message.chat.id, "👑 **Панель администратора:**\nТы успешно авторизован как модератор бота.", parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "⛔ У тебя нет доступа к этой команде.")

@bot.message_handler(func=lambda msg: msg.text in SERVERS)
def select_server(message):
    user_states[message.chat.id] = message.text
    bot.send_message(
        message.chat.id, 
        f"Сервер **{message.text}** выбран! Выберите категорию:", 
        parse_mode="Markdown", 
        reply_markup=get_categories_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == "🔄 Сменить сервер")
def change_server(message):
    bot.send_message(message.chat.id, "Выберите ваш сервер из списка:", reply_markup=get_servers_keyboard())

# --- Обработка разделов цен и показа объявлений о продаже ---

@bot.message_handler(func=lambda msg: msg.text in ["💍 Аксы", "🏎 Все авто,воздушные,водные,тюнинг", "🥼 Скины и Охранники", "🏡 Дома и Бизнесы", "📦 Ресурсы и Оружие"] or msg.text in ["🕶 На лицо", "🪖 На голову", "🥊 На руки", "👕 На грудь", "🛢 На спину", "🔮 Плечо и Спутники", "🚜 Фуры и Грузовики", "🏎 Легковые и Суперкары", "🚐 Трейлеры", "🚁 Самолеты и Вертолеты", "⚙ Тюнинг", "🛥 Яхты и Лодки"])
def sub_categories(message):
    srv = user_states.get(message.chat.id, "Не выбран")
    
    with ads_lock:
        matching_ads = [ad for ad in active_ads.values()]

    response_text = f"📊 Раздел: **{message.text}**\n🌐 Сервер: **{srv}**\n\n"
    if matching_ads:
        response_text += "🛒 **Актуальные предложения о продаже:**\n"
        bot.send_message(message.chat.id, response_text, parse_mode="Markdown")
        
        for ad_id, ad in active_ads.items():
            card_text = f"📢 **Товар на продажу**\n\n{ad['text']}\n\n👤 Отредактировал (админ): {ad['editor']}"
            if ad.get("photo"):
                sent = bot.send_photo(message.chat.id, ad["photo"], caption=card_text, parse_mode="Markdown")
            else:
                sent = bot.send_message(message.chat.id, card_text, parse_mode="Markdown")
            
            ad["subscribers"].add(message.chat.id)
            ad["message_ids_map"][message.chat.id] = sent.message_id
    else:
        response_text += "В данном разделе пока нет активных объявлений о продаже."
        bot.send_message(message.chat.id, response_text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🚫 Отмена")
def cancel_action(message):
    user_states.pop(message.from_user.id, None)
    user_data.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "Главное меню категорий:", reply_markup=get_categories_keyboard())

@bot.message_handler(func=lambda msg: msg.text in ["⬅ Назад", "🔝 Главное Меню"])
def back_navigation(message):
    bot.send_message(message.chat.id, "Главное меню категорий:", reply_markup=get_categories_keyboard())


# --- ПОДАЧА ОБЪЯВЛЕНИЙ И АДМИН-СОЗДАНИЕ ПОСТОВ ---

@bot.message_handler(func=lambda message: message.text == "🛒 Подать объявление о продаже")
def ask_for_submission(message):
    # Проверка лимита времени (08:00 - 22:00) при попытке подачи объявления
    now_time = datetime.now().time()
    if not (dtime(8, 0) <= now_time <= dtime(22, 0)):
        bot.send_message(message.chat.id, "❌ Подача объявлений разрешена только с 08:00 до 22:00!")
        return

    user_states[message.from_user.id] = "waiting_for_submission"
    msg = bot.send_message(
        message.chat.id, 
        "Отправьте **одним сообщением** фотографию товара и описание для продажи:", 
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )
    bot.register_next_step_handler(msg, process_item_submission)

@bot.message_handler(func=lambda message: message.text == "⚙️ Панель администратора")
def open_admin_panel(message):
    user = message.from_user
    user_is_adm = is_admin_or_owner(user) or any(is_server_admin(user.id, s) for s in admins)
    
    if not user_is_adm:
        bot.send_message(message.chat.id, "У вас нет доступа к панели администратора.")
        return
        
    markup = types.InlineKeyboardMarkup()
    if is_owner(user):
        markup.add(
            types.InlineKeyboardButton("➕ Назначить админа", callback_data="owner_add_adm"),
            types.InlineKeyboardButton("➖ Снять админа", callback_data="owner_rem_adm")
        )
    markup.add(
        types.InlineKeyboardButton("📝 Создать пост (Админ)", callback_data="admin_create_post"),
        types.InlineKeyboardButton("📋 Ожидающие заявки", callback_data="show_pending_list")
    )
    
    bot.send_message(
        message.chat.id, 
        f"⚙️ **Панель управления**\nСтатус: {'Владелец (@bounqy)' if is_owner(user) else 'Администратор'}", 
        parse_mode="Markdown", 
        reply_markup=markup
    )

def process_item_submission(message):
    global moderation_counter
    
    user_states.pop(message.from_user.id, None)

    if message.text == "🚫 Отмена":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_categories_keyboard())
        return

    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
    
    text_content = message.caption or message.text
    
    if not photo_id and not text_content:
        bot.send_message(message.chat.id, "❌ Вы не отправили ни фото, ни текст. Попробуйте снова.")
        return

    moderation_counter += 1
    current_id = moderation_counter
    
    username_val = message.from_user.username or "Без юзернейма"
    
    pending_posts[current_id] = {
        "user_id": message.from_user.id,
        "username": username_val,
        "photo": photo_id,
        "text": text_content or "Без описания"
    }
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("1️⃣ Заявки на администратора", callback_data=f"admin_apps_{current_id}"),
        types.InlineKeyboardButton("2️⃣ Редакция", callback_data=f"edit_{current_id}"),
        types.InlineKeyboardButton("3️⃣ Принять (Только для владельца)", callback_data=f"owner_approve_{current_id}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{current_id}")
    )
    
    username_str = f"@{username_val}" if username_val != "Без юзернейма" else "Отсутствует"
    
    forward_text = (
        f"🚨 **Новая заявка на продажу #{current_id}**\n\n"
        f"👤 **От пользователя:** `{message.from_user.id}`\n"
        f"🔗 **Юзернейм:** {username_str}\n\n"
        f"📦 **Содержание:**\n{text_content or ''}"
    )
    
    target_chat = MODERATION_CHAT_ID if MODERATION_CHAT_ID != -1001234567890 else message.chat.id
    
    try:
        if photo_id:
            bot.send_photo(target_chat, photo_id, caption=forward_text, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(target_chat, forward_text, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Ошибка отправки в чат модерации: {e}")
        if target_chat != message.chat.id:
            if photo_id:
                bot.send_photo(message.chat.id, photo_id, caption=forward_text, parse_mode="Markdown", reply_markup=markup)
            else:
                bot.send_message(message.chat.id, forward_text, parse_mode="Markdown", reply_markup=markup)

    bot.send_message(message.chat.id, "✅ Ваша заявка успешно отправлена на модерацию администраторам!", reply_markup=get_categories_keyboard())


# --- ОБРАБОТКА CALLBACK КНОПОК ---

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    global pending_posts
    data = call.data
    user = call.from_user
    
    if data == "admin_create_post":
        if not is_admin_or_owner(user):
            bot.answer_callback_query(call.id, "Недостаточно прав.", show_alert=True)
            return
        user_states[user.id] = "admin_choosing_type"
        user_data[user.id] = {}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "Выберите тип товара для публикации:", reply_markup=get_admin_item_types_keyboard())
        return

    if data.startswith("admin_apps_"):
        post_id = int(data.split('_')[2])
        bot.answer_callback_query(call.id, text=f"Раздел заявок на администратора (Заявка #{post_id})", show_alert=True)

    elif data.startswith("edit_"):
        post_id = int(data.split('_')[1])
        
        if not is_admin_or_owner(user):
            bot.answer_callback_query(call.id, "⛔ Ошибка: Редактировать заявки могут только администраторы!", show_alert=True)
            return
            
        bot.answer_callback_query(call.id, text=f"Введите текст редактирования для заявки #{post_id}")
        user_states[user.id] = f"editing_post_{post_id}"
        bot.send_message(call.message.chat.id, f"✏️ Введите новый текст для объявления/заявки #{post_id}:", reply_markup=get_cancel_keyboard())

    elif data.startswith("owner_approve_"):
        post_id = int(data.split('_')[2])
        
        if not is_owner(user):
            bot.answer_callback_query(call.id, "⛔ Ошибка: Принятие заявки доступно ТОЛЬКО для владельца бота (@bounqy)!", show_alert=True)
            return
            
        if post_id in pending_posts:
            # Проверяем время при публикации владельцем
            now_time = datetime.now().time()
            if not (dtime(8, 0) <= now_time <= dtime(22, 0)):
                bot.answer_callback_query(call.id, "❌ Публикация разрешена только с 08:00 до 22:00!", show_alert=True)
                return

            post = pending_posts[post_id]
            target_channel = "@Bounty_Squad31"
            
            publication_text = (
                f"🛒 **Новое объявление о продаже!**\n\n"
                f"{post['text']}\n\n"
                f"👤 Продавец: @{post['username']}"
            )
            
            try:
                if post["photo"]:
                    sent_channel_msg = bot.send_photo(target_channel, post["photo"], caption=publication_text, parse_mode="Markdown")
                else:
                    sent_channel_msg = bot.send_message(target_channel, publication_text, parse_mode="Markdown")
                
                admin_name = f"@{user.username}" if user.username else user.first_name
                with ads_lock:
                    active_ads[post_id] = {
                        "text": publication_text,
                        "photo": post["photo"],
                        "editor": admin_name,
                        "last_updated": time.time(),
                        "subscribers": {target_channel[1:]},
                        "message_ids_map": {target_channel: sent_channel_msg.message_id}
                    }

                bot.answer_callback_query(call.id, "Успешно опубликовано в канал владельцем!")
                success_msg = f"✅ Одобрено и опубликовано владельцем (@{user.username})"
                
                if call.message.caption:
                    bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=success_msg, reply_markup=None)
                else:
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=success_msg, reply_markup=None)
                
                try:
                    bot.send_message(post["user_id"], "🎉 Ваша заявка была одобрена владельцем и опубликована в канале!")
                except:
                    pass
            except Exception as e:
                bot.answer_callback_query(call.id, f"Ошибка публикации: {e}", show_alert=True)
                
            del pending_posts[post_id]
        else:
            bot.answer_callback_query(call.id, "Заявка уже устарела или была обработана.")

    elif data.startswith("reject_"):
        post_id = int(data.split("_")[1])
        if not is_admin_or_owner(user):
            bot.answer_callback_query(call.id, "Недостаточно прав.", show_alert=True)
            return
            
        if post_id in pending_posts:
            post_info = pending_posts.pop(post_id)
            bot.answer_callback_query(call.id, "Заявка отклонена.")
            
            reject_msg = "❌ Заявка отклонена администратором."
            try:
                if call.message.caption:
                    bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=reject_msg, reply_markup=None)
                else:
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=reject_msg, reply_markup=None)
            except Exception as e:
                print(f"Ошибка изменения сообщения при отклонении: {e}")
                
            try:
                bot.send_message(post_info["user_id"], "❌ К сожалению, ваша заявка была отклонена модератором.")
            except:
                pass
        else:
            bot.answer_callback_query(call.id, "Заявка уже обработана.")

    elif data == "owner_add_adm":
        if not is_owner(user):
            bot.answer_callback_query(call.id, "Только владелец (@bounqy) может это делать!", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, "Отправьте ID пользователя и сервер (например: `123456789 server_1`):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_add_admin)

    elif data == "owner_rem_adm":
        if not is_owner(user):
            bot.answer_callback_query(call.id, "Только владелец (@bounqy) может это делать!", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, "Отправьте ID пользователя и сервер для удаления (например: `123456789 server_1`):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_remove_admin)
        
    elif data == "show_pending_list":
        if not pending_posts:
            bot.answer_callback_query(call.id, "Нет активных ожидающих заявок.", show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"Активных заявок в очереди: {len(pending_posts)}")

def process_add_admin(message):
    if not is_owner(message.from_user):
        return
    try:
        parts = message.text.strip().split()
        user_id = int(parts[0])
        server = parts[1]
        
        if server in admins:
            admins[server].add(user_id)
            bot.send_message(message.chat.id, f"✅ Пользователь {user_id} назначен администратором сервера `{server}`.")
        else:
            bot.send_message(message.chat.id, "❌ Неверное название сервера. Используйте `server_1` или `server_2`.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка формата: {e}")

def process_remove_admin(message):
    if not is_owner(message.from_user):
        return
    try:
        parts = message.text.strip().split()
        user_id = int(parts[0])
        server = parts[1]
        
        if server in admins and user_id in admins[server]:
            admins[server].remove(user_id)
            bot.send_message(message.chat.id, f"✅ Пользователь {user_id} снят с поста админа `{server}`.")
        else:
            bot.send_message(message.chat.id, "❌ Пользователь не найден в списке админов этого сервера.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка формата: {e}")


# --- ОБРАБОТЧИК РЕДАКТИРОВАНИЯ ОБЪЯВЛЕНИЙ АДМИНАМИ ---

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id, "").startswith("editing_post_"))
def save_edited_post_step(message):
    if message.text == "🚫 Отмена":
        user_states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_categories_keyboard())
        return

    state = user_states.pop(message.from_user.id)
    post_id = int(state.split("_")[2])

    admin_name = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    new_text = message.text

    with ads_lock:
        if post_id in active_ads:
            ad = active_ads[post_id]
            ad["text"] = new_text
            ad["editor"] = admin_name
            ad["last_updated"] = time.time()

            updated_card_text = f"📢 **Объявление о продаже (Отредактировано)**\n\n{new_text}\n\n👤 Отредактировал (админ): {admin_name}"
            for sub_chat_id, msg_id in list(ad["message_ids_map"].items()):
                try:
                    if ad.get("photo"):
                        bot.edit_message_caption(chat_id=sub_chat_id, message_id=msg_id, caption=updated_card_text, parse_mode="Markdown")
                    else:
                        bot.edit_message_text(chat_id=sub_chat_id, message_id=msg_id, text=updated_card_text, parse_mode="Markdown")
                except Exception as e:
                    print(f"Не удалось обновить сообщение у пользователя {sub_chat_id}: {e}")

    bot.send_message(message.chat.id, "✅ Объявление успешно отредактировано, разослано пользователям!", reply_markup=get_categories_keyboard())


# --- ОБРАБОТЧИК ПОШАГОВОГО СОЗДАНИЯ ПОСТА АДМИНИСТРАТОРОМ ---

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "admin_choosing_type")
def admin_choose_type_step(message):
    if message.text == "🚫 Отмена":
        user_states.pop(message.from_user.id, None)
        user_data.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_categories_keyboard())
        return

    item_types_map = {
        "🚗 Продажа машины": "Продажа машины",
        "💍 Продажа акса": "Продажа аксессуара",
        "🥼 Продажа скина": "Продажа скина",
        "🏡 Продажа недвижимости": "Продажа недвижимости"
    }

    if message.text not in item_types_map:
        bot.send_message(message.chat.id, "❌ Пожалуйста, выберите тип с помощью кнопок ниже.")
        return

    user_data[message.from_user.id] = {"item_type": item_types_map[message.text]}
    user_states[message.from_user.id] = "admin_choosing_server"
    
    bot.send_message(
        message.chat.id, 
        f"Вы выбрали: **{item_types_map[message.text]}**.\nТеперь выберите сервер для этого объявления:", 
        parse_mode="Markdown", 
        reply_markup=get_admin_servers_keyboard()
    )

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "admin_choosing_server")
def admin_choose_server_step(message):
    if message.text == "🚫 Отмена":
        user_states.pop(message.from_user.id, None)
        user_data.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_categories_keyboard())
        return

    if message.text not in SERVERS:
        bot.send_message(message.chat.id, "❌ Пожалуйста, выберите сервер из предложенных кнопками.")
        return

    user_data[message.from_user.id]["server"] = message.text
    user_states[message.from_user.id] = "admin_entering_price_and_desc"

    bot.send_message(
        message.chat.id, 
        "Отлично! Теперь введите описание и сумму товара (текстом или прикрепите фото с текстом):", 
        reply_markup=get_cancel_keyboard()
    )

@bot.message_handler(content_types=['text', 'photo'], func=lambda msg: user_states.get(msg.from_user.id) == "admin_entering_price_and_desc")
def admin_finish_post_step(message):
    global moderation_counter
    if message.text == "🚫 Отмена":
        user_states.pop(message.from_user.id, None)
        user_data.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_categories_keyboard())
        return

    # Проверка времени публикации администратором
    now_time = datetime.now().time()
    if not (dtime(8, 0) <= now_time <= dtime(22, 0)):
        bot.send_message(message.chat.id, "❌ Публикация объявлений разрешена только с 08:00 до 22:00!", reply_markup=get_categories_keyboard())
        user_states.pop(message.from_user.id, None)
        user_data.pop(message.from_user.id, None)
        return

    data = user_data.get(message.from_user.id, {})
    item_type = data.get("item_type", "Товар")
    server = data.get("server", "Не указан")

    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
    
    text_content = message.caption or message.text or "Без описания"

    final_post_text = (
        f"🛒 **{item_type}**\n"
        f"🌐 Сервер: **{server}**\n\n"
        f"{text_content}\n\n"
        f"👑 Опубликовано администратором"
    )

    target_channel = "@Bounty_Squad31"
    try:
        if photo_id:
            sent_msg = bot.send_photo(target_channel, photo_id, caption=final_post_text, parse_mode="Markdown")
        else:
            sent_msg = bot.send_message(target_channel, final_post_text, parse_mode="Markdown")
        
        moderation_counter += 1
        admin_name = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        with ads_lock:
            active_ads[moderation_counter] = {
                "text": final_post_text,
                "photo": photo_id,
                "editor": admin_name,
                "last_updated": time.time(),
                "subscribers": {target_channel[1:]},
                "message_ids_map": {target_channel: sent_msg.message_id}
            }

        bot.send_message(message.chat.id, "✅ Объявление успешно опубликовано в канал и добавлено в систему ротации!", reply_markup=get_categories_keyboard())
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Ошибка публикации в канал: {e}", reply_markup=get_categories_keyboard())

    user_states.pop(message.from_user.id, None)
    user_data.pop(message.from_user.id, None)


# --- ОБЩИЙ ОБРАБОТЧИК ТЕКСТА ---

@bot.message_handler(content_types=['text'])
def handle_incoming_content(message):
    if user_states.get(message.from_user.id) in ["waiting_for_submission", "admin_choosing_type", "admin_choosing_server", "admin_entering_price_and_desc"] or user_states.get(message.from_user.id, "").startswith("editing_post_"):
        return
        
    srv = user_states.get(message.chat.id, "Не выбран")
    bot.send_message(
        message.chat.id,
        f"📊 Раздел: **{message.text}**\n🌐 Сервер: **{srv}**\n\nДанные подгружаются из базы...",
        parse_mode="Markdown"
    )

# ---------------- ЗАПУСК ----------------

if __name__ == '__main__':
    bot.remove_webhook()
    print("🚀 Бот успешно запущен! Добавлена проверка и автоматическое удаление объявлений вне интервала 08:00 - 22:00.")
    bot.infinity_polling(skip_pending=True)
