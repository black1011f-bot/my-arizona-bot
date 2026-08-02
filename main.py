import telebot
from telebot import types

# Инициализация бота
TOKEN = "8962696714:AAH5dYsLqlAqoLdVr5-sJH35OJnw1ttgpJ0"
bot = telebot.TeleBot(TOKEN)

# Данные пользователей (выбранный сервер)
user_states = {}

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

def get_skins_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("👑 Уникальные скины"),
        types.KeyboardButton("🏃 Скины с бегом CJ")
    )
    markup.add(
        types.KeyboardButton("🧍 Охранники (Pets)"),
        types.KeyboardButton("💼 Фракционные скины")
    )
    markup.add(
        types.KeyboardButton("⬅ Назад"),
        types.KeyboardButton("🔝 Главное Меню")
    )
    return markup

def get_houses_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🏢 Квартиры и ЖК"),
        types.KeyboardButton("🏡 Дома (по районам)")
    )
    markup.add(
        types.KeyboardButton("🅿 Парковочные места"),
        types.KeyboardButton("🏢 Бизнесы")
    )
    markup.add(
        types.KeyboardButton("🚜 Огороды и Фермы")
    )
    markup.add(
        types.KeyboardButton("⬅ Назад"),
        types.KeyboardButton("🔝 Главное Меню")
    )
    return markup

def get_resources_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🪙 Талоны и AZ"),
        types.KeyboardButton("🔫 Оружие и Аксы-ган")
    )
    markup.add(
        types.KeyboardButton("🎁 Ларцы и Рулетки"),
        types.KeyboardButton("🎒 Ресурсы")
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

# --- Подменю категорий ---

@bot.message_handler(func=lambda msg: msg.text == "🏎 Все авто,воздушные,водные,тюнинг")
def category_auto(message):
    bot.send_message(message.chat.id, message.text, reply_markup=get_auto_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "🥼 Скины и Охранники")
def category_skins(message):
    bot.send_message(message.chat.id, message.text, reply_markup=get_skins_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "🏡 Дома и Бизнесы")
def category_houses(message):
    bot.send_message(message.chat.id, message.text, reply_markup=get_houses_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "📦 Ресурсы и Оружие")
def category_resources(message):
    bot.send_message(message.chat.id, message.text, reply_markup=get_resources_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "💍 Аксы")
def category_accessories(message):
    bot.send_message(
        message.chat.id, 
        "💍 **Категория: Аксессуары**\n\nНапиши название акса или выбери вариант из меню ниже.", 
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "📩 Предложить цену")
def suggest_price(message):
    text = (
        "📸 **Запостил лавку — помог серверу!**\n\n"
        "Наткнулся на сочные цены на ЦР или АБ? Видишь лютый оверпрайс или слив за копейки? Не держи в себе! 💰\n\n"
        "💬 **Засылай сюда:**\n"
        "1. Четкий скриншот лавки или рынка (обязательно с `/time` ⏰).\n"
        "2. Название предмета и его точную цену.\n\n"
        "🚀 *Твой скрин поможет обновить базу и убережет игроков от оверпрайса! Ждем фоток!*"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_cancel_keyboard())

# --- Навигация и отмена ---

@bot.message_handler(func=lambda msg: msg.text in ["⬅ Назад", "🔝 Главное Меню", "🚫 Отмена"])
def back_navigation(message):
    bot.send_message(message.chat.id, "Главное меню категорий:", reply_markup=get_categories_keyboard())

# --- Обработка остальных сообщений ---

@bot.message_handler(func=lambda msg: True)
def handle_all_other_messages(message):
    srv = user_states.get(message.chat.id, "Не выбран")
    bot.send_message(
        message.chat.id,
        f"📊 Раздел: **{message.text}**\n🌐 Сервер: **{srv}**\n\nДанные подгружаются из базы...",
        parse_mode="Markdown"
    )

# ---------------- ЗАПУСК ----------------

if __name__ == '__main__':
    # Автоматический сброс вебхука при запуске (избавляет от ошибки 409 Conflict)
    bot.delete_webhook()
    print("🚀 Бот успешно запущен и готов к работе!")
    bot.infinity_polling(skip_pending=True)



