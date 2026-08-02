import telebot
from telebot import types

TOKEN = "8962696714:AAH5dYsLq1AqoLdVr5-sJH35OJnw"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start_message(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_online = types.KeyboardButton("🟢 Посмотреть онлайн")
    btn_custom = types.KeyboardButton("🔍 Ввести название")
    markup.add(btn_online, btn_custom)
    
    text = (
        "👋 Привет! Это неофициальный бот с ценами для Arizona RP!\n\n"
        "🎯 Выбирай сервер из списка и узнавай актуальные цены с ЦР и АБ.\n\n"
        "🛡 Безопасность:\n"
        "• Мы НИКОГДА не просим пароли или данные!\n"
        "• Бот абсолютно бесплатный.\n\n"
        "📢 Наш Telegram-канал: @Bounty_Squad31\n\n"
        "❤️ Спасибо, что используешь нашего бота!"
    )
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text == "🟢 Посмотреть онлайн":
        bot.send_message(message.chat.id, "Загружаю данные по онлайну...")
    elif message.text == "🔍 Ввести название":
        bot.send_message(message.chat.id, "Введи название предмета для поиска цены:")

if __name__ == '__main__':
    bot.infinity_polling()

