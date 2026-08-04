from datetime import datetime, time as dtime
import html
import logging
import os
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

TOKEN = "8916669266:AAFall7GhTxs_ZAlMr4_d4W_XMZnunkY2NA"
YT_CHANNEL_URL = "https://youtube.com/@bounty_squad31"

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=20)

OWNER_USERNAME = "bounqy"
ADMIN_USERNAMES = {"bounqy31", "bounqy"}

DB_NAME = "smi_bot.db"
db_lock = threading.Lock()
state_lock = threading.Lock()

ADS_PER_PAGE = 5

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

SYSTEM_NAV_BUTTONS = [
    "🔍 Найти товар в базе",
    "❤️ Сохраненные",
    "🔔 Уведомления о поиске",
    "📋 Мои публикации",
    "📊 Анализ цен на сервере",
    "📖 Справка и правила",
    "📤 Продать товар",
    "📥 Скупить товар",
    "💱 Курс VC и калькулятор",
    "💎 VIP-статус",
    "🌐 Сменить игровой сервер",
    "👑 Админ-панель",
    "📝 Стать редактором / админом",
    "❌ Отменить действие",
] + CATEGORIES

BAD_WORDS = [
    "хуй",
    "пизд",
    "еб",
    "бля",
    "сук",
    "залуп",
    "мраз",
    "ебан",
    "долбоеб",
    "samp-rp",
    "advance",
    "Arizona V",
    "Diamond",
    "продажа вирт",
    "продам вирты",
]

# ==========================================
# ПОТОКОБЕЗОПАСНОЕ УПРАВЛЕНИЕ СОСТОЯНИЯМИ
# ==========================================
user_states = {}


def get_state(uid: int) -> dict:
  with state_lock:
    return user_states.get(uid, {}).copy()


def set_state(uid: int, data: dict):
  with state_lock:
    srv = user_states.get(uid, {}).get("server")
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
    if uid in user_states:
      srv = user_states[uid].get("server")
      user_states[uid] = {"server": srv} if srv else {}


# ==========================================
# БЕЗОПАСНАЯ ОТПРАВКА СООБЩЕНИЙ (HTML)
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


# ==========================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
# ==========================================
def init_db():
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
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
                last_updated REAL
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
                last_updated REAL
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
            CREATE TABLE IF NOT EXISTS chat_logs_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                receiver_id INTEGER,
                text TEXT,
                timestamp REAL
            )
        """)

    for tbl in [
        "active_ads",
        "pending_posts",
        "active_buy_ads",
        "pending_buy_posts",
    ]:
      try:
        cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN is_edited INTEGER DEFAULT 0")
      except sqlite3.OperationalError:
        pass

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
                last_ad_time REAL
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
            CREATE TABLE IF NOT EXISTS seller_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER,
                buyer_id INTEGER,
                rating INTEGER,
                comment TEXT
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
            CREATE TABLE IF NOT EXISTS admin_apps (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                application_text TEXT
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS approved_admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT
            )
        """)

    conn.commit()


init_db()

# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ И ВРЕМЯ ПО МСК
# ==========================================


def get_msk_time():
  try:
    return datetime.now(ZoneInfo("Europe/Moscow"))
  except Exception:
    return datetime.now()


def check_working_hours() -> bool:
  now_time = get_msk_time().time()
  return dtime(8, 0, 1) <= now_time <= dtime(22, 0, 1)


def background_cleanup_ads():
  last_cleaned_date = None
  while True:
    time.sleep(30)
    try:
      now_msk = get_msk_time()
      current_time = now_msk.time()
      current_date = now_msk.date()

      if current_time >= dtime(22, 0, 1) or current_time < dtime(8, 0, 1):
        if last_cleaned_date != current_date:
          with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM active_ads")
            cur.execute("DELETE FROM active_buy_ads")
            cur.execute("DELETE FROM pending_posts")
            cur.execute("DELETE FROM pending_buy_posts")
            conn.commit()
          logger.info(
              f"Ночная очистка объявлений выполнена в {current_time} МСК."
          )
          last_cleaned_date = current_date
    except Exception as e:
      logger.error(f"Ошибка фоновой ночной очистки: {e}")


threading.Thread(target=background_cleanup_ads, daemon=True).start()

# ==========================================
# ФОНОВАЯ ПРОВЕРКА YOUTUBE СТРИМОВ
# ==========================================


def background_youtube_stream_checker():
  last_live_id = None
  time.sleep(15)
  while True:
    try:
      headers = {
          "User-Agent": (
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          )
      }
      resp = requests.get(
          f"{YT_CHANNEL_URL}/live",
          headers=headers,
          allow_redirects=True,
          timeout=15,
      )
      final_url = resp.url

      if "/watch?v=" in final_url:
        video_id = final_url.split("v=")[1].split("&")[0]
        if video_id != last_live_id:
          last_live_id = video_id
          admin_chats = get_admin_chat_ids()
          notif_text = (
              "🔴 <b>ВНИМАНИЕ! СТРИМ НА YOUTUBE НАЧАЛСЯ!</b> 🎥\n\n"
              "📡 Канал: <b>Bounty Squad</b>\n"
              f"🔗 Ссылка: https://www.youtube.com/watch?v={video_id}"
          )
          for chat_id in admin_chats:
            try:
              safe_send_message(chat_id, notif_text)
            except Exception as e:
              logger.error(
                  "Не удалось отправить уведомление о стриме в чат"
                  f" {chat_id}: {e}"
              )
      else:
        last_live_id = None
    except Exception as e:
      logger.error(f"Ошибка в фоновой проверке стримов YouTube: {e}")

    time.sleep(180)


threading.Thread(target=background_youtube_stream_checker, daemon=True).start()


def get_vc_rate() -> float:
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute("SELECT value FROM bot_settings WHERE key = 'vc_rate'")
    row = cur.fetchone()
    return float(row[0]) if row else 95000.0


def set_vc_rate(rate: float):
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('vc_rate',"
        " ?)",
        (str(rate),),
    )
    conn.commit()


def register_admin_chat(chat_id: int):
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO admin_chats (chat_id) VALUES (?)", (chat_id,)
    )
    conn.commit()


def get_admin_chat_ids():
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM admin_chats")
    return [row[0] for row in cur.fetchall()]


def get_all_admin_ids():
  admin_ids = set(get_admin_chat_ids())
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM approved_admins")
    for row in cur.fetchall():
      admin_ids.add(row[0])
  return list(admin_ids)


def get_owner_user_id() -> int:
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id FROM user_data WHERE LOWER(username) = ?",
        (OWNER_USERNAME.lower(),),
    )
    row = cur.fetchone()
    if row:
      return row[0]
  return 0


def is_owner(user) -> bool:
  return bool(
      user and user.username and user.username.lower() == OWNER_USERNAME.lower()
  )


def is_admin_or_owner(user) -> bool:
  if not user:
    return False
  if is_owner(user):
    return True
  uname = user.username.lower().lstrip("@") if user.username else ""
  if uname in ADMIN_USERNAMES:
    return True
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM approved_admins WHERE user_id = ? OR LOWER(username) = ?",
        (user.id, uname),
    )
    if cur.fetchone():
      return True
  return False


def is_admin_or_owner_id(user_id: int) -> bool:
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM approved_admins WHERE user_id = ?", (user_id,))
    if cur.fetchone():
      return True
    cur.execute("SELECT username FROM user_data WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row and row[0]:
      uname = row[0].lower().lstrip("@")
      if uname == OWNER_USERNAME.lower() or uname in ADMIN_USERNAMES:
        return True
    cur.execute("SELECT 1 FROM admin_chats WHERE chat_id = ?", (user_id,))
    if cur.fetchone():
      return True
  return False


def is_user_premium(user_id: int) -> bool:
  if is_admin_or_owner_id(user_id):
    return True
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT expires_at FROM premium_users WHERE user_id = ?", (user_id,)
    )
    row = cur.fetchone()
  return bool(row and row[0] > time.time())


def get_seller_rating_info(seller_id: int) -> str:
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT AVG(rating), COUNT(rating) FROM seller_reviews WHERE seller_id"
        " = ?",
        (seller_id,),
    )
    row = cur.fetchone()
  if not row or row[1] == 0:
    return "⭐ Нет оценок (0)"
  return f"⭐ {row[0]:.1f} / 5 (Отзывов: {row[1]})"


def check_auto_moderation(text: str) -> bool:
  if not text:
    return True
  lower_text = text.lower()
  for word in BAD_WORDS:
    if word in lower_text:
      return False
  return True


def get_user_last_ad_time(user_id):
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT last_ad_time FROM user_data WHERE user_id = ?", (user_id,)
    )
    row = cur.fetchone()
    return row[0] if row else 0


def set_user_last_ad_time(user_id, t):
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO user_data (user_id, last_ad_time) VALUES (?,"
        " ?)",
        (user_id, t),
    )
    conn.commit()


def register_user(user_id, username=None):
  uname = username.lstrip("@").lower() if username else None
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO user_data (user_id, username, last_ad_time)"
        " VALUES (?, ?, 0)",
        (user_id, uname),
    )
    if uname:
      cur.execute(
          "UPDATE user_data SET username = ? WHERE user_id = ?", (uname, user_id)
      )
    conn.commit()


def is_banned(user) -> bool:
  if not user:
    return False
  uname = user.username.lower().lstrip("@") if user.username else ""
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM bans WHERE (is_id = 1 AND target = ?) OR (is_id = 0 AND"
        " target = ?)",
        (str(user.id), uname),
    )
    res = cur.fetchone()
  return bool(res)


def verify_admin_callback(call) -> bool:
  if not is_admin_or_owner(call.from_user):
    try:
      bot.answer_callback_query(
          call.id, "⛔ Нет доступа к функциям СМИ!", show_alert=True
      )
    except Exception:
      pass
    return False
  return True


def clean_server_name(server: str) -> str:
  return server.split(" ", 1)[-1] if " " in server else server


