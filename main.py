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
# ЗАЩИТА ОТ ФЛУДА И СПИСОК МАТА
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
# УНИВЕРСАЛЬНЫЙ ПАРСЕР ЦЕН
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
            CREATE TABLE IF NOT EXISTS user_bonuses (
                user_id INTEGER PRIMARY KEY,
                last_claim_date TEXT,
                vip_ads_count INTEGER DEFAULT 0,
                last_deduct_date TEXT
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
            CREATE TABLE IF NOT EXISTS user_data (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                last_ad_time REAL,
                server TEXT
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS premium_users (
                user_id INTEGER PRIMARY KEY,
                expires_at REAL
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
# ФОНОВЫЙ ПЛАНИЩИК (СГОРЕБНИЕ ВИП-ОБЪЯВЛЕНИЙ И ОЧИСТКА)
# ==========================================
def background_maintenance_worker():
  last_ad_clean_date = ""
  last_log_clean_date = ""
  last_bonus_deduct_date = ""

  while True:
    try:
      now = get_msk_time()
      current_time_str = now.strftime("%H:%M:%S")
      current_date_str = now.strftime("%Y-%m-%d")

      # Сгорание бонусов VIP-объявлений раз в сутки в полночь (00:00:05)
      if (
          "00:00:00" <= current_time_str <= "00:01:00"
          and last_bonus_deduct_date != current_date_str
      ):
        with db_lock, get_db() as conn:
          cur = conn.cursor()
          cur.execute("""
                        UPDATE user_bonuses 
                        SET vip_ads_count = CASE WHEN vip_ads_count > 0 THEN vip_ads_count - 1 ELSE 0 END
                        WHERE vip_ads_count > 0
                    """)
        logger.info(
            "Ежедневное сгорание неиспользованных бонусных VIP-объявлений"
            " выполнено."
        )
        last_bonus_deduct_date = current_date_str

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
      types.KeyboardButton("↩️ Назад в меню"),
      types.KeyboardButton("❌ Отменить действие"),
  )


def kb_back():
  return types.ReplyKeyboardMarkup(resize_keyboard=True).add(
      types.KeyboardButton("↩️ Назад в меню")
  )


# ==========================================
# МОДУЛЬ VIP-СТАТУСА И ПОКУПКИ ЗА ЗВЕЗДЫ
# ==========================================
def info_premium(m):
  uid = m.from_user.id
  is_prem = is_user_premium(uid)
  status_text = "🟢 Активна" if is_prem else "🔴 Не активна"

  text = (
      f"💎 <b>VIP-статус и привилегии</b>\n\n"
      f"Ваш текущий статус: <b>{status_text}</b>\n\n"
      f"✨ <b>Что дает VIP-подписка:</b>\n"
      f"• Уменьшенный кулдаун между подачей объявлений: <b>60 секунд</b> (у"
      f" обычных — 120 секунд).\n"
      f"• Автоматическая публикация без выбора типа (обычная/VIP) и особый"
      f" VIP-значок!\n"
      f"• Приоритет в ленте и эксклюзивные возможности.\n\n"
      f"💰 <b>Стоимость подписки:</b> <b>100 Telegram Stars (⭐)</b> на 30 дней.\n\n"
      f"Нажмите кнопку ниже для безопасной оплаты:"
  )
  markup = types.InlineKeyboardMarkup(row_width=1)
  markup.add(
      types.InlineKeyboardButton(
          "⭐ Купить VIP за 100 Звёзд", callback_data="buy_vip_stars"
      )
  )
  safe_send_message(m.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data == "buy_vip_stars")
def cb_buy_vip_stars(call):
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass
  uid = call.from_user.id
  chat_id = call.message.chat.id

  title = "VIP-подписка (30 дней)"
  description = "Приобретение VIP-статуса в торговом боте Arizona RP на 30 дней."
  payload = f"vip_sub_{uid}_{int(time.time())}"
  currency = "XTR"
  prices = [types.LabeledPrice(label="VIP-статус", amount=100)]

  try:
    bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        invoice_payload=payload,
        provider_token="",
        currency=currency,
        prices=prices,
    )
  except Exception as e:
    logger.error(f"Ошибка отправки инвойса: {e}")
    safe_send_message(
        chat_id, "⚠️ Не удалось создать счет на оплату. Попробуйте позже."
    )


@bot.pre_checkout_query_handler(func=lambda query: True)
def pre_checkout_query(query):
  bot.answer_pre_checkout_query(query.id, ok=True)


@bot.message_handler(content_types=["successful_payment"])
def successful_payment(m):
  uid = m.from_user.id
  payment_info = m.successful_payment
  if payment_info.currency == "XTR":
    expires = time.time() + 30 * 86400
    with db_lock, get_db() as conn:
      cur = conn.cursor()
      cur.execute(
          "INSERT OR REPLACE INTO premium_users (user_id, expires_at) VALUES"
          " (?, ?)",
          (uid, expires),
      )
    safe_send_message(
        m.chat.id,
        "🎉 <b>Поздравляем! Оплата прошла успешно!</b>\nВам активирована"
        " <b>VIP-подписка на 30 дней</b> 🌟.",
        reply_markup=kb_main_menu(uid),
    )


# ==========================================
# МОДУЛЬ 1: РЕФЕРАЛЫ И БОНУСЫ
# ==========================================
def show_ref_bonus_menu(m):
  uid = m.from_user.id
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT last_claim_date, vip_ads_count FROM user_bonuses WHERE user_id ="
        " ?",
        (uid,),
    )
    b_data = cur.fetchone()

  last_claim = b_data["last_claim_date"] if b_data else None
  vip_count = b_data["vip_ads_count"] if b_data else 0
  today_str = get_msk_time().strftime("%Y-%m-%d")

  can_claim = last_claim != today_str

  text = (
      f"🎁 <b>Рефералы и ежедневные бонусы</b>\n\n"
      f"🌟 Ваши доступные бонусные VIP-объявления: <b>{vip_count} шт.</b>\n"
      f"<i>(Внимание: если бонусные VIP-объявления не расходуются в течение дня,"
      f" каждый день сгорает по 1 шт.!)</i>\n\n"
  )
  if can_claim:
    text += (
        "🔥 Вы можете забрать ежедневный бонус прямо сейчас! Нажмите кнопку"
        " ниже:"
    )
  else:
    text += "⏳ Вы уже забрали бонус сегодня. Приходите завтра!"

  markup = types.InlineKeyboardMarkup(row_width=1)
  if can_claim:
    markup.add(
        types.InlineKeyboardButton(
            "🎁 Забрать ежедневный бонус", callback_data="claim_daily_bonus"
        )
    )

  ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
  text += f"\n\n🔗 <b>Ваша реферальная ссылка:</b>\n<code>{ref_link}</code>"

  safe_send_message(m.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data == "claim_daily_bonus")
