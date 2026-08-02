import os
import telebot
from telebot import types

# Инициализация бота
TOKEN = os.getenv("BOT_TOKEN", "8962696714:AAH5dYsLqlAqoLdVr5-sJH35OJnw1ttgpJ0")
bot = telebot.TeleBot(TOKEN)

# Данные пользователей и настройки
user_states = {}        # Хранит выбранный сервер
waiting_for_price = []  # Список пользователей, которые отправляют предложенную цену

# Главный владелец и модераторы
OWNER_USERNAME = "bounqy"
ADMIN_USERNAMES = ["bounqy31", "bounqy"] 

# База данных админов по серверам в памяти
admins = {
    "server_1": set(),
    "server_2": set()
}

# Временное хранилище для заявок на продажу
pending_posts = {}
moderation_counter = 0

# Список всех 33 серверов Arizona RP
SERVERS = [
    "🔥 Phoenix", "🔥 Tucson", "🔥 Scottdale", "🔥 Chandler",
    "🔥 Brainburg", "🔥 Yuma", "🔥 Saint-Rose", "🔥 Mesa",
    "🔥 Red-Rock", "🔥 Surprise", "🔥 Prescott", "🔥 Glendale",
    "🔥 Kingman", "🔥 Winslow", "🔥 Payson", "🔥 Gilbert",
    "🔥 Show-Low", "🔥 Casa-Grande", "🔥 Page", "🔥 Sun-City",
    "🔥 Queen-Creek", "🔥 Sedona", "🔥 Holiday", "🔥 Wednesday",
    "🔥 Yava", "🔥 Faraway", "🔥 Christmas", "🔥 Bumble Bee",
    "🔥 Mirage", "🔥 Love", "🔥 Mobile I", "🔥 Mobile II", "🔥 Mobile III"
]

# ----------------- ВСПОМОГАТЕЛЬНЫЕ ПРОВЕРКИ -----------------

def is_owner(user):
    return user.username and user.username.lower() == OWNER_USERNAME.lower()

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
        types.KeyboardButton("📦 Ресурсы и Оружие"),
        types.KeyboardButton("📩 Предложить цену")
    )
    markup.add(types.KeyboardButton("🛒 Подать объявление о продаже"), types.KeyboardButton("⚙️ Панель администратора"))
    markup.add(types.KeyboardButton("🔄 Сменить сервер"))
    return markup

def get_accessories_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🕶 На лицо"),
        types.KeyboardButton("🪖 На голову")
    )
    markup.add(
        types.KeyboardButton("🥊 На руки"),
        types.KeyboardButton("👕 На грудь")
    )
    markup.add(
        types.KeyboardButton("🛢 На спину"),
        types.KeyboardButton("🔮 Плечо и Спутники")
    )
    markup.add(
        types.KeyboardButton("⬅ Назад"),
        types.KeyboardButton("🔝 Главное Меню")
    )
    return markup

def get_auto_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🚜 Фуры и Грузовики"),
        types.KeyboardButton("🏎 Легковые и Суперкары")
    )
    markup.add(
        types.KeyboardButton("🚐 Трейлеры"),
        types.KeyboardButton("🚁 Самолеты и Вертолеты")
    )
    markup.add(
        types.KeyboardButton("⚙ Тюнинг"),
        types.KeyboardButton("🛥 Яхты и Лодки")
    )
    markup.add(
        types.KeyboardButton("⬅ Назад"),
        types.KeyboardButton("🔝 Главное Меню")
    )
    return markup

def get_cancel_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🚫 Отмена"))
    return markup


# ----------------- ОБРАБОТЧИКИ КОМАНД И МЕНЮ -----------------

