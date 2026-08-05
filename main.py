from datetime import datetime, time as dtime, timedelta
import contextlib
import html
import io
import logging
import os
import random
import re
import sqlite3
import threading
import time
from zoneinfo import ZoneInfo
import requests
import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

# ==========================================
# ЛОГИРОВАНИЕ И КОНФИГУРАЦИЯ
# ==========================================
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

TOKEN = "8916669266:AAFbIqOvrkdekhVkh1NTmMvpxSI_neTyN9I"
MANAGER_USERNAME = "bounqy31"
BOT_USERNAME = "arizona_coin_bot"

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=20)

OWNER_USERNAME = "bounqy"
ADMIN_USERNAMES = {"bounqy31", "bounqy"}

DB_NAME = "smi_bot.db"
db_lock = threading.Lock()
state_lock = threading.Lock()


# ==========================================
# ЗАЩИТА ОТ ФЛУДА И РАСШИРЕННЫЙ СПИСОК МАТА
# ==========================================
antispam_lock = threading.Lock()
user_last_message_time = {}
RATE_LIMIT_SECONDS = 0.6

SERVERS = [
    "🔥 Phoenix",
    "🌴 Tucson",
    "🌵 Scottdale",
    "⚜️ Chandler",
    "❄️ Brainburg",
    "🌊 Yuma",
    "✨ Saint-Rose",
    "🏛 Mesa",
    "❤️ Red-Rock",
    "🍀 Surprise",
    "⚡️ Prescott",
    "🌲 Glendale",
    "👑 Kingman",
    "⚓️ Winslow",
    "🌴 Payson",
    "💎 Gilbert",
    "🔥 Show-Low",
    "🌴 Casa-Grande",
    "📜 Page",
    "☀️ Sun-City",
    "👑 Queen-Creek",
    "🌵 Sedona",
    "🎄 Holiday",
    "🍀 Wednesday",
    "⚡️ Yava",
    "🌌 Faraway",
    "🎁 Christmas",
    "🐝 Bumble Bee",
    "🪞 Mirage",
    "💖 Love",
    "📱 Mobile I",
    "📱 Mobile II",
    "📱 Mobile III",
]

CATEGORIES = [
    "💍 Аксессуары и вещи",
    "🚗 Транспорт и тюнинг",
    "👕 Скины и охранники",
    "🏠 Недвижимость и бизнесы",
    "📦 Ресурсы и материалы",
]

BAD_WORDS = [
    "хуй",
    "хуе",
    "хуя",
    "хуи",
    "пизд",
    "еб",
    "бля",
    "сук",
    "залуп",
    "мраз",
    "ебан",
    "долбоеб",
    "сука",
    "блять",
    "ебать",
    "хуесос",
    "пидорас",
    "пидар",
    "мразь",
    "урод",
    "чмо",
    "шлюх",
    "блядь",
    "сукин",
    "залупа",
    "гандон",
    "ондон",
    "дроч",
    "ебуч",
    "еблан",
    "пиздюк",
    "выбляд",
    "samp-rp",
    "advance",
    "Arizona V",
    "Diamond",
    "продажа вирт",
    "продам вирты",
]


def is_flooding(user_id: int) -> bool:
  if is_admin_or_owner_id(user_id):
    return False

  current_time = time.time()
  with antispam_lock:
    last_time = user_last_message_time.get(user_id, 0)
    if current_time - last_time < RATE_LIMIT_SECONDS:
      return True
    user_last_message_time[user_id] = current_time
  return False


# ==========================================
# УНИВЕРСАЛЬНЫЙ ПАРСЕР ЦЕН (1кк, 1к, 1.5кк, 1.000 и т.д.)
# ==========================================
def parse_flexible_price(text: str) -> int:
  if not text:
    raise ValueError("Пустая цена")
  cleaned = text.strip().lower()
  cleaned = (
      cleaned.replace("$", "")
      .replace("руб", "")
      .replace("вк", "")
      .replace("vc", "")
      .strip()
  )

  multiplier = 1
  if "миллиард" in cleaned or "ккк" in cleaned:
    multiplier = 1_000_000_000
    cleaned = cleaned.replace("миллиард", "").replace("ккк", "").strip()
  elif (
      "кк" in cleaned
      or "kk" in cleaned
      or "лям" in cleaned
      or "лимон" in cleaned
  ):
    multiplier = 1_000_000
    cleaned = (
        cleaned.replace("кк", "")
        .replace("kk", "")
        .replace("лям", "")
        .replace("лимон", "")
        .strip()
    )
  elif "к" in cleaned or "k" in cleaned or "тыс" in cleaned:
    multiplier = 1_000
    cleaned = (
        cleaned.replace("к", "").replace("k", "").replace("тыс", "").strip()
    )

  cleaned = cleaned.replace(" ", "").replace("_", "")
  if "." in cleaned or "," in cleaned:
    cleaned = cleaned.replace(",", ".")
    try:
      val = float(cleaned)
      return int(val * multiplier)
    except ValueError:
      cleaned = cleaned.replace(".", "")

  try:
    return int(float(cleaned) * multiplier)
  except ValueError:
    raise ValueError(f"Не удалось распознать цену: {text}")


# ==========================================
# ПОТОКОБЕЗОПАСНОЕ УПРАВЛЕНИЕ СОСТОЯНИЯМИ И БД
# ==========================================
user_states = {}


@contextlib.contextmanager
def get_db():
  conn = sqlite3.connect(DB_NAME, timeout=10.0)
  conn.row_factory = sqlite3.Row
  try:
    yield conn
    conn.commit()
  except Exception:
    conn.rollback()
    raise
  finally:
    conn.close()


def is_banned(user) -> bool:
  if not user:
    return False
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM bans WHERE target = ? OR target = ?",
        (str(user.id), str(user.username) if user.username else ""),
    )
    return cur.fetchone() is not None


def is_banned_id(user_id: int) -> bool:
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM bans WHERE target = ?", (str(user_id),))
    return cur.fetchone() is not None


def is_admin_or_owner_id(user_id: int) -> bool:
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT username FROM user_data WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row and row["username"] and row["username"].lstrip("@") in ADMIN_USERNAMES:
      return True
    cur.execute("SELECT 1 FROM approved_admins WHERE user_id = ?", (user_id,))
    if cur.fetchone():
      return True
  return False


def is_admin_or_owner(user) -> bool:
  if not user:
    return False
  if user.username and user.username.lstrip("@") in ADMIN_USERNAMES:
    return True
  return is_admin_or_owner_id(user.id)


def is_owner(user) -> bool:
  if not user:
    return False
  if user.username and user.username.lstrip("@") == OWNER_USERNAME:
    return True
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT username FROM user_data WHERE user_id = ?", (user.id,))
    row = cur.fetchone()
    if (
        row
        and row["username"]
        and row["username"].lstrip("@") == OWNER_USERNAME
    ):
      return True
  return False


def get_owner_id() -> int:
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id FROM user_data WHERE username = ? OR username = ?",
        (OWNER_USERNAME, f"@{OWNER_USERNAME}"),
    )
    row = cur.fetchone()
    if row:
      return row["user_id"]
  return 0


def get_admin_chat_ids() -> list:
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM admin_chats")
    return [row["chat_id"] for row in cur.fetchall()]


def register_admin_chat(chat_id: int):
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO admin_chats (chat_id) VALUES (?)", (chat_id,)
    )


def register_user(user_id: int, username: str):
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO user_data (user_id, username, last_ad_time) VALUES (?, ?,"
        " 0) ON CONFLICT(user_id) DO UPDATE SET username = ?",
        (user_id, username or "", username or ""),
    )


def get_user_last_ad_time(user_id: int) -> float:
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT last_ad_time FROM user_data WHERE user_id = ?", (user_id,)
    )
    row = cur.fetchone()
    return row["last_ad_time"] if row and row["last_ad_time"] else 0.0


def set_user_last_ad_time(user_id: int, t: float):
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "UPDATE user_data SET last_ad_time = ? WHERE user_id = ?", (t, user_id)
    )


def is_user_premium(user_id: int) -> bool:
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT expires_at FROM premium_users WHERE user_id = ?", (user_id,)
    )
    row = cur.fetchone()
    if row and row["expires_at"] > time.time():
      return True
  return False


def check_auto_moderation(text: str) -> bool:
  t_lower = text.lower()
  for w in BAD_WORDS:
    if w in t_lower:
      return False
  return True


def get_msk_time():
  return datetime.now(ZoneInfo("Europe/Moscow"))


def set_user_server(user_id: int, server: str):
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO user_data (user_id, server, last_ad_time) VALUES (?, ?,"
        " 0) ON CONFLICT(user_id) DO UPDATE SET server = ?",
        (user_id, server, server),
    )
  update_state(user_id, server=server)


def get_user_server(user_id: int) -> str:
  with state_lock:
    srv = user_states.get(user_id, {}).get("server")
    if srv:
      return srv
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT server FROM user_data WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row and row["server"]:
      srv = row["server"]
      update_state(user_id, server=srv)
      return srv
  default_srv = SERVERS[0]
  update_state(user_id, server=default_srv)
  return default_srv


def get_state(uid: int) -> dict:
  with state_lock:
    st = user_states.get(uid, {}).copy()
  if "server" not in st:
    st["server"] = get_user_server(uid)
  return st


def set_state(uid: int, data: dict):
  with state_lock:
    srv = user_states.get(uid, {}).get("server") or get_user_server(uid)
    user_states[uid] = data
    if srv and "server" not in user_states[uid]:
      user_states[uid]["server"] = srv


def update_state(uid: int, **kwargs):
  with state_lock:
    if uid not in user_states:
      user_states[uid] = {}
    user_states[uid].update(kwargs)


def clear_state(uid: int):
  with state_lock:
    srv = user_states.get(uid, {}).get("server") or get_user_server(uid)
    user_states[uid] = {"server": srv} if srv else {}


# ==========================================
# БЕЗОПАСНАЯ ОТПРАВКА СООБЩЕНИЙ
# ==========================================
def safe_send_message(chat_id, text, parse_mode="HTML", reply_markup=None):
  try:
    return bot.send_message(
        chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup
    )
  except ApiTelegramException as e:
    logger.error(f"Ошибка отправки сообщения: {e}")
    return bot.send_message(
        chat_id, text, parse_mode=None, reply_markup=reply_markup
    )


def safe_send_photo(
    chat_id, photo, caption, parse_mode="HTML", reply_markup=None
):
  try:
    return bot.send_photo(
        chat_id,
        photo,
        caption=caption,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
    )
  except ApiTelegramException as e:
    logger.error(f"Ошибка отправки фото: {e}")
    return bot.send_photo(
        chat_id,
        photo,
        caption=caption,
        parse_mode=None,
        reply_markup=reply_markup,
    )


def send_log_file(
    chat_id, filename, text_content, caption=None, reply_markup=None
):
  file_bytes = io.BytesIO(text_content.encode("utf-8"))
  file_bytes.name = filename
  try:
    bot.send_document(
        chat_id,
        document=file_bytes,
        caption=caption,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )
  except Exception as e:
    logger.error(f"Ошибка отправки файла логов: {e}")
    safe_send_message(chat_id, text_content[:4000], reply_markup=reply_markup)