def cb_claim_daily_bonus(call):
  uid = call.from_user.id
  today_str = get_msk_time().strftime("%Y-%m-%d")

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT last_claim_date, vip_ads_count FROM user_bonuses WHERE user_id ="
        " ?",
        (uid,),
    )
    row = cur.fetchone()

    if row and row["last_claim_date"] == today_str:
      try:
        return bot.answer_callback_query(
            call.id,
            "⚠️ Вы уже забирали бонус сегодня! Ждем вас завтра.",
            show_alert=True,
        )
      except Exception:
        return

    granted = random.randint(1, 5)
    new_count = (row["vip_ads_count"] if row else 0) + granted

    cur.execute(
        "INSERT OR REPLACE INTO user_bonuses (user_id, last_claim_date,"
        " vip_ads_count) VALUES (?, ?, ?)",
        (uid, today_str, new_count),
    )

  try:
    bot.answer_callback_query(call.id, f"🎉 Вы получили +{granted} VIP-объявлений!")
    bot.edit_message_text(
        f"🎉 <b>Успешно!</b> Вы забрали ежедневный бонус и получили"
        f" <b>+{granted} VIP-объявлений</b>!\n\nВсего доступно бонусных:"
        f" <b>{new_count} шт.</b>\n<i>Помните: неиспользованные бонусные VIP"
        f" сгорают по 1 шт. в день.</i>",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=None,
    )
  except Exception:
    pass


# ==========================================
# ДОБАВЛЕНИЕ ОБЪЯВЛЕНИЙ (ПРОДАЖА И СКУПКА)
# ==========================================
def start_add_ad(m):
  uid = m.from_user.id

  last_time = get_user_last_ad_time(uid)
  now = time.time()
  is_prem = is_user_premium(uid)
  cooldown = 60 if is_prem else 120

  if now - last_time < cooldown:
    left = int(cooldown - (now - last_time))
    return safe_send_message(
        m.chat.id,
        f"⏳ <b>Подождите!</b> Действует кулдаун между подачей объявлений.\nОсталось"
        f" ждать: <b>{left} сек.</b>",
        reply_markup=kb_main_menu(uid),
    )

  update_state(uid, posting_ad={"type": "sell", "step": "category"})
  safe_send_message(
      m.chat.id,
      "📤 <b>Подача объявления о продаже</b>\n\nВыберите категорию товара из"
      " списка ниже:",
      reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
          *(types.KeyboardButton(c) for c in CATEGORIES),
          types.KeyboardButton("↩️ Назад в меню"),
      ),
  )


def start_add_buy_ad(m):
  uid = m.from_user.id
  last_time = get_user_last_ad_time(uid)
  now = time.time()
  is_prem = is_user_premium(uid)
  cooldown = 60 if is_prem else 120

  if now - last_time < cooldown:
    left = int(cooldown - (now - last_time))
    return safe_send_message(
        m.chat.id,
        f"⏳ <b>Подождите!</b> Действует кулдаун между подачей объявлений.\nОсталось"
        f" ждать: <b>{left} сек.</b>",
        reply_markup=kb_main_menu(uid),
    )

  update_state(uid, posting_ad={"type": "buy", "step": "category"})
  safe_send_message(
      m.chat.id,
      "📥 <b>Подача объявления о скупке</b>\n\nВыберите категорию товара из"
      " списка ниже:",
      reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
          *(types.KeyboardButton(c) for c in CATEGORIES),
          types.KeyboardButton("↩️ Назад в меню"),
      ),
  )


