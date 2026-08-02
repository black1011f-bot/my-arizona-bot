import telebot
from telebot import types

# Твой токен бота
TOKEN = "8962696714:AAH5dYsLq1AqoLdVr5-sJH35OJnw"
bot = telebot.TeleBot(TOKEN)

# Список всех серверов для клавиатуры
SERVERS_LIST = [
    "🔥 Phoenix", "🌵 Tucson", "🌽 Scottdale", "💼 Chandler",
    "🧠 Brainburg", "🤠 Yuma", "🌹 Saint-Rose", "🏛 Mesa",
    "🎸 Red-Rock", "🎁 Surprise", "🌲 Prescott", "🎰 Glendale",
    "👑 Kingman", "🏙 Winslow", "🏔 Payson", "⚡ Gilbert",
    "🎙 Show-Low", "🏡 Casa-Grande", "📄 Page", "☀️ Sun-City",
    "👑 Queen-Creek", "🔴 Sedona", "🎄 Holiday", "🐸 Wednesday",
    "☕ Yava", "🌌 Faraway", "🎅 Christmas", "🐝 Bumble Bee",
    "🏝 Mirage", "❤️ Love", "📱 Mobile I", "📲 Mobile II", "⚡ Mobile III"
]

# Главное меню со списком серверов
def get_servers_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [types.KeyboardButton(name) for name in SERVERS_LIST]
    markup.add(*buttons)
    return markup

# Меню категорий цен
def get_categories_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("💍 Аксы")
    btn2 = types.KeyboardButton("🏎 Все авто, воздушные, водные, тюнинг")
    btn3 = types.KeyboardButton("🥼 Скины и Охранники")
    btn4 = types.KeyboardButton("🏠 Дом и Бизнес")
    btn5 = types.KeyboardButton("📦 Ресурсы и Оружие")
    btn6 = types.KeyboardButton("🗿 Предложить цену")
    btn7 = types.KeyboardButton("🌵 Отслеживать предмет")
    btn_back = types.KeyboardButton("🔙 Назад")
    btn_main = types.KeyboardButton("🔝 Главное Меню")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn_back, btn_main)
    return markup

# Команда /start
@bot.message_handler(commands=['start'])
def start_cmd(message):
    welcome_text = (
        "👋 **Привет! Это неофициальный бот с ценами для Arizona RP!**\n\n"
        "🎯 Выбирай сервер из списка и узнавай актуальные цены с ЦР и АБ.\n\n"
        "🛡 **Безопасность:**\n"
        "• Мы НИКОГДА не просим пароли или данные от аккаунта!\n"
        "• Бот абсолютно бесплатный.\n\n"
        "📢 Наш Telegram-канал: @Bounty_Squad31\n\n"
        "👇 **Выбери свой сервер ниже:**"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_servers_keyboard(), parse_mode="Markdown")

# Кнопки возврата
@bot.message_handler(func=lambda msg: msg.text in ["🔝 Главное Меню", "🔙 Назад"])
def back_to_main(message):
    bot.send_message(message.chat.id, "👇 **Выбери сервер из списка:**", reply_markup=get_servers_keyboard())

# Обработка выбора любого сервера
@bot.message_handler(func=lambda msg: msg.text in SERVERS_LIST)
def server_select(message):
    server_name = message.text
    text = f"🌐 **Выбран сервер:** {server_name}\n\n👇 **Выбери категорию цен ниже:**"
    bot.send_message(message.chat.id, text, reply_markup=get_categories_keyboard(), parse_mode="Markdown")

# Обработка нажатий на категории
@bot.message_handler(func=lambda msg: True)
def handle_categories(message):
    bot.send_message(message.chat.id, f"Вы выбрали: {message.text}. Раздел наполняется ценами! 🛠")

if __name__ == "__main__":
    bot.infinity_polling()