def format_smi_post(
    server: str,
    category: str,
    text: str,
    player_username: str,
    editor_username: str,
    is_vip: bool = False,
    user_id: int = 0,
    is_buy: bool = False,
    viewer_user_id: int = 0,
) -> str:
  clean_srv = html.escape(clean_server_name(server))
  cat_esc = html.escape(category)
  text_esc = html.escape(text)

  is_prem = is_user_premium(user_id) if user_id else False
  is_viewer_vip_or_admin = is_admin_or_owner_id(viewer_user_id) or is_user_premium(
      viewer_user_id
  )

  if is_vip and not is_viewer_vip_or_admin:
    player_contact = "🛡️ <i>[Контакт скрыт (VIP-привилегия)]</i>"
    vip_header = "👑 <b>[VIP ОБЪЯВЛЕНИЕ]</b>\n"
  else:
    p_uname = (
        html.escape(player_username)
        if player_username and player_username != "Без юзернейма"
        else ""
    )
    player_contact = f"@{p_uname}" if p_uname else "Не указан"
    vip_header = "👑 <b>[VIP ОБЪЯВЛЕНИЕ]</b>\n" if is_vip else ""

  ed_uname = html.escape(editor_username) if editor_username else "СМИ"
  editor_contact = f"@{ed_uname}"
  prem_icon = "💎 " if is_prem else ""
  rating_str = get_seller_rating_info(user_id) if user_id else ""
  ad_type_label = "📥 <b>[СКУПКА]</b>" if is_buy else "📤 <b>[ПРОДАЖА]</b>"

  return (
      f"{vip_header}"
      f"📰 | <b>[СМИ {clean_srv}] Объявление:</b> {ad_type_label} {prem_icon}\n"
      f"📞 <b>Контакт:</b> {player_contact} | {rating_str}\n\n"
      f"{text_esc}\n\n"
      f"📂 <b>Раздел:</b> {cat_esc}\n"
      f"👨‍💻 <b>Отредактировал:</b> {editor_contact}"
  )


# ==========================================
# КЛАВИАТУРЫ
# ==========================================
def kb_servers():
  m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  for i in range(0, len(SERVERS), 2):
    m.add(*[types.KeyboardButton(s) for s in SERVERS[i : i + 2]])
  m.add(types.KeyboardButton("📖 Справка и правила"))
  m.add(
      types.KeyboardButton("💎 VIP-статус"), types.KeyboardButton("👑 Админ-панель")
  )
  m.add(types.KeyboardButton("📝 Стать редактором / админом"))
  return m


def kb_main_menu():
  m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  m.add("🌐 Сменить игровой сервер")
  m.add("💍 Аксессуары и вещи", "🚗 Транспорт и тюнинг")
  m.add("👕 Скины и охранники", "🏠 Недвижимость и бизнесы")
  m.add("📦 Ресурсы и материалы")
  m.add("📤 Продать товар", "📥 Скупить товар")
  m.add("💱 Курс VC и калькулятор")
  m.add("🔍 Найти товар в базе", "❤️ Сохраненные")
  m.add("🔔 Уведомления о поиске", "📋 Мои публикации")
  m.add("📊 Анализ цен на сервере")
  m.add("💎 VIP-статус")
  m.add("👑 Админ-панель", "📝 Стать редактором / админом")
  return m


def kb_cancel():
  return types.ReplyKeyboardMarkup(resize_keyboard=True).add(
      types.KeyboardButton("❌ Отменить действие")
  )


def ikb_chat_controls(aid: int):
  markup = types.InlineKeyboardMarkup(row_width=1)
  markup.add(
      types.InlineKeyboardButton(
          "🛑 Завершить диалог", callback_data=f"stop_chat_{aid}"
      ),
      types.InlineKeyboardButton(
          "🔄 Возобновить / Начать заново", callback_data=f"resume_chat_{aid}"
      ),
  )
  return markup


def ikb_ad_actions(
    aid: int, is_fav: bool = False, user_id: int = 0, is_buy: bool = False
):
  markup = types.InlineKeyboardMarkup(row_width=2)
  fav_text = "❌ Убрать из избранного" if is_fav else "❤️ В избранное"
  markup.add(
      types.InlineKeyboardButton(
          "✉️ Написать автору", callback_data=f"contact_seller_{aid}"
      ),
      types.InlineKeyboardButton(fav_text, callback_data=f"fav_toggle_{aid}"),
  )
  if user_id and is_admin_or_owner_id(user_id):
    del_prefix = "admin_del_buy_" if is_buy else "admin_del_"
    markup.add(
        types.InlineKeyboardButton(
            "🗑 Удалить (Админ)", callback_data=f"{del_prefix}{aid}"
        )
    )
  return markup


# ==========================================
# ПЕРЕХВАТЧИК ДЛЯ ЗАБЛОКИРОВАННЫХ ПОЛЬЗОВАТЕЛЕЙ
# ==========================================
@bot.message_handler(func=lambda m: is_banned(m.from_user))
def blocked_user_message(m):
  safe_send_message(
      m.chat.id,
      "⛔ <b>Вы заблокированы в системе модерации.</b> Ваши кнопки отключены, и"
      " доступ к функциям бота ограничен.",
      reply_markup=types.ReplyKeyboardRemove(),
  )


@bot.callback_query_handler(func=lambda c: is_banned(c.from_user))
def blocked_user_callback(c):
  try:
    bot.answer_callback_query(
        c.id, "⛔ Вы заблокированы в системе и не можете использовать бота!", show_alert=True
    )
  except Exception:
    pass


# ==========================================
# УМНЫЙ МИДДЛВЕЙР НАВИГАЦИИ
# ==========================================
def should_override_nav(msg):
  if not msg.text:
    return False

  uid = msg.from_user.id
  st = get_state(uid)

  if msg.text == "❌ Отменить действие" or msg.text.startswith("/"):
    return True

  if "posting_ad" in st or "posting_buy_ad" in st:
    p_key = "posting_ad" if "posting_ad" in st else "posting_buy_ad"
    step = st[p_key].get("step")
    if step in ["text_or_photo", "waiting_choice"]:
      return False

  if (
      "admin_editing_pid" in st
      or "admin_editing_buy_pid" in st
      or "admin_editing_active_aid" in st
      or "applying_admin" in st
      or "vc_setting_rate" in st
      or "vc_calc_step" in st
      or "vc_conv_input" in st
      or "admin_action" in st
      or "editing_active_ad_id" in st
      or "searching_keyword" in st
      or "adding_subscription" in st
      or "waiting_for_new_text" in st
      or "waiting_for_username_ban" in st
      or "waiting_for_username_unban" in st
      or "waiting_for_admin_add" in st
      or "waiting_for_admin_remove" in st
      or "admin_editing_pid" in st
  ):
    return False

  if "posting_ad" in st or "posting_buy_ad" in st:
    p_key = "posting_ad" if "posting_ad" in st else "posting_buy_ad"
    step = st[p_key].get("step")
    if step == "category" and msg.text in CATEGORIES:
      return False

  if msg.text in SERVERS:
    return bool(st.get("changing_server", False) or not st.get("server"))

  nav_buttons = [
      "🔍 Найти товар в базе",
      "❤️ Сохраненные",
      "🔔 Уведомления о поиске",
      "📋 Мои публикации",
      "📊 Анализ цен на сервере",
      "📖 Справка и правила",
      "📤 Продать товар",
      "📥 Скупить товар",
      "💱 Курс VC и калькулятор",
      "💎 VIP-статус",
      "🌐 Сменить игровой сервер",
      "👑 Админ-панель",
      "📝 Стать редактором / админом",
      "❌ Отменить действие",
  ] + CATEGORIES

  return msg.text in nav_buttons


@bot.message_handler(func=should_override_nav)
def handle_navigation_override(m):
  clear_state(m.from_user.id)

  if m.text == "/start":
    cmd_start(m)
  elif m.text == "/help":
    cmd_help(m)
  elif m.text == "🌐 Сменить игровой сервер":
    change_server(m)
  elif m.text == "📖 Справка и правила":
    how_bot_works(m)
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
  elif m.text == "📝 Стать редактором / админом":
    start_admin_application(m)
  elif m.text in CATEGORIES:
    if get_state(m.from_user.id).get("viewing_buy_categories"):
      show_buy_ads_category(m)
    else:
      show_ads_category(m)
  elif m.text in SERVERS:
    select_srv(m)


# ==========================================
# ОСНОВНЫЕ КОМАНДЫ И НАВИГАЦИЯ
# ==========================================
def cancel_action(m):
  clear_state(m.from_user.id)
  safe_send_message(
      m.chat.id,
      "❌ Текущее действие отменено. Вы вернулись в главное меню.",
      reply_markup=kb_main_menu(),
  )


@bot.message_handler(commands=["start"])
def cmd_start(m):
  register_user(m.from_user.id, m.from_user.username)

  if is_banned(m.from_user):
    return safe_send_message(
        m.chat.id,
        "⛔ Вы заблокированы в системе модерации.",
        reply_markup=types.ReplyKeyboardRemove(),
    )

  if is_admin_or_owner(m.from_user):
    register_admin_chat(m.chat.id)

  update_state(m.from_user.id, changing_server=True)
  caption_text = (
      "🌟 <b>Привет! Обратите внимание: мы не официальный бот</b>, а независимый"
      " помощник для игроков Arizona RP. Мы помогаем игрокам находить"
      " аксессуары, транспорт, недвижимость и другие ценные вещи, а также"
      " следить за экономикой и курсами.\n\n🔒 <b>Безопасность:</b> Мы"
      " <b>никогда</b> не просим пароли от игровых аккаунтов или личные"
      " данные!\n\n⏱ <b>Режим работы радиоцентра:</b> ежедневно с <b>08:00:01 до"
      " 22:00:01 МСК</b>.\n\n👇 <b>Для начала работы выберите свой игровой сервер"
      " ниже:</b>"
  )
  safe_send_message(m.chat.id, caption_text, reply_markup=kb_servers())