@bot.message_handler(
    func=lambda m: get_state(m.from_user.id).get("posting_ad", {}).get("step")
    == "category"
)
def process_ad_category(m):
  uid = m.from_user.id
  cat = m.text.strip()
  if cat not in CATEGORIES:
    return safe_send_message(
        m.chat.id, "⚠️ Пожалуйста, выберите категорию с помощью кнопок ниже."
    )

  update_state(
      uid, posting_ad={"type": get_state(uid)["posting_ad"]["type"], "step": "text_or_photo", "category": cat}
  )
  safe_send_message(
      m.chat.id,
      f"📝 Выбрана категория: <b>{html.escape(cat)}</b>\n\nТеперь отправьте"
      " текст вашего объявления (можно прикрепить фото):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    content_types=["text", "photo"],
    func=lambda m: get_state(m.from_user.id).get("posting_ad", {}).get("step")
    == "text_or_photo",
)
def process_ad_text(m):
  uid = m.from_user.id
  text = m.text or m.caption
  photo = m.photo[-1].file_id if m.photo else None

  if not text:
    return safe_send_message(
        m.chat.id,
        "⚠️ Текст объявления не может быть пустым. Отправьте описание товара.",
    )

  if not check_auto_moderation(text):
    clear_state(uid)
    return safe_send_message(
        m.chat.id,
        "🤬 Текст содержит запрещенные слова или мат! Публикация отклонена.",
        reply_markup=kb_main_menu(uid),
    )

  st = get_state(uid)["posting_ad"]
  st["text"] = text
  st["photo"] = photo

  if is_user_premium(uid):
    st["is_vip"] = 1
    finalize_ad_creation(m, uid, st)
    return

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT vip_ads_count FROM user_bonuses WHERE user_id = ?", (uid,)
    )
    row = cur.fetchone()
    bonus_vip = row["vip_ads_count"] if row else 0

  st["step"] = "choose_ad_type"
  update_state(uid, posting_ad=st)

  markup = types.InlineKeyboardMarkup(row_width=1)
  markup.add(
      types.InlineKeyboardButton(
          "📋 Обычное объявление (Бесплатно)", callback_data="ad_type_norm"
      )
  )

  if bonus_vip > 0:
    markup.add(
        types.InlineKeyboardButton(
            f"🌟 VIP-объявление (Использовать бонус: {bonus_vip} ост.)",
            callback_data="ad_type_vip_bonus",
        )
    )
  else:
    markup.add(
        types.InlineKeyboardButton(
            "⭐ VIP-объявление (Стоит 1 Звезду ⭐)",
            callback_data="ad_type_vip_star",
        )
    )

  safe_send_message(
      m.chat.id,
      "⚙️ <b>Выберите тип публикации вашего объявления:</b>\n\n• <b>Обычное"
      " объявление:</b> бесплатно.\n• <b>VIP-объявление:</b> повышенный"
      " приоритет в ленте.",
      reply_markup=markup,
  )


@bot.callback_query_handler(
    func=lambda c: c.data in ["ad_type_norm", "ad_type_vip_bonus", "ad_type_vip_star"]
)
def cb_choose_ad_type(call):
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass

  uid = call.from_user.id
  st = get_state(uid).get("posting_ad")
  if not st:
    return safe_send_message(
        call.message.chat.id, "⚠️ Сессия истекла. Начните заново."
    )

  data = call.data
  if data == "ad_type_norm":
    st["is_vip"] = 0
    finalize_ad_creation(call.message, uid, st)

  elif data == "ad_type_vip_bonus":
    with db_lock, get_db() as conn:
      cur = conn.cursor()
      cur.execute(
          "SELECT vip_ads_count FROM user_bonuses WHERE user_id = ?", (uid,)
      )
      row = cur.fetchone()
      bonus_vip = row["vip_ads_count"] if row else 0

      if bonus_vip <= 0:
        return safe_send_message(
            call.message.chat.id,
            "⚠️ У вас больше нет бонусных VIP-объявлений.",
        )

      cur.execute(
          "UPDATE user_bonuses SET vip_ads_count = vip_ads_count - 1 WHERE"
          " user_id = ?",
          (uid,),
      )

    st["is_vip"] = 1
    finalize_ad_creation(call.message, uid, st)

  elif data == "ad_type_vip_star":
    chat_id = call.message.chat.id
    title = "VIP-объявление"
    description = "Публикация VIP-объявления в торговом боте за 1 Telegram Star."
    payload = f"vip_ad_{uid}_{int(time.time())}"
    currency = "XTR"
    prices = [types.LabeledPrice(label="VIP-объявление", amount=1)]

    try:
      bot.send_invoice(
          chat_id=chat_id,
          title=title,
          description=description,
          invoice_payload=payload,
          provider_token="",
          currency=currency,
          prices=prices,
      )
    except Exception as e:
      logger.error(f"Ошибка счета VIP-объявления: {e}")
      safe_send_message(chat_id, "⚠️ Не удалось создать счет за 1 звезду.")


