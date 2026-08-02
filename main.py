import telebot
from telebot import types
from samp_client.client import SampClient

# Твой токен бота вставлен напрямую, чтобы избежать ошибок с переменными
TOKEN = "8962696714:AAH5dYsLq1AqoLdVr5-sJH35OJnw"
bot = telebot.TeleBot(TOKEN)

# Список всех серверов Arizona RP с IP и портами
SERVERS_IP = {
    "🔥 Phoenix": ("185.169.134.3", 7777),
    "🌵 Tucson": ("185.169.134.4", 7777),
    "🌽 Scottdale": ("185.169.134.11", 7777),
    "💼 Chandler": ("185.169.134.43", 7777),
    "🧠 Brainburg": ("185.169.134.44", 7777),
    "🤠 Yuma": ("185.169.134.107", 7777),
    "🌹 Saint-Rose": ("185.169.134.45", 7777),
    "🏛 Mesa": ("185.169.134.59", 7777),
    "🎸 Red-Rock": ("185.169.134.60", 7777),
    "🎁 Surprise": ("185.169.134.61", 7777),
    "🌲 Prescott": ("185.169.134.22", 7777),
    "🎰 Glendale": ("185.169.134.171", 7777),
    "👑 Kingman": ("185.169.134.172", 7777),
    "🏙 Winslow": ("185.169.134.173", 7777),
    "🏔 Payson": ("185.169.134.174", 7777),
    "⚡ Gilbert": ("185.169.134.170", 7777),
    "🎙 Show-Low": ("185.169.134.166", 7777),
    "🏡 Casa-Grande": ("185.169.134.165", 7777),
    "📄 Page": ("185.169.134.20", 7777),
    "☀️ Sun-City": ("185.169.134.21", 7777),
    "👑 Queen-Creek": ("185.169.134.34", 7777),
    "🔴 Sedona": ("185.169.134.33", 7777),
    "🎄 Holiday": ("185.169.134.40", 7777),
    "🐸 Wednesday": ("185.169.134.41", 7777),
    "☕ Yava": ("185.169.134.42", 7777),
    "🌌 Faraway": ("185.169.134.8", 7777),
    "🎅 Christmas": ("185.169.134.9", 7777),
    "🐝 Bumble Bee": ("185.169.134.10", 7777),
    "🏝 Mirage": ("185.169.134.12", 7777),
    "❤️ Love": ("185.169.134.13", 7777),
    "📱 Mobile I": ("185.169.134.16", 7777),
    "📲 Mobile II": ("185.169.134.17", 7777),
    "⚡ Mobile III": ("185.169.134.18", 7777)
}

def get_server_online(ip, port):
    try:
        with SampClient(address=ip, port=port) as client:
            info = client.get_server_info()
            return f"📊 **Онлайн:** `{info.players}/{info.max_players}`\n🟢 **Статус:** Работает"
    except Exception:
        return "⚠️ **Статус:** Не удалось запросить онлайн"

# Клавиатура со списком серверов
def get_servers_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [types.KeyboardButton(name) for name in SERVERS_IP.keys()]
    markup.add(*buttons)
    return markup

# Клавиатура с категориями товаров
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

# Кнопки возврата назад
@bot.message_handler(func=lambda msg: msg.text in ["🔝 Главное Меню", "🔙 Назад"])
def back_to_main(message):
    bot.send_message(message.chat.id, "👇 **Выбери сервер из списка:**", reply_markup=get_servers_keyboard())

# Обработка выбора сервера
@bot.message_handler(func=lambda msg: msg.text in SERVERS_IP.keys())
def server_select(message):
    server_name = message.text
    ip, port = SERVERS_IP[server_name]
    
    online_info = get_server_online(ip, port)
    text = f"{server_name}\n\n{online_info}\n\n👇 **Выбери категорию цен:**"
    
    bot.send_message(message.chat.id, text, reply_markup=get_categories_keyboard(), parse_mode="Markdown")

if __name__ == "__main__":
    bot.infinity_polling()