@bot.message_handler(commands=["help"])
def cmd_help(m):
  help_text = (
      "🛠 <b>Помощь, правила и расширенный FAQ</b>\n\n❓ <b>1. Как подать"
      " объявление о продаже или скупке?</b>\n💡 <i>Выберите нужный игровой"
      " сервер в главном меню -> Нажмите «📤 Продать товар» или «📥 Скупить"
      " товар» -> Выберите категорию -> Введите товар, цену и условия ->"
      " Отправьте на модерацию редакторам.</i>\n\n❓ <b>2. Сколько времени"
      " модераторы проверяют заявки?</b>\n💡 <i>Обычно проверка занимает от"
      " силы пару минут, если редактора находятся в сети. Вы получите"
      " уведомление в чат сразу после публикации или отклонения"
      " объявления.</i>\n\n❓ <b>3. Как изменить или удалить уже"
      " опубликованное объявление?</b>\n💡 <i>В личном кабинете или разделе"
      " управления объявлениями вы можете в любой момент снять товар с"
      " публикации, изменить цену или обновить описание.</i>\n\n❓ <b>4. Как"
      " работает калькулятор Vice City и конвертер валют?</b>\n💡 <i>В разделе"
      " «💱 Курс VC и калькулятор» можно мгновенно переводить вирты в"
      " VC-баксы по актуальному курсу, а также рассчитывать выгоду перелетов и"
      " чистую прибыль с учетом комиссий.</i>\n\n❓ <b>5. Как безопасно связаться"
      " с продавцом или покупателем?</b>\n💡 <i>Под карточкой каждого активного"
      " объявления есть кнопка «✉️ Написать автору». Она открывает"
      " защищенный внутренний чат для обсуждения всех деталей сделки.</i>\n\n❓"
      " <b>6. Каковы главные правила подачи объявлений и модерации?</b>\n💡"
      " <i>Запрещено указывать нереалистичные цены, использовать нецензурную"
      " лексику, рекламировать сторонние ресурсы или нарушать правила"
      " проекта. Нарушители могут получить бан в боте.</i>\n\n❓ <b>7. Что"
      " делать, если мое объявление отклонили?</b>\n💡 <i>В системном"
      " уведомлении об отклонении всегда указана причина. Чаще всего это"
      " опечатки, отсутствие конкретики или нарушение правил. Просто исправьте"
      " текст и отправьте его повторно.</i>\n\n❓ <b>8. Куда обращаться при"
      " обнаружении багов или технических неполадок?</b>\n💡 <i>Если бот завис,"
      " работает некорректно или вы нашли ошибку, обязательно напишите об этом"
      " в наше официальное сообщество ВКонтакте: <b>@bountyarz</b>. Наша"
      " команда оперативно всё проверит!</i>\n\n⏱ <b>Дополнительная"
      " информация:</b> Радиоцентр и редакция работают ежедневно с"
      " <b>08:00:01 до 22:00:01 МСК</b>."
  )
  safe_send_message(m.chat.id, help_text, reply_markup=kb_main_menu())


def change_server(m):
  update_state(m.from_user.id, changing_server=True)
  safe_send_message(
      m.chat.id, "👇 Выберите новый игровой сервер:", reply_markup=kb_servers()
  )


def select_srv(m):
  srv = m.text
  uid = m.from_user.id
  st = get_state(uid)
  st.pop("changing_server", None)
  update_state(uid, server=srv, **st)
  safe_send_message(
      m.chat.id,
      f"✅ Игровой сервер установлен: <b>{html.escape(srv)}</b>",
      reply_markup=kb_main_menu(),
  )


def how_bot_works(m):
  text = (
      "📖 <b>Справочник: Как работает бот и радиоцентр</b>\n\n1. <b>Подача"
      " объявления:</b> Выбирается тип (продажа/скупка), сервер, категория и"
      " текст.\n2. <b>Проверка редакторами:</b> Редакторы проверяют материалы"
      " с 08:00:01 до 22:00:01 МСК.\n3. <b>Публикация:</b> Одобренное"
      " объявление уходит в ленту.\n4. <b>Инструменты VC:</b> Полноценный курс,"
      " конвертер и калькулятор прибыли для перекупщиков."
  )
  safe_send_message(m.chat.id, text)


# ==========================================
# ОТОБРАЖЕНИЕ ОБЪЯВЛЕНИЙ ПО КАТЕГОРИЯМ
# ==========================================
def show_ads_category(m):
  _show_ads(m, is_buy=False)


def show_buy_ads_category(m):
  _show_ads(m, is_buy=True)


def _show_ads(m, is_buy):
  uid = m.from_user.id
  st = get_state(uid)
  srv = st.get("server", "Phoenix")
  cat = m.text

  table = "active_buy_ads" if is_buy else "active_ads"
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        f"SELECT id, user_id, text, photo, is_vip FROM {table} WHERE server = ?"
        " AND category = ? ORDER BY is_vip DESC, id DESC LIMIT 10",
        (srv, cat),
    )
    ads = cur.fetchall()

  if not ads:
    type_str = "скупке" if is_buy else "продаже"
    return safe_send_message(
        m.chat.id,
        f"📭 В категории «{cat}» на сервере <b>{srv}</b> пока нет объявлений о"
        f" {type_str}.",
        reply_markup=kb_main_menu(),
    )

  type_str = "📥 Скупка" if is_buy else "📤 Продажа"
  safe_send_message(
      m.chat.id, f"📂 <b>{cat}</b> | {srv} | {type_str}\nПоследние 10 объявлений:"
  )

  for aid, owner_id, text, photo, is_vip in ads:
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
      cur = conn.cursor()
      cur.execute(
          "SELECT 1 FROM favorites WHERE user_id = ? AND ad_id = ?", (uid, aid)
      )
      is_fav = bool(cur.fetchone())

    markup = ikb_ad_actions(aid, is_fav=is_fav, user_id=uid, is_buy=is_buy)
    fmt_text = html.escape(text)
    if is_vip:
      fmt_text = f"👑 <b>[VIP ОБЪЯВЛЕНИЕ]</b>\n{fmt_text}"

    if photo:
      safe_send_photo(m.chat.id, photo, caption=fmt_text, reply_markup=markup)
    else:
      safe_send_message(m.chat.id, fmt_text, reply_markup=markup)


# ==========================================
# УПРАВЛЕНИЕ ИЗБРАННЫМ И СВОИМИ ПУБЛИКАЦИЯМИ
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("fav_toggle_"))
def cb_fav_toggle(call):
  aid = int(call.data.split("_")[2])
  uid = call.from_user.id

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM favorites WHERE user_id = ? AND ad_id = ?", (uid, aid)
    )
    exists = cur.fetchone()
    if exists:
      cur.execute(
          "DELETE FROM favorites WHERE user_id = ? AND ad_id = ?", (uid, aid)
      )
      is_fav = False
      try:
        bot.answer_callback_query(call.id, "❌ Удалено из избранного")
      except Exception:
        pass
    else:
      cur.execute(
          "INSERT INTO favorites (user_id, ad_id) VALUES (?, ?)", (uid, aid)
      )
      is_fav = True
      try:
        bot.answer_callback_query(call.id, "❤️ Добавлено в избранное")
      except Exception:
        pass
    conn.commit()

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM active_buy_ads WHERE id = ?", (aid,))
    is_buy = bool(cur.fetchone())

  markup = ikb_ad_actions(aid, is_fav=is_fav, user_id=uid, is_buy=is_buy)
  try:
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
    )
  except Exception:
    pass


def show_favorites(m):
  uid = m.from_user.id
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute("SELECT ad_id FROM favorites WHERE user_id = ?", (uid,))
    favs = cur.fetchall()

  if not favs:
    return safe_send_message(
        m.chat.id,
        "❤️ У вас пока нет сохраненных (избранных) объявлений.",
        reply_markup=kb_main_menu(),
    )

  safe_send_message(m.chat.id, "❤️ <b>Ваши сохраненные объявления:</b>")
  for (aid,) in favs:
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
      cur = conn.cursor()
      cur.execute(
          "SELECT id, user_id, server, category, text, photo, is_vip FROM"
          " active_ads WHERE id = ?",
          (aid,),
      )
      row = cur.fetchone()
      is_buy = False
      if not row:
        cur.execute(
            "SELECT id, user_id, server, category, text, photo, is_vip FROM"
            " active_buy_ads WHERE id = ?",
            (aid,),
        )
        row = cur.fetchone()
        is_buy = True

    if row:
      _, _, _, _, text, photo, _ = row
      markup = ikb_ad_actions(aid, is_fav=True, user_id=uid, is_buy=is_buy)
      fmt_text = html.escape(text)
      if photo:
        safe_send_photo(m.chat.id, photo, caption=fmt_text, reply_markup=markup)
      else:
        safe_send_message(m.chat.id, fmt_text, reply_markup=markup)