def finalize_ad_creation(m_obj, uid, st):
  clear_state(uid)
  srv = get_user_server(uid)
  is_buy = st["type"] == "buy"
  table = "pending_buy_posts" if is_buy else "pending_posts"
  username = m_obj.from_user.username or str(uid)

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO {table} (user_id, username, server, category, text,"
        " photo, is_vip) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            uid,
            username,
            srv,
            st["category"],
            st["text"],
            st["photo"],
            st["is_vip"],
        ),
    )

  set_user_last_ad_time(uid, time.time())
  chat_id = m_obj.chat.id if hasattr(m_obj, "chat") else m_obj.from_user.id

  safe_send_message(
      chat_id,
      "✅ <b>Ваше объявление успешно отправлено на модерацию администраторам!</b>"
      " Как только модератор проверит его, оно появится в ленте.",
      reply_markup=kb_main_menu(uid),
  )


# ==========================================
# МОДУЛЬ УДАЛЕНИЯ АКТИВНЫХ ОБЪЯВЛЕНИЙ (АДМИН / ПОЛЬЗОВАТЕЛЬ)
# ==========================================
@bot.callback_query_handler(
    func=lambda c: c.data.startswith("del_active_ad_")
    or c.data.startswith("del_active_buy_")
)
def cb_delete_active_ad(call):
  if not is_admin_or_owner(call.from_user):
    try:
      return bot.answer_callback_query(
          call.id, "⛔ Нет прав администратора!", show_alert=True
      )
    except Exception:
      return

  data = call.data
  is_buy = "del_active_buy_" in data
  prefix = "del_active_buy_" if is_buy else "del_active_ad_"
  try:
    aid = int(data.replace(prefix, ""))
  except ValueError:
    return

  table = "active_buy_ads" if is_buy else "active_ads"

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table} WHERE id = ?", (aid,))
    ad = cur.fetchone()
    if not ad:
      try:
        bot.answer_callback_query(
            call.id, "⚠️ Объявление уже удалено или не найдено.", show_alert=True
        )
        bot.delete_message(call.message.chat.id, call.message.message_id)
      except Exception:
        pass
      return

    cur.execute(f"DELETE FROM {table} WHERE id = ?", (aid,))
    admin_uname = call.from_user.username or str(call.from_user.id)
    cur.execute(
        "INSERT INTO admin_action_logs (admin_username, action, target,"
        " timestamp) VALUES (?, ?, ?, ?)",
        (
            admin_uname,
            "Удаление активного объявления",
            f"Объявление #{aid} ({ad['server']})",
            time.time(),
        ),
    )

  try:
    bot.answer_callback_query(
        call.id, "✅ Объявление успешно удалено администратором."
    )
    bot.delete_message(call.message.chat.id, call.message.message_id)
  except Exception:
    with contextlib.suppress(Exception):
      safe_send_message(
          call.message.chat.id,
          f"✅ Объявление #{aid} успешно удалено администратором.",
      )


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("del_my_ad_")
    or c.data.startswith("del_my_buy_ad_")
)
def cb_delete_my_ad(call):
  uid = call.from_user.id
  data = call.data
  is_buy = "del_my_buy_ad_" in data
  prefix = "del_my_buy_ad_" if is_buy else "del_my_ad_"
  try:
    aid = int(data.replace(prefix, ""))
  except ValueError:
    return

  table = "active_buy_ads" if is_buy else "active_ads"

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        f"SELECT * FROM {table} WHERE id = ? AND user_id = ?", (aid, uid)
    )
    ad = cur.fetchone()
    if not ad and not is_admin_or_owner(call.from_user):
      try:
        return bot.answer_callback_query(
            call.id,
            "⚠️ Объявление не найдено или принадлежит другому пользователю.",
            show_alert=True,
        )
      except Exception:
        return

    if not ad and is_admin_or_owner(call.from_user):
      cur.execute(f"SELECT * FROM {table} WHERE id = ?", (aid,))
      ad = cur.fetchone()

    if not ad:
      try:
        bot.answer_callback_query(
            call.id, "⚠️ Объявление уже удалено.", show_alert=True
        )
        bot.delete_message(call.message.chat.id, call.message.message_id)
      except Exception:
        pass
      return

    cur.execute(f"DELETE FROM {table} WHERE id = ?", (aid,))

  try:
    bot.answer_callback_query(call.id, "✅ Объявление успешно удалено!")
    bot.delete_message(call.message.chat.id, call.message.message_id)
  except Exception:
    with contextlib.suppress(Exception):
      safe_send_message(
          call.message.chat.id, f"✅ Объявление #{aid} успешно удалено."
      )


