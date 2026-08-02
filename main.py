import telebot
from telebot import types

# Твой токен
TOKEN = "8962696714:AAH5dYsLqlAqoLdVr5-sJH35OJnw1ttgpJ0"
bot = telebot.TeleBot(TOKEN)

GIF_FILE_ID = None
user_states = {}

# Список всех серверов Arizona RP
SERVERS_LIST = [
    "👑шаблон для VIP👑", "🔥 Phoenix", "🌵 Tucson", "🌽 Scottdale", 
    "💼 Chandler", "🧠 Brainburg", "🤠 Yuma", "🌹 Saint-Rose", 
    "🏛 Mesa", "🎸 Red-Rock", "🎁 Surprise", "🌲 Prescott", 
    "🎰 Glendale", "👑 Kingman", "🏙 Winslow", "🏔 Payson", 
    "⚡ Gilbert", "🎙 Show-Low", "🏡 Casa-Grande", "📄 Page", 
    "☀️ Sun-City", "👑 Queen-Creek", "🔴 Sedona", "🎄 Holiday", 
    "🐸 Wednesday", "☕ Yava", "🌌 Faraway", "🎅 Christmas", 
    "🐝 Bumble Bee", "🏝 Mirage", "❤️ Love", "📱 Mobile I", 
    "📲 Mobile II", "⚡ Mobile III"
]

def get_servers_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [types.KeyboardButton(name) for name in SERVERS_LIST]
    markup.add(*buttons)
    return markup

def get_categories_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("💍 Аксы")
    btn2 = types.KeyboardButton("🏎 Все авто, воздушные, водные, тюнинг")
    btn3 = types.KeyboardButton("🥼 Скины и Охранники")
    btn4 = types.KeyboardButton("🏠 Дома и Бизнесы")
    btn5 = types.KeyboardButton("📦 Ресурсы и Оружие")
    btn6 = types.KeyboardButton("🗿 Предложить цену")
    btn7 = types.KeyboardButton("🌵 Отслеживать предмет")
    btn_back = types.KeyboardButton("🔙 Назад")
    btn_main = types.KeyboardButton("🔝 Главное Меню")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn_back, btn_main)
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    welcome_text = (
        "👋 **Привет! Это неофициальный бот с ценами для Arizona RP!**\n\n"
        "🎯 Выбирай сервер из списка и узнавай актуальные цены с ЦР и АБ.\n\n"
        "🛡 **Безопасность:**\n"
        "• Мы НИКОГДА не просим пароли, пин-коды или данные от аккаунта!\n"
        "• Бот абсолютно бесплатный.\n\n"
        "📢 Наш Telegram-канал: @Bounty_Squad31\n\n"
        "👇 **Выбери свой сервер ниже:**"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_servers_keyboard(), parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text in ["🔝 Главное Меню", "🔙 Назад"])
def back_to_main(message):
    bot.send_message(message.chat.id, "👇 **Выбери сервер из списка:**", reply_markup=get_servers_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "👑шаблон для VIP👑")
def vip_template(message):
    vip_text = (
        "👑 **ГОТОВЫЕ ШАБЛОНЫ ДЛЯ VIP-ЧАТА (/vr) И РАДИО**\n\n"
        "🛒 **ПОКУПКА / СКУПКА:**\n"
        "`Куплю [Предмет/Авто] | Бюджет: [Сумма] $ | Звоните: [Номер]`\n\n"
        "🏷 **ПРОДАЖА:**\n"
        "`Продам [Предмет/Авто] | Цена: [Сумма] $ (Торг) | Звоните: [Номер]`"
    )
    bot.send_message(message.chat.id, vip_text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text in SERVERS_LIST)
def server_select(message):
    text = f"🏰 **Сервер:** {message.text}\n\n👇 **Выбери категорию цен:**"
    bot.send_message(message.chat.id, text, reply_markup=get_categories_keyboard(), parse_mode="Markdown")

@bot.message_handler(func=lambda msg: True)
def handle_categories(message):
    bot.send_message(message.chat.id, f"Вы выбрали: {message.text}. Раздел наполняется ценами! 🛠")

if __name__ == "__main__":
    bot.infinity_polling()