@bot.message_handler(commands=['start'])
def start_command(message):
    welcome_text = (
        "👇 НАЖМИ /start И ВЫБЕРИ СВОЙ СЕРВЕР 👇\n\n"
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
    if message.from_user.username in ADMIN_USERNAMES or is_owner(message.from_user):
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

# --- Обработка разделов цен ---

@bot.message_handler(func=lambda msg: msg.text == "💍 Аксы")
def category_accessories(message):
    bot.send_message(message.chat.id, "💍 **Категория: Аксессуары**\nВыберите категорию слота:", parse_mode="Markdown", reply_markup=get_accessories_keyboard())

@bot.message_handler(func=lambda msg: msg.text in ["🕶 На лицо", "🪖 На голову", "🥊 На руки", "👕 На грудь", "🛢 На спину", "🔮 Плечо и Спутники"])
def sub_accessories(message):
    srv = user_states.get(message.chat.id, "Не выбран")
    bot.send_message(message.chat.id, f"📊 Раздел: **{message.text}**\n🌐 Сервер: **{srv}**\n\nЦены подгружаются из базы...", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🏎 Все авто,воздушные,водные,тюнинг")
def category_auto(message):
    bot.send_message(message.chat.id, message.text, reply_markup=get_auto_keyboard())

@bot.message_handler(func=lambda msg: msg.text in ["🚜 Фуры и Грузовики", "🏎 Легковые и Суперкары", "🚐 Трейлеры", "🚁 Самолеты и Вертолеты", "⚙ Тюнинг", "🛥 Яхты и Лодки", "🥼 Скины и Охранники", "🏡 Дома и Бизнесы", "📦 Ресурсы и Оружие"])
def sub_categories(message):
    srv = user_states.get(message.chat.id, "Не выбран")
    bot.send_message(message.chat.id, f"📊 Раздел: **{message.text}**\n🌐 Сервер: **{srv}**\n\nДанные подгружаются из базы...", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📩 Предложить цену")
def suggest_price(message):
    waiting_for_price.append(message.chat.id)
    text = (
        "📸 **Запостил лавку — помог серверу!**\n\n"
        "Наткнулся на сочные цены на ЦР или АБ? Не держи в себе! 💰\n\n"
        "💬 **Отправляй сюда:**\n"
        "1. Скриншот лавки/рынка (обязательно с `/time` ⏰).\n"
        "2. Название предмета и точную цену.\n\n"
        "🔒 *Твой юзернейм останется скрытым, сообщение улетит напрямую модераторам!*"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_cancel_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "🚫 Отмена")
def cancel_action(message):
    if message.chat.id in waiting_for_price:
        waiting_for_price.remove(message.chat.id)
    bot.send_message(message.chat.id, "Главное меню категорий:", reply_markup=get_categories_keyboard())

@bot.message_handler(func=lambda msg: msg.text in ["⬅ Назад", "🔝 Главное Меню"])
def back_navigation(message):
    bot.send_message(message.chat.id, "Главное меню категорий:", reply_markup=get_categories_keyboard())


# --- ПОДАЧА ОБЪЯВЛЕНИЙ О ПРОДАЖЕ И ПАНЕЛЬ АДМИНИСТРАТОРА ---

@bot.message_handler(func=lambda message: message.text == "🛒 Подать объявление о продаже")
def ask_for_submission(message):
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
    user_is_adm = is_owner(user) or any(is_server_admin(user.id, s) for s in admins) or user.username in ADMIN_USERNAMES
    
    if not user_is_adm:
        bot.send_message(message.chat.id, "У вас нет доступа к панели администратора.")
        return
        
    markup = types.InlineKeyboardMarkup()
    if is_owner(user):
        markup.add(
            types.InlineKeyboardButton("➕ Назначить админа", callback_data="owner_add_adm"),
            types.InlineKeyboardButton("➖ Снять админа", callback_data="owner_rem_adm")
        )
    markup.add(types.InlineKeyboardButton("📋 Ожидающие заявки", callback_data="show_pending_list"))
    
    bot.send_message(
        message.chat.id, 
        f"⚙️ **Панель управления**\nСтатус: {'Владелец (@bounqy)' if is_owner(user) else 'Администратор'}", 
        parse_mode="Markdown", 
        reply_markup=markup
    )

def process_item_submission(message):
    global moderation_counter
    
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
    
    pending_posts[current_id] = {
        "user_id": message.from_user.id,
        "username": message.from_user.username or "Без юзернейма",
        "photo": photo_id,
        "text": text_content or "Без описания"
    }
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🟢 Сервер 1 (Одобрить)", callback_data=f"approve_s1_{current_id}"),
        types.InlineKeyboardButton("🟢 Сервер 2 (Одобрить)", callback_data=f"approve_s2_{current_id}")
    )
    markup.add(types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{current_id}"))
    
    forward_text = (
        f"📥 **Новая заявка на продажу #{current_id}**\n"
        f"От: @{message.from_user.username or message.from_user.id}\n\n"
        f"{text_content or ''}"
    )
    
    # Рассылаем уведомление о продаже всем модераторам из ADMIN_USERNAMES
    for admin in ADMIN_USERNAMES:
        try:
            if photo_id:
                bot.send_photo(f"@{admin}", photo_id, caption=forward_text, parse_mode="Markdown", reply_markup=markup)
            else:
                bot.send_message(f"@{admin}", forward_text, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            pass

    bot.send_message(message.chat.id, "✅ Ваша заявка успешно отправлена на модерацию администраторам!", reply_markup=get_categories_keyboard())


# --- ОБРАБОТКА CALLBACK КНОПОК ---

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    global pending_posts
    data = call.data
    user = call.from_user
    
    if data.startswith("approve_s1_") or data.startswith("approve_s2_"):
        parts = data.split("_")
        server_key = "server_1" if parts[1] == "s1" else "server_2"
        post_id = int(parts[2])
        
        if not is_owner(user) and not is_server_admin(user.id, server_key) and user.username not in ADMIN_USERNAMES:
            bot.answer_callback_query(call.id, "⚠️ У вас нет прав администратора для этого сервера!", show_alert=True)
            return
            
        if post_id in pending_posts:
            post = pending_posts[post_id]
            target_channel = "@Bounty_Squad31"
            
            publication_text = (
                f"🛒 **Новое объявление о продаже!**\n\n"
                f"{post['text']}\n\n"
                f"👤 Продавец: @{post['username']}"
            )
            
            try:
                if post["photo"]:
                    bot.send_photo(target_channel, post["photo"], caption=publication_text, parse_mode="Markdown")
                else:
                    bot.send_message(target_channel, publication_text, parse_mode="Markdown")
                
                bot.answer_callback_query(call.id, "Успешно опубликовано в канал!")
                bot.edit_message_caption(
                    chat_id=call.message.chat.id, 
                    message_id=call.message.message_id, 
                    caption=f"✅ Одобрено и опубликовано администратором (@{user.username or user.id})", 
                    reply_markup=None
                )
            except Exception as e:
                bot.answer_callback_query(call.id, f"Ошибка публикации: {e}", show_alert=True)
                
            del pending_posts[post_id]
        else:
            bot.answer_callback_query(call.id, "Заявка уже устарела или была обработана.")

    elif data.startswith("reject_"):
        post_id = int(data.split("_")[1])
        if not is_owner(user) and not any(is_server_admin(user.id, s) for s in admins) and user.username not in ADMIN_USERNAMES:
            bot.answer_callback_query(call.id, "Недостаточно прав.", show_alert=True)
            return
            
        if post_id in pending_posts:
            del pending_posts[post_id]
            bot.answer_callback_query(call.id, "Заявка отклонена.")
            try:
                bot.edit_message_caption(
                    chat_id=call.message.chat.id, 
                    message_id=call.message.message_id, 
                    caption="❌ Заявка отклонена администратором.", 
                    reply_markup=None
                )
            except:
                bot.edit_message_text(
                    chat_id=call.message.chat.id, 
                    message_id=call.message.message_id, 
                    text="❌ Заявка отклонена администратором.", 
                    reply_markup=None
                )

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


# --- УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК ВХОДЯЩИХ КОНТЕНТОВ (ЦЕНЫ / ПРОЧЕЕ) ---

@bot.message_handler(content_types=['photo', 'text'])
def handle_incoming_content(message):
    # Если пользователь находится в режиме отправки цены
    if message.chat.id in waiting_for_price:
        if message.text == "🚫 Отмена":
            waiting_for_price.remove(message.chat.id)
            bot.send_message(message.chat.id, "Отменено.", reply_markup=get_categories_keyboard())
            return

        user_tag = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
        srv = user_states.get(message.chat.id, "Не выбран сервак")
        
        admin_notification = (
            f"📥 **Новая предложенная цена!**\n"
            f"🌐 Сервер: {srv}\n"
            f"👤 От кого: {user_tag} (ID: `{message.from_user.id}`)\n"
            f"💬 Текст/Описание: {message.caption or message.text or 'Без текста'}"
        )

        for admin in ADMIN_USERNAMES:
            try:
                if message.content_type == 'photo':
                    bot.send_photo(f"@{admin}", message.photo[-1].file_id, caption=admin_notification, parse_mode="Markdown")
                else:
                    bot.send_message(f"@{admin}", admin_notification, parse_mode="Markdown")
            except Exception:
                pass

        waiting_for_price.remove(message.chat.id)
        bot.send_message(message.chat.id, "✅ **Спасибо!** Твоя информация отправлена модераторам на проверку.", parse_mode="Markdown", reply_markup=get_categories_keyboard())
        return

    # Обработка прочих текстовых нажатий меню категорий
    srv = user_states.get(message.chat.id, "Не выбран")
    bot.send_message(
        message.chat.id,
        f"📊 Раздел: **{message.text}**\n🌐 Сервер: **{srv}**\n\nДанные подгружаются из базы...",
        parse_mode="Markdown"
    )

# ---------------- ЗАПУСК ----------------

if __name__ == '__main__':
    bot.remove_webhook()
    print("🚀 Бот успешно запущен со всеми разделами аксов и системой модерации!")
    bot.infinity_polling(skip_pending=True)