# ==========================================
# ДОПОЛНИТЕЛЬНЫЕ ИНТЕГРИРОВАННЫЕ МОДУЛИ
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
  markup.row(types.KeyboardButton("↩️ Назад в меню"))

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
      f" <b>@{MANAGER_USERNAME}</b> 🤝"
  )
  safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(uid))


# ==========================================
# МОДУЛЬ: КУРС VC И КАЛЬКУЛЯТОР
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
      f"Используйте кнопки ниже для пересчета валюты:"
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
        " <code>1.5к</code>):",
        reply_markup=kb_back(),
    )
  elif data == "vc_conv_to_vc":
    update_state(uid, vc_calc_mode="to_vc")
    safe_send_message(
        call.message.chat.id,
        "🧮 Введите сумму в <b>долларах ($)</b> (например: <code>15кк</code>,"
        " <code>1000000</code>):",
        reply_markup=kb_back(),
    )
  elif data == "vc_change_rate":
    if not is_admin_or_owner(call.from_user):
      return safe_send_message(call.message.chat.id, "⛔ Доступ запрещен.")
    update_state(uid, vc_setting_rate=True)
    rate = get_vc_rate()
    safe_send_message(
        call.message.chat.id,
        f"⚙️ Текущий курс: <b>1 VC = {rate} $</b>\n\nВведите новый курс (целое"
        " число в долларах):",
        reply_markup=kb_back(),
    )


@bot.message_handler(
    func=lambda m: get_state(m.from_user.id).get("vc_calc_mode") is not None
    or get_state(m.from_user.id).get("vc_setting_rate") is True
)
def process_vc_input(m):
  uid = m.from_user.id
  if m.text == "↩️ Назад в меню":
    clear_state(uid)
    return safe_send_message(
        m.chat.id, "↩️ Возвращаем в главное меню.", reply_markup=kb_main_menu(uid)
    )

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
        "⚠️ Не удалось распознать сумму. Введите число (например: 100, 1.5кк).",
        reply_markup=kb_main_menu(uid),
    )

  if mode == "to_usd":
    result = val * rate
    text = (
        f"🧮 <b>Результат расчета:</b>\n\n💎 {val:,.0f} VC = <b>{result:,.0f}"
        f" $</b>\n<i>(Курс: 1 VC = {rate:,.0f} $)</i>"
    )
  else:
    if rate == 0:
      return safe_send_message(m.chat.id, "⚠️ Ошибка: курс равен 0.")
    result = val / rate
    text = (
        f"🧮 <b>Результат расчета:</b>\n\n💵 {val:,.0f} $ = <b>{result:,.2f}"
        f" VC</b>\n<i>(Курс: 1 VC = {rate:,.0f} $)</i>"
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
    safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(uid))
  else:
    safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(uid))
    for a in ads:
      aid = a["id"]
      markup = types.InlineKeyboardMarkup()
      markup.add(
          types.InlineKeyboardButton(
              "❌ Удалить объявление", callback_data=f"del_my_ad_{aid}"
          )
      )
      safe_send_message(
          m.chat.id,
          f"▪️ <b>Продажа (#{aid}):</b>\n{html.escape(a['text'])}",
          reply_markup=markup,
      )
    for a in buy_ads:
      aid = a["id"]
      markup = types.InlineKeyboardMarkup()
      markup.add(
          types.InlineKeyboardButton(
              "❌ Удалить объявление", callback_data=f"del_my_buy_ad_{aid}"
          )
      )
      safe_send_message(
          m.chat.id,
          f"▪️ <b>Скупка (#{aid}):</b>\n{html.escape(a['text'])}",
          reply_markup=markup,
      )


def show_favorites(m):
  safe_send_message(
      m.chat.id,
      "❤️ <b>Сохраненные объявления:</b>\n\nСписок избранных товаров пуст.",
      reply_markup=kb_main_menu(m.from_user.id),
  )


def start_search(m):
  safe_send_message(
      m.chat.id,
      "🔍 <b>Поиск товара в базе:</b>\n\nВведите ключевое слово или название"
      " предмета:",
      reply_markup=kb_back(),
  )
  update_state(m.from_user.id, searching_keyword=True)


