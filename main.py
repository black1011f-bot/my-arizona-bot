import os
import time
import threading
import logging
from datetime import datetime, time as dtime

import telebot
from telebot import types

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- ТОКЕН ---
# ВНИМАНИЕ: Никогда не выкладывай этот файл с токеном на GitHub или в чаты!
# Для продакшена используй переменные окружения.
TOKEN = os.getenv("BOT_TOKEN", "8916669266:AAHthuVb2azh-1SsiEQdRqOZLSyufcCQaWQ")

if not TOKEN:
    logger.error("❌ Ошибка: BOT_TOKEN не найден!")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# --- ДАННЫЕ (В ПАМЯТИ) ---
user_states = {}       # Состояние пользователя (сервер, шаг и т.д.)
user_data = {}          # Данные пользователя (кулдауны и прочее)
active_ads = {}         # Активные объявления (только одобренные)
pending_posts = {}      # Заявки на модерации
ads_lock = threading.Lock()
moderation_counter = 0

OWNER_USERNAME = "bounqy"
ADMIN_USERNAMES = ["bounqy31", "bounqy"]
# ID чата модерации. Можно поменять через переменную окружения
MODERATION_CHAT_ID = int(os.getenv("MODERATION_CHAT_ID", "-1001234567890"))

SERVERS = [
    "🔥 Phoenix", "🌴 Tucson", "🌵 Scottdale", "⚜️ Chandler", "❄️ Brainburg", "🌊 Yuma",
    "✨ Saint-Rose", "🏛 Mesa", "❤️ Red-Rock", "🍀 Surprise", "⚡️ Prescott", "🌲 Glendale",
    "👑 Kingman", "⚓️ Winslow", "🌴 Payson", "💎 Gilbert", "🔥 Show-Low", "🌴 Casa-Grande",
    "📜 Page", "☀️ Sun-City", "👑 Queen-Creek", "🌵 Sedona", "🎄 Holiday", "🍀 Wednesday",
    "⚡️ Yava", "🌌 Faraway", "🎁 Christmas", "🐝 Bumble Bee", "🪞 Mirage", "💖 Love",
    "📱 Mobile I", "📱 Mobile II", "📱 Mobile III"
]

CATEGORIES = [
    "💍 Аксы",
    "🏎 Все авто,воздушные,водные,тюнинг",
    "🥼 Скины и Охранники",
    "🏡 Дом и Бизнес",
    "📦 Ресурсы и Оружие"
]

# --- ФОНОВАЯ ОЧИСТКА ---
def background_cleanup_ads():
    while True:
        time.sleep(30)
        now = datetime.now()
        now_time = now.time()
        curr_t = time.time()

        # Ночное время: 22:00:22 — 07:59:59
        is_night = now_time >= dtime(22, 0, 22) or now_time < dtime(8, 0, 0)
        # Утренний интервал очистки: 08:00:00 — 08:05:22
        is_morning_clean = dtime(8, 0, 0) <= now_time <= dtime(8, 5, 22)

        with ads_lock:
            expired_ids = []
            for aid, data in active_ads.items():
                # Удаляем если: прошло >10 мин ИЛИ ночь ИЛИ утренняя чистка
                if (curr_t - data.get("last_updated", 0) > 600) or is_night or is_morning_clean:
                    expired_ids.append(aid)

            for aid in expired_ids:
                msg_map = active_ads[aid].get("message_ids_map", {})
                for target_id, msg_id in list(msg_map.items()):
                    try:
                        bot.delete_message(target_id, msg_id)
                    except Exception as e:
                        logger.warning(f"Не удалось удалить сообщение {msg_id}: {e}")
                del active_ads[aid]
                logger.info(f"Объявление #{aid} удалено.")

threading.Thread(target=background_cleanup_ads, daemon=True).start()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def is_owner(user):
    return user and user.username and user.username.lower() == OWNER_USERNAME.lower()

def is_admin_or_owner(user):
    if not user: return False
    if is_owner(user): return True
    if user.username:
        return user.username.lower() in [a.lower() for a in ADMIN_USERNAMES]
    return False

def check_working_hours():
    now_time = datetime.now().time()
    return dtime(8, 0, 0) <= now_time <= dtime(22, 0, 22)

def kb_servers():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for i in range(0, len(SERVERS), 2):
        markup.add(*[types.KeyboardButton(s) for s in SERVERS[i:i+2]])
    markup.add(types.KeyboardButton("🛒 Подать объявление о продаже"), types.KeyboardButton("👑 Админ"))
    return markup