def show_my_ads(m):
  uid = m.from_user.id
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, server, category, text FROM active_ads WHERE user_id = ?",
        (uid,),
    )
    sales = cur.fetchall()
    cur.execute(
        "SELECT id, server, category, text FROM active_buy_ads WHERE user_id ="
        " ?",
        (uid,),
    )
    buys = cur.fetchall()

  if not sales and not buys:
    return safe_send_message(
        m.chat.id,
        "📋 У вас нет активных опубликованных объявлений.",
        reply_markup=kb_main_menu(),
    )

  markup = types.InlineKeyboardMarkup(row_width=1)
  for aid, srv, cat, text in sales:
    markup.add(
        types.InlineKeyboardButton(
            f"🗑 [Продажа | {srv}] ID {aid}: {text[:25]}...",
            callback_data=f"my_del_sale_{aid}",
        )
    )
  for aid, srv, cat, text in buys:
    markup.add(
        types.InlineKeyboardButton(
            f"🗑 [Скупка | {srv}] ID {aid}: {text[:25]}...",
            callback_data=f"my_del_buy_{aid}",
        )
    )

  safe_send_message(
      m.chat.id,
      "📋 <b>Ваши активные публикации:</b>\nНажмите на объявление, чтобы удалить"
      " его:",
      reply_markup=markup,
  )


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("my_del_sale_")
    or c.data.startswith("my_del_buy_")
)
def cb_my_del_ad(call):
  is_buy = "my_del_buy_" in call.data
  prefix = "my_del_buy_" if is_buy else "my_del_sale_"
  aid = int(call.data.replace(prefix, ""))
  table = "active_buy_ads" if is_buy else "active_ads"
  uid = call.from_user.id

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(f"SELECT user_id FROM {table} WHERE id = ?", (aid,))
    row = cur.fetchone()
    if row and row[0] == uid:
      cur.execute(f"DELETE FROM {table} WHERE id = ?", (aid,))
      conn.commit()
      try:
        bot.answer_callback_query(call.id, "✅ Объявление удалено!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
      except Exception:
        pass
    else:
      try:
        bot.answer_callback_query(
            call.id, "⚠️ Ошибка или объявление не принадлежит вам!", show_alert=True
        )
      except Exception:
        pass


# ==========================================
# ПОДАЧА ОБЪЯВЛЕНИЙ (С ОБРАБОТКОЙ ФОТО/ТЕКСТА)
# ==========================================
def start_add_ad(m):
  if not check_working_hours():
    return safe_send_message(
        m.chat.id,
        "⏱ <b>Радиоцентр закрыт!</b>\nПодача объявлений возможна ежедневно с"
        " <b>08:00:01 до 22:00:01 МСК</b>.",
        reply_markup=kb_main_menu(),
    )
  update_state(m.from_user.id, posting_ad={"step": "category"})
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  markup.add(*CATEGORIES)
  markup.add("❌ Отменить действие")
  safe_send_message(
      m.chat.id, "📤 Выберите категорию для <b>ПРОДАЖИ</b>:", reply_markup=markup
  )


def start_add_buy_ad(m):
  if not check_working_hours():
    return safe_send_message(
        m.chat.id,
        "⏱ <b>Радиоцентр закрыт!</b>\nПодача объявлений возможна ежедневно с"
        " <b>08:00:01 до 22:00:01 МСК</b>.",
        reply_markup=kb_main_menu(),
    )
  update_state(m.from_user.id, posting_buy_ad={"step": "category"})
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  markup.add(*CATEGORIES)
  markup.add("❌ Отменить действие")
  safe_send_message(
      m.chat.id, "📥 Выберите категорию для <b>СКУПКИ</b>:", reply_markup=markup
  )


@bot.message_handler(
    func=lambda msg: get_state(msg.from_user.id)
    .get("posting_ad", {})
    .get("step")
    == "category"
    or get_state(msg.from_user.id).get("posting_buy_ad", {}).get("step")
    == "category"
)
def process_ad_category(m):
  uid = m.from_user.id
  st = get_state(uid)
  if m.text not in CATEGORIES:
    return safe_send_message(
        m.chat.id, "⚠️ Пожалуйста, выберите категорию из меню кнопок."
    )

  key = "posting_ad" if "posting_ad" in st else "posting_buy_ad"
  st[key]["category"] = m.text
  st[key]["step"] = "text_or_photo"
  update_state(uid, **{key: st[key]})
  safe_send_message(
      m.chat.id,
      "✍️ Отправьте текст объявления (или прикрепите фото с текстом в"
      " описании):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    content_types=["text", "photo"],
    func=lambda msg: get_state(msg.from_user.id)
    .get("posting_ad", {})
    .get("step")
    == "text_or_photo"
    or get_state(msg.from_user.id).get("posting_buy_ad", {}).get("step")
    == "text_or_photo",
)
def process_ad_content(m):
  uid = m.from_user.id

  if not check_working_hours():
    clear_state(uid)
    return safe_send_message(
        m.chat.id,
        "⏱ <b>Радиоцентр закрыт!</b>\nПодача объявлений возможна ежедневно с"
        " <b>08:00:01 до 22:00:01 МСК</b>.",
        reply_markup=kb_main_menu(),
    )

  is_vip_user = is_user_premium(uid) or is_admin_or_owner_id(uid)

  # Проверка кулдауна 2 минуты (120 секунд) для не-VIP пользователей
  if not is_vip_user:
    last_ad = get_user_last_ad_time(uid)
    diff = time.time() - last_ad
    if diff < 120:
      left = int(120 - diff)
      return safe_send_message(
          m.chat.id,
          f"⏳ <b>Кулдаун!</b> Бесплатные объявления можно подавать не чаще, чем раз в 2 минуты.\nПодождите еще <b>{left} сек.</b>",
      )

  st = get_state(uid)
  key = "posting_ad" if "posting_ad" in st else "posting_buy_ad"

  text = m.caption if m.photo else m.text
  photo = m.photo[-1].file_id if m.photo else None

  if not text:
    return safe_send_message(
        m.chat.id,
        "⚠️ Пожалуйста, укажите текст объявления (или добавьте описание к"
        " фото).",
    )

  if not check_auto_moderation(text):
    return safe_send_message(
        m.chat.id,
        "🤬 В вашем тексте обнаружены запрещенные слова. Пожалуйста, исправьте"
        " текст и отправьте снова.",
    )

  st[key]["text"] = text
  st[key]["photo"] = photo
  st[key]["step"] = "waiting_choice"
  update_state(uid, **{key: st[key]})

  is_buy = key == "posting_buy_ad"

  # VIP пользователи сразу кидают VIP объявление без КД и оплаты
  if is_vip_user:
    p_data = st.get(key)
    p_data["is_vip"] = 1
    finish_posting(m.chat.id, uid, m.from_user.username, photo, is_buy)
    return

  markup = types.InlineKeyboardMarkup(row_width=1)
  if is_buy:
    markup.add(
        types.InlineKeyboardButton(
            "🆓 Обычная публикация", callback_data="vip_free_buy_pub"
        ),
        types.InlineKeyboardButton(
            "⭐ VIP публикация (1 ⭐️)", callback_data="buy_single_vip_star_buy"
        ),
    )
  else:
    markup.add(
        types.InlineKeyboardButton(
            "🆓 Обычная публикация", callback_data="vip_free_ad_pub"
        ),
        types.InlineKeyboardButton(
            "⭐ VIP публикация (1 ⭐️)", callback_data="buy_single_vip_star"
        ),
    )
  safe_send_message(m.chat.id, "Выберите тип публикации:", reply_markup=kb_main_menu())
  safe_send_message(m.chat.id, "⬇️ Нажмите на кнопку ниже:", reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data in ["vip_free_buy_pub", "vip_free_ad_pub"])
def callback_publish_choice(call):
  uid = call.from_user.id
  st = get_state(uid)
  is_buy = "buy_pub" in call.data
  p_key = "posting_buy_ad" if is_buy else "posting_ad"
  p_data = st.get(p_key)

  if p_data:
    is_vip = 1 if "vip_free" in call.data else 0
    p_data["is_vip"] = is_vip
    finish_posting(
        call.message.chat.id,
        uid,
        call.from_user.username,
        p_data.get("photo"),
        is_buy,
    )
    try:
      bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
      pass
  else:
    bot.answer_callback_query(
        call.id, "⚠️ Ошибка данных. Попробуйте подать заново."
    )


@bot.callback_query_handler(func=lambda c: c.data in ["buy_single_vip_star", "buy_single_vip_star_buy"])
def cb_buy_single_vip(call):
  is_buy = "_buy" in call.data
  payload = "vip_single_buy_pub" if is_buy else "vip_single_ad_pub"
  prices = [types.LabeledPrice(label="VIP Объявление", amount=1)]
  try:
    bot.send_invoice(
        chat_id=call.message.chat.id,
        title="VIP Публикация",
        description="Оплата VIP статуса для одного объявления",
        invoice_payload=payload,
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="buy_vip_ad",
    )
  except Exception as e:
    try:
      bot.answer_callback_query(
          call.id, f"Ошибка создания счета: {e}", show_alert=True
      )
    except Exception:
      pass


def finish_posting(chat_id, uid, username, photo_id, is_buy):
  st = get_state(uid)
  p_key = "posting_buy_ad" if is_buy else "posting_ad"
  p_data = st.get(p_key)

  if not p_data:
    return safe_send_message(
        chat_id, "⚠️ Ошибка: данные объявления не найдены. Попробуйте еще раз."
    )

  server = p_data.get("server")
  if not server:
    server = st.get("server", "Phoenix")

  category = p_data.get("category")
  text = p_data.get("text")
  is_vip = p_data.get("is_vip", 0)

  table = "pending_buy_posts" if is_buy else "pending_posts"

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        f"""
            INSERT INTO {table} (user_id, username, server, category, text, photo, is_vip, editing_by, editing_since) 
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
        """,
        (uid, username or "Без юзернейма", server, category, text, photo_id, is_vip),
    )
    conn.commit()

  set_user_last_ad_time(uid, time.time())
  clear_state(uid)

  safe_send_message(
      chat_id,
      "✅ Ваше объявление успешно отправлено на модерацию редакторам!",
      reply_markup=kb_main_menu(),
  )

  admin_chats = get_all_admin_ids()
  ad_type = "СКУПКУ" if is_buy else "ПРОДАЖУ"
  notif = (
      f"🔔 <b>Новое объявление на {ad_type} ожидает модерации!</b>\nСервер:"
      f" {server} | Категория: {category}"
  )
  for adm in admin_chats:
    try:
      safe_send_message(adm, notif)
    except Exception:
      pass


# ==========================================
# ПОИСК ТОВАРОВ И УВЕДОМЛЕНИЯ ПО ПОДПИСКАМ
# ==========================================
def start_search(m):
  uid = m.from_user.id
  update_state(uid, searching_keyword=True)
  safe_send_message(
      m.chat.id,
      "🔍 <b>Поиск товара в базе объявлений:</b>\n\nОтправьте ключевое слово"
      " или название предмета для поиска (например: <code>аксессуар</code>,"
      " <code>нимб</code>, <code>дом</code>):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("searching_keyword"))
def process_search_keyword(m):
  uid = m.from_user.id
  clear_state(uid)
  query = m.text.strip().lower()

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, server, category, text, photo, is_vip FROM active_ads WHERE"
        " LOWER(text) LIKE ? OR LOWER(category) LIKE ? ORDER BY id DESC LIMIT 10",
        (f"%{query}%", f"%{query}%"),
    )
    sales = cur.fetchall()
    cur.execute(
        "SELECT id, server, category, text, photo, is_vip FROM active_buy_ads"
        " WHERE LOWER(text) LIKE ? OR LOWER(category) LIKE ? ORDER BY id DESC"
        " LIMIT 10",
        (f"%{query}%", f"%{query}%"),
    )
    buys = cur.fetchall()

  if not sales and not buys:
    return safe_send_message(
        m.chat.id,
        f"🔍 По запросу «<b>{html.escape(query)}</b>» ничего не найдено.",
        reply_markup=kb_main_menu(),
    )

  safe_send_message(
      m.chat.id,
      f"🔍 <b>Результаты поиска по запросу:</b> «{html.escape(query)}»",
  )

  for aid, srv, cat, text, photo, is_vip in sales:
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
      cur = conn.cursor()
      cur.execute(
          "SELECT 1 FROM favorites WHERE user_id = ? AND ad_id = ?", (uid, aid)
      )
      is_fav = bool(cur.fetchone())
    markup = ikb_ad_actions(aid, is_fav=is_fav, user_id=uid, is_buy=False)
    fmt_text = f"📤 <b>[Продажа | {srv}]</b>\n{html.escape(text)}"
    if photo:
      safe_send_photo(m.chat.id, photo, caption=fmt_text, reply_markup=markup)
    else:
      safe_send_message(m.chat.id, fmt_text, reply_markup=markup)

  for aid, srv, cat, text, photo, is_vip in buys:
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
      cur = conn.cursor()
      cur.execute(
          "SELECT 1 FROM favorites WHERE user_id = ? AND ad_id = ?", (uid, aid)
      )
      is_fav = bool(cur.fetchone())
    markup = ikb_ad_actions(aid, is_fav=is_fav, user_id=uid, is_buy=True)
    fmt_text = f"📥 <b>[Скупка | {srv}]</b>\n{html.escape(text)}"
    if photo:
      safe_send_photo(m.chat.id, photo, caption=fmt_text, reply_markup=markup)
    else:
      safe_send_message(m.chat.id, fmt_text, reply_markup=markup)