@bot.message_handler(
    func=lambda m: get_state(m.from_user.id).get("searching_keyword") is True
)
def process_search_keyword(m):
  uid = m.from_user.id
  if m.text == "↩️ Назад в меню":
    clear_state(uid)
    return safe_send_message(
        m.chat.id, "↩️ Возвращаем в главное меню.", reply_markup=kb_main_menu(uid)
    )

  keyword = m.text.strip().lower()
  clear_state(uid)
  srv = get_user_server(uid)

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM active_ads WHERE server = ? AND (LOWER(text) LIKE ? OR"
        " LOWER(category) LIKE ?) ORDER BY id DESC LIMIT 10",
        (srv, f"%{keyword}%", f"%{keyword}%"),
    )
    ads = cur.fetchall()

  text = (
      f"🔍 Результаты поиска по запросу '<b>{html.escape(keyword)}</b>' на"
      f" сервере <b>{html.escape(srv)}</b>:\n\n"
  )
  if not ads:
    text += "Ничего не найдено по вашему запросу."
    safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(uid))
  else:
    safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(uid))
    for a in ads:
      aid = a["id"]
      markup = types.InlineKeyboardMarkup()
      markup.add(
          types.InlineKeyboardButton(
              "✉️ Связаться с продавцом", callback_data=f"contact_seller_{aid}"
          )
      )
      if is_admin_or_owner(m.from_user):
        markup.add(
            types.InlineKeyboardButton(
                "❌ Удалить объявление (Админ)",
                callback_data=f"del_active_ad_{aid}",
            )
        )
      cap = f"🏷 <b>Объявление продажи #{aid}</b>\n\n{html.escape(a['text'])}"
      if a["photo"]:
        safe_send_photo(m.chat.id, a["photo"], caption=cap, reply_markup=markup)
      else:
        safe_send_message(m.chat.id, cap, reply_markup=markup)


def manage_subscriptions(m):
  safe_send_message(
      m.chat.id,
      "🔔 <b>Уведомления о поиске:</b>\n\nУ вас нет активных подписок.",
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
    safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(uid))
  else:
    safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(uid))
    for a in ads:
      aid = a["id"]
      markup = types.InlineKeyboardMarkup()
      markup.add(
          types.InlineKeyboardButton(
              "✉️ Связаться с продавцом", callback_data=f"contact_seller_{aid}"
          )
      )
      if is_admin_or_owner(m.from_user):
        markup.add(
            types.InlineKeyboardButton(
                "❌ Удалить объявление (Админ)",
                callback_data=f"del_active_ad_{aid}",
            )
        )
      cap = f"🏷 <b>Объявление продажи #{aid}</b>\n\n{html.escape(a['text'])}"
      if a["photo"]:
        safe_send_photo(m.chat.id, a["photo"], caption=cap, reply_markup=markup)
      else:
        safe_send_message(m.chat.id, cap, reply_markup=markup)


# ==========================================
# ПЕРЕХВАТЧИК НАВИГАЦИИ И КНОПОК «НАЗАД»
# ==========================================
def should_override_nav(msg):
  if not msg.text:
    return False
  if msg.text in ["❌ Отменить действие", "↩️ Назад в меню"]:
    return True

  uid = msg.from_user.id
  st = get_state(uid)

  is_in_active_input = (
      st.get("posting_ad", {}).get("step")
      in ["category", "text_or_photo", "choose_ad_type"]
      or st.get("searching_keyword")
      or st.get("vc_setting_rate")
      or st.get("vc_calc_mode")
      or st.get("barter_input")
      or st.get("auction_create_step")
      or st.get("owner_action_input")
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
  if m.text in ["❌ Отменить действие", "↩️ Назад в меню"]:
    clear_state(m.from_user.id)
    return safe_send_message(
        m.chat.id,
        "↩️ Возвращаем в главное меню.",
        reply_markup=kb_main_menu(m.from_user.id),
    )

  if m.text == "🌐 Сменить игровой сервер":
    change_server(m)
  elif m.text == "💎 VIP-статус":
    info_premium(m)
  elif m.text == "📊 Анализ цен на сервере":
    show_average_prices(m)
  elif m.text == "📤 Продать товар":
    start_add_ad(m)
  elif m.text == "📥 Скупить товар":
    start_add_buy_ad(m)
  elif m.text == "💱 Курс VC и калькулятор":
    show_vc_menu(m)
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
      "📢 Введите текст или отправьте пост для рассылки всем пользователям:",
      reply_markup=kb_back(),
  )


@bot.message_handler(
    content_types=["text", "photo"],
    func=lambda m: get_state(m.from_user.id).get("broadcast_input") is True,
)
def process_broadcast(m):
  uid = m.from_user.id
  if m.text == "↩️ Назад в меню":
    clear_state(uid)
    return safe_send_message(
        m.chat.id, "↩️ Возвращаем в главное меню.", reply_markup=kb_main_menu(uid)
    )

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
      f"✅ <b>Рассылка завершена!</b>\n\n📤 Успешно:"
      f" {success}\n❌ Ошибок / заблокировали бота: {failed}",
      reply_markup=kb_main_menu(uid),
  )


# ==========================================
# МОДУЛЬ УПРАВЛЕНИЯ ВЛАДЕЛЬЦА И АДМИНОВ
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
  safe_send_message(m.chat.id, prompts[action_type], reply_markup=kb_back())


