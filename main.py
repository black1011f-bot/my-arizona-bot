import os
import telebot
from telebot import types

# Инициализация бота
TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")
bot = telebot.TeleBot(TOKEN)

# Временное хранилище данных пользователей (в продакшене лучше использовать БД)
user_data = {}

# Этапы создания объявления
SERVER, CATEGORY, PHOTO, PRICE, CONFIRM = range(5)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_sell = types.KeyboardButton("📢 Продать товар")
    btn_catalog = types.KeyboardButton("📦 Каталог объявлений")
    markup.add(btn_sell, btn_catalog)

    bot.send_message(
        message.chat.id,
        "Привет! Это неофициальный бот-помощник для игроков Arizona RP.\n"
        "Здесь вы можете безопасно подать объявление о продаже транспорта или аксессуаров.",
        reply_markup=markup
    )


@bot.message_handler(func=lambda message: message.text == "📢 Продать товар")
def start_selling(message):
    user_data[message.chat.id] = {}
    
    # Шаг 1: Выбор сервера
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Phoenix", "Scottdale", "Casa-Grande", "Yuma") # Примеры серверов
    markup.add("❌ Отмена")
    
    bot.send_message(
        message.chat.id,
        "**Шаг 1 из 4:** Выберите игровой сервер, на котором продается товар:",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, process_server)


def process_server(message):
    if message.text == "❌ Отмена":
        return cancel_process(message)
        
    user_data[message.chat.id]['server'] = message.text
    
    # Шаг 2: Выбор категории
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("🚗 Транспорт", "💎 Аксессуары")
    markup.add("❌ Отмена")
    
    bot.send_message(
        message.chat.id,
        f"Сервер: **{message.text}**\n\n"
        "**Шаг 2 из 4:** Выберите категорию товара:",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, process_category)


def process_category(message):
    if message.text == "❌ Отмена":
        return cancel_process(message)
        
    user_data[message.chat.id]['category'] = message.text
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("❌ Отмена")

    bot.send_message(
        message.chat.id,
        "**Шаг 3 из 4:** Загрузите скриншот или фотографию товара, а также укажите его цену в описании.\n"
        "Отправьте фото с подписью:",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, process_photo_and_price)


def process_photo_and_price(message):
    if message.text == "❌ Отмена":
        return cancel_process(message)
        
    if not message.photo:
        bot.send_message(message.chat.id, "Пожалуйста, отправьте именно **фотографию** товара с ценой. Попробуйте еще раз:")
        return bot.register_next_step_handler(message, process_photo_and_price)

    # Сохраняем ID фото и текст (цену/описание)
    user_data[message.chat.id]['photo'] = message.photo[-1].file_id
    user_data[message.chat.id]['details'] = message.caption if message.caption else "Цена не указана"

    data = user_data[message.chat.id]

    # Шаг 4: Подтверждение и отправка на модерацию
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("✅ Отправить на модерацию", "❌ Отмена")

    preview_text = (
        "**Шаг 4 из 4:** Проверьте ваше объявление перед отправкой:\n\n"
        f"• **Сервер:** {data['server']}\n"
        f"• **Категория:** {data['category']}\n"
        f"• **Описание/Цена:** {data['details']}\n\n"
        "Всё верно?"
    )

    bot.send_photo(message.chat.id, data['photo'], caption=preview_text, reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(message, process_final_submit)


def process_final_submit(message):
    if message.text == "✅ Отправить на модерацию":
        # Здесь объявление уходит модераторам
        bot.send_message(
            message.chat.id,
            "🎉 Ваше объявление успешно отправлено на проверку модератору!\n"
            "После одобрения оно автоматически опубликуется в соответствующем разделе.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        # Возвращаем главное меню
        send_welcome(message)
    else:
        cancel_process(message)


def cancel_process(message):
    bot.send_message(message.chat.id, "Создание объявления отменено.", reply_markup=types.ReplyKeyboardRemove())
    send_welcome(message)


@bot.message_handler(func=lambda message: message.text == "📦 Каталог объявлений")
def show_catalog(message):
    bot.send_message(
        message.chat.id,
        "📦 **Каталог товаров**\n\n"
        "Здесь игроки могут просматривать уже одобренные модерацией объявления по серверам и категориям. "
        "(Раздел находится в разработке)",
        parse_mode="Markdown"
    )


if __name__ == "__main__":
    try:
        bot.remove_webhook()
        print("🚀 Бот запущен и готов к работе по сценарию подачи объявлений!")
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print(f"Ошибка: {e}")