def manage_subscriptions(m):
  uid = m.from_user.id
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, server, keyword FROM keyword_subscriptions WHERE user_id ="
        " ?",
        (uid,),
    )
    subs = cur.fetchall()

  markup = types.InlineKeyboardMarkup(row_width=1)
  if subs:
    for sub_id, srv, kw in subs:
      markup.add(
          types.InlineKeyboardButton(
              f"🗑 Удалить: {kw} ({srv})", callback_data=f"del_sub_{sub_id}"
          )
      )
  markup.add(
      types.InlineKeyboardButton(
          "➕ Добавить уведомление", callback_data="add_sub_start"
      )
  )

  text = (
      "🔔 <b>Ваши уведомления о новых объявлениях:</b>\n\nВы будете получать"
      " оповещения, когда появится объявление с нужным ключевым словом на"
      " выбранном сервере."
  )
  if not subs:
    text += "\n\n<i>У вас пока нет активных подписок.</i>"

  safe_send_message(m.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith("del_sub_"))
def cb_del_sub(call):
  sub_id = int(call.data.replace("del_sub_", ""))
  uid = call.from_user.id
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM keyword_subscriptions WHERE id = ? AND user_id = ?",
        (sub_id, uid),
    )
    conn.commit()
  try:
    bot.answer_callback_query(call.id, "✅ Подписка удалена")
  except Exception:
    pass
  manage_subscriptions(call.message)


@bot.callback_query_handler(func=lambda c: c.data == "add_sub_start")
def cb_add_sub_start(call):
  uid = call.from_user.id
  st = get_state(uid)
  srv = st.get("server")
  if not srv:
    try:
      bot.answer_callback_query(
          call.id, "⚠️ Сначала выберите сервер в главном меню!", show_alert=True
      )
    except Exception:
      pass
    return
  update_state(uid, adding_subscription=True)
  safe_send_message(
      call.message.chat.id,
      f"🔔 Введите ключевое слово для сервера <b>{html.escape(srv)}</b>"
      " (например, <i>Premium VIP</i>):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("adding_subscription"))
def process_add_subscription(m):
  uid = m.from_user.id
  st = get_state(uid)
  srv = st.get("server")
  kw = m.text.strip().lower()

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM keyword_subscriptions WHERE user_id = ?", (uid,)
    )
    if cur.fetchone()[0] >= 5 and not is_user_premium(uid):
      return safe_send_message(
          m.chat.id,
          "⚠️ Максимум 5 подписок для обычных пользователей. Приобретите"
          " VIP-статус для увеличения лимита.",
          reply_markup=kb_main_menu(),
      )

    cur.execute(
        "INSERT INTO keyword_subscriptions (user_id, server, keyword) VALUES"
        " (?, ?, ?)",
        (uid, srv, kw),
    )
    conn.commit()

  clear_state(uid)
  safe_send_message(
      m.chat.id,
      f"✅ Вы подписались на уведомления по запросу «<b>{html.escape(kw)}</b>»"
      f" на сервере {html.escape(srv)}.",
      reply_markup=kb_main_menu(),
  )


def notify_subscribers(server: str, text: str, aid: int, is_buy: bool):
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, keyword FROM keyword_subscriptions WHERE server = ?",
        (server,),
    )
    subs = cur.fetchall()

  low_text = text.lower()
  ad_type = "СКУПКУ" if is_buy else "ПРОДАЖУ"

  for uid, kw in subs:
    if kw in low_text:
      notif = (
          "🔔 <b>Уведомление по подписке!</b>\nПоявилось новое объявление на"
          f" {ad_type} (Сервер: {server}) с ключевым словом"
          f" «<b>{html.escape(kw)}</b>»."
      )
      markup = ikb_ad_actions(aid, False, uid, is_buy)
      try:
        safe_send_message(uid, notif, reply_markup=markup)
      except Exception:
        pass


# ==========================================
# ЧАТЫ (P2P ОБЩЕНИЕ)
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("contact_seller_"))
def start_dialog_with_seller(call):
  aid = int(call.data.replace("contact_seller_", ""))
  buyer_id = call.from_user.id
  buyer_uname = call.from_user.username or "Без юзернейма"

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, server, text FROM active_ads WHERE id = ?", (aid,)
    )
    row = cur.fetchone()
    is_buy = False
    if not row:
      cur.execute(
          "SELECT user_id, server, text FROM active_buy_ads WHERE id = ?",
          (aid,),
      )
      row = cur.fetchone()
      is_buy = True

  if not row:
    try:
      bot.answer_callback_query(
          call.id, "❌ Объявление не найдено или снято.", show_alert=True
      )
    except Exception:
      pass
    return

  seller_id, srv, text = row

  if buyer_id == seller_id:
    try:
      bot.answer_callback_query(
          call.id, "Вы не можете написать сами себе :)", show_alert=True
      )
    except Exception:
      pass
    return

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT is_active FROM active_dialogs WHERE buyer_id=? AND"
        " seller_id=? AND ad_id=?",
        (buyer_id, seller_id, aid),
    )
    dialog = cur.fetchone()

  if dialog and dialog[0] == 1:
    try:
      bot.answer_callback_query(call.id, "Диалог уже открыт!", show_alert=True)
    except Exception:
      pass
    return

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO active_dialogs (buyer_id, seller_id, ad_id,"
        " is_active) VALUES (?, ?, ?, 1)",
        (buyer_id, seller_id, aid),
    )
    conn.commit()

  ad_type_str = "скупке" if is_buy else "продаже"
  buyer_msg = (
      f"✅ Вы начали диалог с автором объявления (ID: {aid}). Теперь все ваши"
      " сообщения в бот будут пересылаться ему. Нажмите кнопку, чтобы"
      " завершить чат."
  )
  seller_msg = (
      f"✉️ <b>Новое сообщение от покупателя @{buyer_uname}!</b>\nПо объявлению"
      f" о {ad_type_str} (ID: {aid}):\n<i>{text[:50]}...</i>\nТеперь ваши"
      " сообщения будут пересылаться ему."
  )

  safe_send_message(
      buyer_id, buyer_msg, reply_markup=ikb_chat_controls(aid)
  )
  safe_send_message(
      seller_id, seller_msg, reply_markup=ikb_chat_controls(aid)
  )


@bot.callback_query_handler(func=lambda c: c.data.startswith("stop_chat_"))
def cb_stop_chat(call):
  aid = int(call.data.replace("stop_chat_", ""))
  uid = call.from_user.id

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT buyer_id, seller_id FROM active_dialogs WHERE ad_id=? AND"
        " (buyer_id=? OR seller_id=?)",
        (aid, uid, uid),
    )
    row = cur.fetchone()

  if not row:
    return

  buyer_id, seller_id = row
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "UPDATE active_dialogs SET is_active=0 WHERE ad_id=? AND buyer_id=? AND"
        " seller_id=?",
        (aid, buyer_id, seller_id),
    )
    conn.commit()

  other_id = seller_id if uid == buyer_id else buyer_id

  try:
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None,
    )
  except Exception:
    pass

  safe_send_message(uid, f"🛑 Диалог по объявлению {aid} завершен.")
  safe_send_message(other_id, f"🛑 Собеседник завершил диалог по объявлению {aid}.")

  if uid == buyer_id:
    markup = types.InlineKeyboardMarkup(row_width=5)
    markup.add(*[
        types.InlineKeyboardButton(
            str(i), callback_data=f"rate_{seller_id}_{i}"
        )
        for i in range(1, 6)
    ])
    safe_send_message(
        uid, "Пожалуйста, оцените продавца от 1 до 5:", reply_markup=markup
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("rate_"))
def cb_rate_seller(call):
  parts = call.data.split("_")
  seller_id = int(parts[1])
  rating = int(parts[2])
  buyer_id = call.from_user.id

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO seller_reviews (seller_id, buyer_id, rating, comment)"
        " VALUES (?, ?, ?, '')",
        (seller_id, buyer_id, rating),
    )
    conn.commit()

  try:
    bot.answer_callback_query(call.id, f"✅ Спасибо! Вы поставили оценку {rating}.")
    bot.delete_message(call.message.chat.id, call.message.message_id)
  except Exception:
    pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("resume_chat_"))
def cb_resume_chat(call):
  aid = int(call.data.replace("resume_chat_", ""))
  buyer_id = call.from_user.id

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT seller_id, is_active FROM active_dialogs WHERE ad_id=? AND"
        " buyer_id=?",
        (aid, buyer_id),
    )
    row = cur.fetchone()

  if not row:
    return
  seller_id, is_active = row

  if is_active:
    try:
      bot.answer_callback_query(call.id, "Диалог уже активен!", show_alert=True)
    except Exception:
      pass
    return

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "UPDATE active_dialogs SET is_active=1 WHERE ad_id=? AND buyer_id=? AND"
        " seller_id=?",
        (aid, buyer_id, seller_id),
    )
    conn.commit()

  safe_send_message(
      buyer_id,
      f"✅ Диалог по объявлению {aid} возобновлен.",
      reply_markup=ikb_chat_controls(aid),
  )
  safe_send_message(
      seller_id,
      f"✅ Покупатель возобновил диалог по объявлению {aid}.",
      reply_markup=ikb_chat_controls(aid),
  )


@bot.message_handler(
    content_types=["text", "photo"],
    func=lambda msg: not msg.text or not msg.text.startswith("/"),
)
def handle_chat_message(m):
  uid = m.from_user.id

  if is_banned(m.from_user):
    return

  if should_override_nav(m):
    return handle_navigation_override(m)

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT buyer_id, seller_id, ad_id FROM active_dialogs WHERE"
        " (buyer_id=? OR seller_id=?) AND is_active=1",
        (uid, uid),
    )
    dialogs = cur.fetchall()

  if dialogs:
    for buyer_id, seller_id, ad_id in dialogs:
      target_id = seller_id if uid == buyer_id else buyer_id
      try:
        if m.photo:
          safe_send_photo(
              target_id,
              m.photo[-1].file_id,
              caption=f"[Объявление ID {ad_id}]: {m.caption or ''}",
          )
        elif m.text:
          safe_send_message(target_id, f"[Объявление ID {ad_id}]: {m.text}")

        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
          cur = conn.cursor()
          cur.execute(
              "INSERT INTO chat_logs_history (sender_id, receiver_id, text,"
              " timestamp) VALUES (?, ?, ?, ?)",
              (uid, target_id, m.text or "[ФОТО]", time.time()),
          )
          conn.commit()
      except Exception as e:
        logger.error(f"Ошибка пересылки сообщения: {e}")
    return