# ==========================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ И ФОНОВЫХ ЗАДАЧ
# ==========================================
def init_db():
  with db_lock, get_db() as conn:
    cursor = conn.cursor()

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                server TEXT,
                category TEXT,
                text TEXT,
                photo TEXT,
                is_vip INTEGER,
                last_updated REAL,
                edit_count INTEGER DEFAULT 0
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                server TEXT,
                category TEXT,
                text TEXT,
                photo TEXT,
                is_vip INTEGER,
                editing_by INTEGER,
                editing_since REAL
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_buy_ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                server TEXT,
                category TEXT,
                text TEXT,
                photo TEXT,
                is_vip INTEGER,
                last_updated REAL,
                edit_count INTEGER DEFAULT 0
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_buy_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                server TEXT,
                category TEXT,
                text TEXT,
                photo TEXT,
                is_vip INTEGER,
                editing_by INTEGER,
                editing_since REAL
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS barter_ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                server TEXT,
                text TEXT,
                photo TEXT,
                last_updated REAL
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS auctions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                server TEXT,
                item_name TEXT,
                start_price INTEGER,
                current_bid INTEGER,
                highest_bidder INTEGER,
                status TEXT DEFAULT 'active',
                created_at REAL
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS auction_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auction_id INTEGER,
                user_id INTEGER,
                action TEXT,
                timestamp REAL
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS auction_complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auction_id INTEGER,
                owner_id INTEGER,
                target_user_id INTEGER,
                reason TEXT,
                timestamp REAL
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                referrer_id INTEGER,
                referred_id INTEGER,
                qualified_days INTEGER DEFAULT 0,
                last_active_date TEXT,
                ads_today INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                PRIMARY KEY (referrer_id, referred_id)
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_bonuses (
                user_id INTEGER PRIMARY KEY,
                last_claim_date TEXT,
                vip_ads_count INTEGER DEFAULT 0,
                vip_ads_expiry REAL DEFAULT 0
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_logs_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                receiver_id INTEGER,
                text TEXT,
                timestamp REAL
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_action_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_username TEXT,
                action TEXT,
                target TEXT,
                timestamp REAL
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
    cursor.execute(
        "INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('vc_rate',"
        " '95000')"
    )

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS bans (
                target TEXT PRIMARY KEY,
                is_id INTEGER
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS editor_stats (
                username TEXT PRIMARY KEY,
                count INTEGER
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_ad_stats (
                username TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_data (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                last_ad_time REAL,
                server TEXT
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_dialogs (
                buyer_id INTEGER,
                seller_id INTEGER,
                ad_id INTEGER,
                is_active INTEGER,
                PRIMARY KEY (buyer_id, seller_id, ad_id)
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER,
                ad_id INTEGER,
                PRIMARY KEY (user_id, ad_id)
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS keyword_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                server TEXT,
                keyword TEXT
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS premium_users (
                user_id INTEGER PRIMARY KEY,
                expires_at REAL
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_chats (
                chat_id INTEGER PRIMARY KEY
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS approved_admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT
            )
        """)


init_db()


# ==========================================
# ФОНОВЫЙ ПЛАНИЩИК (УДАЛЕНИЕ ОБЪЯВЛЕНИЙ И ЛОГОВ)
# ==========================================
def background_maintenance_worker():
  last_ad_clean_date = ""
  last_log_clean_date = ""
  while True:
    try:
      now = get_msk_time()
      current_time_str = now.strftime("%H:%M:%S")
      current_date_str = now.strftime("%Y-%m-%d")

      if (
          "07:50:00" <= current_time_str <= "07:51:00"
          and last_ad_clean_date != current_date_str
      ):
        with db_lock, get_db() as conn:
          cur = conn.cursor()
          cur.execute("DELETE FROM active_ads")
          cur.execute("DELETE FROM active_buy_ads")
          cur.execute("DELETE FROM barter_ads")
          cur.execute("DELETE FROM auctions WHERE status != 'active'")
        logger.info(
            "Автоматическое удаление старых объявлений в 07:50:00 выполнено."
        )
        last_ad_clean_date = current_date_str

      if (
          "22:30:00" <= current_time_str <= "22:31:00"
          and last_log_clean_date != current_date_str
      ):
        two_days_ago = time.time() - (2 * 86400)
        with db_lock, get_db() as conn:
          cur = conn.cursor()
          cur.execute(
              "DELETE FROM chat_logs_history WHERE timestamp < ?",
              (two_days_ago,),
          )
          cur.execute(
              "DELETE FROM admin_action_logs WHERE timestamp < ?",
              (two_days_ago,),
          )
          cur.execute(
              "DELETE FROM auction_logs WHERE timestamp < ?", (two_days_ago,)
          )
        logger.info("Автоматическая очистка старых логов в 22:30:00 выполнена.")
        last_log_clean_date = current_date_str

    except Exception as e:
      logger.error(f"Ошибка в фоновом планировщике: {e}")
    time.sleep(20)


threading.Thread(target=background_maintenance_worker, daemon=True).start()


# ==========================================
# ОБРАБОТЧИКИ АНТИФЛУДА И БАНОВ
# ==========================================
@bot.message_handler(
    func=lambda m: is_flooding(m.from_user.id), content_types=["text", "photo"]
)
def handle_flood(m):
  try:
    bot.send_message(
        m.chat.id,
        "⚠️ <b>Слишком частые запросы!</b> Пожалуйста, отправляйте сообщения"
        " немного медленнее.",
    )
  except Exception:
    pass


@bot.callback_query_handler(func=lambda c: is_flooding(c.from_user.id))
def handle_flood_callback(c):
  try:
    bot.answer_callback_query(
        c.id, "⚠️ Не так быстро! Подождите пару секунд.", show_alert=False
    )
  except Exception:
    pass


@bot.message_handler(func=lambda m: is_banned(m.from_user))
def blocked_user_message(m):
  safe_send_message(
      m.chat.id,
      "⛔ <b>Вы заблокированы в системе модерации.</b>",
      reply_markup=types.ReplyKeyboardRemove(),
  )


@bot.callback_query_handler(func=lambda c: is_banned(c.from_user))
def blocked_user_callback(c):
  try:
    bot.answer_callback_query(c.id, "⛔ Вы заблокированы!", show_alert=True)
  except Exception:
    pass


# ==========================================
# КЛАВИАТУРЫ
# ==========================================
def kb_servers():
  m = types.ReplyKeyboardMarkup(resize_keyboard=True)
  for i in range(0, len(SERVERS), 2):
    row_buttons = [types.KeyboardButton(s) for s in SERVERS[i : i + 2]]
    m.row(*row_buttons)
  m.row(
      types.KeyboardButton("💎 VIP-статус"),
      types.KeyboardButton("👑 Админ-панель"),
  )
  m.row(types.KeyboardButton("💬 Связаться с менеджером"))
  return m


def kb_main_menu(user_id=None):
  m = types.ReplyKeyboardMarkup(resize_keyboard=True)
  m.row(types.KeyboardButton("🌐 Сменить игровой сервер"))
  m.row(
      types.KeyboardButton("💍 Аксессуары и вещи"),
      types.KeyboardButton("🚗 Транспорт и тюнинг"),
  )
  m.row(
      types.KeyboardButton("👕 Скины и охранники"),
      types.KeyboardButton("🏠 Недвижимость и бизнесы"),
  )
  m.row(types.KeyboardButton("📦 Ресурсы и материалы"))
  m.row(
      types.KeyboardButton("📤 Продать товар"),
      types.KeyboardButton("📥 Скупить товар"),
  )
  m.row(
      types.KeyboardButton("🔄 Бартер / Обмен"),
      types.KeyboardButton("🏛 Аукционы"),
  )
  m.row(types.KeyboardButton("👥 Рефералы и Бонусы"))
  m.row(types.KeyboardButton("💱 Курс VC и калькулятор"))
  m.row(
      types.KeyboardButton("🔍 Найти товар в базе"),
      types.KeyboardButton("🔔 Уведомления о поиске"),
  )
  m.row(
      types.KeyboardButton("❤️ Сохраненные"),
      types.KeyboardButton("📋 Мои публикации"),
  )
  m.row(types.KeyboardButton("📊 Анализ цен на сервере"))
  m.row(
      types.KeyboardButton("💎 VIP-статус"),
      types.KeyboardButton("💬 Связаться с менеджером"),
  )

  if user_id and is_admin_or_owner_id(user_id):
    m.row(types.KeyboardButton("👑 Админ-панель"))

  return m


def kb_cancel():
  return types.ReplyKeyboardMarkup(resize_keyboard=True).add(
      types.KeyboardButton("❌ Отменить действие")
  )


# ==========================================
# ДОБАВЛЕННЫЕ ИСПРАВЛЕННЫЕ ОБРАБОТЧИКИ КНОПОК
# ==========================================
def change_server(m):
  uid = m.from_user.id
  update_state(uid, changing_server=True)
  safe_send_message(
      m.chat.id,
      "🌐 <b>Выберите игровой сервер из списка ниже:</b>",
      reply_markup=kb_servers(),
  )


def select_srv(m):
  uid = m.from_user.id
  srv = m.text.strip()
  if srv not in SERVERS:
    return
  set_user_server(uid, srv)
  clear_state(uid)
  safe_send_message(
      m.chat.id,
      f"✅ Игровой сервер успешно изменен на: <b>{html.escape(srv)}</b>",
      reply_markup=kb_main_menu(uid),
  )


def admin_panel(m):
  uid = m.from_user.id
  if not is_admin_or_owner_id(uid):
    return safe_send_message(m.chat.id, "⛔ Доступ запрещен.")

  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  if is_owner(m.from_user):
    markup.row(
        types.KeyboardButton("модерация продажи"),
        types.KeyboardButton("модерация скупки"),
    )
    markup.row(
        types.KeyboardButton("рассылка"), types.KeyboardButton("📋 Логи чатов")
    )
    markup.row(
        types.KeyboardButton("🔨 Забанить игрока"),
        types.KeyboardButton("🔓 Разбанить игрока"),
    )
    markup.row(
        types.KeyboardButton("👑 Добавить адм"),
        types.KeyboardButton("🚫 Снять с адм"),
    )
  else:
    markup.row(
        types.KeyboardButton("модерация продажи"),
        types.KeyboardButton("модерация скупки"),
    )
  markup.row(types.KeyboardButton("❌ Отменить действие"))

  safe_send_message(
      m.chat.id,
      "👑 <b>Панель управления администратора:</b>",
      reply_markup=markup,
  )


def cancel_action(m):
  uid = m.from_user.id
  clear_state(uid)
  safe_send_message(
      m.chat.id, "❌ Действие отменено.", reply_markup=kb_main_menu(uid)
  )


# ==========================================
# ИНТЕГРИРОВАННЫЕ ФУНКЦИИ ИЗ ВАШЕГО СКРИПТА
# ==========================================
def show_average_prices(m):
  uid = m.from_user.id
  srv = get_user_server(uid)
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT category, COUNT(*) as cnt FROM active_ads WHERE server = ? GROUP"
        " BY category",
        (srv,),
    )
    rows = cur.fetchall()

  text = (
      f"📊 <b>Анализ цен на сервере {html.escape(srv)}</b>\n\nСтатистика"
      " активных объявлений по категориям:\n"
  )
  if rows:
    for r in rows:
      text += f"▪️ {html.escape(r['category'])}: <b>{r['cnt']}</b> объявлений\n"
  else:
    text += "Пока нет данных для анализа цен."

  safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(uid))


def contact_manager(m):
  uid = m.from_user.id
  text = (
      f"💬 <b>Связь с менеджером</b>\n\nПо всем вопросам сотрудничества и"
      f" поддержки вы можете обратиться к менеджеру проекта:"
      f" <b>@{MANAGER_USERNAME}</b>"
  )
  safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(uid))


# ==========================================
# ИСПРАВЛЕННЫЙ МОДУЛЬ 1: КУРС VC И КАЛЬКУЛЯТОР
# ==========================================
def get_vc_rate() -> int:
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT value FROM bot_settings WHERE key = 'vc_rate'")
    row = cur.fetchone()
    if row:
      try:
        return int(row["value"])
      except ValueError:
        return 95000
  return 95000


def set_vc_rate(rate: int):
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('vc_rate',"
        " ?)",
        (str(rate),),
    )


def show_vc_menu(m):
  uid = m.from_user.id
  rate = get_vc_rate()
  text = (
      f"💱 <b>Курс VC и калькулятор</b>\n\n"
      f"📈 Текущий курс обмена на сервере: <b>1 VC = {rate:,.0f} $</b>\n\n"
      f"Используйте кнопки ниже для пересчета валюты или изменения курса:"
  )
  markup = types.InlineKeyboardMarkup(row_width=1)
  markup.add(
      types.InlineKeyboardButton(
          "🧮 Перевести VC в доллары ($)", callback_data="vc_conv_to_usd"
      ),
      types.InlineKeyboardButton(
          "🧮 Перевести доллары ($) в VC", callback_data="vc_conv_to_vc"
      ),
  )
  if is_admin_or_owner(m.from_user):
    markup.add(
        types.InlineKeyboardButton(
            "⚙️ Изменить курс VC", callback_data="vc_change_rate"
        )
    )
  safe_send_message(m.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(
    func=lambda c: c.data in ["vc_conv_to_usd", "vc_conv_to_vc", "vc_change_rate"]
)
def cb_vc_actions(call):
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass
  uid = call.from_user.id
  data = call.data

  if data == "vc_conv_to_usd":
    update_state(uid, vc_calc_mode="to_usd")
    safe_send_message(
        call.message.chat.id,
        "🧮 Введите количество <b>VC-коинов</b> (например: <code>150</code>,"
        " <code>1.5к</code>, <code>10к</code>):",
        reply_markup=kb_cancel(),
    )
  elif data == "vc_conv_to_vc":
    update_state(uid, vc_calc_mode="to_vc")
    safe_send_message(
        call.message.chat.id,
        "🧮 Введите сумму в <b>долларах ($)</b> (например: <code>15кк</code>,"
        " <code>1000000</code>, <code>1.5кк</code>):",
        reply_markup=kb_cancel(),
    )
  elif data == "vc_change_rate":
    if not is_admin_or_owner(call.from_user):
      return safe_send_message(
          call.message.chat.id, "⛔ Доступ запрещен."
      )
    update_state(uid, vc_setting_rate=True)
    rate = get_vc_rate()
    safe_send_message(
        call.message.chat.id,
        f"⚙️ Текущий курс: <b>1 VC = {rate} $</b>\n\nВведите новый курс (целое"
        " число в долларах, например: <code>97000</code>):",
        reply_markup=kb_cancel(),
    )


@bot.message_handler(
    func=lambda m: get_state(m.from_user.id).get("vc_calc_mode") is not None
    or get_state(m.from_user.id).get("vc_setting_rate") is True
)
def process_vc_input(m):
  uid = m.from_user.id
  st = get_state(uid)
  clear_state(uid)
  rate = get_vc_rate()

  if st.get("vc_setting_rate"):
    if not is_admin_or_owner(m.from_user):
      return safe_send_message(m.chat.id, "⛔ Доступ запрещен.")
    try:
      new_rate = parse_flexible_price(m.text)
      if new_rate <= 0:
        raise ValueError
    except ValueError:
      return safe_send_message(
          m.chat.id,
          "⚠️ Введите корректное число для курса (например: 95000, 100к).",
          reply_markup=kb_main_menu(uid),
      )
    set_vc_rate(new_rate)
    return safe_send_message(
        m.chat.id,
        f"✅ Курс VC успешно обновлен! Новый курс: <b>1 VC = {new_rate:,.0f}"
        " $</b>",
        reply_markup=kb_main_menu(uid),
    )

  mode = st.get("vc_calc_mode")
  try:
    val = parse_flexible_price(m.text)
  except ValueError:
    return safe_send_message(
        m.chat.id,
        "⚠️ Не удалось распознать сумму. Введите число (например: 100, 1.5кк,"
        " 50к).",
        reply_markup=kb_main_menu(uid),
    )

  if mode == "to_usd":
    result = val * rate
    text = (
        f"🧮 <b>Результат расчета:</b>\n\n💎 {val:,.0f} VC = <b>{result:,.0f}"
        f" $</b>\n<i>(Текущий курс: 1 VC = {rate:,.0f} $)</i>"
    )
  else:
    if rate == 0:
      return safe_send_message(m.chat.id, "⚠️ Ошибка: курс равен 0.")
    result = val / rate
    text = (
        f"🧮 <b>Результат расчета:</b>\n\n💵 {val:,.0f} $ = <b>{result:,.2f}"
        f" VC</b>\n<i>(Текущий курс: 1 VC = {rate:,.0f} $)</i>"
    )

  safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(uid))


def show_my_ads(m):
  uid = m.from_user.id
  srv = get_user_server(uid)
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM active_ads WHERE user_id = ? AND server = ?", (uid, srv)
    )
    ads = cur.fetchall()
    cur.execute(
        "SELECT * FROM active_buy_ads WHERE user_id = ? AND server = ?",
        (uid, srv),
    )
    buy_ads = cur.fetchall()

  text = f"📋 <b>Ваши активные публикации на сервере {html.escape(srv)}:</b>\n\n"
  if not ads and not buy_ads:
    text += "У вас нет активных объявлений."
  else:
    for a in ads:
      text += (
          f"▪️ <b>Продажа (#{a['id']}):</b>"
          f" {html.escape(a['text'][:50])}...\n"
      )
    for a in buy_ads:
      text += (
          f"▪️ <b>Скупка (#{a['id']}):</b>"
          f" {html.escape(a['text'][:50])}...\n"
      )
  safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(m.from_user.id))


def show_favorites(m):
  safe_send_message(
      m.chat.id,
      "❤️ <b>Сохраненные объявления:</b>\n\nСписок сохраненных избранных"
      " товаров пуст.",
      reply_markup=kb_main_menu(m.from_user.id),
  )


def start_search(m):
  safe_send_message(
      m.chat.id,
      "🔍 <b>Поиск товара в базе:</b>\n\nВведите ключевое слово или название"
      " предмета для поиска:",
      reply_markup=kb_cancel(),
  )
  update_state(m.from_user.id, searching_keyword=True)


def manage_subscriptions(m):
  safe_send_message(
      m.chat.id,
      "🔔 <b>Уведомления о поиске:</b>\n\nУ вас нет активных подписок на"
      " ключевые слова.",
      reply_markup=kb_main_menu(m.from_user.id),
  )


def show_category_ads(m):
  cat = m.text
  uid = m.from_user.id
  srv = get_user_server(uid)
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM active_ads WHERE server = ? AND category = ? ORDER BY id"
        " DESC LIMIT 5",
        (srv, cat),
    )
    ads = cur.fetchall()

  text = (
      f"📦 Категория: <b>{html.escape(cat)}</b>\n🌐 Сервер:"
      f" <b>{html.escape(srv)}</b>\n\n"
  )
  if not ads:
    text += "В этой категории пока нет объявлений о продаже."
    safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(m.from_user.id))
  else:
    safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(m.from_user.id))
    for a in ads:
      aid = a["id"]
      markup = types.InlineKeyboardMarkup()
      markup.add(
          types.InlineKeyboardButton(
              "✉️ Связаться с продавцом", callback_data=f"contact_seller_{aid}"
          )
      )
      cap = f"🏷 <b>Объявление продажи #{aid}</b>\n\n{html.escape(a['text'])}"
      if a["photo"]:
        safe_send_photo(m.chat.id, a["photo"], caption=cap, reply_markup=markup)
      else:
        safe_send_message(m.chat.id, cap, reply_markup=markup)


# ==========================================
# ПЕРЕХВАТЧИК НАВИГАЦИИ И ОТМЕНЫ
# ==========================================
def should_override_nav(msg):
  if not msg.text:
    return False
  if msg.text == "❌ Отменить действие":
    return True

  uid = msg.from_user.id
  st = get_state(uid)

  is_in_active_input = (
      st.get("posting_ad", {}).get("step")
      in ["category", "text_or_photo", "choose_ad_type"]
      or st.get("searching_keyword")
      or st.get("adding_subscription")
      or st.get("vc_setting_rate")
      or st.get("vc_conv_input")
      or st.get("vc_calc_mode")
      or st.get("barter_input")
      or st.get("auction_create_step")
      or st.get("auction_bid_input")
      or st.get("auction_complaint_step")
      or st.get("owner_action_input")
      or st.get("ref_link_input")
      or st.get("chat_with_seller_id")
      or st.get("broadcast_input")
  )

  nav_buttons = [
      "🔍 Найти товар в базе",
      "❤️ Сохраненные",
      "🔔 Уведомления о поиске",
      "📋 Мои публикации",
      "📊 Анализ цен на сервере",
      "📤 Продать товар",
      "📥 Скупить товар",
      "💱 Курс VC и калькулятор",
      "💎 VIP-статус",
      "🌐 Сменить игровой сервер",
      "👑 Админ-панель",
      "💬 Связаться с менеджером",
      "🔄 Бартер / Обмен",
      "🏛 Аукционы",
      "👥 Рефералы и Бонусы",
      "🔨 Забанить игрока",
      "🔓 Разбанить игрока",
      "👑 Добавить адм",
      "🚫 Снять с адм",
      "📋 Логи чатов",
      "модерация продажи",
      "модерация скупки",
      "рассылка",
  ] + CATEGORIES

  if is_in_active_input:
    return False

  return msg.text in nav_buttons or msg.text in SERVERS


@bot.message_handler(func=should_override_nav)
def handle_navigation_override(m):
  if m.text != "❌ Отменить действие":
    clear_state(m.from_user.id)

  if m.text == "🌐 Сменить игровой сервер":
    change_server(m)
  elif m.text == "💎 VIP-статус":
    info_premium(m) if "info_premium" in globals() else show_vc_menu(m)
  elif m.text == "📊 Анализ цен на сервере":
    show_average_prices(m)
  elif m.text == "📤 Продать товар":
    start_add_ad(m)
  elif m.text == "📥 Скупить товар":
    start_add_buy_ad(m)
  elif m.text == "💱 Курс VC и калькулятор":
    show_vc_menu(m)
  elif m.text == "❌ Отменить действие":
    cancel_action(m)
  elif m.text == "📋 Мои публикации":
    show_my_ads(m)
  elif m.text == "❤️ Сохраненные":
    show_favorites(m)
  elif m.text == "🔍 Найти товар в базе":
    start_search(m)
  elif m.text == "🔔 Уведомления о поиске":
    manage_subscriptions(m)
  elif m.text == "👑 Админ-панель":
    admin_panel(m)
  elif m.text == "💬 Связаться с менеджером":
    contact_manager(m)
  elif m.text == "🔄 Бартер / Обмен":
    show_barter_menu(m)
  elif m.text == "🏛 Аукционы":
    show_auctions_menu(m)
  elif m.text == "👥 Рефералы и Бонусы":
    show_ref_bonus_menu(m)
  elif m.text == "📋 Логи чатов":
    show_owner_logs_menu(m)
  elif m.text == "модерация продажи":
    show_pending_sales(m)
  elif m.text == "модерация скупки":
    show_pending_buys(m)
  elif m.text == "рассылка":
    start_broadcast(m)
  elif m.text == "🔨 Забанить игрока":
    owner_prompt_action(m, "ban")
  elif m.text == "🔓 Разбанить игрока":
    owner_prompt_action(m, "unban")
  elif m.text == "👑 Добавить адм":
    owner_prompt_action(m, "add_admin")
  elif m.text == "🚫 Снять с адм":
    owner_prompt_action(m, "remove_admin")
  elif m.text in CATEGORIES:
    show_category_ads(m)
  elif m.text in SERVERS:
    select_srv(m)


# ==========================================
# МОДУЛЬ МОДЕРАЦИИ И РАССЫЛКИ
# ==========================================
def show_pending_sales(m):
  if not is_admin_or_owner(m.from_user):
    return safe_send_message(m.chat.id, "⛔ Доступ запрещен.")
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT * FROM pending_posts LIMIT 10")
    posts = cur.fetchall()

  if not posts:
    return safe_send_message(
        m.chat.id, "📭 На данный момент нет объявлений о продаже на модерации."
    )

  safe_send_message(
      m.chat.id, f"📋 <b>Очередь модерации продаж (найдено: {len(posts)}):</b>"
  )
  for p in posts:
    pid = p["id"]
    text = p["text"]
    srv = p["server"]
    photo = p["photo"]
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(
            "✅ Одобрить", callback_data=f"mod_acc_{pid}"
        ),
        types.InlineKeyboardButton(
            "❌ Отклонить", callback_data=f"mod_rej_{pid}"
        ),
    )
    caption = f"📋 <b>Пост продажи #{pid}</b>\n🌐 Сервер: {srv}\n\n{text}"
    if photo:
      safe_send_photo(m.chat.id, photo, caption=caption, reply_markup=markup)
    else:
      safe_send_message(m.chat.id, caption, reply_markup=markup)


def show_pending_buys(m):
  if not is_admin_or_owner(m.from_user):
    return safe_send_message(m.chat.id, "⛔ Доступ запрещен.")
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT * FROM pending_buy_posts LIMIT 10")
    posts = cur.fetchall()

  if not posts:
    return safe_send_message(
        m.chat.id, "📭 На данный момент нет объявлений о скупке на модерации."
    )

  safe_send_message(
      m.chat.id, f"📋 <b>Очередь модерации скупки (найдено: {len(posts)}):</b>"
  )
  for p in posts:
    pid = p["id"]
    text = p["text"]
    srv = p["server"]
    photo = p["photo"]
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(
            "✅ Одобрить", callback_data=f"mod_acc_buy_{pid}"
        ),
        types.InlineKeyboardButton(
            "❌ Отклонить", callback_data=f"mod_rej_buy_{pid}"
        ),
    )
    caption = f"📋 <b>Пост скупки #{pid}</b>\n🌐 Сервер: {srv}\n\n{text}"
    if photo:
      safe_send_photo(m.chat.id, photo, caption=caption, reply_markup=markup)
    else:
      safe_send_message(m.chat.id, caption, reply_markup=markup)


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("mod_acc_")
    or c.data.startswith("mod_rej_")
    or c.data.startswith("mod_acc_buy_")
    or c.data.startswith("mod_rej_buy_")
)
def cb_moderate_post(call):
  if not is_admin_or_owner(call.from_user):
    try:
      return bot.answer_callback_query(
          call.id, "⛔ Нет прав администратора!", show_alert=True
      )
    except Exception:
      return

  data = call.data
  parts = data.split("_")
  is_buy_mod = "buy" in data
  action = parts[1]
  pid = int(parts[-1])

  table = "pending_buy_posts" if is_buy_mod else "pending_posts"
  target_active_table = "active_buy_ads" if is_buy_mod else "active_ads"

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table} WHERE id = ?", (pid,))
    post = cur.fetchone()

  if not post:
    try:
      bot.answer_callback_query(
          call.id,
          "⚠️ Объявление уже обработано или не найдено.",
          show_alert=True,
      )
      bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
      pass
    return

  admin_uname = call.from_user.username or str(call.from_user.id)

  if action == "acc":
    with db_lock, get_db() as conn:
      cur = conn.cursor()
      cur.execute(
          f"INSERT INTO {target_active_table} (user_id, server, category,"
          " text, photo, is_vip, last_updated) VALUES (?, ?, ?, ?, ?, ?, ?)",
          (
              post["user_id"],
              post["server"],
              post["category"],
              post["text"],
              post["photo"],
              post["is_vip"],
              time.time(),
          ),
      )
      cur.execute(f"DELETE FROM {table} WHERE id = ?", (pid,))
      cur.execute(
          "INSERT INTO editor_stats (username, count) VALUES (?, 1) ON"
          " CONFLICT(username) DO UPDATE SET count = count + 1",
          (admin_uname,),
      )
      cur.execute(
          "INSERT INTO admin_action_logs (admin_username, action, target,"
          " timestamp) VALUES (?, ?, ?, ?)",
          (
              admin_uname,
              "Одобрение объявления",
              f"Пост #{pid} ({post['server']})",
              time.time(),
          ),
      )

    try:
      bot.answer_callback_query(call.id, "✅ Объявление одобрено и опубликовано!")
      bot.edit_message_caption(
          f"✅ <b>Одобрено администратором @{html.escape(admin_uname)}</b>\n\n{post['text']}",
          call.message.chat.id,
          call.message.message_id,
          reply_markup=None,
      )
    except Exception:
      with contextlib.suppress(Exception):
        bot.edit_message_text(
            f"✅ <b>Одобрено администратором @{html.escape(admin_uname)}</b>\n\n{post['text']}",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=None,
        )

    with contextlib.suppress(Exception):
      safe_send_message(
          post["user_id"],
          f"✅ Ваше объявление (ID #{pid}) было успешно одобрено модератором и"
          " опубликовано!",
      )

  else:
    with db_lock, get_db() as conn:
      cur = conn.cursor()
      cur.execute(f"DELETE FROM {table} WHERE id = ?", (pid,))
      cur.execute(
          "INSERT INTO admin_action_logs (admin_username, action, target,"
          " timestamp) VALUES (?, ?, ?, ?)",
          (
              admin_uname,
              "Отклонение объявления",
              f"Пост #{pid} ({post['server']})",
              time.time(),
          ),
      )

    try:
      bot.answer_callback_query(call.id, "❌ Объявление отклонено.")
      bot.edit_message_caption(
          f"❌ <b>Отклонено администратором @{html.escape(admin_uname)}</b>\n\n{post['text']}",
          call.message.chat.id,
          call.message.message_id,
          reply_markup=None,
      )
    except Exception:
      with contextlib.suppress(Exception):
        bot.edit_message_text(
            f"❌ <b>Отклонено администратором @{html.escape(admin_uname)}</b>\n\n{post['text']}",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=None,
        )

    with contextlib.suppress(Exception):
      safe_send_message(
          post["user_id"],
          f"❌ Ваше объявление (ID #{pid}) было отклонено модератором.",
      )


def start_broadcast(m):
  if not is_owner(m.from_user):
    return safe_send_message(
        m.chat.id,
        f"⛔ Эта функция доступна только владельцу (@{OWNER_USERNAME}).",
    )
  update_state(m.from_user.id, broadcast_input=True)
  safe_send_message(
      m.chat.id,
      "📢 Введите текст или отправьте пост (с фото/медиа) для рассылки всем"
      " пользователям бота:",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    content_types=["text", "photo"],
    func=lambda m: get_state(m.from_user.id).get("broadcast_input") is True,
)
def process_broadcast(m):
  uid = m.from_user.id
  clear_state(uid)
  if not is_owner(m.from_user):
    return safe_send_message(m.chat.id, "⛔ Доступ запрещен.")

  text = m.text or m.caption
  photo = m.photo[-1].file_id if m.photo else None

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM user_data")
    users = [row["user_id"] for row in cur.fetchall()]

  safe_send_message(
      m.chat.id, f"🚀 Начинаю рассылку для {len(users)} пользователей..."
  )

  success = 0
  failed = 0
  for u_id in users:
    try:
      if photo:
        bot.send_photo(u_id, photo, caption=text, parse_mode="HTML")
      else:
        bot.send_message(u_id, text, parse_mode="HTML")
      success += 1
      time.sleep(0.04)
    except Exception:
      failed += 1

  safe_send_message(
      m.chat.id,
      f"✅ <b>Рассылка завершена!</b>\n\n📤 Успешно доставлено:"
      f" {success}\n❌ Ошибок / заблокировали бота: {failed}",
      reply_markup=kb_main_menu(uid),
  )


# ==========================================
# МОДУЛЬ УПРАВЛЕНИЯ ВЛАДЕЛЬЦА И АДМИН-ПАНЕЛИ
# (ИСПРАВЛЕНО: ДОБАВЛЕНО ПОДТВЕРЖДЕНИЕ КНОПКАМИ)
# ==========================================
def owner_prompt_action(m, action_type):
  if not is_owner(m.from_user):
    return safe_send_message(
        m.chat.id,
        f"⛔ Эта кнопка доступна только владельцу (@{OWNER_USERNAME}).",
    )

  prompts = {
      "ban": "🔨 Введите User ID или @username игрока для блокировки:",
      "unban": "🔓 Введите User ID или @username игрока для разблокировки:",
      "add_admin": (
          "👑 Введите User ID или @username пользователя для назначения"
          " администратором:"
      ),
      "remove_admin": (
          "🚫 Введите User ID или @username администратора для снятия с"
          " должности:"
      ),
  }
  update_state(m.from_user.id, owner_action_input=action_type)
  safe_send_message(m.chat.id, prompts[action_type], reply_markup=kb_cancel())


@bot.message_handler(
    func=lambda m: get_state(m.from_user.id).get("owner_action_input")
    is not None
)
def process_owner_action_input(m):
  uid = m.from_user.id
  st = get_state(uid)
  action_type = st.get("owner_action_input")
  target_str = m.text.strip()

  if target_str == "❌ Отменить действие":
    clear_state(uid)
    return cancel_action(m)

  if not is_owner(m.from_user):
    clear_state(uid)
    return safe_send_message(m.chat.id, "⛔ Доступ запрещен.")

  update_state(
      uid,
      owner_action_target=target_str,
      owner_action_input=None,
      owner_action_confirm=action_type,
  )

  action_names = {
      "ban": "блокировку игрока",
      "unban": "разблокировку игрока",
      "add_admin": "назначение администратором",
      "remove_admin": "снятие с должности администратора",
  }

  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton(
          "✅ Подтвердить", callback_data=f"owner_conf_{action_type}"
      ),
      types.InlineKeyboardButton("❌ Отмена", callback_data="owner_conf_cancel"),
  )

  safe_send_message(
      m.chat.id,
      f"⚠️ <b>Подтверждение действия:</b>\n\nДействие:"
      f" <b>{action_names.get(action_type, action_type)}</b>\nЦель:"
      f" <b>{html.escape(target_str)}</b>\n\nПодтвердите выполнение:",
      reply_markup=markup,
  )


@bot.callback_query_handler(func=lambda c: c.data.startswith("owner_conf_"))
def cb_owner_confirmation(call):
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass

  uid = call.from_user.id
  st = get_state(uid)
  action_type = call.data.replace("owner_conf_", "")

  if action_type == "cancel":
    clear_state(uid)
    try:
      bot.edit_message_text(
          "❌ Действие отменено.", call.message.chat.id, call.message.message_id
      )
    except Exception:
      pass
    return admin_panel(call.message)

  target_str = st.get("owner_action_target")
  clear_state(uid)

  if not target_str or not is_owner(call.from_user):
    try:
      bot.edit_message_text(
          "⛔ Ошибка или истекло время сессии.",
          call.message.chat.id,
          call.message.message_id,
      )
    except Exception:
      pass
    return admin_panel(call.message)

  admin_uname = call.from_user.username or str(uid)

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    target_uid = None
    target_uname = target_str.lstrip("@")

    if target_str.isdigit():
      target_uid = int(target_str)
      cur.execute(
          "SELECT username FROM user_data WHERE user_id = ?", (target_uid,)
      )
      row = cur.fetchone()
      if row and row["username"]:
        target_uname = row["username"].lstrip("@")
    else:
      cur.execute(
          "SELECT user_id FROM user_data WHERE username = ? OR username = ?",
          (target_str, f"@{target_str}"),
      )
      row = cur.fetchone()
      if row:
        target_uid = row["user_id"]

    if action_type == "ban":
      b_target = str(target_uid) if target_uid else target_str
      cur.execute(
          "INSERT OR REPLACE INTO bans (target, is_id) VALUES (?, ?)",
          (b_target, 1 if target_uid else 0),
      )
      if target_uname:
        cur.execute(
            "INSERT OR REPLACE INTO bans (target, is_id) VALUES (?, ?)",
            (target_uname, 0),
        )

      cur.execute(
          "INSERT INTO admin_action_logs (admin_username, action, target,"
          " timestamp) VALUES (?, ?, ?, ?)",
          (
              admin_uname,
              "Выдача бана",
              f"Игрок: {target_str} (ID: {target_uid})",
              time.time(),
          ),
      )
      res_text = (
          f"✅ Игрок <b>{html.escape(target_str)}</b> успешно заблокирован."
      )
      with contextlib.suppress(Exception):
        if target_uid:
          safe_send_message(
              target_uid, "⛔ Вы были заблокированы администрацией."
          )

    elif action_type == "unban":
      b_target = str(target_uid) if target_uid else target_str
      cur.execute(
          "DELETE FROM bans WHERE target = ? OR target = ?",
          (b_target, target_uname),
      )
      cur.execute(
          "INSERT INTO admin_action_logs (admin_username, action, target,"
          " timestamp) VALUES (?, ?, ?, ?)",
          (
              admin_uname,
              "Снятие бана",
              f"Игрок: {target_str} (ID: {target_uid})",
              time.time(),
          ),
      )
      res_text = f"✅ Игрок <b>{html.escape(target_str)}</b> разблокирован."

    elif action_type == "add_admin":
      if not target_uid:
        res_text = (
            f"⚠️ Пользователь {target_str} не найден в базе данных бота. Пусть"
            " он сначала запустит бота (/start)."
        )
      else:
        cur.execute(
            "INSERT OR REPLACE INTO approved_admins (user_id, username) VALUES"
            " (?, ?)",
            (target_uid, target_uname),
        )
        cur.execute(
            "INSERT INTO admin_action_logs (admin_username, action, target,"
            " timestamp) VALUES (?, ?, ?, ?)",
            (
                admin_uname,
                "Назначение админа",
                f"@{target_uname} (ID: {target_uid})",
                time.time(),
            ),
        )
        res_text = (
            f"👑 Пользователь @{target_uname} (ID: {target_uid}) назначен"
            " администратором!"
        )
        with contextlib.suppress(Exception):
          safe_send_message(
              target_uid,
              "👑 Поздравляем! Вам назначены права администратора в боте.",
          )

    elif action_type == "remove_admin":
      if target_uid:
        cur.execute(
            "DELETE FROM approved_admins WHERE user_id = ?", (target_uid,)
        )
      if target_uname:
        cur.execute(
            "DELETE FROM approved_admins WHERE username = ?", (target_uname,)
        )
      cur.execute(
          "INSERT INTO admin_action_logs (admin_username, action, target,"
          " timestamp) VALUES (?, ?, ?, ?)",
          (
              admin_uname,
              "Снятие с адм",
              f"@{target_uname} (ID: {target_uid})",
              time.time(),
          ),
      )
      res_text = (
          f"🚫 Администратор <b>{html.escape(target_str)}</b> снят с должности."
      )
      with contextlib.suppress(Exception):
        if target_uid:
          safe_send_message(
              target_uid,
              "🚫 Вы были сняты с должности администратора.",
          )
    else:
      res_text = "✅ Действие выполнено."

  try:
    bot.edit_message_text(res_text, call.message.chat.id, call.message.message_id)
  except Exception:
    safe_send_message(call.message.chat.id, res_text)

  admin_panel(call.message)


# ==========================================
# УНИФИЦИРОВАННОЕ МЕНЮ ЛОГОВ
# ==========================================
def show_owner_logs_menu(m):
  if not is_owner(m.from_user) and not is_admin_or_owner_id(m.from_user.id):
    return safe_send_message(
        m.chat.id,
        f"⛔ Этот раздел доступен только владельцу (@{OWNER_USERNAME}).",
    )

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT * FROM auctions ORDER BY id DESC LIMIT 5")
    auctions = cur.fetchall()

  text = (
      f"📋 <b>Единый центр логов системы (@{OWNER_USERNAME})</b>\n\nВсе"
      " необходимые логи разделены по категориям ниже. Выберите нужный пункт"
      " для выгрузки файлов:"
  )
  safe_send_message(m.chat.id, text)

  markup = types.InlineKeyboardMarkup(row_width=1)
  for a in auctions:
    markup.add(
        types.InlineKeyboardButton(
            f"🏛 Логи аукциона #{a['id']} ({a['item_name']})",
            callback_data=f"owner_view_auc_{a['id']}",
        )
    )

  markup.add(
      types.InlineKeyboardButton(
          "💬 Логи всех чатов/общения (файлом)",
          callback_data="owner_view_chats",
      )
  )
  markup.add(
      types.InlineKeyboardButton(
          "📢 Логи действий, банов и объявлений админов (файлом)",
          callback_data="owner_view_admin_ads",
      )
  )

  safe_send_message(
      m.chat.id, "Доступные разделы логов:", reply_markup=markup
  )


@bot.callback_query_handler(func=lambda c: c.data.startswith("owner_view_auc_"))
def cb_owner_view_auc(call):
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass
  aid = int(call.data.replace("owner_view_auc_", ""))

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT * FROM auctions WHERE id = ?", (aid,))
    auc = cur.fetchone()
    if not auc:
      return safe_send_message(call.message.chat.id, "⚠️ Аукцион не найден.")
    cur.execute(
        "SELECT * FROM auction_logs WHERE auction_id = ? ORDER BY timestamp ASC",
        (aid,),
    )
    logs = cur.fetchall()

  log_text = (
      f"ЛОГИ АУКЦИОНА #{aid}\nТовар: {auc['item_name']}\nСтатус:"
      f" {auc['status']}\n"
      + "=" * 40
      + "\n\n"
  )
  if logs:
    for l in logs:
      dt = datetime.fromtimestamp(l["timestamp"]).strftime("%d.%m %H:%M:%S")
      log_text += f"[{dt}] [User ID {l['user_id']}]: {l['action']}\n"
  else:
    log_text += "Логи аукциона пусты."

  caption = f"📁 <b>Файл с логами аукциона #{aid}</b>\nТовар: <b>{html.escape(auc['item_name'])}</b>"
  send_log_file(
      call.message.chat.id, f"auction_{aid}_logs.txt", log_text, caption=caption
  )


@bot.callback_query_handler(func=lambda c: c.data == "owner_view_chats")
def cb_owner_view_chats(call):
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT * FROM chat_logs_history ORDER BY id DESC LIMIT 100")
    chats = cur.fetchall()

  log_text = (
      f"ИСТОРИЯ ОБЩЕНИЯ ИГРОКОВ В СДЕЛКАХ (Последние 100 сообщений)\n"
      + "=" * 50
      + "\n\n"
  )
  if chats:
    for c_row in chats:
      dt = datetime.fromtimestamp(c_row["timestamp"]).strftime("%d.%m %H:%M:%S")
      log_text += (
          f"[{dt}] (От ID {c_row['sender_id']} -> К ID"
          f" {c_row['receiver_id']}): {c_row['text']}\n"
      )
  else:
    log_text += "История общения пуста."

  send_log_file(
      call.message.chat.id,
      "chat_history_logs.txt",
      log_text,
      caption="📁 <b>Файл истории переписок игроков в сделках</b>",
  )


def cb_owner_view_admin_ads_msg(m):
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT * FROM admin_action_logs ORDER BY id DESC LIMIT 100")
    logs = cur.fetchall()

  log_text = (
      f"ЛОГИ ДЕЙСТВИЙ, БАНОВ И АДМИНИСТРИРОВАНИЯ\n" + "=" * 50 + "\n\n"
  )
  if logs:
    for l in logs:
      dt = datetime.fromtimestamp(l["timestamp"]).strftime("%d.%m %H:%M:%S")
      log_text += (
          f"[{dt}] Администратор (@{l['admin_username']}): Действие:"
          f" {l['action']} | Цель: {l['target']}\n"
      )
  else:
    log_text += "Логи действий администрации пустые."

  send_log_file(
      m.chat.id,
      "admin_actions_logs.txt",
      log_text,
      caption=(
          "📁 <b>Файл логов банов, разбанов, админок и модерации</b>"
      ),
  )


@bot.callback_query_handler(func=lambda c: c.data == "owner_view_admin_ads")
def cb_owner_view_admin_ads(call):
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass
  cb_owner_view_admin_ads_msg(call.message)


# ==========================================
# МОДУЛЬ 1: РАЗДЕЛ «БАРТЕР / ОБМЕН»
# ==========================================
def show_barter_menu(m):
  uid = m.from_user.id
  srv = get_user_server(uid)
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM barter_ads WHERE server = ? ORDER BY id DESC LIMIT 10",
        (srv,),
    )
    barters = cur.fetchall()

  text = f"🔄 <b>Раздел «Бартер / Обмен»</b>\n🌐 Сервер: <b>{html.escape(srv)}</b>\n\n"
  if barters:
    text += "Актуальные предложения обмена:\n"
  else:
    text += "В этом разделе пока нет предложений обмена.\n"

  safe_send_message(m.chat.id, text)

  for b in barters:
    bid = b["id"]
    b_text = b["text"]
    photo = b["photo"]
    fmt = f"🔄 <b>Обмен #{bid}</b>\n{html.escape(b_text)}"
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "✉️ Предложить обмен", callback_data=f"contact_seller_{bid}"
        )
    )
    if photo:
      safe_send_photo(m.chat.id, photo, caption=fmt, reply_markup=markup)
    else:
      safe_send_message(m.chat.id, fmt, reply_markup=markup)

  markup_btn = types.InlineKeyboardMarkup()
  markup_btn.add(
      types.InlineKeyboardButton(
          "➕ Выставить предложение на обмен", callback_data="barter_add_start"
      )
  )
  safe_send_message(
      m.chat.id,
      "Хотите предложить свой товар/имущество на обмен?",
      reply_markup=markup_btn,
  )


@bot.callback_query_handler(func=lambda c: c.data == "barter_add_start")
def cb_barter_add_start(call):
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass

  warning_text = (
      "⚠️ <b>Внимание! Уведомление безопасности:</b>\nАдминистрация бота <b>не"
      " несет никакой ответственности</b> за проведение сделок, обмена"
      " имущества или возможные договоренности между игроками. Вы совершаете"
      " все операции исключительно на свой страх и риск!"
  )
  safe_send_message(call.message.chat.id, warning_text)

  update_state(call.from_user.id, barter_input=True)
  safe_send_message(
      call.message.chat.id,
      "🔄 Опишите, что вы отдаете и что хотите получить взамен (можно"
      " прикрепить фото):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    content_types=["text", "photo"],
    func=lambda m: get_state(m.from_user.id).get("barter_input"),
)
def process_barter_create(m):
  uid = m.from_user.id
  srv = get_user_server(uid)
  text = m.text or m.caption
  photo = m.photo[-1].file_id if m.photo else None
  clear_state(uid)

  if not text:
    return safe_send_message(
        m.chat.id, "⚠️ Описание не может быть пустым.", reply_markup=kb_main_menu(uid)
    )

  if not check_auto_moderation(text):
    clear_state(uid)
    return safe_send_message(
        m.chat.id,
        "🤬 Текст содержит запрещенные слова. Публикация отменена.",
        reply_markup=kb_main_menu(uid),
    )

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO barter_ads (user_id, server, text, photo, last_updated)"
        " VALUES (?, ?, ?, ?, ?)",
        (uid, srv, text, photo, time.time()),
    )

  safe_send_message(
      m.chat.id,
      "✅ Ваше предложение по обмену успешно опубликовано!",
      reply_markup=kb_main_menu(uid),
  )


# ==========================================
# МОДУЛЬ 2: СИСТЕМА АУКЦИОНОВ
# ==========================================
def check_auction_working_hours() -> bool:
  now_time = get_msk_time().time()
  start_t = dtime(8, 0, 0)
  end_t = dtime(22, 0, 0)
  if start_t <= now_time <= end_t:
    return True
  return False


def show_auctions_menu(m):
  uid = m.from_user.id
  srv = get_user_server(uid)
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM auctions WHERE server = ? AND status = 'active'", (srv,)
    )
    auctions = cur.fetchall()

  text = f"🏛 <b>Система аукционов</b>\n🌐 Сервер: <b>{html.escape(srv)}</b>\n\n"
  if auctions:
    text += "Активные аукционы:\n"
  else:
    text += "На данный момент нет активных аукционов.\n"

  safe_send_message(m.chat.id, text)

  for a in auctions:
    aid = a["id"]
    item = a["item_name"]
    price = a["current_bid"] or a["start_price"]
    is_owner_lot = a["user_id"] == uid
    fmt = (
        f"🏛 <b>Аукцион #{aid}</b>\n"
        f"📦 Товар: <b>{html.escape(item)}</b>\n"
        f"💰 Текущая ставка: <b>{price:,.0f} $</b>\n"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    if is_owner_lot:
      markup.add(
          types.InlineKeyboardButton(
              "❌ Удалить мой лот", callback_data=f"auc_remove_{aid}"
          )
      )
    else:
      markup.add(
          types.InlineKeyboardButton(
              "💵 Сделать ставку", callback_data=f"auc_bid_{aid}"
          )
      )
    safe_send_message(m.chat.id, fmt, reply_markup=markup)

  markup_btn = types.InlineKeyboardMarkup()
  markup_btn.add(
      types.InlineKeyboardButton(
          "➕ Выставить товар на аукцион", callback_data="auc_create_start"
      )
  )
  safe_send_message(m.chat.id, "Хотите выставить лот?", reply_markup=markup_btn)


@bot.callback_query_handler(func=lambda c: c.data.startswith("auc_remove_"))
def cb_auc_remove(call):
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass
  aid = int(call.data.replace("auc_remove_", ""))
  uid = call.from_user.id

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT * FROM auctions WHERE id = ?", (aid,))
    auc = cur.fetchone()
    if not auc:
      return safe_send_message(call.message.chat.id, "⚠️ Аукцион не найден.")
    if auc["user_id"] != uid and not is_admin_or_owner(call.from_user):
      return safe_send_message(
          call.message.chat.id, "⛔ Вы не можете удалить чужой лот."
      )

    cur.execute("DELETE FROM auctions WHERE id = ?", (aid,))
    cur.execute("DELETE FROM auction_logs WHERE auction_id = ?", (aid,))

  safe_send_message(
      call.message.chat.id,
      f"✅ Ваш лот аукциона #{aid} ({auc['item_name']}) успешно удален.",
      reply_markup=kb_main_menu(uid),
  )


@bot.callback_query_handler(func=lambda c: c.data == "auc_create_start")
def cb_auc_create_start(call):
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass
  if not check_auction_working_hours() and not is_admin_or_owner(
      call.from_user
  ):
    return safe_send_message(
        call.message.chat.id,
        "❌ Выставлять товары на аукцион можно строго с <b>08:00:00 до"
        " 22:00:00 МСК</b>.",
    )
  update_state(call.from_user.id, auction_create_step="item_name")
  safe_send_message(
      call.message.chat.id,
      "🏛 Введите название товара для аукциона:",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    func=lambda m: get_state(m.from_user.id).get("auction_create_step")
    == "item_name"
)
def process_auc_item(m):
  uid = m.from_user.id
  update_state(uid, auc_item=m.text.strip(), auction_create_step="start_price")
  safe_send_message(
      m.chat.id, "💰 Введите начальную цену лота (в $):", reply_markup=kb_cancel()
  )


@bot.message_handler(
    func=lambda m: get_state(m.from_user.id).get("auction_create_step")
    == "start_price"
)
def process_auc_price(m):
  uid = m.from_user.id
  srv = get_user_server(uid)
  try:
    price = parse_flexible_price(m.text)
  except ValueError:
    return safe_send_message(
        m.chat.id,
        "⚠️ Введите корректную сумму (например: 1кк, 500к, 1000000, 1.5кк).",
    )

  st = get_state(uid)
  item = st.get("auc_item")
  clear_state(uid)

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO auctions (user_id, server, item_name, start_price,"
        " current_bid, status, created_at) VALUES (?, ?, ?, ?, ?, 'active', ?)",
        (uid, srv, item, price, price, time.time()),
    )
    auc_id = cur.lastrowid
    cur.execute(
        "INSERT INTO auction_logs (auction_id, user_id, action, timestamp)"
        " VALUES (?, ?, ?, ?)",
        (
            auc_id,
            uid,
            f"Создан аукцион на лот '{item}' с ценой {price}",
            time.time(),
        ),
    )

  owner_id = get_owner_id()
  if owner_id:
    with contextlib.suppress(Exception):
      log_content = (
          f"ЛОГ АУКЦИОНА #{auc_id}\nСоздан новый лот: {item}\nID создателя:"
          f" {uid}\nНачальная цена: {price}\n"
      )
      markup_log = types.InlineKeyboardMarkup()
      markup_log.add(
          types.InlineKeyboardButton(
              "📋 Посмотреть логи аукциона",
              callback_data=f"owner_view_auc_{auc_id}",
          )
      )
      send_log_file(
          owner_id,
          f"auction_{auc_id}_created.txt",
          log_content,
          caption=(
              f"🔔 <b>Лог аукциона:</b> Пользователь (ID {uid}) выставил лот"
              f" <b>{html.escape(item)}</b> на аукцион #{auc_id}."
          ),
          reply_markup=markup_log,
      )

  safe_send_message(
      m.chat.id,
      f"✅ Аукцион на лот <b>{html.escape(item)}</b> успешно запущен!\n\nВы"
      " можете свободно выходить в меню, ваш товар выставлен и участвует в"
      " аукционе.",
      reply_markup=kb_main_menu(uid),
  )


@bot.callback_query_handler(func=lambda c: c.data.startswith("auc_bid_"))
def cb_auc_bid(call):
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass
  aid = int(call.data.replace("auc_bid_", ""))
  uid = call.from_user.id

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT * FROM auctions WHERE id = ? AND status = 'active'", (aid,))
    auc = cur.fetchone()

  if not auc:
    return safe_send_message(
        call.message.chat.id, "⚠️ Аукцион не найден или завершен."
    )

  if auc["user_id"] == uid:
    return safe_send_message(
        call.message.chat.id, "⚠️ Вы не можете делать ставки на свой аукцион."
    )

  curr_price = auc["current_bid"] or auc["start_price"]
  update_state(uid, auction_bid_input=aid)
  safe_send_message(
      call.message.chat.id,
      f"💵 Текущая ставка: <b>{curr_price:,.0f} $</b>\n\nВведите вашу ставку"
      " (любым удобным способом: 1кк, 500к, 1000000 и т.д.):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    func=lambda m: get_state(m.from_user.id).get("auction_bid_input") is not None
)
def process_custom_auc_bid(m):
  uid = m.from_user.id
  st = get_state(uid)
  aid = st.get("auction_bid_input")
  clear_state(uid)

  try:
    new_bid = parse_flexible_price(m.text)
  except ValueError:
    return safe_send_message(
        m.chat.id,
        "⚠️ Введите корректную сумму (например: 1кк, 500к, 1000000).",
    )

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM auctions WHERE id = ? AND status = 'active'", (aid,)
    )
    auc = cur.fetchone()
    if not auc:
      return safe_send_message(m.chat.id, "⚠️ Аукцион не найден.")

    curr_price = auc["current_bid"] or auc["start_price"]
    if new_bid <= curr_price:
      return safe_send_message(
          m.chat.id,
          f"⚠️ Ваша ставка должна быть больше текущей ({curr_price:,.0f} $).",
      )

    cur.execute(
        "UPDATE auctions SET current_bid = ?, highest_bidder = ? WHERE id = ?",
        (new_bid, uid, aid),
    )
    cur.execute(
        "INSERT INTO auction_logs (auction_id, user_id, action, timestamp)"
        " VALUES (?, ?, ?, ?)",
        (aid, uid, f"Сделана ставка: {new_bid}", time.time()),
    )

  owner_id = get_owner_id()
  if owner_id:
    with contextlib.suppress(Exception):
      log_content = (
          f"ЛОГ СТАВКИ В АУКЦИОНЕ #{aid}\nЛот: {auc['item_name']}\nПокупатель ID:"
          f" {uid}\nСумма ставки: {new_bid}\n"
      )
      markup_log = types.InlineKeyboardMarkup()
      markup_log.add(
          types.InlineKeyboardButton(
              "📋 Посмотреть логи аукциона",
              callback_data=f"owner_view_auc_{aid}",
          )
      )
      send_log_file(
          owner_id,
          f"auction_{aid}_bid.txt",
          log_content,
          caption=(
              f"🔔 <b>Лог ставки в аукционе #{aid}:</b>\nПокупатель (ID {uid})"
              f" сделал ставку <b>{new_bid:,.0f} $</b> на лот"
              f" <i>{html.escape(auc['item_name'])}</i>."
          ),
          reply_markup=markup_log,
      )

  safe_send_message(
      m.chat.id,
      f"✅ Вы успешно сделали ставку <b>{new_bid:,.0f} $</b>!",
      reply_markup=kb_main_menu(uid),
  )


# ==========================================
# МОДУЛЬ ОБЩЕНИЯ ПРОДАВЦА И ПОКУПАТЕЛЯ И ЖАЛОБ
# ==========================================
@bot.callback_query_handler(
    func=lambda c: c.data.startswith("contact_seller_")
    or c.data.startswith("reply_to_buyer_")
)
def cb_start_dialog(call):
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass
  parts = call.data.split("_")
  ad_id = int(parts[-1])

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT user_id, text FROM barter_ads WHERE id = ?", (ad_id,))
    row = cur.fetchone()
    if not row:
      cur.execute("SELECT user_id, text FROM active_ads WHERE id = ?", (ad_id,))
      row = cur.fetchone()
    if not row:
      cur.execute(
          "SELECT user_id, text FROM active_buy_ads WHERE id = ?", (ad_id,)
      )
      row = cur.fetchone()

  if not row:
    return safe_send_message(
        call.message.chat.id, "⚠️ Объявление или лот не найден."
    )

  seller_id = row["user_id"]
  buyer_id = call.from_user.id

  if seller_id == buyer_id:
    return safe_send_message(
        call.message.chat.id, "⚠️ Вы не можете писать сами себе."
    )

  update_state(buyer_id, chat_with_seller_id=seller_id, chat_ad_id=ad_id)

  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton(
          "❌ Закончить диалог", callback_data=f"chat_end_{ad_id}_{seller_id}"
      ),
      types.InlineKeyboardButton(
          "⚠️ Пожаловаться на продавца",
          callback_data=f"chat_complaint_{ad_id}_{seller_id}",
      ),
  )
  safe_send_message(
      call.message.chat.id,
      f"✉️ <b>Связь по объявлению/лоту #{ad_id}</b>\nНапишите ваше сообщение"
      " продавцу. Переписка логируется.",
      reply_markup=markup,
  )


@bot.message_handler(
    func=lambda m: get_state(m.from_user.id).get("chat_with_seller_id")
    is not None,
    content_types=["text", "photo"],
)
def process_chat_message(m):
  uid = m.from_user.id
  st = get_state(uid)
  target_id = st.get("chat_with_seller_id")
  ad_id = st.get("chat_ad_id")
  text = m.text or m.caption or "[Фото/Медиа]"

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chat_logs_history (sender_id, receiver_id, text,"
        " timestamp) VALUES (?, ?, ?, ?)",
        (uid, target_id, text, time.time()),
    )

  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton(
          "✉️ Ответить / Возобновить", callback_data=f"contact_seller_{ad_id}"
      ),
      types.InlineKeyboardButton(
          "❌ Закончить диалог", callback_data=f"chat_end_{ad_id}_{uid}"
      ),
      types.InlineKeyboardButton(
          "⚠️ Пожаловаться", callback_data=f"chat_complaint_{ad_id}_{uid}"
      ),
  )

  update_state(target_id, chat_with_seller_id=uid, chat_ad_id=ad_id)

  try:
    if m.photo:
      bot.send_photo(
          target_id,
          m.photo[-1].file_id,
          caption=(
              f"💬 <b>Сообщение по сделке #{ad_id}:</b>\n{html.escape(text)}"
          ),
          reply_markup=markup,
      )
    else:
      safe_send_message(
          target_id,
          f"💬 <b>Сообщение по сделке #{ad_id}:</b>\n{html.escape(text)}",
          reply_markup=markup,
      )
    safe_send_message(m.chat.id, "✅ Сообщение успешно отправлено собеседнику!")
  except Exception as e:
    safe_send_message(
        m.chat.id, "⚠️ Не удалось доставить сообщение пользователю."
    )
    logger.error(f"Ошибка пересылки сообщения: {e}")


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("chat_end_")
    or c.data.startswith("chat_complaint_")
)
def cb_chat_actions(call):
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass
  parts = call.data.split("_")
  action_type = parts[1]
  ad_id = int(parts[2])
  target_id = int(parts[3])
  uid = call.from_user.id

  if action_type == "end":
    clear_state(uid)
    clear_state(target_id)
    safe_send_message(
        call.message.chat.id,
        "❌ Диалог по сделке завершен.",
        reply_markup=kb_main_menu(uid),
    )
    with contextlib.suppress(Exception):
      safe_send_message(
          target_id,
          "❌ Собеседник завершил диалог по сделке.",
          reply_markup=kb_main_menu(target_id),
      )
  elif action_type == "complaint":
    update_state(uid, chat_complaint_target=target_id, chat_complaint_ad=ad_id)
    safe_send_message(
        call.message.chat.id,
        "⚠️ Опишите причину жалобы на продавца/участника сделки:",
        reply_markup=kb_cancel(),
    )


@bot.message_handler(
    func=lambda m: get_state(m.from_user.id).get("chat_complaint_target")
    is not None
)
def process_chat_complaint_text(m):
  uid = m.from_user.id
  st = get_state(uid)
  target_id = st.get("chat_complaint_target")
  ad_id = st.get("chat_complaint_ad")
  reason = m.text
  clear_state(uid)

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM chat_logs_history WHERE (sender_id = ? AND receiver_id ="
        " ?) OR (sender_id = ? AND receiver_id = ?) ORDER BY timestamp ASC",
        (uid, target_id, target_id, uid),
    )
    logs = cur.fetchall()

  log_text = (
      f"ИСТОРИЯ ПЕРЕПИСКИ ПО СДЕЛКЕ #{ad_id} (Жалоба)\n" + "=" * 40 + "\n\n"
  )
  for l in logs:
    dt = datetime.fromtimestamp(l["timestamp"]).strftime("%H:%M:%S")
    log_text += f"[{dt}] ID {l['sender_id']} -> ID {l['receiver_id']}: {l['text']}\n"
  log_text += f"\nПричина жалобы: {reason}\n"

  owner_id = get_owner_id()
  if owner_id:
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "🔨 Забанить игрока", callback_data=f"auc_ban_{target_id}_{ad_id}"
        )
    )
    send_log_file(
        owner_id,
        f"complaint_chat_{ad_id}.txt",
        log_text,
        caption=(
            f"🚨 <b>Жалоба на участника сделки #{ad_id}:</b>\nПользователь ID"
            f" {uid} пожаловался на ID {target_id}.\nПричина:"
            f" {html.escape(reason)}"
        ),
        reply_markup=markup,
    )

  safe_send_message(
      m.chat.id,
      "✅ Жалоба и лог переписки отправлены администрации.",
      reply_markup=kb_main_menu(uid),
  )


# ==========================================
# МОДУЛЬ РЕФЕРАЛОВ И ЕЖЕДНЕВНЫХ БОНУСОВ
# ==========================================
def show_ref_bonus_menu(m):
  uid = m.from_user.id
  bot_uname = BOT_USERNAME
  ref_link = f"https://t.me/{bot_uname}?start=ref_{uid}"

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) as cnt FROM referrals WHERE referrer_id = ? AND"
        " completed = 1",
        (uid,),
    )
    row = cur.fetchone()
    ref_count = row["cnt"] if row else 0

    cur.execute("SELECT * FROM user_bonuses WHERE user_id = ?", (uid,))
    bonus_row = cur.fetchone()
    vip_ads = bonus_row["vip_ads_count"] if bonus_row else 0

  text = (
      f"👥 <b>Реферальная система и ежедневные бонусы</b>\n\n🔗 Ваша реферальная"
      f" ссылка:\n<code>{ref_link}</code>\n👥 Успешно приглашено друзей:"
      f" <b>{ref_count}</b>\n👑 Доступно VIP-объявлений:"
      f" <b>{vip_ads} шт.</b>\n\n📌 <b>Как работает реферальная"
      " система:</b>\n1. Поделитесь этой ссылкой с другом.\n2. Друг должен"
      " запустить бота и в течение <b>3 дней</b> активно отправлять не менее"
      " <b>3 объявлений в день</b>.\n3. Накрутка и саморефералы не"
      " засчитываются.\n4. После выполнения условий вы и ваш друг получите"
      " <b>VIP-статус на 10 дней</b>!"
  )
  markup = types.InlineKeyboardMarkup(row_width=1)
  markup.add(
      types.InlineKeyboardButton(
          "📤 Поделиться ссылкой",
          url=(
              "https://t.me/share/url?url="
              f"{ref_link}&text=Присоединяйся%20к%20лучшему%20боту%20для%20торговли%20и%20публикации%20объявлений%20Arizona%20RP!"
          ),
      ),
      types.InlineKeyboardButton(
          "🎁 Получить ежедневный бонус", callback_data="claim_daily_bonus"
      ),
  )
  safe_send_message(m.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data == "claim_daily_bonus")
def cb_claim_daily_bonus(call):
  uid = call.from_user.id
  today = datetime.now().strftime("%Y-%m-%d")

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT last_claim_date FROM user_bonuses WHERE user_id = ?", (uid,))
    row = cur.fetchone()
    if row and row["last_claim_date"] == today:
      try:
        return bot.answer_callback_query(
            call.id,
            "⚠️ Вы уже получали бонус сегодня! Приходите завтра.",
            show_alert=True,
        )
      except Exception:
        pass
      return

    got_vip_sub = random.random() < 0.10
    if got_vip_sub:
      expires = time.time() + 10 * 86400
      cur.execute(
          "INSERT OR REPLACE INTO premium_users (user_id, expires_at) VALUES"
          " (?, ?)",
          (uid, expires),
      )
      reward_msg = (
          "💎 Поздравляем! Вам выпала <b>VIP-подписка на 10 дней</b>!"
      )
    else:
      vip_ads_count = random.choices(
          [1, 2, 3, 4, 5], weights=[40, 25, 18, 12, 5]
      )[0]
      expiry = time.time() + 3 * 86400
      cur.execute(
          "INSERT OR REPLACE INTO user_bonuses (user_id, last_claim_date,"
          " vip_ads_count, vip_ads_expiry) VALUES (?, ?, ?, ?)",
          (uid, today, vip_ads_count, expiry),
      )
      reward_msg = (
          f"🎁 В ежедневном бонусе вам выпало: <b>{vip_ads_count}"
          " VIP-объявлений</b> (действуют 3 дня)!"
      )

  try:
    bot.answer_callback_query(call.id, "🎉 Бонус успешно получен!", show_alert=True)
    bot.edit_message_text(
        f"🎉 <b>Ежедневный бонус открыт!</b>\n\n{reward_msg}",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb_main_menu(uid),
    )
  except Exception:
    pass


# ==========================================
# КОМАНДЫ /start И /help
# ==========================================
@bot.message_handler(commands=["start"])
def cmd_start(m):
  try:
    bot.delete_message(m.chat.id, m.message_id)
  except Exception:
    pass

  uid = m.from_user.id
  register_user(uid, m.from_user.username)

  args = m.text.split()
  if len(args) > 1 and args[1].startswith("ref_"):
    try:
      referrer_id = int(args[1].replace("ref_", ""))
      if referrer_id != uid:
        with db_lock, get_db() as conn:
          cur = conn.cursor()
          cur.execute(
              "INSERT OR IGNORE INTO referrals (referrer_id, referred_id,"
              " qualified_days, last_active_date, ads_today, completed) VALUES"
              " (?, ?, 0, ?, 0, 0)",
              (referrer_id, uid, datetime.now().strftime("%Y-%m-%d")),
          )
    except Exception:
      pass

  if is_banned(m.from_user):
    return safe_send_message(
        m.chat.id, "⛔ Вы заблокированы.", reply_markup=types.ReplyKeyboardRemove()
    )

  if is_admin_or_owner(m.from_user):
    register_admin_chat(m.chat.id)

  update_state(uid, changing_server=True)

  welcome_text = (
      "👋 <b>Добро пожаловать в неофициальный торговый бот Arizona RP!</b>\n\n🔒"
      " <b>Отказ от ответственности и безопасность:</b>\n• Обратите внимание,"
      " что мы <b>не являемся официальным ботом</b> разработчиков Arizona"
      " RP.\n• <b>Администрация не несет никакой ответственности</b> за"
      " содержание объявлений, совершаемые сделки, передачу игровой"
      " валюты/имущества и возможные случаи мошенничества (скама). Все"
      " договоренности вы совершаете на свой страх и риск.\n• Тем не менее,"
      " <b>мы по возможности стараемся помогать</b> игрокам в спорных"
      " ситуациях, анализировать логи переписок и принимать меры против"
      " нарушителей.\n\n👇 <b>Выберите свой игровой сервер в меню ниже, чтобы"
      " начать работу:</b>"
  )
  safe_send_message(
      m.chat.id, welcome_text, reply_markup=kb_servers(), parse_mode="HTML"
  )


@bot.message_handler(commands=["help"])
def cmd_help(m):
  help_text = (
      "📖 <b>Справка и часто задаваемые вопросы (FAQ)</b>\n\n<b>1. Как подать"
      " объявление о продаже или скупке?</b>\nВыберите свой сервер, затем"
      " нажмите «📤 Продать товар» или «📥 Скупить товар», выберите категорию,"
      " отправьте текст с фото и выберите тип публикации.\n\n<b>2. Почему мое"
      " объявление не появилось сразу?</b>\nВсе объявления проверяются"
      " администраторами. После одобрения модератором пост публикуется в"
      " ленте.\n\n<b>3. Что делать, если бот завис или не реагируют"
      " кнопки?</b>\nНажмите команду /start для сброса состояния и перезагрузки"
      " главного меню.\n\n<b>4. Безопасны ли сделки через бота?</b>\nБот —"
      " независимая рекламная площадка. Администрация не несет ответственности"
      " за скам, но в спорных ситуациях вы можете нажать кнопку жалобы в"
      " диалоге сделки.\n\n<b>5. Как работают аукционы и бартер?</b>\nВ"
      " разделах «🏛 Аукционы» и «🔄 Бартер / Обмен» вы можете выставлять свои"
      " лоты, делать ставки или предлагать имущество на обмен с другими"
      " игроками.\n\n<b>6. Что дает реферальная система и ежедневные"
      " бонусы?</b>\nПриглашайте друзей по вашей реферальной ссылке (условие: 3"
      " активных дня по 3 объявления) или крутите ежедневный бонус для получения"
      " VIP-статуса и VIP-объявлений.\n\n<b>7. Когда работает мой бот?</b>\nБот"
      " принимает и публикует объявления строго с <b>08:00:01 до 22:00:01"
      " МСК</b>. Вне этого времени отправка объявлений приостановлена (ночной"
      " режим)."
  )
  safe_send_message(
      m.chat.id, help_text, reply_markup=kb_main_menu(m.from_user.id)
  )


# ==========================================
# ПОДАЧА ОБЪЯВЛЕНИЙ И КУЛДАУН
# ==========================================
def check_working_hours() -> bool:
  now_time = get_msk_time().time()
  start_t = dtime(8, 0, 1)
  end_t = dtime(22, 0, 1)
  if start_t <= now_time <= end_t:
    return True
  return False


def start_add_ad(m):
  uid = m.from_user.id
  srv = get_user_server(uid)
  last_time = get_user_last_ad_time(uid)
  cooldown = 60 if is_user_premium(uid) else 120
  if time.time() - last_time < cooldown and not is_admin_or_owner(m.from_user):
    rem = int(cooldown - (time.time() - last_time))
    return safe_send_message(
        m.chat.id,
        f"⏳ Подождите. Кулдаун на подачу объявлений: еще {rem} сек.",
        reply_markup=kb_main_menu(uid),
    )

  if not check_working_hours() and not is_admin_or_owner(m.from_user):
    return safe_send_message(
        m.chat.id,
        "❌ <b>Отправка объявлений временно заблокирована!</b>\n\n🌙 Ночной режим"
        " активен. Радиоцентр принимает объявления строго с <b>08:00:01 до"
        " 22:00:01 МСК</b>.",
        reply_markup=kb_main_menu(uid),
    )

  update_state(uid, posting_ad={"step": "category", "is_buy": False})
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  for cat in CATEGORIES:
    markup.add(types.KeyboardButton(cat))
  markup.add(types.KeyboardButton("❌ Отменить действие"))
  safe_send_message(
      m.chat.id,
      f"📤 <b>Подача объявления о продаже</b>\n🌐 Сервер:"
      f" {html.escape(srv)}\n\nВыберите категорию товара:",
      reply_markup=markup,
  )


def start_add_buy_ad(m):
  uid = m.from_user.id
  srv = get_user_server(uid)
  last_time = get_user_last_ad_time(uid)
  cooldown = 60 if is_user_premium(uid) else 120
  if time.time() - last_time < cooldown and not is_admin_or_owner(m.from_user):
    rem = int(cooldown - (time.time() - last_time))
    return safe_send_message(
        m.chat.id,
        f"⏳ Подождите. Кулдаун на подачу объявлений: еще {rem} сек.",
        reply_markup=kb_main_menu(uid),
    )

  if not check_working_hours() and not is_admin_or_owner(m.from_user):
    return safe_send_message(
        m.chat.id,
        "❌ <b>Отправка объявлений временно заблокирована!</b>\n\n🌙 Ночной режим"
        " активен. Радиоцентр принимает объявления строго с <b>08:00:01 до"
        " 22:00:01 МСК</b>.",
        reply_markup=kb_main_menu(uid),
    )

  update_state(uid, posting_ad={"step": "category", "is_buy": True})
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  for cat in CATEGORIES:
    markup.add(types.KeyboardButton(cat))
  markup.add(types.KeyboardButton("❌ Отменить действие"))
  safe_send_message(
      m.chat.id,
      f"📥 <b>Подача объявления о скупке</b>\n🌐 Сервер:"
      f" {html.escape(srv)}\n\nВыберите категорию товара:",
      reply_markup=markup,
  )


@bot.message_handler(
    func=lambda msg: get_state(msg.from_user.id)
    .get("posting_ad", {})
    .get("step")
    == "category"
)
def process_ad_category(m):
  uid = m.from_user.id
  cat = m.text.strip()
  if cat not in CATEGORIES:
    return safe_send_message(
        m.chat.id, "⚠️ Пожалуйста, выберите категорию из меню."
    )

  st = get_state(uid)
  st["posting_ad"]["category"] = cat
  st["posting_ad"]["step"] = "text_or_photo"
  update_state(uid, posting_ad=st["posting_ad"])

  safe_send_message(
      m.chat.id,
      f"✍️ Вы выбрали: <b>{html.escape(cat)}</b>\n\nТеперь введите текст"
      " объявления и прикрепите фото (по желанию):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    content_types=["text", "photo"],
    func=lambda msg: get_state(msg.from_user.id)
    .get("posting_ad", {})
    .get("step")
    == "text_or_photo",
)
def process_ad_text_or_photo(m):
  uid = m.from_user.id
  st = get_state(uid)
  text = m.text or m.caption
  if not text:
    return safe_send_message(m.chat.id, "⚠️ Укажите текст объявления.")

  if not check_auto_moderation(text):
    clear_state(uid)
    return safe_send_message(
        m.chat.id,
        "🤬 Обнаружены запрещенные слова! Публикация отменена.",
        reply_markup=kb_main_menu(uid),
    )

  st["posting_ad"]["polished_text"] = text
  st["posting_ad"]["photo_id"] = m.photo[-1].file_id if m.photo else None
  st["posting_ad"]["step"] = "choose_ad_type"
  update_state(uid, posting_ad=st["posting_ad"])

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT vip_ads_count, vip_ads_expiry FROM user_bonuses WHERE user_id ="
        " ?",
        (uid,),
    )
    b_row = cur.fetchone()
    has_vip_bonus = (
        b_row
        and b_row["vip_ads_count"] > 0
        and b_row["vip_ads_expiry"] > time.time()
    )
    vip_count_left = b_row["vip_ads_count"] if b_row else 0

  markup = types.InlineKeyboardMarkup(row_width=1)
  if has_vip_bonus:
    markup.add(
        types.InlineKeyboardButton(
            f"👑 VIP-объявление (Бесплатно за бонус: {vip_count_left} шт.)",
            callback_data="ad_type_bonus_vip",
        ),
        types.InlineKeyboardButton(
            "📄 Обычное объявление (Бесплатно)", callback_data="ad_type_regular"
        ),
    )
  elif is_user_premium(uid):
    markup.add(
        types.InlineKeyboardButton(
            "👑 VIP-объявление (По подписке)", callback_data="ad_type_vip_sub"
        ),
        types.InlineKeyboardButton(
            "📄 Обычное объявление (Бесплатно)", callback_data="ad_type_regular"
        ),
    )
  else:
    markup.add(
        types.InlineKeyboardButton(
            "👑 VIP-объявление (1 ⭐)", callback_data="ad_type_vip_paid"
        ),
        types.InlineKeyboardButton(
            "📄 Обычное объявление (Бесплатно)", callback_data="ad_type_regular"
        ),
    )

  safe_send_message(
      m.chat.id,
      f"📝 <b>Текст:</b>\n\n{html.escape(text)}\n\nВыберите тип объявления:",
      reply_markup=markup,
  )


@bot.callback_query_handler(
    func=lambda c: c.data
    in ["ad_type_vip_sub", "ad_type_regular", "ad_type_bonus_vip", "ad_type_vip_paid"]
)
def cb_publish_ad_free(call):
  try:
    bot.answer_callback_query(call.id, "✅ Отправлено на модерацию!")
  except Exception:
    pass

  uid = call.from_user.id
  st = get_state(uid)
  post_data = st.get("posting_ad")
  if not post_data:
    return

  is_vip = 1 if call.data in ["ad_type_vip_sub", "ad_type_bonus_vip", "ad_type_vip_paid"] else 0

  if call.data == "ad_type_bonus_vip":
    with db_lock, get_db() as conn:
      cur = conn.cursor()
      cur.execute("SELECT vip_ads_count FROM user_bonuses WHERE user_id = ?", (uid,))
      row = cur.fetchone()
      if row and row["vip_ads_count"] > 0:
        cur.execute("UPDATE user_bonuses SET vip_ads_count = vip_ads_count - 1 WHERE user_id = ?", (uid,))

  srv = get_user_server(uid)
  cat = post_data["category"]
  text = post_data["polished_text"]
  photo = post_data["photo_id"]
  is_buy = post_data["is_buy"]

  table = "pending_buy_posts" if is_buy else "pending_posts"
  username = call.from_user.username or str(uid)

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO {table} (user_id, username, server, category, text, photo, is_vip, editing_by, editing_since) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)",
        (uid, username, srv, cat, text, photo, is_vip),
    )

  set_user_last_ad_time(uid, time.time())
  clear_state(uid)

  try:
    bot.edit_message_text(
        "✅ <b>Ваше объявление успешно отправлено на модерацию!</b>\n\nОно появится в ленте после проверки администратором.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=None,
    )
  except Exception:
    pass
  safe_send_message(call.message.chat.id, "Главное меню:", reply_markup=kb_main_menu(uid))


# ==========================================
# ЗАПУСК БОТА
# ==========================================
if __name__ == "__main__":
  logger.info("Бот запущен и готов к работе...")
  bot.infinity_polling(skip_pending=True)

