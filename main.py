import telebot
from telebot import types
from samp_client.client import SampClient

# Твой обновленный токен
TOKEN = "8962696714:AAH5dYsLqlAqoLdVr5-sJH35OJnw1ttgpJ0"
bot = telebot.TeleBot(TOKEN)

# Если захочешь добавить GIF — вставишь её file_id сюда
GIF_FILE_ID = None

user_states = {}

# Список всех серверов Arizona RP
SERVERS_IP = {
    "👑шаблон для VIP👑": None,
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

def check_player_online(ip, port, nickname):
    try:
        with SampClient(address=ip, port=port) as client:
            players = client.get_server_clients()
            for player in players:
                if player.name.lower() == nickname.lower():
                    return f"🟢 Игрок **{player.name}** в сети! (Score: {player.score})"
            return f"🔴 Игрока **{nickname}** нет в сети."
    except Exception:
        return "⚠️ Ошибка при подгрузке списка игроков."

# --- КЛАВИАТУРЫ ---

def get_servers_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [types.KeyboardButton(name) for name in SERVERS_IP.keys()]
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
    btn8 = types.KeyboardButton("🔍 Проверить Ник в игре")
    btn_back = types.KeyboardButton("🔙 Назад")
    btn_main = types.KeyboardButton("🔝 Главное Меню")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8, btn_back, btn_main)
    return markup

# --- ОБРАБОТЧИКИ ---

@bot.message_handler(content_types=['animation'])
def handle_gif(message):
    file_id = message.animation.file_id
    bot.reply_to(message, f"🆔 **FILE_ID твоей гифки:**\n`{file_id}`\n\nСкопируй его в переменную GIF_FILE_ID!")

@bot.message_handler(commands=['start'])
def start_cmd(message):
    welcome_text = (
        "👋 **Привет! Это неофициальный бот с ценами для Arizona RP!**\n\n"
        "🎯 Выбирай сервер из списка и узнавай актуальные цены с ЦР и АБ.\n\n"
        "🛡 **Безопасность:**\n"
        "• Мы НИКОГДА не просим пароли, пин-коды или данные от аккаунта!\n"
        "• Бот абсолютно бесплатный — мы НЕ просим деньги за работу.\n\n"
        "📢 Наш Telegram-канал: @Bounty_Squad31\n\n"
        "❤️ **Спасибо, что используешь нашего бота! Удачных сделок!**"
    )
    
    if GIF_FILE_ID:
        try:
            bot.send_animation(message.chat.id, GIF_FILE_ID, caption=welcome_text, reply_markup=get_servers_keyboard(), parse_mode="Markdown")
            return
        except Exception:
            pass
            
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_servers_keyboard(), parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text in ["🔝 Главное Меню", "🔙 Назад"])
def back_to_main(message):
    user_states.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "👇 **Выбери сервер из списка:**", reply_markup=get_servers_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "👑шаблон для VIP👑")
def vip_template(message):
    vip_text = (
        "👑 **ГОТОВЫЕ ШАБЛОНЫ ДЛЯ VIP-ЧАТА (/vr) И РАДИО**\n\n"
        "Нажми на нужный текст, чтобы скопировать, подставь свои данные (цена, название, телефон) и отправляй в чат!\n\n"
        "🛒 **ПОКУПКА / СКУПКА:**\n"
        "`Куплю [Предмет/Авто] | Бюджет: [Сумма] $ | Звоните: [Номер]`\n"
        "`Скупаю аксы, ресурсы и ларцы в лавке на ЦР! Палатка №[Номер]. Жду всех!`\n"
        "`Куплю любой активный акс +12 / сет. Бюджет свободный! Звоните: [Номер]`\n\n"
        "🏷 **ПРОДАЖА:**\n"
        "`Продам [Предмет/Авто] | Цена: [Сумма] $ (Торг) | Звоните: [Номер]`\n"
        "`Срочно продам [Предмет] ниже рынка! Нужны вирты! Звоните: [Номер]`\n"
        "`Продам сет аксессуаров [Заточка/Цвет]. Подробности по тел: [Номер]`\n\n"
        "🔄 **ОБМЕН:**\n"
        "`Обменяю [Твой предмет/авто] на [Другой предмет] с моей/твоей ДП. Звоните: [Номер]`\n\n"
        "⚠️ *Напоминание: Не забывай соблюдать интервал (КД) на рекламу в /vr на своем сервере!*"
    )
    bot.send_message(message.chat.id, vip_text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text in SERVERS_IP.keys())
def server_select(message):
    server_name = message.text
    user_states[message.chat.id] = {"selected_server": server_name}
    
    ip, port = SERVERS_IP[server_name]
    online_info = get_server_online(ip, port)
    
    text = f"🏰 **Сервер:** {server_name}\n\n{online_info}\n\n👇 **Выбери категорию цен:**"
    bot.send_message(message.chat.id, text, reply_markup=get_categories_keyboard(), parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🔍 Проверить Ник в игре")
def ask_nickname(message):
    state = user_states.get(message.chat.id)
    if not state or "selected_server" not in state:
        bot.send_message(message.chat.id, "⚠️ Сначала выбери сервер из списка!")
        return
        
    user_states[message.chat.id]["waiting_for_nick"] = True
    bot.send_message(message.chat.id, "👤 Напиши Nick_Name игрока (например, `Nick_Name`):", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get("waiting_for_nick"))
def process_nickname(message):
    nick = message.text.strip()
    server_name = user_states[message.chat.id]["selected_server"]
    ip, port = SERVERS_IP[server_name]
    
    bot.send_message(message.chat.id, f"🔎 Ищу `{nick}` на сервере {server_name}...", parse_mode="Markdown")
    
    result = check_player_online(ip, port, nick)
    user_states[message.chat.id]["waiting_for_nick"] = False
    
    bot.send_message(message.chat.id, result, parse_mode="Markdown")

if __name__ == "__main__":
    bot.infinity_polling()