# ==========================================
# ИНСТРУМЕНТЫ ДЛЯ VICE CITY (КАЛЬКУЛЯТОРЫ)
# ==========================================
def show_vc_menu(m):
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  markup.add("Настроить курс VC")
  markup.add("Перевести SA$ в VC$", "Перевести VC$ в SA$")
  markup.add("Рассчитать выгоду перелета")
  markup.add("❌ Отменить действие")
  rate = get_vc_rate()
  safe_send_message(
      m.chat.id,
      f"💱 <b>Текущий курс:</b> 1 VC$ = {rate:,.0f} SA$\nВыберите нужное"
      " действие:",
      reply_markup=markup,
  )


@bot.message_handler(func=lambda m: m.text == "Настроить курс VC")
def vc_set_rate_start(m):
  update_state(m.from_user.id, vc_setting_rate=True)
  safe_send_message(
      m.chat.id,
      "💰 Введите актуальный курс (например: 95000):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(func=lambda m: get_state(m.from_user.id).get("vc_setting_rate"))
def vc_set_rate_process(m):
  uid = m.from_user.id
  try:
    val = float(m.text.replace(",", ".").replace(" ", ""))
    if val <= 0:
      raise ValueError
    set_vc_rate(val)
    clear_state(uid)
    safe_send_message(
        m.chat.id,
        f"✅ Курс установлен: {val:,.0f} SA$",
        reply_markup=kb_main_menu(),
    )
    show_vc_menu(m)
  except ValueError:
    safe_send_message(m.chat.id, "⚠️ Ошибка ввода. Введите число.")


@bot.message_handler(func=lambda m: m.text in ["Перевести SA$ в VC$", "Перевести VC$ в SA$"])
def vc_convert_start(m):
  is_to_vc = m.text == "Перевести SA$ в VC$"
  update_state(m.from_user.id, vc_conv_input=True, is_to_vc=is_to_vc)
  safe_send_message(
      m.chat.id,
      "Введите сумму для перевода (можно с пробелами, например 1 000 000):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(func=lambda m: get_state(m.from_user.id).get("vc_conv_input"))
def vc_convert_process(m):
  uid = m.from_user.id
  st = get_state(uid)
  is_to_vc = st.get("is_to_vc")
  try:
    amount = float(m.text.replace(",", ".").replace(" ", ""))
    rate = get_vc_rate()
    clear_state(uid)

    if is_to_vc:
      res = amount / rate
      safe_send_message(
          m.chat.id,
          f"🔄 <b>{amount:,.0f} SA$</b> = <b>{res:,.0f} VC$</b>",
          reply_markup=kb_main_menu(),
      )
    else:
      res = amount * rate
      safe_send_message(
          m.chat.id,
          f"🔄 <b>{amount:,.0f} VC$</b> = <b>{res:,.0f} SA$</b>",
          reply_markup=kb_main_menu(),
      )
    show_vc_menu(m)
  except ValueError:
    safe_send_message(m.chat.id, "⚠️ Ошибка ввода. Введите число.")


@bot.message_handler(func=lambda m: m.text == "Рассчитать выгоду перелета")
def vc_calc_profit_start(m):
  update_state(m.from_user.id, vc_calc_step=1)
  safe_send_message(
      m.chat.id,
      "1️⃣ Введите стоимость билета на перелет (SA$):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(func=lambda m: get_state(m.from_user.id).get("vc_calc_step"))
def vc_calc_profit_process(m):
  uid = m.from_user.id
  st = get_state(uid)
  step = st.get("vc_calc_step")

  try:
    val = float(m.text.replace(",", ".").replace(" ", ""))
    if step == 1:
      update_state(uid, vc_calc_step=2, ticket_cost=val)
      safe_send_message(
          m.chat.id, "2️⃣ Введите ожидаемую прибыль от продаж на Vice City (в VC$):"
      )
    elif step == 2:
      ticket = st.get("ticket_cost")
      profit_vc = val
      rate = get_vc_rate()

      profit_sa = profit_vc * rate
      net_profit = profit_sa - ticket

      clear_state(uid)
      res_text = (
          f"📊 <b>Расчет выгоды:</b>\nБилет: {ticket:,.0f} SA$\nДоход:"
          f" {profit_vc:,.0f} VC$ (≈ {profit_sa:,.0f} SA$)\n\n💰 <b>Чистая"
          f" прибыль: {net_profit:,.0f} SA$</b>"
      )
      safe_send_message(m.chat.id, res_text, reply_markup=kb_main_menu())
      show_vc_menu(m)
  except ValueError:
    safe_send_message(m.chat.id, "⚠️ Ошибка. Введите число.")


# ==========================================
# ПРЕМИУМ-СТАТУС И АНАЛИТИКА
# ==========================================
def info_premium(m):
  uid = m.from_user.id
  is_prem = is_user_premium(uid)
  status_text = "✅ АКТИВЕН" if is_prem else "❌ НЕ АКТИВЕН"

  text = (
      f"💎 <b>VIP-статус: {status_text}</b>\n\n<b>Преимущества:</b>\n- 👑"
      " Уникальная иконка 💎 в ваших объявлениях\n- 📌 Отсутствие КД на подачу объявлений\n- 👑 Автоматические VIP-объявления\n- 🔔 Безлимитные подписки на ключевые"
      " слова (обычно макс. 5)\n- 💬 Доступ к скрытым контактным данным в"
      " VIP-объявлениях\n\n<i>Нажмите кнопку ниже для оплаты через Telegram"
      " Stars.</i>"
  )
  markup = types.InlineKeyboardMarkup()
  if not is_prem:
    markup.add(
        types.InlineKeyboardButton(
            "⭐ Купить VIP (30 дней) за 100 ⭐️", callback_data="buy_premium_30"
        )
    )
  else:
    markup.add(
        types.InlineKeyboardButton(
            "⭐ Продлить VIP (30 дней) за 100 ⭐️", callback_data="buy_premium_30"
        )
    )

  safe_send_message(m.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data == "buy_premium_30")
def cb_buy_premium_30(call):
  prices = [types.LabeledPrice(label="VIP Статус (30 дней)", amount=100)]
  try:
    bot.send_invoice(
        chat_id=call.message.chat.id,
        title="VIP Статус",
        description="Подписка на VIP статус бота на 30 дней",
        invoice_payload="premium_30",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="buy_premium",
    )
  except Exception as e:
    try:
      bot.answer_callback_query(
          call.id, f"Ошибка создания счета: {e}", show_alert=True
      )
    except Exception:
      pass


@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout_query(pre_checkout_query):
  bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@bot.message_handler(content_types=["successful_payment"])
def process_successful_payment(message):
  uid = message.from_user.id
  payload = message.successful_payment.invoice_payload

  if payload == "premium_30":
    duration = 30 * 24 * 3600
    current_expiry = time.time()

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
      cur = conn.cursor()
      cur.execute(
          "SELECT expires_at FROM premium_users WHERE user_id = ?", (uid,)
      )
      row = cur.fetchone()
      if row and row[0] > current_expiry:
        current_expiry = row[0]

      new_expiry = current_expiry + duration
      cur.execute(
          "INSERT OR REPLACE INTO premium_users (user_id, expires_at) VALUES"
          " (?, ?)",
          (uid, new_expiry),
      )
      conn.commit()

    safe_send_message(
        message.chat.id,
        "🎉 Оплата прошла успешно! VIP-статус активирован на 30 дней.",
    )

  elif payload in ["vip_single_ad_pub", "vip_single_buy_pub"]:
    is_buy = payload == "vip_single_buy_pub"
    st = get_state(uid)
    p_key = "posting_buy_ad" if is_buy else "posting_ad"
    p_data = st.get(p_key)

    if p_data:
      p_data["is_vip"] = 1
      finish_posting(
          message.chat.id,
          uid,
          message.from_user.username,
          p_data.get("photo"),
          is_buy,
      )
    else:
      safe_send_message(
          message.chat.id,
          "⚠️ Оплата прошла, но данные объявления утеряны. Напишите админам"
          " для ручного возврата или выдачи VIP.",
      )


def show_average_prices(m):
  st = get_state(m.from_user.id)
  srv = st.get("server", "Phoenix")

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT category, COUNT(*) FROM active_ads WHERE server = ? GROUP BY"
        " category",
        (srv,),
    )
    sales_data = cur.fetchall()
    cur.execute(
        "SELECT category, COUNT(*) FROM active_buy_ads WHERE server = ? GROUP"
        " BY category",
        (srv,),
    )
    buys_data = cur.fetchall()

  text = f"📊 <b>Аналитика рынка | {html.escape(srv)}</b>\n\n"
  text += "<b>Активность продаж:</b>\n"
  for cat, count in sales_data:
    text += f"- {html.escape(cat)}: {count} объявлений\n"

  text += "\n<b>Активность скупки:</b>\n"
  for cat, count in buys_data:
    text += f"- {html.escape(cat)}: {count} объявлений\n"

  text += "\n<i>*Более точный анализ средних цен появится в следующих обновлениях.</i>"
  safe_send_message(m.chat.id, text)


# ==========================================
# ЗАЯВКИ В АДМИНЫ И ПАНЕЛЬ УПРАВЛЕНИЯ
# ==========================================
def start_admin_application(m):
  update_state(m.from_user.id, applying_admin=True)
  safe_send_message(
      m.chat.id,
      "📝 <b>Заявка на пост редактора/администратора</b>\n\nНапишите небольшой"
      " текст о себе: ваш опыт, возраст, сколько времени готовы уделять боту"
      " и на каком сервере играете.",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("applying_admin"))
def process_admin_application(m):
  uid = m.from_user.id
  uname = m.from_user.username or "Без юзернейма"
  text = m.text
  clear_state(uid)

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO admin_apps (user_id, username,"
        " application_text) VALUES (?, ?, ?)",
        (uid, uname, text),
    )
    conn.commit()

  safe_send_message(
      m.chat.id,
      "✅ Ваша заявка успешно отправлена владельцу на рассмотрение!",
      reply_markup=kb_main_menu(),
  )

  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton(
          "✅ Принять", callback_data=f"app_accept_{uid}"
      ),
      types.InlineKeyboardButton(
          "❌ Отклонить", callback_data=f"app_reject_{uid}"
      ),
  )

  owner_id = get_owner_user_id()
  if owner_id:
    try:
      safe_send_message(
          owner_id,
          f"📝 <b>Новая заявка в админы!</b>\nОт: @{uname} (ID:"
          f" {uid})\n\n<i>{html.escape(text)}</i>",
          reply_markup=markup,
      )
    except Exception:
      pass


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("app_accept_")
    or c.data.startswith("app_reject_")
)
def cb_manage_admin_app(call):
  if not is_owner(call.from_user):
    try:
      bot.answer_callback_query(
          call.id, "Только владелец может управлять заявками!", show_alert=True
      )
    except Exception:
      pass
    return

  uid = int(call.data.split("_")[2])
  is_accept = "accept" in call.data

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute("SELECT username FROM admin_apps WHERE user_id = ?", (uid,))
    row = cur.fetchone()

    if row:
      if is_accept:
        cur.execute(
            "INSERT OR IGNORE INTO approved_admins (user_id, username) VALUES"
            " (?, ?)",
            (uid, row[0]),
        )
        safe_send_message(
            uid,
            "🎉 Ваша заявка в администраторы <b>ОДОБРЕНА</b>! Добро пожаловать"
            " в команду.",
        )
        msg = "Одобрено"
      else:
        safe_send_message(
            uid, "❌ К сожалению, ваша заявка в администраторы отклонена."
        )
        msg = "Отклонено"

      cur.execute("DELETE FROM admin_apps WHERE user_id = ?", (uid,))
      conn.commit()

      try:
        bot.edit_message_text(
            f"{call.message.text}\n\n<b>Статус: {msg}</b>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
        )
      except Exception:
        pass
    else:
      try:
        bot.answer_callback_query(call.id, "Заявка не найдена.", show_alert=True)
      except Exception:
        pass


