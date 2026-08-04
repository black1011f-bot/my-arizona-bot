from datetime import datetime, time as dtime
import contextlib
import html
import io
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

TOKEN = "8916669266:AAFbIqOvrkdekhVkh1NTmMvpxSI_neTyN9I"
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


def log_admin_action(admin_username: str, action: str, target: str):
  """Записывает лог действий администраторов для владельца."""
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO admin_action_logs (admin_username, action, target,"
        " timestamp) VALUES (?, ?, ?, ?)",
        (admin_username, action, target, time.time()),
    )


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

    for tbl in ["active_ads", "active_buy_ads"]:
      try:
        cursor.execute(
            f"ALTER TABLE {tbl} ADD COLUMN edit_count INTEGER DEFAULT 0"
        )
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
                last_ad_time REAL,
                server TEXT
            )
        """)
    try:
      cursor.execute("ALTER TABLE user_data ADD COLUMN server TEXT")
    except sqlite3.OperationalError:
      pass

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


init_db()


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ УВЕДОМЛЕНИЙ ПОИСКА
# ==========================================
def notify_subscribers(server: str, text: str, ad_id: int, is_buy: bool):
  """Уведомляет пользователей, подписанных на ключевые слова."""
  try:
    with db_lock, get_db() as conn:
      cur = conn.cursor()
      cur.execute(
          "SELECT user_id, keyword FROM keyword_subscriptions WHERE server = ?",
          (server,),
      )
      subs = cur.fetchall()

    lower_text = text.lower()
    notified_users = set()

    for row in subs:
      uid = row["user_id"]
      kw = row["keyword"].lower()
      if kw in lower_text and uid not in notified_users:
        notified_users.add(uid)
        type_str = "скупки" if is_buy else "продажи"
        notif_msg = (
            f"🔔 <b>Найдено совпадение по вашей подписке!</b>\n"
            f"🌐 Сервер: {server} | Тип: {type_str}\n\n"
            f"{text}"
        )
        markup = ikb_ad_actions(ad_id, user_id=uid, is_buy=is_buy)
        try:
          safe_send_message(uid, notif_msg, reply_markup=markup)
        except Exception:
          pass
  except Exception as e:
    logger.error(f"Ошибка отправки уведомлений по подпискам: {e}")


def manage_subscriptions(m):
  uid = m.from_user.id
  srv = get_user_server(uid)
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, keyword FROM keyword_subscriptions WHERE user_id = ? AND"
        " server = ?",
        (uid, srv),
    )
    subs = cur.fetchall()

  text = (
      f"🔔 <b>Уведомления о поиске (Ключевые слова)</b>\n🌐 Сервер:"
      f" <b>{html.escape(srv)}</b>\n\n"
  )
  if subs:
    text += "Ваши активные подписки на этом сервере:\n"
    for row in subs:
      text += f"• <code>{html.escape(row['keyword'])}</code> (ID: {row['id']})\n"
  else:
    text += "У вас нет активных подписок на ключевые слова для этого сервера.\n"

  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton(
          "➕ Добавить ключевое слово", callback_data="sub_add_start"
      ),
      types.InlineKeyboardButton(
          "🗑 Удалить подписку", callback_data="sub_del_start"
      ),
  )
  safe_send_message(m.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data == "sub_add_start")
def cb_sub_add_start(call):
  update_state(call.from_user.id, adding_subscription=True)
  safe_send_message(
      call.message.chat.id,
      "➕ Введите ключевое слово или фразу, при появлении которой в новых"
      " объявлениях вы хотите получать уведомления:",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    func=lambda msg: get_state(msg.from_user.id).get("adding_subscription")
)
def process_add_subscription(m):
  uid = m.from_user.id
  srv = get_user_server(uid)
  kw = m.text.strip().lower()
  clear_state(uid)

  if not kw:
    return safe_send_message(
        m.chat.id, "⚠️ Ключевое слово не может быть пустым."
    )

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) as cnt FROM keyword_subscriptions WHERE user_id = ? AND"
        " server = ?",
        (uid, srv),
    )
    row = cur.fetchone()
    limit = 20 if is_user_premium(uid) else 5
    if row and row["cnt"] >= limit:
      return safe_send_message(
          m.chat.id,
          f"⚠️ Достигнут лимит подписок для этого сервера ({limit} шт.).",
          reply_markup=kb_main_menu(),
      )

    cur.execute(
        "INSERT INTO keyword_subscriptions (user_id, server, keyword) VALUES"
        " (?, ?, ?)",
        (uid, srv, kw),
    )

  safe_send_message(
      m.chat.id,
      f"✅ Подписка на ключевое слово <code>{html.escape(kw)}</code> для сервера"
      f" <b>{html.escape(srv)}</b> успешно добавлена!",
      reply_markup=kb_main_menu(),
  )


@bot.callback_query_handler(func=lambda c: c.data == "sub_del_start")
def cb_sub_del_start(call):
  uid = call.from_user.id
  srv = get_user_server(uid)
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, keyword FROM keyword_subscriptions WHERE user_id = ? AND"
        " server = ?",
        (uid, srv),
    )
    subs = cur.fetchall()

  if not subs:
    try:
      return bot.answer_callback_query(
          call.id,
          "⚠️ У вас нет подписок для удаления на этом сервере.",
          show_alert=True,
      )
    except Exception:
      pass

  markup = types.InlineKeyboardMarkup(row_width=1)
  for row in subs:
    markup.add(
        types.InlineKeyboardButton(
            f"❌ Удалить: {row['keyword']}",
            callback_data=f"sub_del_id_{row['id']}",
        )
    )
  try:
    bot.edit_message_text(
        "🗑 Выберите подписку для удаления:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )
  except Exception:
    pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("sub_del_id_"))
def cb_sub_del_id(call):
  sub_id = int(call.data.replace("sub_del_id_", ""))
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("DELETE FROM keyword_subscriptions WHERE id = ?", (sub_id,))

  try:
    bot.answer_callback_query(call.id, "✅ Подписка удалена!")
    bot.delete_message(call.message.chat.id, call.message.message_id)
  except Exception:
    pass
  safe_send_message(
      call.message.chat.id,
      "✅ Выбранная подписка успешно удалена.",
      reply_markup=kb_main_menu(),
  )


# ==========================================
# ПОИСК ТОВАРА В БАЗЕ
# ==========================================
def start_search(m):
  update_state(m.from_user.id, searching_keyword=True)
  safe_send_message(
      m.chat.id,
      "🔍 <b>Поиск товара в базе</b>\n\nВведите ключевое слово или название"
      " товара для поиска по активным объявлениям текущего сервера:",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    func=lambda msg: get_state(msg.from_user.id).get("searching_keyword")
)
def process_search_keyword(m):
  uid = m.from_user.id
  srv = get_user_server(uid)
  query = m.text.strip().lower()
  clear_state(uid)

  if not query:
    return safe_send_message(
        m.chat.id, "⚠️ Поисковый запрос не может быть пустым."
    )

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, user_id, category, text, photo, is_vip, 'sale' as"
        " ad_type FROM active_ads WHERE server = ? AND LOWER(text) LIKE ? "
        "UNION ALL "
        "SELECT id, user_id, category, text, photo, is_vip, 'buy' as ad_type"
        " FROM active_buy_ads WHERE server = ? AND LOWER(text) LIKE ? LIMIT 15",
        (srv, f"%{query}%", srv, f"%{query}%"),
    )
    results = cur.fetchall()

  if not results:
    return safe_send_message(
        m.chat.id,
        f"📭 По запросу <code>{html.escape(query)}</code> на сервере"
        f" <b>{html.escape(srv)}</b> ничего не найдено.",
        reply_markup=kb_main_menu(),
    )

  safe_send_message(
      m.chat.id,
      f"🔎 <b>Результаты поиска по запросу:</b> <code>{html.escape(query)}</code>"
      f" (Сервер: {srv})\nНайдено совпадений: {len(results)}",
  )

  for row in results:
    aid = row["id"]
    owner_id = row["user_id"]
    category = row["category"]
    text = row["text"]
    photo = row["photo"]
    is_vip = row["is_vip"]
    is_buy = row["ad_type"] == "buy"

    with db_lock, get_db() as conn:
      cur = conn.cursor()
      cur.execute(
          "SELECT 1 FROM favorites WHERE user_id = ? AND ad_id = ?", (uid, aid)
      )
      is_fav = bool(cur.fetchone())

    markup = ikb_ad_actions(aid, is_fav=is_fav, user_id=uid, is_buy=is_buy)
    type_badge = "📥 [Скупка]" if is_buy else "📤 [Продажа]"
    fmt_text = f"{type_badge} <b>{category}</b>\n{html.escape(text)}"
    if is_vip:
      fmt_text = f"👑 <b>[VIP]</b>\n{fmt_text}"

    if photo:
      safe_send_photo(m.chat.id, photo, caption=fmt_text, reply_markup=markup)
    else:
      safe_send_message(m.chat.id, fmt_text, reply_markup=markup)


# ==========================================
# ВНУТРЕННИЙ ЧАТ МЕЖДУ ПОКУПАТЕЛЕМ И ПРОДАВЦОМ
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("contact_seller_"))
def cb_contact_seller(call):
  aid = int(call.data.replace("contact_seller_", ""))
  uid = call.from_user.id

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, server, category, text FROM active_ads WHERE id = ?",
        (aid,),
    )
    row = cur.fetchone()
    is_buy = False
    if not row:
      cur.execute(
          "SELECT user_id, server, category, text FROM active_buy_ads WHERE id"
          " = ?",
          (aid,),
      )
      row = cur.fetchone()
      is_buy = True

  if not row:
    try:
      return bot.answer_callback_query(
          call.id,
          "⚠️ Объявление уже неактивно или удалено.",
          show_alert=True,
      )
    except Exception:
      pass

  seller_id = row["user_id"]
  if seller_id == uid:
    try:
      return bot.answer_callback_query(
          call.id,
          "⚠️ Вы не можете начать диалог сами с собой по своему объявлению!",
          show_alert=True,
      )
    except Exception:
      pass

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO active_dialogs (buyer_id, seller_id, ad_id,"
        " is_active) VALUES (?, ?, ?, 1)",
        (uid, seller_id, aid),
    )

  update_state(
      uid, chat_with={"seller_id": seller_id, "ad_id": aid, "is_buy": is_buy}
  )
  update_state(
      seller_id,
      chat_with={"buyer_id": uid, "ad_id": aid, "is_buy": is_buy},
  )

  markup = ikb_chat_controls(aid)
  safe_send_message(
      uid,
      "💬 <b>Защищенный чат по сделке открыт!</b>\nВсе сообщения, отправленные"
      " сюда, будут пересылаться автору объявления. Соблюдайте правила"
      " безопасности.",
      reply_markup=markup,
  )
  safe_send_message(
      seller_id,
      f"💬 <b>С вами хотят связаться по объявлению #{aid}!</b>\nПользователь"
      " начал диалог. Напишите ответное сообщение прямо сюда:",
      reply_markup=markup,
  )
  try:
    bot.answer_callback_query(call.id, "✅ Чат инициализирован!")
  except Exception:
    pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("stop_chat_"))
def cb_stop_chat(call):
  aid = int(call.data.replace("stop_chat_", ""))
  uid = call.from_user.id
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "UPDATE active_dialogs SET is_active = 0 WHERE (buyer_id = ? OR"
        " seller_id = ?) AND ad_id = ?",
        (uid, uid, aid),
    )
  clear_state(uid)
  try:
    bot.answer_callback_query(call.id, "🛑 Диалог завершен.")
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None,
    )
  except Exception:
    pass
  safe_send_message(
      call.message.chat.id,
      "🛑 Диалог по объявлению завершен.",
      reply_markup=kb_main_menu(),
  )


@bot.callback_query_handler(func=lambda c: c.data.startswith("resume_chat_"))
def cb_resume_chat(call):
  aid = int(call.data.replace("resume_chat_", ""))
  uid = call.from_user.id
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "UPDATE active_dialogs SET is_active = 1 WHERE (buyer_id = ? OR"
        " seller_id = ?) AND ad_id = ?",
        (uid, uid, aid),
    )
  try:
    bot.answer_callback_query(call.id, "🔄 Диалог возобновлен!")
  except Exception:
    pass
  safe_send_message(
      call.message.chat.id,
      "🔄 Диалог возобновлен. Можете продолжить общение.",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    func=lambda msg: get_state(msg.from_user.id).get("chat_with") is not None
)
def handle_internal_chat_messages(m):
  uid = m.from_user.id
  st = get_state(uid)
  chat_info = st.get("chat_with")
  if not chat_info:
    return

  target_id = (
      chat_info.get("seller_id")
      if chat_info.get("seller_id")
      else chat_info.get("buyer_id")
  )
  aid = chat_info.get("ad_id")

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT is_active FROM active_dialogs WHERE ((buyer_id = ? AND"
        " seller_id = ?) OR (buyer_id = ? AND seller_id = ?)) AND ad_id = ?",
        (uid, target_id, target_id, uid, aid),
    )
    row = cur.fetchone()

  if not row or not row["is_active"]:
    return safe_send_message(
        m.chat.id,
        "⚠️ Этот диалог был завершен. Вы не можете отправлять сообщения.",
    )

  text = m.text or m.caption or "[Медиа/Фото]"
  forward_text = (
      f"✉️ <b>Сообщение по объявлению #{aid}</b>\n"
      f"От @{m.from_user.username or 'Пользователя'}:\n\n{html.escape(text)}"
  )

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chat_logs_history (sender_id, receiver_id, text,"
        " timestamp) VALUES (?, ?, ?, ?)",
        (uid, target_id, text, time.time()),
    )

  try:
    if m.photo:
      safe_send_photo(target_id, m.photo[-1].file_id, caption=forward_text)
    else:
      safe_send_message(target_id, forward_text)
    safe_send_message(
        m.chat.id, "✔️ Сообщение доставлено собеседнику.", parse_mode=None
    )
  except Exception as e:
    safe_send_message(
        m.chat.id,
        f"⚠️ Не удалось доставить сообщение пользователю: {e}",
        parse_mode=None,
    )


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
    time.sleep(15)
    try:
      now_msk = get_msk_time()
      current_time = now_msk.time()
      current_date = now_msk.date()

      if (
          current_time.hour == 7
          and current_time.minute == 58
          and current_time.second < 20
      ):
        if last_cleaned_date != current_date:
          with db_lock, get_db() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM active_ads")
            cur.execute("DELETE FROM active_buy_ads")
            cur.execute("DELETE FROM pending_posts")
            cur.execute("DELETE FROM pending_buy_posts")
          logger.info(
              f"Утренняя авто-очистка объявлений выполнена ровно в {current_time}"
              " МСК."
          )
          last_cleaned_date = current_date
    except Exception as e:
      logger.error(f"Ошибка фоновой авто-очистки: {e}")


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
              " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
          )
      }
      resp = requests.get(
          f"{YT_CHANNEL_URL}/live",
          headers=headers,
          allow_redirects=True,
          timeout=15,
      )
      html_content = resp.text

      match = re.search(r"watch\?v=([a-zA-Z0-9_-]{11})", html_content)
      if not match:
        match = re.search(r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"', html_content)

      is_actually_live = "isLive\":true" in html_content or "LIVE" in html_content

      if match and is_actually_live:
        video_id = match.group(1)
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


threading.Thread(
    target=background_youtube_stream_checker, daemon=True
).start()


def get_vc_rate() -> float:
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT value FROM bot_settings WHERE key = 'vc_rate'")
    row = cur.fetchone()
    return float(row["value"]) if row else 95000.0


def set_vc_rate(rate: float):
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('vc_rate',"
        " ?)",
        (str(rate),),
    )


def register_admin_chat(chat_id: int):
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO admin_chats (chat_id) VALUES (?)", (chat_id,)
    )


def get_admin_chat_ids():
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM admin_chats")
    return [row["chat_id"] for row in cur.fetchall()]


def get_all_admin_ids():
  admin_ids = set(get_admin_chat_ids())
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM approved_admins")
    for row in cur.fetchall():
      admin_ids.add(row["user_id"])
  return list(admin_ids)


def get_owner_user_id() -> int:
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id FROM user_data WHERE LOWER(username) = ?",
        (OWNER_USERNAME.lower(),),
    )
    row = cur.fetchone()
    if row:
      return row["user_id"]
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
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM approved_admins WHERE user_id = ? OR LOWER(username) ="
        " ?",
        (user.id, uname),
    )
    if cur.fetchone():
      return True
  return False


def is_admin_or_owner_id(user_id: int) -> bool:
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM approved_admins WHERE user_id = ?", (user_id,))
    if cur.fetchone():
      return True
    cur.execute("SELECT username FROM user_data WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row and row["username"]:
      uname = row["username"].lower().lstrip("@")
      if uname == OWNER_USERNAME.lower() or uname in ADMIN_USERNAMES:
        return True
    cur.execute("SELECT 1 FROM admin_chats WHERE chat_id = ?", (user_id,))
    if cur.fetchone():
      return True
  return False


def is_user_premium(user_id: int) -> bool:
  if is_admin_or_owner_id(user_id):
    return True
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT expires_at FROM premium_users WHERE user_id = ?", (user_id,)
    )
    row = cur.fetchone()
  return bool(row and row["expires_at"] > time.time())


def get_seller_rating_info(seller_id: int) -> str:
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT AVG(rating) as avg_r, COUNT(rating) as cnt FROM seller_reviews"
        " WHERE seller_id = ?",
        (seller_id,),
    )
    row = cur.fetchone()
  if not row or row["cnt"] == 0:
    return "⭐ Нет оценок (0)"
  return f"⭐ {row['avg_r']:.1f} / 5 (Отзывов: {row['cnt']})"


def check_auto_moderation(text: str) -> bool:
  if not text:
    return True
  lower_text = text.lower()
  for word in BAD_WORDS:
    if word in lower_text:
      return False
  return True


def get_user_last_ad_time(user_id):
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT last_ad_time FROM user_data WHERE user_id = ?", (user_id,)
    )
    row = cur.fetchone()
    return row["last_ad_time"] if row else 0


def set_user_last_ad_time(user_id, t):
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "UPDATE user_data SET last_ad_time = ? WHERE user_id = ?",
        (t, user_id),
    )


def register_user(user_id, username=None):
  uname = username.lstrip("@").lower() if username else None
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO user_data (user_id, username, last_ad_time,"
        " server) VALUES (?, ?, 0, ?)",
        (user_id, uname, SERVERS[0]),
    )
    if uname:
      cur.execute(
          "UPDATE user_data SET username = ? WHERE user_id = ?", (uname, user_id)
      )


def is_banned(user) -> bool:
  if not user:
    return False
  uname = user.username.lower().lstrip("@") if user.username else ""
  with db_lock, get_db() as conn:
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


# ==========================================
# КЛАВИАТУРЫ
# ==========================================
def kb_servers():
  m = types.ReplyKeyboardMarkup(resize_keyboard=True)
  for i in range(0, len(SERVERS), 2):
    row_buttons = [types.KeyboardButton(s) for s in SERVERS[i : i + 2]]
    m.row(*row_buttons)
  m.row(types.KeyboardButton("📖 Справка и правила"))
  m.row(
      types.KeyboardButton("💎 VIP-статус"),
      types.KeyboardButton("👑 Админ-панель"),
  )
  m.row(types.KeyboardButton("📝 Стать редактором / админом"))
  return m


def kb_main_menu():
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
  m.row(types.KeyboardButton("💱 Курс VC и калькулятор"))
  m.row(
      types.KeyboardButton("🔍 Найти товар в базе"),
      types.KeyboardButton("❤️ Сохраненные"),
  )
  m.row(
      types.KeyboardButton("🔔 Уведомления о поиске"),
      types.KeyboardButton("📋 Мои публикации"),
  )
  m.row(types.KeyboardButton("📊 Анализ цен на сервере"))
  m.row(types.KeyboardButton("💎 VIP-статус"))
  m.row(
      types.KeyboardButton("👑 Админ-панель"),
      types.KeyboardButton("📝 Стать редактором / админом"),
  )
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


def ikb_user_ad_actions(
    aid: int, is_fav: bool = False, is_buy: bool = False, edit_count: int = 0
):
  markup = types.InlineKeyboardMarkup(row_width=2)
  fav_text = "❌ Убрать из избранного" if is_fav else "❤️ В избранное"
  markup.add(
      types.InlineKeyboardButton(
          "✉️ Написать автору", callback_data=f"contact_seller_{aid}"
      ),
      types.InlineKeyboardButton(fav_text, callback_data=f"fav_toggle_{aid}"),
  )
  if edit_count < 1:
    edit_prefix = "edit_my_buy_" if is_buy else "edit_my_sale_"
    markup.add(
        types.InlineKeyboardButton(
            "✏️ Редактировать объявление", callback_data=f"{edit_prefix}{aid}"
        )
    )
  return markup


def ikb_ad_actions(
    aid: int,
    is_fav: bool = False,
    user_id: int = 0,
    is_buy: bool = False,
    edit_count: int = 0,
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
        c.id,
        "⛔ Вы заблокированы в системе и не можете использовать бота!",
        show_alert=True,
    )
  except Exception:
    pass


# ==========================================
# УМНЫЙ МИДДЛВЕЙР НАВИГАЦИИ
# ==========================================
def should_override_nav(msg):
  if not msg.text:
    return False

  if msg.text == "❌ Отменить действие":
    return True

  uid = msg.from_user.id
  st = get_state(uid)

  is_in_active_input = (
      st.get("posting_ad", {}).get("step") in ["category", "text_or_photo"]
      or st.get("posting_buy_ad", {}).get("step") in ["category", "text_or_photo"]
      or st.get("searching_keyword")
      or st.get("adding_subscription")
      or st.get("vc_setting_rate")
      or st.get("vc_conv_input")
      or st.get("vc_calc_step")
      or st.get("applying_admin")
      or st.get("admin_editing_pid")
      or st.get("admin_editing_buy_pid")
      or st.get("owner_broadcast_input")
      or st.get("editing_user_ad_id")
      or st.get("admin_action_input")
  )

  if is_in_active_input:
    return False

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
  ] + CATEGORIES

  return msg.text in nav_buttons or msg.text in SERVERS


@bot.message_handler(func=should_override_nav)
def handle_navigation_override(m):
  if m.text != "❌ Отменить действие":
    clear_state(m.from_user.id)

  if m.text == "🌐 Сменить игровой сервер":
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

  set_user_server(uid, srv)

  safe_send_message(
      m.chat.id,
      f"✅ Игровой сервер установлен: <b>{html.escape(srv)}</b>\nДобро"
      " пожаловать в панель управления!",
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


def info_premium(m):
  text = (
      "💎 <b>VIP-статус в боте</b>\n\n"
      "Привилегии владельца VIP-статуса:\n"
      "• Кулдаун на подачу объявлений сокращен в 2 раза (1 минута вместо 2х).\n"
      "• Возможность добавлять до 20 уведомлений по поиску.\n"
      "• Увеличенные лимиты и приоритетный показ.\n\n"
      "Оформить подписку можно через Telegram Stars."
  )
  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton(
          "💎 Купить VIP на 30 дней (150 ⭐)", callback_data="buy_premium_30"
      )
  )
  safe_send_message(m.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data == "buy_premium_30")
def cb_buy_premium_30(call):
  prices = [types.LabeledPrice(label="VIP Статус на 30 дней", amount=150)]
  try:
    bot.send_invoice(
        chat_id=call.message.chat.id,
        title="VIP Статус (30 дней)",
        description="Оформление VIP-статуса в боте на 1 месяц",
        invoice_payload="premium_30",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="buy_vip",
    )
  except Exception as e:
    try:
      bot.answer_callback_query(
          call.id, f"Ошибка создания счета: {e}", show_alert=True
      )
    except Exception:
      pass


# ==========================================
# КАЛЬКУЛЯТОР И КУРС VC
# ==========================================
def show_vc_menu(m):
  rate = get_vc_rate()
  text = (
      f"💱 <b>Курс обмена Vice City и Калькулятор</b>\n\n"
      f"Текущий курс обмена (SA $: VC $): <b>1 VC = {rate:,.0f} SA $</b>\n\n"
      "Выберите нужное действие:"
  )
  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton(
          "🔄 Конвертер валют", callback_data="vc_conv_start"
      ),
      types.InlineKeyboardButton(
          "🧮 Калькулятор перелетов", callback_data="vc_calc_start"
      ),
  )
  if is_admin_or_owner(m.from_user):
    markup.add(
        types.InlineKeyboardButton(
            "⚙️ Изменить курс VC", callback_data="vc_set_rate_start"
        )
    )
  safe_send_message(m.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data == "vc_set_rate_start")
def cb_vc_set_rate_start(call):
  if not verify_admin_callback(call):
    return
  update_state(call.from_user.id, vc_setting_rate=True)
  safe_send_message(
      call.message.chat.id,
      "⚙️ Введите новый курс обмена (целое число SA $ за 1 VC):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    func=lambda msg: get_state(msg.from_user.id).get("vc_setting_rate")
)
def process_vc_set_rate(m):
  uid = m.from_user.id
  clear_state(uid)
  try:
    new_rate = float(m.text.strip().replace(" ", "").replace(",", "."))
    if new_rate <= 0:
      raise ValueError()
  except ValueError:
    return safe_send_message(
        m.chat.id, "⚠️ Неверный формат курса. Введите положительное число."
    )

  set_vc_rate(new_rate)
  safe_send_message(
      m.chat.id,
      f"✅ Курс VC успешно обновлен: <b>1 VC = {new_rate:,.0f} SA $</b>",
      reply_markup=kb_main_menu(),
  )


@bot.callback_query_handler(func=lambda c: c.data == "vc_conv_start")
def cb_vc_conv_start(call):
  update_state(call.from_user.id, vc_conv_input=True)
  safe_send_message(
      call.message.chat.id,
      "🔄 <b>Конвертер валют</b>\n\nВведите сумму (например: <code>1500000</code>"
      " для SA $ или <code>500vc</code> для VC-долларов):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    func=lambda msg: get_state(msg.from_user.id).get("vc_conv_input")
)
def process_vc_conv(m):
  uid = m.from_user.id
  clear_state(uid)
  text = m.text.strip().lower().replace(" ", "").replace(",", ".")
  rate = get_vc_rate()

  try:
    if "vc" in text:
      val = float(text.replace("vc", ""))
      sa_val = val * rate
      res = f"🧮 <b>Результат конвертации:</b>\n{val:,.2f} VC = <b>{sa_val:,.0f} SA $</b>"
    else:
      val = float(text)
      vc_val = val / rate if rate > 0 else 0
      res = f"🧮 <b>Результат конвертации:</b>\n{val:,.0f} SA $ = <b>{vc_val:,.2f} VC</b>"
  except ValueError:
    return safe_send_message(
        m.chat.id,
        "⚠️ Неверный формат ввода. Укажите число (например, <code>1000000</code>"
        " или <code>500vc</code>).",
    )

  safe_send_message(m.chat.id, res, reply_markup=kb_main_menu())


@bot.callback_query_handler(func=lambda c: c.data == "vc_calc_start")
def cb_vc_calc_start(call):
  update_state(call.from_user.id, vc_calc_step="buy_price")
  safe_send_message(
      call.message.chat.id,
      "🧮 <b>Калькулятор перелетов / прибыли</b>\n\n1️⃣ Введите цену покупки"
      " товара на своем сервере (в SA $):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    func=lambda msg: get_state(msg.from_user.id).get("vc_calc_step")
    == "buy_price"
)
def process_calc_buy(m):
  uid = m.from_user.id
  try:
    val = float(m.text.strip().replace(" ", "").replace(",", "."))
  except ValueError:
    return safe_send_message(
        m.chat.id, "⚠️ Введите корректное числовое значение цены."
    )

  st = get_state(uid)
  st["calc_buy"] = val
  st["vc_calc_step"] = "sell_price"
  update_state(uid, **st)
  safe_send_message(
      m.chat.id,
      "2️⃣ Введите цену продажи товара на сервере Vice City (в VC $):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    func=lambda msg: get_state(msg.from_user.id).get("vc_calc_step")
    == "sell_price"
)
def process_calc_sell(m):
  uid = m.from_user.id
  try:
    val = float(m.text.strip().replace(" ", "").replace(",", "."))
  except ValueError:
    return safe_send_message(
        m.chat.id, "⚠️ Введите корректное числовое значение цены."
    )

  st = get_state(uid)
  buy_price = st.get("calc_buy", 0)
  clear_state(uid)

  rate = get_vc_rate()
  sell_price_sa = val * rate
  profit = sell_price_sa - buy_price
  percent = (profit / buy_price * 100) if buy_price > 0 else 0

  res = (
      f"📊 <b>Финансовый расчет сделки:</b>\n\n"
      f"• Цена покупки (SA $): <b>{buy_price:,.0f} SA $</b>\n"
      f"• Цена продажи в VC: <b>{val:,.2f} VC</b> (~{sell_price_sa:,.0f} SA $)\n"
      f"• Курс конвертации: <b>1 VC = {rate:,.0f} SA $</b>\n\n"
      f"💰 Чистая прибыль: <b>{profit:,.0f} SA $</b>\n"
      f"📈 Рентабельность: <b>{percent:+.2f}%</b>"
  )
  safe_send_message(m.chat.id, res, reply_markup=kb_main_menu())


def admin_panel(m):
  if not is_admin_or_owner(m.from_user):
    return safe_send_message(
        m.chat.id, "⛔ У вас нет доступа к админ-панели.", reply_markup=kb_main_menu()
    )
  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton(
          "📤 Модерация продаж", callback_data="admin_mod_sales"
      ),
      types.InlineKeyboardButton(
          "📥 Модерация скупке", callback_data="admin_mod_buys"
      ),
  )

  if is_owner(m.from_user):
    markup.add(
        types.InlineKeyboardButton(
            "📢 Сделать рассылку", callback_data="owner_broadcast_start"
        ),
        types.InlineKeyboardButton(
            "📋 Логи действий (Файл)", callback_data="owner_get_logs"
        ),
    )
    markup.add(
        types.InlineKeyboardButton(
            "🔨 Забанить / Разбанить", callback_data="owner_manage_ban"
        ),
        types.InlineKeyboardButton(
            "👑 Управление админами", callback_data="owner_manage_admins"
        ),
    )

  safe_send_message(
      m.chat.id,
      "👑 <b>Панель администратора / редактора СМИ:</b>\nВыберите раздел для"
      " управления:",
      reply_markup=markup,
  )


@bot.callback_query_handler(
    func=lambda c: c.data in ["admin_mod_sales", "admin_mod_buys"]
)
def cb_admin_mod_menu(call):
  if not verify_admin_callback(call):
    return
  is_buy = "buy" in call.data
  table = "pending_buy_posts" if is_buy else "pending_posts"
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(f"SELECT id, server, category, text FROM {table} LIMIT 5")
    posts = cur.fetchall()

  if not posts:
    try:
      return bot.answer_callback_query(
          call.id, "📭 Очередь модерации пуста.", show_alert=True
      )
    except Exception:
      pass

  markup = types.InlineKeyboardMarkup(row_width=1)
  for row in posts:
    markup.add(
        types.InlineKeyboardButton(
            f"[{row['server']}] {row['category']}: {row['text'][:25]}...",
            callback_data=f"mod_open_{'buy_' if is_buy else ''}{row['id']}",
        )
    )
  try:
    bot.edit_message_text(
        "📋 <b>Очередь постов на модерацию:</b>\nВыберите пост для проверки:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )
  except Exception:
    pass


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("mod_open_")
    or c.data.startswith("mod_open_buy_")
)
def cb_mod_open(call):
  if not verify_admin_callback(call):
    return
  is_buy = "mod_open_buy_" in call.data
  prefix = "mod_open_buy_" if is_buy else "mod_open_"
  pid = int(call.data.replace(prefix, ""))
  table = "pending_buy_posts" if is_buy else "pending_posts"

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table} WHERE id = ?", (pid,))
    post = cur.fetchone()

  if not post:
    try:
      return bot.answer_callback_query(
          call.id, "⚠️ Этот пост уже промодерирован.", show_alert=True
      )
    except Exception:
      pass

  markup = types.InlineKeyboardMarkup(row_width=2)
  acc_prefix = "mod_acc_buy_" if is_buy else "mod_acc_"
  rej_prefix = "mod_rej_buy_" if is_buy else "mod_rej_"
  markup.add(
      types.InlineKeyboardButton(
          "✅ Одобрить", callback_data=f"{acc_prefix}{pid}"
      ),
      types.InlineKeyboardButton(
          "❌ Отклонить", callback_data=f"{rej_prefix}{pid}"
      ),
  )

  text = (
      f"🔍 <b>Модерация поста #{pid}</b> ({'Скупка' if is_buy else 'Продажа'})\n"
      f"🌐 Сервер: {post['server']}\n"
      f"📂 Категория: {post['category']}\n"
      f"👤 Автор ID: {post['user_id']}\n\n{post['text']}"
  )
  if post["photo"]:
    safe_send_photo(
        call.message.chat.id,
        post["photo"],
        caption=text,
        reply_markup=markup,
    )
  else:
    safe_send_message(call.message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("mod_acc_")
    or c.data.startswith("mod_acc_buy_")
    or c.data.startswith("mod_rej_")
    or c.data.startswith("mod_rej_buy_")
)
def cb_mod_decision(call):
  if not verify_admin_callback(call):
    return
  is_buy = "buy" in call.data
  is_acc = "acc" in call.data
  if is_buy:
    prefix = "mod_acc_buy_" if is_acc else "mod_rej_buy_"
  else:
    prefix = "mod_acc_" if is_acc else "mod_rej_"

  pid = int(call.data.replace(prefix, ""))
  p_table = "pending_buy_posts" if is_buy else "pending_posts"
  a_table = "active_buy_ads" if is_buy else "active_ads"

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {p_table} WHERE id = ?", (pid,))
    post = cur.fetchone()
    if post:
      cur.execute(f"DELETE FROM {p_table} WHERE id = ?", (pid,))

  if not post:
    try:
      return bot.answer_callback_query(
          call.id, "⚠️ Ошибка: пост не найден.", show_alert=True
      )
    except Exception:
      pass

  if is_acc:
    with db_lock, get_db() as conn:
      cur = conn.cursor()
      cur.execute(
          f"INSERT INTO {a_table} (user_id, server, category, text, photo,"
          " is_vip, last_updated) VALUES (?, ?, ?, ?, ?, ?, ?)",
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
      new_ad_id = cur.lastrowid

    notify_subscribers(
        post["server"], post["text"], new_ad_id, is_buy=is_buy
    )

    try:
      safe_send_message(
          post["user_id"],
          f"✅ Ваше объявление #{new_ad_id} успешно проверено и опубликовано в"
          " ленте!",
      )
    except Exception:
      pass
  else:
    try:
      safe_send_message(
          post["user_id"],
          "❌ Ваше объявление было отклонено модератором. Проверьте правила и"
          " попробуйте снова.",
      )
    except Exception:
      pass

  try:
    bot.answer_callback_query(
        call.id, "✅ Решение успешно применено!"
    )
    bot.delete_message(call.message.chat.id, call.message.message_id)
  except Exception:
    pass


@bot.callback_query_handler(func=lambda c: c.data == "back_to_admin")
def cb_back_to_admin(call):
  if not verify_admin_callback(call):
    return
  admin_panel(call.message)


# ==========================================
# РАСШИРЕННЫЕ ФУНКЦИИ ВЛАДЕЛЬЦА (@bounqy)
# ==========================================
@bot.callback_query_handler(
    func=lambda c: c.data == "owner_broadcast_start" and is_owner(c.from_user)
)
def cb_owner_broadcast_start(call):
  update_state(call.from_user.id, owner_broadcast_input=True)
  safe_send_message(
      call.message.chat.id,
      "📢 <b>Режим рассылки сообщений</b>\n\nОтправьте текст (поддерживается"
      " HTML-разметка и красивые смайлики), который будет разослан всем"
      " пользователям бота:",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    func=lambda m: get_state(m.from_user.id).get("owner_broadcast_input")
    and is_owner(m.from_user)
)
def process_owner_broadcast(m):
  clear_state(m.from_user.id)
  text = m.text
  if not text:
    return safe_send_message(m.chat.id, "⚠️ Текст рассылки не может быть пустым.")

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM user_data")
    users = cur.fetchall()

  success = 0
  fail = 0
  safe_send_message(
      m.chat.id, f"🚀 Начинаю рассылку для {len(users)} пользователей..."
  )

  for row in users:
    uid = row["user_id"]
    try:
      safe_send_message(uid, text)
      success += 1
      time.sleep(0.05)
    except Exception:
      fail += 1

  safe_send_message(
      m.chat.id,
      f"✅ <b>Рассылка завершена!</b>\n\n✔️ Успешно отправлено:"
      f" {success}\n❌ Ошибок / заблокировали: {fail}",
      reply_markup=kb_main_menu(),
  )


@bot.callback_query_handler(
    func=lambda c: c.data == "owner_get_logs" and is_owner(c.from_user)
)
def cb_owner_get_logs(call):
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT admin_username, action, target, timestamp FROM"
        " admin_action_logs ORDER BY id DESC"
    )
    logs = cur.fetchall()

  log_text = "=== ЖУРНАЛ ДЕЙСТВИЙ АДМИНИСТРАТОРОВ ===\n\n"
  for row in logs:
    dt = datetime.fromtimestamp(row["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
    log_text += (
        f"[{dt}] Администратор @{row['admin_username']}:"
        f" {row['action']} -> {row['target']}\n"
    )

  if not logs:
    log_text += "Логи пока пусты."

  file_bytes = io.BytesIO(log_text.encode("utf-8"))
  file_bytes.name = "admin_actions_log.txt"

  try:
    bot.send_document(
        call.message.chat.id,
        file_bytes,
        caption="📋 Файл логов действий администраторов",
    )
  except Exception as e:
    safe_send_message(call.message.chat.id, f"Ошибка отправки файла логов: {e}")


@bot.callback_query_handler(
    func=lambda c: c.data == "owner_manage_ban" and is_owner(c.from_user)
)
def cb_owner_manage_ban(call):
  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton(
          "🔨 Забанить юзера", callback_data="owner_ban_user"
      ),
      types.InlineKeyboardButton(
          "🔓 Разбанить юзера", callback_data="owner_unban_user"
      ),
  )
  markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin"))
  bot.edit_message_text(
      "🔨 Управление блокировками (по юзернейму/ID):",
      call.message.chat.id,
      call.message.message_id,
      reply_markup=markup,
  )


@bot.callback_query_handler(
    func=lambda c: c.data in ["owner_ban_user", "owner_unban_user"]
    and is_owner(c.from_user)
)
def cb_owner_ban_prompt(call):
  action_type = "ban" if "ban_user" in call.data else "unban"
  update_state(call.from_user.id, admin_action_input=action_type)
  safe_send_message(
      call.message.chat.id,
      f"Введите юзернейм (без @) или ID пользователя для"
      f" {'бана' if action_type == 'ban' else 'разбана'}:",
      reply_markup=kb_cancel(),
  )


@bot.callback_query_handler(
    func=lambda c: c.data == "owner_manage_admins" and is_owner(c.from_user)
)
def cb_owner_manage_admins(call):
  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton(
          "➕ Сделать админом", callback_data="owner_make_admin"
      ),
      types.InlineKeyboardButton(
          "➖ Снять с адм", callback_data="owner_remove_admin"
      ),
  )
  markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin"))
  bot.edit_message_text(
      "👑 Управление администраторами:",
      call.message.chat.id,
      call.message.message_id,
      reply_markup=markup,
  )


@bot.callback_query_handler(
    func=lambda c: c.data in ["owner_make_admin", "owner_remove_admin"]
    and is_owner(c.from_user)
)
def cb_owner_admin_prompt(call):
  action_type = "make_adm" if "make_admin" in call.data else "remove_adm"
  update_state(call.from_user.id, admin_action_input=action_type)
  safe_send_message(
      call.message.chat.id,
      f"Введите юзернейм (без @) или ID пользователя, чтобы"
      f" {'назначить администратором' if action_type == 'make_adm' else 'снять с поста администратора'}:",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    func=lambda msg: get_state(msg.from_user.id).get("admin_action_input")
    and is_owner(msg.from_user)
)
def process_admin_action_input(m):
  uid = m.from_user.id
  st = get_state(uid)
  action = st.get("admin_action_input")
  target_raw = m.text.strip().lstrip("@")
  clear_state(uid)

  is_id = 1 if target_raw.isdigit() else 0
  target_val = int(target_raw) if is_id else target_raw.lower()

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    if action == "ban":
      cur.execute(
          "INSERT OR REPLACE INTO bans (target, is_id) VALUES (?, ?)",
          (str(target_raw), is_id),
      )
      log_admin_action(
          m.from_user.username or "owner", "BAN", str(target_raw)
      )
      safe_send_message(
          m.chat.id,
          f"✅ Пользователь <b>{target_raw}</b> заблокирован.",
          reply_markup=kb_main_menu(),
      )
    elif action == "unban":
      cur.execute("DELETE FROM bans WHERE target = ?", (str(target_raw),))
      log_admin_action(
          m.from_user.username or "owner", "UNBAN", str(target_raw)
      )
      safe_send_message(
          m.chat.id,
          f"✅ Пользователь <b>{target_raw}</b> разблокирован.",
          reply_markup=kb_main_menu(),
      )
    elif action == "make_adm":
      if is_id:
        cur.execute(
            "SELECT user_id, username FROM user_data WHERE user_id = ?",
            (target_val,),
        )
      else:
        cur.execute(
            "SELECT user_id, username FROM user_data WHERE LOWER(username) = ?",
            (target_val,),
        )
      u_row = cur.fetchone()
      target_id = (
          u_row["user_id"] if u_row else (target_val if is_id else 0)
      )
      target_uname = (
          u_row["username"] if u_row and u_row["username"] else str(target_raw)
      )

      cur.execute(
          "INSERT OR REPLACE INTO approved_admins (user_id, username) VALUES"
          " (?, ?)",
          (target_id, target_uname),
      )
      log_admin_action(
          m.from_user.username or "owner", "MAKE_ADMIN", str(target_raw)
      )
      safe_send_message(
          m.chat.id,
          f"✅ Пользователь <b>{target_raw}</b> назначен администратором.",
          reply_markup=kb_main_menu(),
      )
      if target_id:
        try:
          safe_send_message(
              target_id,
              "🎉 Вам были выданы права администратора владельцем бота!",
          )
        except Exception:
          pass
    elif action == "remove_adm":
      if is_id:
        cur.execute(
            "DELETE FROM approved_admins WHERE user_id = ?", (target_val,)
        )
      else:
        cur.execute(
            "DELETE FROM approved_admins WHERE LOWER(username) = ?",
            (target_raw.lower(),),
        )
      log_admin_action(
          m.from_user.username or "owner", "REMOVE_ADMIN", str(target_raw)
      )
      safe_send_message(
          m.chat.id,
          f"✅ Пользователь <b>{target_raw}</b> снят с поста администратора.",
          reply_markup=kb_main_menu(),
      )


def show_average_prices(m):
  uid = m.from_user.id
  srv = get_user_server(uid)
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT category, COUNT(*) as cnt FROM active_ads WHERE server = ?"
        " GROUP BY category",
        (srv,),
    )
    sales_stats = cur.fetchall()
    cur.execute(
        "SELECT category, COUNT(*) as cnt FROM active_buy_ads WHERE server = ?"
        " GROUP BY category",
        (srv,),
    )
    buys_stats = cur.fetchall()

  text = f"📊 <b>Анализ цен и рынка на сервере {html.escape(srv)}</b>\n\n"
  text += "📤 <b>Активные продажи по категориям:</b>\n"
  if sales_stats:
    for row in sales_stats:
      text += f"- {row['category']}: объявлений {row['cnt']}\n"
  else:
    text += "<i>Нет активных объявлений о продаже.</i>\n"

  text += "\n📥 <b>Активная скупка по категориям:</b>\n"
  if buys_stats:
    for row in buys_stats:
      text += f"- {row['category']}: объявлений {row['cnt']}\n"
  else:
    text += "<i>Нет активных объявлений о скупке.</i>\n"

  safe_send_message(m.chat.id, text, reply_markup=kb_main_menu())


# ==========================================
# ПОДАЧА ЗАЯВКИ НА РЕДАКТОРА / АДМИНА
# ==========================================
def start_admin_application(m):
  uid = m.from_user.id
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM approved_admins WHERE user_id = ?", (uid,))
    if cur.fetchone() or is_admin_or_owner_id(uid):
      return safe_send_message(
          m.chat.id,
          "✅ Вы уже являетесь редактором или администратором системы!",
          reply_markup=kb_main_menu(),
      )
    cur.execute("SELECT 1 FROM admin_apps WHERE user_id = ?", (uid,))
    if cur.fetchone():
      return safe_send_message(
          m.chat.id,
          "⏳ Ваша заявка на пост редактора/администратора уже находится на"
          " рассмотрении.",
          reply_markup=kb_main_menu(),
      )

  update_state(uid, applying_admin={"step": "nickname"})
  safe_send_message(
      m.chat.id,
      "📝 <b>Подача заявки на пост редактора / администратора СМИ</b>\n\n1️⃣"
      " Введите ваш игровой Nickname и сервер (например: <i>Bounty_Squad |"
      " Tucson</i>):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    func=lambda msg: get_state(msg.from_user.id)
    .get("applying_admin", {})
    .get("step")
    == "nickname"
)
def process_app_nickname(m):
  uid = m.from_user.id
  text = m.text.strip()
  if not text:
    return safe_send_message(m.chat.id, "⚠️ Поле не может быть пустым.")

  st = get_state(uid)
  st["applying_admin"]["nickname"] = text
  st["applying_admin"]["step"] = "age_exp"
  update_state(uid, applying_admin=st["applying_admin"])
  safe_send_message(
      m.chat.id,
      "2️⃣ Укажите ваш реальный возраст и опыт игры на Arizona RP (или в"
      " SAMP/CRMP):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    func=lambda msg: get_state(msg.from_user.id)
    .get("applying_admin", {})
    .get("step")
    == "age_exp"
)
def process_app_age_exp(m):
  uid = m.from_user.id
  text = m.text.strip()
  if not text:
    return safe_send_message(m.chat.id, "⚠️ Поле не может быть пустым.")

  st = get_state(uid)
  st["applying_admin"]["age_exp"] = text
  st["applying_admin"]["step"] = "motivation"
  update_state(uid, applying_admin=st["applying_admin"])
  safe_send_message(
      m.chat.id,
      "3️⃣ Расскажите немного о себе и почему вы хотите стать редактором"
      " / администратором:",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    func=lambda msg: get_state(msg.from_user.id)
    .get("applying_admin", {})
    .get("step")
    == "motivation"
)
def process_app_motivation(m):
  uid = m.from_user.id
  motivation = m.text.strip()
  if not motivation:
    return safe_send_message(m.chat.id, "⚠️ Поле не может быть пустым.")

  st = get_state(uid)
  app_data = st.get("applying_admin", {})
  nickname = app_data.get("nickname", "Не указан")
  age_exp = app_data.get("age_exp", "Не указан")

  full_text = (
      f"👤 Кандидат: @{m.from_user.username or 'Без юзернейма'} (ID: {uid})\n"
      f"🎮 Ник / Сервер: {nickname}\n"
      f"📊 Возраст и опыт: {age_exp}\n"
      f"💡 Мотивация:\n{motivation}"
  )

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO admin_apps (user_id, username, application_text)"
        " VALUES (?, ?, ?)",
        (uid, m.from_user.username or "", full_text),
    )

  clear_state(uid)
  safe_send_message(
      m.chat.id,
      "✅ Ваша заявка успешно отправлена администрации на рассмотрение!",
      reply_markup=kb_main_menu(),
  )

  owner_id = get_owner_user_id()
  admin_chats = get_all_admin_ids()
  recipients = set(admin_chats)
  if owner_id:
    recipients.add(owner_id)
  else:
    # Фоллбэк на владельца по юзернейму bounqy
    try:
      with db_lock, get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id FROM user_data WHERE LOWER(username) = ?",
            (OWNER_USERNAME.lower(),),
        )
        row = cur.fetchone()
        if row:
          recipients.add(row["user_id"])
    except Exception:
      pass

  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton(
          "✅ Одобрить", callback_data=f"admin_app_acc_{uid}"
      ),
      types.InlineKeyboardButton(
          "❌ Отклонить", callback_data=f"admin_app_rej_{uid}"
      ),
  )
  notif_text = f"📋 <b>Новая заявка на пост редактора / админа!</b>\n\n{full_text}"

  for adm in recipients:
    try:
      safe_send_message(adm, notif_text, reply_markup=markup)
    except Exception:
      pass


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("admin_app_acc_")
    or c.data.startswith("admin_app_rej_")
)
def cb_admin_app_decision(call):
  if not verify_admin_callback(call):
    return

  is_acc = call.data.startswith("admin_app_acc_")
  target_uid = int(
      call.data.replace("admin_app_acc_", "").replace("admin_app_rej_", "")
  )

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT username, application_text FROM admin_apps WHERE user_id = ?",
        (target_uid,),
    )
    row = cur.fetchone()
    cur.execute("DELETE FROM admin_apps WHERE user_id = ?", (target_uid,))

    if is_acc and row:
      uname = row["username"].lstrip("@").lower() if row["username"] else ""
      cur.execute(
          "INSERT OR REPLACE INTO approved_admins (user_id, username) VALUES"
          " (?, ?)",
          (target_uid, uname),
      )
      log_admin_action(
          call.from_user.username or "admin",
          "APPROVE_ADMIN_APP",
          str(target_uid),
      )

  try:
    bot.answer_callback_query(
        call.id,
        (
            "✅ Заявка одобрена, пользователь назначен редактором/админом!"
            if is_acc
            else "❌ Заявка отклонена."
        ),
    )
    bot.delete_message(call.message.chat.id, call.message.message_id)
  except Exception:
    pass

  if is_acc:
    safe_send_message(
        target_uid,
        "🎉 <b>Поздравляем!</b> Ваша заявка на пост редактора / администратора"
        " была одобрена. Вам доступны административные функции.",
        reply_markup=kb_main_menu(),
    )
  else:
    safe_send_message(
        target_uid,
        "❌ К сожалению, ваша заявка на пост редактора / администратора была"
        " отклонена.",
        reply_markup=kb_main_menu(),
    )


# ==========================================
# ОТОБРАЖЕНИЕ ОБЪЯВЛЕНИЙ ПО КАТЕГОРИЯМ
# ==========================================
def show_ads_category(m):
  _show_ads(m, is_buy=False)


def show_buy_ads_category(m):
  _show_ads(m, is_buy=True)


def _show_ads(m, is_buy):
  uid = m.from_user.id
  srv = get_user_server(uid)
  cat = m.text

  table = "active_buy_ads" if is_buy else "active_ads"
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        f"SELECT id, user_id, text, photo, is_vip, edit_count FROM {table} WHERE"
        " server = ? AND category = ? ORDER BY is_vip DESC, id DESC LIMIT 10",
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

  for row in ads:
    aid, owner_id, text, photo, is_vip, edit_count = (
        row["id"],
        row["user_id"],
        row["text"],
        row["photo"],
        row["is_vip"],
        row["edit_count"],
    )
    with db_lock, get_db() as conn:
      cur = conn.cursor()
      cur.execute(
          "SELECT 1 FROM favorites WHERE user_id = ? AND ad_id = ?", (uid, aid)
      )
      is_fav = bool(cur.fetchone())

    if uid == owner_id:
      markup = ikb_user_ad_actions(
          aid, is_fav=is_fav, is_buy=is_buy, edit_count=edit_count
      )
    else:
      markup = ikb_ad_actions(
          aid,
          is_fav=is_fav,
          user_id=uid,
          is_buy=is_buy,
          edit_count=edit_count,
      )

    fmt_text = html.escape(text)
    if is_vip:
      fmt_text = f"👑 <b>[VIP ОБЪЯВЛЕНИЕ]</b>\n{fmt_text}"

    if photo:
      safe_send_photo(m.chat.id, photo, caption=fmt_text, reply_markup=markup)
    else:
      safe_send_message(m.chat.id, fmt_text, reply_markup=markup)


# ==========================================
# РЕДАКТИРОВАНИЕ И УПРАВЛЕНИЕ СВОИМИ ОБЪЯВЛЕНИЯМИ
# ==========================================
@bot.callback_query_handler(
    func=lambda c: c.data.startswith("edit_my_sale_")
    or c.data.startswith("edit_my_buy_")
)
def cb_edit_my_ad(call):
  is_buy = "edit_my_buy_" in call.data
  prefix = "edit_my_buy_" if is_buy else "edit_my_sale_"
  aid = int(call.data.replace(prefix, ""))
  table = "active_buy_ads" if is_buy else "active_ads"
  uid = call.from_user.id

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(f"SELECT user_id, edit_count FROM {table} WHERE id = ?", (aid,))
    row = cur.fetchone()

  if not row or row["user_id"] != uid:
    try:
      return bot.answer_callback_query(
          call.id,
          "⚠️ Объявление не найдено или не принадлежит вам!",
          show_alert=True,
      )
    except Exception:
      pass

  if row["edit_count"] >= 1:
    try:
      return bot.answer_callback_query(
          call.id,
          "⚠️ Это объявление уже было отредактировано 1 раз!",
          show_alert=True,
      )
    except Exception:
      pass

  update_state(uid, editing_user_ad_id=aid, editing_user_is_buy=is_buy)
  safe_send_message(
      call.message.chat.id,
      "✏️ Введите новый текст для вашего объявления (доступна 1 редакция):",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    func=lambda msg: get_state(msg.from_user.id).get("editing_user_ad_id")
    is not None
)
def process_user_edit_ad_text(m):
  uid = m.from_user.id
  st = get_state(uid)
  aid = st.get("editing_user_ad_id")
  is_buy = st.get("editing_user_is_buy", False)
  clear_state(uid)

  new_text = m.text.strip()
  if not new_text:
    return safe_send_message(m.chat.id, "⚠️ Текст не может быть пустым.")

  if not check_auto_moderation(new_text):
    return safe_send_message(
        m.chat.id, "🤬 В вашем тексте обнаружены запрещенные слова."
    )

  table = "active_buy_ads" if is_buy else "active_ads"
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        f"UPDATE {table} SET text = ?, edit_count = edit_count + 1 WHERE id = ?"
        " AND user_id = ?",
        (new_text, aid, uid),
    )

  safe_send_message(
      m.chat.id,
      f"✅ Объявление #{aid} успешно отредактировано!",
      reply_markup=kb_main_menu(),
  )


# ==========================================
# УПРАВЛЕНИЕ ИЗБРАННЫМ И СВОИМИ ПУБЛИКАЦИЯМИ
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("fav_toggle_"))
def cb_fav_toggle(call):
  aid = int(call.data.split("_")[2])
  uid = call.from_user.id

  with db_lock, get_db() as conn:
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

  with db_lock, get_db() as conn:
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


# ==========================================
# УДАЛЕНИЕ ОБЪЯВЛЕНИЙ АДМИНАМИ
# ==========================================
@bot.callback_query_handler(
    func=lambda c: c.data.startswith("admin_del_")
    or c.data.startswith("admin_del_buy_")
)
def cb_admin_delete_ad(call):
  if not verify_admin_callback(call):
    return
  is_buy = "admin_del_buy_" in call.data
  prefix = "admin_del_buy_" if is_buy else "admin_del_"
  aid = int(call.data.replace(prefix, ""))
  table = "active_buy_ads" if is_buy else "active_ads"

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {table} WHERE id = ?", (aid,))
    log_admin_action(
        call.from_user.username or "admin", "DELETE_AD", f"ID {aid}"
    )

  try:
    bot.answer_callback_query(
        call.id, "✅ Объявление успешно удалено администратором!"
    )
    bot.delete_message(call.message.chat.id, call.message.message_id)
  except Exception:
    pass


def show_favorites(m):
  uid = m.from_user.id
  with db_lock, get_db() as conn:
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
  for row_fav in favs:
    aid = row_fav["ad_id"]
    with db_lock, get_db() as conn:
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
      text, photo = row["text"], row["photo"]
      markup = ikb_ad_actions(aid, is_fav=True, user_id=uid, is_buy=is_buy)
      fmt_text = html.escape(text)
      if photo:
        safe_send_photo(m.chat.id, photo, caption=fmt_text, reply_markup=markup)
      else:
        safe_send_message(m.chat.id, fmt_text, reply_markup=markup)


def show_my_ads(m):
  uid = m.from_user.id
  with db_lock, get_db() as conn:
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
  for row in sales:
    aid, srv, cat, text = (
        row["id"],
        row["server"],
        row["category"],
        row["text"],
    )
    markup.add(
        types.InlineKeyboardButton(
            f"🗑 [Продажа | {srv}] ID {aid}: {text[:25]}...",
            callback_data=f"my_del_sale_{aid}",
        )
    )
  for row in buys:
    aid, srv, cat, text = (
        row["id"],
        row["server"],
        row["category"],
        row["text"],
    )
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

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(f"SELECT user_id FROM {table} WHERE id = ?", (aid,))
    row = cur.fetchone()
    if row and row["user_id"] == uid:
      cur.execute(f"DELETE FROM {table} WHERE id = ?", (aid,))
      try:
        bot.answer_callback_query(call.id, "✅ Объявление удалено!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
      except Exception:
        pass
    else:
      try:
        bot.answer_callback_query(
            call.id,
            "⚠️ Ошибка или объявление не принадлежит вам!",
            show_alert=True,
        )
      except Exception:
        pass


# ==========================================
# ПОДАЧА ОБЪЯВЛЕНИЙ
# ==========================================
def start_add_ad(m):
  if not check_working_hours():
    return safe_send_message(
        m.chat.id,
        "⏱ <b>Радиоцентр закрыт!</b>\nПодача объявлений возможна ежедневно с"
        " <b>08:00:01 до 22:00:01 МСК</b>.",
        reply_markup=kb_main_menu(),
    )
  update_state(
      m.from_user.id,
      posting_ad={"step": "category"},
      viewing_buy_categories=False,
  )
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
  update_state(
      m.from_user.id,
      posting_buy_ad={"step": "category"},
      viewing_buy_categories=True,
  )
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
  cooldown = 60 if is_vip_user else 120

  last_ad = get_user_last_ad_time(uid)
  diff = time.time() - last_ad
  if diff < cooldown:
    left = int(cooldown - diff)
    mins = left // 60
    secs = left % 60
    time_str = f"{mins} мин. {secs} сек." if mins > 0 else f"{secs} сек."
    return safe_send_message(
        m.chat.id,
        f"⏳ <b>Кулдаун!</b> Подавать объявления можно не чаще, чем раз в"
        f" {'1 минуту' if is_vip_user else '2 минуты'}.\nПодождите еще"
        f" <b>{time_str}</b>.",
    )

  st = get_state(uid)
  if "posting_ad" in st:
    key = "posting_ad"
  elif "posting_buy_ad" in st:
    key = "posting_buy_ad"
  else:
    clear_state(uid)
    return safe_send_message(
        m.chat.id,
        "⚠️ Ошибка состояния. Пожалуйста, начните подачу объявления заново.",
        reply_markup=kb_main_menu(),
    )

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
            "⭐ VIP публикация (1 ⭐️)", callback_data="buy_single_vip_star_ad"
        ),
    )

  safe_send_message(
      m.chat.id,
      "📌 Выберите тип публикации объявления:",
      reply_markup=markup,
  )


@bot.callback_query_handler(
    func=lambda c: c.data
    in [
        "vip_free_ad_pub",
        "vip_free_buy_pub",
        "buy_single_vip_star_ad",
        "buy_single_vip_star_buy",
    ]
)
def cb_pub_choice(call):
  uid = call.from_user.id
  st = get_state(uid)
  is_buy = "buy" in call.data
  is_vip = "star" in call.data

  key = "posting_buy_ad" if is_buy else "posting_ad"
  if key not in st:
    try:
      return bot.answer_callback_query(
          call.id,
          "⚠️ Сессия устарела. Начните подачу объявления заново.",
          show_alert=True,
      )
    except Exception:
      pass

  st[key]["is_vip"] = 1 if is_vip else 0
  update_state(uid, **{key: st[key]})

  if is_vip:
    prices = [
        types.LabeledPrice(label="VIP публикация объявления", amount=1)
    ]
    try:
      bot.send_invoice(
          chat_id=call.message.chat.id,
          title="VIP Публикация",
          description=(
              "Закреп и выделение вашего объявления в ленте на 1 месяц"
          ),
          invoice_payload=f"vip_pub_{'buy_' if is_buy else ''}{uid}",
          provider_token="",
          currency="XTR",
          prices=prices,
          start_parameter="vip_pub",
      )
    except Exception as e:
      try:
        bot.answer_callback_query(
            call.id, f"Ошибка создания инвойса: {e}", show_alert=True
        )
      except Exception:
        pass
  else:
    finish_posting(
        call.message.chat.id,
        uid,
        call.from_user.username,
        st[key]["photo"],
        is_buy,
    )
    try:
      bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
      pass


@bot.pre_checkout_query_handler(func=lambda query: True)
def pre_checkout_query(query):
  bot.answer_pre_checkout_query(query.id, ok=True)


@bot.message_handler(content_types=["successful_payment"])
def successful_payment(message):
  uid = message.from_user.id
  payload = message.successful_payment.invoice_payload

  if "premium_30" in payload:
    expires = time.time() + 30 * 86400
    with db_lock, get_db() as conn:
      cur = conn.cursor()
      cur.execute(
          "INSERT OR REPLACE INTO premium_users (user_id, expires_at) VALUES"
          " (?, ?)",
          (uid, expires),
      )
    safe_send_message(
        message.chat.id,
        "🎉 <b>Поздравляем!</b> Вы успешно оформили VIP-статус на 30 дней!",
        reply_markup=kb_main_menu(),
    )
  elif "vip_pub_" in payload:
    is_buy = "buy_" in payload
    st = get_state(uid)
    key = "posting_buy_ad" if is_buy else "posting_ad"
    if key in st and st[key].get("text"):
      st[key]["is_vip"] = 1
      finish_posting(message.chat.id, uid, message.from_user.username, st[key]["photo"], is_buy)


def finish_posting(chat_id, uid, username, photo, is_buy):
  st = get_state(uid)
  key = "posting_buy_ad" if is_buy else "posting_ad"
  data = st.get(key, {})

  category = data.get("category")
  text = data.get("text")
  is_vip = data.get("is_vip", 0)
  srv = get_user_server(uid)
  clear_state(uid)

  if not category or not text:
    return safe_send_message(
        chat_id,
        "⚠️ Данные объявления не найдены. Начните заново.",
        reply_markup=kb_main_menu(),
    )

  p_table = "pending_buy_posts" if is_buy else "pending_posts"
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO {p_table} (user_id, username, server, category, text,"
        " photo, is_vip) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uid, username or "", srv, category, text, photo, is_vip),
    )
    pid = cur.lastrowid

  set_user_last_ad_time(uid, time.time())

  safe_send_message(
      chat_id,
      "✅ <b>Ваше объявление отправлено на модерацию редакторам!</b>\nОжидайте"
      " проверки.",
      reply_markup=kb_main_menu(),
  )

  admin_chats = get_all_admin_ids()
  markup = types.InlineKeyboardMarkup(row_width=2)
  acc_prefix = "mod_acc_buy_" if is_buy else "mod_acc_"
  rej_prefix = "mod_rej_buy_" if is_buy else "mod_rej_"
  markup.add(
      types.InlineKeyboardButton(
          "✅ Одобрить", callback_data=f"{acc_prefix}{pid}"
      ),
      types.InlineKeyboardButton(
          "❌ Отклонить", callback_data=f"{rej_prefix}{pid}"
      ),
  )

  notif_text = (
      f"📋 <b>Новый пост на модерацию #{pid}</b> ({'Скупка' if is_buy else 'Продажа'})\n"
      f"🌐 Сервер: {srv}\n"
      f"📂 Категория: {category}\n"
      f"👤 Автор ID: {uid}\n\n{text}"
  )

  for adm in admin_chats:
    try:
      if photo:
        safe_send_photo(adm, photo, caption=notif_text, reply_markup=markup)
      else:
        safe_send_message(adm, notif_text, reply_markup=markup)
    except Exception:
      pass


if __name__ == "__main__":
  logger.info("Бот успешно запущен и работает...")
  while True:
    try:
      bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except Exception as e:
      logger.error(f"Ошибка в polling: {e}")
      time.sleep(5)