@bot.message_handler(
    func=lambda m: get_state(m.from_user.id).get("owner_action_input")
    is not None
)
def process_owner_action_input(m):
  uid = m.from_user.id
  if m.text == "↩️ Назад в меню":
    clear_state(uid)
    return safe_send_message(
        m.chat.id, "↩️ Возвращаем в главное меню.", reply_markup=kb_main_menu(uid)
    )

  st = get_state(uid)
  action_type = st.get("owner_action_input")
  target_str = m.text.strip()

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
      res_text = (
          f"✅ Игрок <b>{html.escape(target_str)}</b> успешно заблокирован."
      )

    elif action_type == "unban":
      b_target = str(target_uid) if target_uid else target_str
      cur.execute(
          "DELETE FROM bans WHERE target = ? OR target = ?",
          (b_target, target_uname),
      )
      res_text = f"✅ Игрок <b>{html.escape(target_str)}</b> разблокирован."

    elif action_type == "add_admin":
      if not target_uid:
        res_text = (
            f"⚠️ Пользователь {target_str} не найден в базе данных бота."
        )
      else:
        cur.execute(
            "INSERT OR REPLACE INTO approved_admins (user_id, username) VALUES"
            " (?, ?)",
            (target_uid, target_uname),
        )
        res_text = (
            f"👑 Пользователь @{target_uname} (ID: {target_uid}) назначен"
            " администратором!"
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
      res_text = (
          f"🚫 Администратор <b>{html.escape(target_str)}</b> снят с должности."
      )
    else:
      res_text = "✅ Действие выполнено."

  try:
    bot.edit_message_text(res_text, call.message.chat.id, call.message.message_id)
  except Exception:
    safe_send_message(call.message.chat.id, res_text)

  admin_panel(call.message)


# ==========================================
# УНИФИЦИРОВАННЫЙ ЦЕНТР ЛОГОВ
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
      f"📋 <b>Единый центр логов системы (@{OWNER_USERNAME})</b>\n\nВыберите"
      " нужный пункт для выгрузки файлов:"
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
          "📢 Логи действий админов (файлом)",
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

  send_log_file(
      call.message.chat.id,
      f"auction_{aid}_logs.txt",
      log_text,
      caption=(
          f"📁 <b>Файл с логами аукциона #{aid}</b>\nТовар:"
          f" <b>{html.escape(auc['item_name'])}</b>"
      ),
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

  log_text = "ИСТОРИЯ ОБЩЕНИЯ ИГРОКОВ В СДЕЛКАХ\n" + "=" * 50 + "\n\n"
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
      caption="📁 <b>Файл истории переписок игроков</b>",
  )


@bot.callback_query_handler(func=lambda c: c.data == "owner_view_admin_ads")
def cb_owner_view_admin_ads(call):
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT * FROM admin_action_logs ORDER BY id DESC LIMIT 100")
    logs = cur.fetchall()

  log_text = "ЛОГИ ДЕЙСТВИЙ И АДМИНИСТРИРОВАНИЯ\n" + "=" * 50 + "\n\n"
  if logs:
    for l in logs:
      dt = datetime.fromtimestamp(l["timestamp"]).strftime("%d.%m %H:%M:%S")
      log_text += (
          f"[{dt}] Администратор (@{l['admin_username']}): Действие:"
          f" {l['action']} | Цель: {l['target']}\n"
      )
  else:
    log_text += "Логи действий пустые."

  send_log_file(
      call.message.chat.id,
      "admin_actions_logs.txt",
      log_text,
      caption="📁 <b>Файл логов банов и модерации</b>",
  )


# ==========================================
# МОДУЛЬ: БАРТЕР / ОБМЕН
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
      "Хотите предложить свое имущество на обмен?",
      reply_markup=markup_btn,
  )


@bot.callback_query_handler(func=lambda c: c.data == "barter_add_start")
def cb_barter_add_start(call):
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass

  warning_text = (
      "⚠️ <b>Внимание! Безопасность сделок:</b>\nАдминистрация бота <b>не несет"
      " ответственности</b> за обмен имущества между игроками. Совершайте"
      " сделки на свой страх и риск!"
  )
  safe_send_message(call.message.chat.id, warning_text)

  update_state(call.from_user.id, barter_input=True)
  safe_send_message(
      call.message.chat.id,
      "🔄 Опишите, что вы отдаете и что хотите получить взамен:",
      reply_markup=kb_back(),
  )


@bot.message_handler(
    content_types=["text", "photo"],
    func=lambda m: get_state(m.from_user.id).get("barter_input"),
)
def process_barter_create(m):
  uid = m.from_user.id
  if m.text == "↩️ Назад в меню":
    clear_state(uid)
    return safe_send_message(
        m.chat.id, "↩️ Возвращаем в главное меню.", reply_markup=kb_main_menu(uid)
    )

  srv = get_user_server(uid)
  text = m.text or m.caption
  photo = m.photo[-1].file_id if m.photo else None
  clear_state(uid)

  if not text:
    return safe_send_message(
        m.chat.id, "⚠️ Описание не может быть пустым.", reply_markup=kb_main_menu(uid)
    )

  if not check_auto_moderation(text):
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
# МОДУЛЬ: АУКЦИОНЫ
# ==========================================
def check_auction_working_hours() -> bool:
  now_time = get_msk_time().time()
  return dtime(8, 0, 0) <= now_time <= dtime(22, 0, 0)


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
      f"✅ Лот аукциона #{aid} успешно удален.",
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
        "❌ Выставлять товары на аукцион можно строго с <b>08:00 до 22:00"
        " МСК</b>.",
    )
  update_state(call.from_user.id, auction_create_step="item_name")
  safe_send_message(
      call.message.chat.id,
      "🏛 Введите название товара для аукциона:",
      reply_markup=kb_back(),
  )