def admin_panel(m):
  if not is_admin_or_owner(m.from_user):
    return safe_send_message(
        m.chat.id, "⛔ Доступ запрещен.", reply_markup=kb_main_menu()
    )

  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton(
          "📤 Модерация Продаж", callback_data="admin_mod_sales"
      ),
      types.InlineKeyboardButton(
          "📥 Модерация Скупок", callback_data="admin_mod_buys"
      ),
  )
  markup.add(
      types.InlineKeyboardButton(
          "📋 Активные объявления", callback_data="admin_active_ads_manage"
      ),
      types.InlineKeyboardButton(
          "📊 Рейтинг редакторов", callback_data="admin_stats"
      ),
  )

  if is_owner(m.from_user):
    markup.add(
        types.InlineKeyboardButton(
            "➕ Сделать адм", callback_data="owner_add_admin"
        ),
        types.InlineKeyboardButton(
            "➖ Снять с адм", callback_data="owner_remove_admin"
        ),
    )
    markup.add(
        types.InlineKeyboardButton(
            "🚫 Забанить игрока", callback_data="start_ban"
        ),
        types.InlineKeyboardButton(
            "✅ Разбанить игрока", callback_data="start_unban"
        ),
    )

  safe_send_message(
      m.chat.id,
      "👑 <b>Панель управления радиоцентра:</b>",
      reply_markup=markup,
  )


# ==========================================
# УПРАВЛЕНИЕ АДМИНАМИ ВЛАДЕЛЬЦЕМ
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data == "owner_add_admin")
def cb_owner_add_admin(call):
  if not is_owner(call.from_user):
    return bot.answer_callback_query(call.id, "⛔ Доступ запрещен", show_alert=True)
  update_state(call.from_user.id, waiting_for_admin_add=True)
  safe_send_message(
      call.message.chat.id,
      "➕ <b>Назначение администратора</b>\n\nВведите юзернейм (например, <code>@username</code>) или Telegram ID пользователя:",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("waiting_for_admin_add"))
def process_owner_add_admin(m):
  uid = m.from_user.id
  clear_state(uid)
  target = m.text.strip()
  clean_target = target.lstrip("@").lower()

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    if target.isdigit():
      t_id = int(target)
      cur.execute("SELECT username FROM user_data WHERE user_id = ?", (t_id,))
      row = cur.fetchone()
      t_uname = row[0] if row and row[0] else "admin"
    else:
      cur.execute("SELECT user_id FROM user_data WHERE LOWER(username) = ?", (clean_target,))
      row = cur.fetchone()
      if row:
        t_id = row[0]
        t_uname = clean_target
      else:
        t_id = 0
        t_uname = clean_target

    cur.execute(
        "INSERT OR REPLACE INTO approved_admins (user_id, username) VALUES (?, ?)",
        (t_id if t_id else None, t_uname),
    )
    conn.commit()

  safe_send_message(
      m.chat.id,
      f"✅ Пользователь <b>{target}</b> успешно назначен администратором!",
      reply_markup=kb_main_menu(),
  )
  if t_id:
    try:
      safe_send_message(t_id, "🎉 Вам были выданы права администратора в боте!")
    except Exception:
      pass


@bot.callback_query_handler(func=lambda c: c.data == "owner_remove_admin")
def cb_owner_remove_admin(call):
  if not is_owner(call.from_user):
    return bot.answer_callback_query(call.id, "⛔ Доступ запрещен", show_alert=True)
  update_state(call.from_user.id, waiting_for_admin_remove=True)
  safe_send_message(
      call.message.chat.id,
      "➖ <b>Снятие администратора</b>\n\nВведите юзернейм или Telegram ID администратора для снятия с должности:",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("waiting_for_admin_remove"))
def process_owner_remove_admin(m):
  uid = m.from_user.id
  clear_state(uid)
  target = m.text.strip()
  clean_target = target.lstrip("@").lower()

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    if target.isdigit():
      cur.execute("DELETE FROM approved_admins WHERE user_id = ?", (int(target),))
    else:
      cur.execute("DELETE FROM approved_admins WHERE LOWER(username) = ?", (clean_target,))
    conn.commit()

  safe_send_message(
      m.chat.id,
      f"✅ Пользователь <b>{target}</b> снят с поста администратора.",
      reply_markup=kb_main_menu(),
  )


# ==========================================
# БАН / РАЗБАН ИГРОКОВ ВЛАДЕЛЬЦЕМ
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data == "start_ban")
def cb_start_ban(call):
  if not is_owner(call.from_user):
    return bot.answer_callback_query(call.id, "⛔ Доступ запрещен", show_alert=True)
  update_state(call.from_user.id, waiting_for_username_ban=True)
  safe_send_message(
      call.message.chat.id,
      "🚫 Введите юзернейм или ID игрока для блокировки:",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("waiting_for_username_ban"))
def process_ban(m):
  uid = m.from_user.id
  clear_state(uid)
  target = m.text.strip()
  clean_target = target.lstrip("@").lower()
  is_id = 1 if target.isdigit() else 0

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO bans (target, is_id) VALUES (?, ?)",
        (target if is_id else clean_target, is_id),
    )
    conn.commit()

  safe_send_message(
      m.chat.id,
      f"✅ Пользователь <b>{target}</b> заблокирован в боте.",
      reply_markup=kb_main_menu(),
  )


@bot.callback_query_handler(func=lambda c: c.data == "start_unban")
def cb_start_unban(call):
  if not is_owner(call.from_user):
    return bot.answer_callback_query(call.id, "⛔ Доступ запрещен", show_alert=True)
  update_state(call.from_user.id, waiting_for_username_unban=True)
  safe_send_message(
      call.message.chat.id,
      "✅ Введите юзернейм или ID игрока для разблокировки:",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("waiting_for_username_unban"))
def process_unban(m):
  uid = m.from_user.id
  clear_state(uid)
  target = m.text.strip()
  clean_target = target.lstrip("@").lower()

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM bans WHERE target = ? OR target = ?",
        (target, clean_target),
    )
    conn.commit()

  safe_send_message(
      m.chat.id,
      f"✅ Пользователь <b>{target}</b> разблокирован.",
      reply_markup=kb_main_menu(),
  )


# ==========================================
# УПРАВЛЕНИЕ АКТИВНЫМИ ОБЪЯВЛЕНИЯМИ В АДМИНКЕ
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data == "admin_active_ads_manage")
def cb_admin_active_ads_manage(call):
  if not verify_admin_callback(call):
    return
  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton(
          "📤 Активные продажи", callback_data="admin_list_active_sales"
      ),
      types.InlineKeyboardButton(
          "📥 Активные скупки", callback_data="admin_list_active_buys"
      ),
      types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin"),
  )
  try:
    bot.edit_message_text(
        "📋 <b>Управление активными объявлениями:</b>",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="HTML",
    )
  except Exception:
    safe_send_message(
        call.message.chat.id,
        "📋 <b>Управление активными объявлениями:</b>",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda c: c.data == "admin_list_active_sales")
def cb_admin_list_active_sales(call):
  if not verify_admin_callback(call):
    return
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, server, category, text FROM active_ads ORDER BY id DESC"
        " LIMIT 15"
    )
    ads = cur.fetchall()

  if not ads:
    return bot.answer_callback_query(
        call.id, "📭 Нет активных продаж.", show_alert=True
    )

  markup = types.InlineKeyboardMarkup(row_width=1)
  for aid, srv, cat, text in ads:
    markup.add(
        types.InlineKeyboardButton(
            f"🗑 [Продажа | {srv}] ID {aid}: {text[:30]}...",
            callback_data=f"admin_del_sale_{aid}",
        )
    )
  markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_active_ads_manage"))
  try:
    bot.edit_message_text(
        "📤 <b>Активные объявления (Продажа):</b>\nНажмите для снятия/удаления:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="HTML",
    )
  except Exception:
    safe_send_message(
        call.message.chat.id,
        "📤 <b>Активные объявления (Продажа):</b>",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda c: c.data == "admin_list_active_buys")
def cb_admin_list_active_buys(call):
  if not verify_admin_callback(call):
    return
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, server, category, text FROM active_buy_ads ORDER BY id DESC"
        " LIMIT 15"
    )
    ads = cur.fetchall()

  if not ads:
    return bot.answer_callback_query(
        call.id, "📭 Нет активных скупок.", show_alert=True
    )

  markup = types.InlineKeyboardMarkup(row_width=1)
  for aid, srv, cat, text in ads:
    markup.add(
        types.InlineKeyboardButton(
            f"🗑 [Скупка | {srv}] ID {aid}: {text[:30]}...",
            callback_data=f"admin_del_buy_{aid}",
        )
    )
  markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_active_ads_manage"))
  try:
    bot.edit_message_text(
        "📥 <b>Активные объявления (Скупка):</b>\nНажмите для снятия/удаления:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="HTML",
    )
  except Exception:
    safe_send_message(
        call.message.chat.id,
        "📥 <b>Активные объявления (Скупка):</b>",
        reply_markup=markup,
    )


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("admin_del_sale_")
    or c.data.startswith("admin_del_buy_")
)
def cb_admin_delete_ad(call):
  if not verify_admin_callback(call):
    return
  is_buy = "admin_del_buy_" in call.data
  prefix = "admin_del_buy_" if is_buy else "admin_del_sale_"
  aid = int(call.data.replace(prefix, ""))
  table = "active_buy_ads" if is_buy else "active_ads"

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {table} WHERE id = ?", (aid,))
    conn.commit()

  try:
    bot.answer_callback_query(call.id, f"✅ Объявление #{aid} успешно снято!")
    bot.delete_message(call.message.chat.id, call.message.message_id)
  except Exception:
    pass


