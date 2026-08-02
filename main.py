import telebot
from telebot import types

# Инициализация бота
TOKEN = "8962696714:AAH5dYsLqlAqoLdVr5-sJH35OJnw1ttgpJ0"
bot = telebot.TeleBot(TOKEN)

# Данные пользователей и настройки
user_states = {}        # Хранит выбранный сервер
waiting_for_price = []  # Список пользователей, которые отправляют скриншот цены

# Твои юзернеймы/ID для получения предложений цен (модерация)
ADMIN_USERNAMES = ["bounqy31", "bounqy"] 

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

# ----------------- КЛАВИАТУРЫ -----------------

def get_servers_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for i in range(0, len(SERVERS), 2):
        pair = SERVERS[i:i+2]
        markup.add(*[types.KeyboardButton(s) for s in pair])
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
    markup.add(types.KeyboardButton("🔄 Сменить сервер"))
    return markup

# Подменю для Аксессуаров (как на твоем скриншоте)
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


# ----------------- ОБРАБОТЧИКИ -----------------

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
def admin_panel(message):
    if message.from_user.username in ADMIN_USERNAMES:
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

# --- Обработка разделов ---

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

# --- Пересылка скриншотов цен модераторам (без палева юзернейма для обычных игроков) ---

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
        
        # Текст, который прилетит тебе в личку (скрыт от остальных)
        admin_notification = (
            f"📥 **Новая предложенная цена!**\n"
            f"🌐 Сервер: {srv}\n"
            f"👤 От кого: {user_tag} (ID: `{message.from_user.id}`)\n"
            f"💬 Текст/Описание: {message.caption or message.text or 'Без текста'}"
        )

        # Рассылаем тебе на @bounqy31 / @bounqy (ищем по юзернеймам или отправляем по твоему ID)
        # Бот пересылает фото или текст тебе в ЛС для проверки
        for admin in ADMIN_USERNAMES:
            try:
                # Отправляем уведомление модераторам
                if message.content_type == 'photo':
                    bot.send_photo(f"@{admin}", message.photo[-1].file_id, caption=admin_notification, parse_mode="Markdown")
                else:
                    bot.send_message(f"@{admin}", admin_notification, parse_mode="Markdown")
            except Exception:
                pass # Если кто-то из админов не написал боту первым, пропускаем ошибку

        waiting_for_price.remove(message.chat.id)
        bot.send_message(message.chat.id, "✅ **Спасибо!** Твоя информация отправлена модераторам на проверку.", parse_mode="Markdown", reply_markup=get_categories_keyboard())
        return

    # Обработка прочих сообщений
    srv = user_states.get(message.chat.id, "Не выбран")
    bot.send_message(
        message.chat.id,
        f"📊 Раздел: **{message.text}**\n🌐 Сервер: **{srv}**\n\nДанные подгружаются из базы...",
        parse_mode="Markdown"
    )

# ---------------- ЗАПУСК ----------------

if __name__ == '__main__':
    bot.delete_webhook()
    print("🚀 Бот успешно запущен со всеми разделами аксов и системой модерации!")
    bot.infinity_polling(skip_pending=True)