@bot.message_handler(
    func=lambda m: get_state(m.from_user.id).get("auction_create_step")
    == "item_name"
)
def process_auc_item(m):
  uid = m.from_user.id
  if m.text == "↩️ Назад в меню":
    clear_state(uid)
    return safe_send_message(
        m.chat.id, "↩️ Возвращаем в главное меню.", reply_markup=kb_main_menu(uid)
    )

  update_state(uid, auc_item=m.text.strip(), auction_create_step="start_price")
  safe_send_message(
      m.chat.id, "💰 Введите начальную цену лота (в $):", reply_markup=kb_back()
  )


@bot.message_handler(
    func=lambda m: get_state(m.from_user.id).get("auction_create_step")
    == "start_price"
)
def process_auc_price(m):
  uid = m.from_user.id
  if m.text == "↩️ Назад в меню":
    clear_state(uid)
    return safe_send_message(
        m.chat.id, "↩️ Возвращаем в главное меню.", reply_markup=kb_main_menu(uid)
    )

  srv = get_user_server(uid)
  try:
    price = parse_flexible_price(m.text)
  except ValueError:
    return safe_send_message(
        m.chat.id, "⚠️ Введите корректную сумму (например: 1кк, 500к, 1.5кк)."
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

  safe_send_message(
      m.chat.id,
      "✅ Ваш товар успешно выставлен на аукцион!",
      reply_markup=kb_main_menu(uid),
  )


# ==========================================
# ОБРАБОТЧИК СВЯЗИ ПРОДАВЦА И ПОКУПАТЕЛЯ
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("contact_seller_"))
def cb_contact_seller(call):
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass

  aid = int(call.data.replace("contact_seller_", ""))
  buyer_id = call.from_user.id

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT user_id, text FROM active_ads WHERE id = ?", (aid,))
    ad = cur.fetchone()
    if not ad:
      cur.execute("SELECT user_id, text FROM active_buy_ads WHERE id = ?", (aid,))
      ad = cur.fetchone()
    if not ad:
      cur.execute("SELECT user_id, text FROM barter_ads WHERE id = ?", (aid,))
      ad = cur.fetchone()

  if not ad:
    return safe_send_message(
        call.message.chat.id, "⚠️ Объявление не найдено или уже удалено."
    )

  seller_id = ad["user_id"]
  if buyer_id == seller_id:
    return safe_send_message(
        call.message.chat.id, "⚠️ Вы не можете связаться сами с собой."
    )

  buyer_uname = call.from_user.username or f"ID: {buyer_id}"
  safe_send_message(
      seller_id,
      f"📩 <b>Игрок @{html.escape(buyer_uname)} хочет связаться с вами по"
      f" поводу объявления #{aid}:</b>\n\n<i>\"{html.escape(ad['text'][:100])}\"</i>\n\nНапишите"
      f" ему в личные сообщения!",
  )
  safe_send_message(
      call.message.chat.id,
      "✅ Уведомление успешно отправлено продавцу! Ожидайте ответа в личных"
      " сообщениях.",
  )


# ==========================================
# ЗАПУСК БОТА
# ==========================================
@bot.message_handler(commands=["start"])
def cmd_start(m):
  uid = m.from_user.id
  username = m.from_user.username or ""
  register_user(uid, username)

  if len(m.text.split()) > 1:
    param = m.text.split()[1]
    if param.startswith("ref_"):
      try:
        referrer_id = int(param.replace("ref_", ""))
        if referrer_id != uid:
          with db_lock, get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR IGNORE INTO referrals (referrer_id, referred_id,"
                " last_active_date) VALUES (?, ?, ?)",
                (referrer_id, uid, get_msk_time().strftime("%Y-%m-%d")),
            )
      except Exception:
        pass

  srv = get_user_server(uid)
  text = (
      f"👋 <b>Приветствую, {html.escape(m.from_user.first_name)}!</b> 🌟\n\n"
      f"🤖 Добро пожаловать в неофициальный торговый бот Arizona RP!\n"
      f"🌐 Ваш текущий сервер: <b>{html.escape(srv)}</b>\n\n"
      f"Используйте удобное меню ниже для управления объявлениями, поиска"
      f" товаров и участия в аукционах! 👇"
  )
  safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(uid))


if __name__ == "__main__":
  logger.info("Бот успешно запущен и работает в многопоточном режиме...")
  bot.infinity_polling(timeout=60, long_polling_timeout=60)