@bot.callback_query_handler(func=lambda c: c.data == "admin_stats")
def cb_admin_stats(call):
  if not verify_admin_callback(call):
    return
  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute("SELECT username, count FROM editor_stats ORDER BY count DESC")
    rows = cur.fetchall()

  text = "📊 <b>Рейтинг редакторов (по количеству проверенных постов):</b>\n\n"
  if not rows:
    text += "<i>Пока нет данных.</i>"
  else:
    for uname, count in rows:
      text += f"👤 @{html.escape(uname)}: <b>{count}</b>\n"

  markup = types.InlineKeyboardMarkup().add(
      types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")
  )
  try:
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup,
    )
  except Exception:
    safe_send_message(call.message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data == "back_to_admin")
def cb_back_to_admin(call):
  if not verify_admin_callback(call):
    return
  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton(
          "📤 Модерация Продаж", callback_data="admin_mod_sales"
      ),
      types.InlineKeyboardButton(
          "📥 Модерация Скупок", callback_data="admin_mod_buys"
      ),
  )
  markup.add(
      types.InlineKeyboardButton(
          "📋 Активные объявления", callback_data="admin_active_ads_manage"
      ),
      types.InlineKeyboardButton(
          "📊 Рейтинг редакторов", callback_data="admin_stats"
      ),
  )
  if is_owner(call.from_user):
    markup.add(
        types.InlineKeyboardButton(
            "➕ Сделать адм", callback_data="owner_add_admin"
        ),
        types.InlineKeyboardButton(
            "➖ Снять с адм", callback_data="owner_remove_admin"
        ),
    )
    markup.add(
        types.InlineKeyboardButton(
            "🚫 Забанить игрока", callback_data="start_ban"
        ),
        types.InlineKeyboardButton(
            "✅ Разбанить игрока", callback_data="start_unban"
        ),
    )
  try:
    bot.edit_message_text(
        "👑 <b>Панель управления радиоцентра:</b>",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="HTML",
    )
  except Exception:
    pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_mod_"))
def cb_admin_mod(call):
  if not verify_admin_callback(call):
    return
  is_buy = "buys" in call.data
  table = "pending_buy_posts" if is_buy else "pending_posts"

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]

  if count == 0:
    return bot.answer_callback_query(
        call.id, "📭 Очередь модерации пуста!", show_alert=True
    )

  _send_next_pending_post(call.message.chat.id, call.from_user.id, is_buy)
  try:
    bot.answer_callback_query(call.id, "🔄 Загружаю объявление...")
  except Exception:
    pass


def _send_next_pending_post(chat_id, admin_id, is_buy=False):
  table = "pending_buy_posts" if is_buy else "pending_posts"
  now = time.time()

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        f"UPDATE {table} SET editing_by = 0, editing_since = 0 WHERE"
        " editing_by != 0 AND ? - editing_since > 300",
        (now,),
    )
    conn.commit()

    cur.execute(
        f"SELECT id, username, server, category, text, photo, is_vip, editing_by"
        f" FROM {table} ORDER BY id ASC LIMIT 1"
    )
    row = cur.fetchone()

    if not row:
      return safe_send_message(chat_id, "📭 Очередь модерации пуста!")

    pid, uname, srv, cat, txt, photo, is_vip, ed_by = row

    if ed_by != 0 and ed_by != admin_id:
      return safe_send_message(
          chat_id,
          "⚠️ Кто-то другой уже модерирует первое объявление. Попробуйте позже.",
      )

    cur.execute(
        f"UPDATE {table} SET editing_by = ?, editing_since = ? WHERE id = ?",
        (admin_id, now, pid),
    )
    conn.commit()

  prefix = "b_" if is_buy else "s_"
  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton(
          "✅ Опубликовать", callback_data=f"mod_pub_{prefix}{pid}"
      ),
      types.InlineKeyboardButton(
          "❌ Отклонить", callback_data=f"mod_rej_{prefix}{pid}"
      ),
  )
  markup.add(
      types.InlineKeyboardButton(
          "✏️ Редактировать", callback_data=f"mod_edit_{prefix}{pid}"
      ),
      types.InlineKeyboardButton(
          "⏭ Пропустить", callback_data=f"mod_skip_{prefix}{pid}"
      ),
  )

  type_str = "СКУПКА" if is_buy else "ПРОДАЖА"
  vip_str = "👑 <b>[VIP]</b> " if is_vip else ""
  text_info = (
      f"🛠 <b>Модерация ({type_str})</b>\n{vip_str}От:"
      f" @{html.escape(uname)}\nСервер: {html.escape(srv)}\nКатегория:"
      f" {html.escape(cat)}\n\nТекст:\n{html.escape(txt)}"
  )

  if photo:
    safe_send_photo(chat_id, photo, caption=text_info, reply_markup=markup)
  else:
    safe_send_message(chat_id, text_info, reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith("mod_"))
def cb_mod_action(call):
  if not verify_admin_callback(call):
    return

  parts = call.data.split("_")
  action = parts[1]
  is_buy = parts[2].startswith("b_")
  pid = int(parts[2][2:])
  admin_id = call.from_user.id
  admin_uname = call.from_user.username or "СМИ"

  table_pend = "pending_buy_posts" if is_buy else "pending_posts"
  table_act = "active_buy_ads" if is_buy else "active_ads"

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(
        f"SELECT user_id, username, server, category, text, photo, is_vip,"
        f" editing_by FROM {table_pend} WHERE id = ?",
        (pid,),
    )
    row = cur.fetchone()

  if not row:
    return bot.answer_callback_query(
        call.id, "⚠️ Объявление уже обработано или удалено.", show_alert=True
    )

  uid, uname, srv, cat, txt, photo, is_vip, ed_by = row

  if ed_by != admin_id and not is_owner(call.from_user):
    return bot.answer_callback_query(
        call.id, "⚠️ Этот пост модерирует кто-то другой!", show_alert=True
    )

  try:
    bot.delete_message(call.message.chat.id, call.message.message_id)
  except Exception:
    pass

  if action == "pub":
    fmt_text = format_smi_post(
        srv, cat, txt, uname, admin_uname, is_vip, uid, is_buy
    )
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
      cur = conn.cursor()
      cur.execute(
          f"INSERT INTO {table_act} (user_id, server, category, text, photo,"
          " is_vip, last_updated) VALUES (?, ?, ?, ?, ?, ?, ?)",
          (uid, srv, cat, fmt_text, photo, is_vip, time.time()),
      )
      new_aid = cur.lastrowid
      cur.execute(f"DELETE FROM {table_pend} WHERE id = ?", (pid,))

      cur.execute(
          "INSERT OR IGNORE INTO editor_stats (username, count) VALUES (?, 0)",
          (admin_uname,),
      )
      cur.execute(
          "UPDATE editor_stats SET count = count + 1 WHERE username = ?",
          (admin_uname,),
      )
      conn.commit()

    try:
      safe_send_message(
          uid,
          f"🎉 Ваше объявление (ID: {new_aid}) успешно проверено редактором"
          f" @{html.escape(admin_uname)} и опубликовано!",
      )
    except Exception:
      pass

    notify_subscribers(srv, fmt_text, new_aid, is_buy)

  elif action == "rej":
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
      cur = conn.cursor()
      cur.execute(f"DELETE FROM {table_pend} WHERE id = ?", (pid,))
      conn.commit()

    try:
      safe_send_message(
          uid,
          f"❌ Ваше объявление в категории «{cat}» было отклонено"
          f" модератором @{html.escape(admin_uname)}.",
      )
    except Exception:
      pass

  elif action == "skip":
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
      cur = conn.cursor()
      cur.execute(
          f"UPDATE {table_pend} SET editing_by = 0, editing_since = 0 WHERE id"
          " = ?",
          (pid,),
      )
      conn.commit()

  elif action == "edit":
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
      cur = conn.cursor()
      cur.execute(
          f"UPDATE {table_pend} SET editing_by = 0, editing_since = 0 WHERE id"
          " = ?",
          (pid,),
      )
      conn.commit()
    update_state(
        admin_id,
        admin_editing_pid=pid,
        admin_editing_is_buy=is_buy,
        admin_editing_srv=srv,
        admin_editing_cat=cat,
        admin_editing_uid=uid,
        admin_editing_uname=uname,
        admin_editing_photo=photo,
        admin_editing_is_vip=is_vip,
    )
    safe_send_message(
        admin_id,
        "✏️ Отправьте новый текст для этого объявления:",
        reply_markup=kb_cancel(),
    )
    return

  _send_next_pending_post(call.message.chat.id, admin_id, is_buy)


@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("admin_editing_pid"))
def process_admin_edit_text(m):
  admin_id = m.from_user.id
  st = get_state(admin_id)
  pid = st.get("admin_editing_pid")
  is_buy = st.get("admin_editing_is_buy")
  srv = st.get("admin_editing_srv")
  cat = st.get("admin_editing_cat")
  uid = st.get("admin_editing_uid")
  uname = st.get("admin_editing_uname")
  photo = st.get("admin_editing_photo")
  is_vip = st.get("admin_editing_is_vip")
  admin_uname = m.from_user.username or "СМИ"

  new_text = m.text
  if not new_text:
    return safe_send_message(m.chat.id, "⚠️ Текст не может быть пустым.")

  clear_state(admin_id)

  table_pend = "pending_buy_posts" if is_buy else "pending_posts"
  table_act = "active_buy_ads" if is_buy else "active_ads"

  with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {table_pend} WHERE id = ?", (pid,))

    fmt_text = format_smi_post(
        srv, cat, new_text, uname, admin_uname, is_vip, uid, is_buy
    )
    cur.execute(
        f"INSERT INTO {table_act} (user_id, server, category, text, photo,"
        " is_vip, last_updated) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uid, srv, cat, fmt_text, photo, is_vip, time.time()),
    )
    new_aid = cur.lastrowid
    conn.commit()

  try:
    safe_send_message(
        uid,
        f"🎉 Ваше объявление (ID: {new_aid}) было отредактировано и опубликовано редактором @{html.escape(admin_uname)}!",
    )
  except Exception:
    pass

  safe_send_message(
      admin_id,
      "✅ Объявление отредактировано и опубликовано!",
      reply_markup=kb_main_menu(),
  )
  notify_subscribers(srv, fmt_text, new_aid, is_buy)


# ==========================================
# ЗАПУСК БОТА
# ==========================================
if __name__ == "__main__":
  logger.info("Бот запущен и готов к работе...")
  bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
