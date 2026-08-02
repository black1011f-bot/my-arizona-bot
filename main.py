import telebot
from telebot import types
from samp_client.client import SampClient

# Твой токен от BotFather
TOKEN = "8962696714:AAH5dYsLqlAqoLdVr5-sJH35OJnw1ttgpJ0"
bot = telebot.TeleBot(TOKEN)

# IP и порт сервера Tucson (Arizona RP)
SERVER_IP = "185.169.134.4"
SERVER_PORT = 7777

@bot.message_handler(commands=['start'])
def start_message(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_online = types.KeyboardButton("🟢 Проверить онлайн Majorka_Bounty")
    btn_custom = types.KeyboardButton("🔍 Ввести другой ник")
    markup.add(btn_online, btn_custom)

    bot.send_message(
        message.chat.id,
        "👋 Привет! Выбери действие на кнопках ниже или напиши ник игрока:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text.strip()

    if text == "🟢 Проверить онлайн Majorka_Bounty":
        check_online(message, "Majorka_Bounty")
    elif text == "🔍 Ввести другой ник":
        bot.send_message(message.chat.id, "Напиши ник игрока в формате `Nick_Name`:")
    else:
        check_online(message, text)

def check_online(message, nickname):
    bot.send_message(message.chat.id, f"🔍 Проверяю {nickname} на сервере...")
    try:
        with SampClient(address=SERVER_IP, port=SERVER_PORT) as client:
            players = client.get_server_clients_detailed()
            found = False
            for p in players:
                if p.name.lower() == nickname.lower():
                    found = True
                    bot.send_message(
                        message.chat.id,
                        f"🟢 **{p.name} в игре!**\n\n🆔 ID: {p.id}\n📊 Пинг: {p.ping}",
                        parse_mode="Markdown"
                    )
                    break
            if not found:
                bot.send_message(message.chat.id, f"🔴 Игрок **{nickname}** сейчас оффлайн.", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, "⚠️ Ошибка подключения к серверу Arizona RP.")

print("Бот запущен...")
bot.polling(none_stop=True)
