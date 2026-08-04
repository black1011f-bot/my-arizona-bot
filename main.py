from datetime import datetime, time as dtime, timedelta
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
MANAGER_USERNAME = "bounqy31"
BOT_USERNAME = "arizona_coin_bot"

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=20)

OWNER_USERNAME = "bounqy"
ADMIN_USERNAMES = {"bounqy31", "bounqy"}

DB_NAME = "smi_bot.db"
db_lock = threading.Lock()
state_lock = threading.Lock()


# ==========================================
# ЗАЩИТА ОТ ФЛУДА (RATE LIMITING)
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
# ОБРАБОТЧИКИ АНТИФЛУДА
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


# ==========================================
# ПРОСМОТР КАТЕГОРИЙ И ИЗБРАННОГО
# ==========================================
def show_category_ads(m):
  uid = m.from_user.id
  srv = get_user_server(uid)
  category = m.text

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, user_id, text, photo, is_vip, 'sale' as ad_type FROM"
        " active_ads WHERE server = ? AND category = ? UNION ALL SELECT id,"
        " user_id, text, photo, is_vip, 'buy' as ad_type FROM active_buy_ads"
        " WHERE server = ? AND category = ? LIMIT 15",
        (srv, category, srv, category),
    )
    results = cur.fetchall()

  if not results:
    return safe_send_message(
        m.chat.id,
        f"📭 В категории <b>{html.escape(category)}</b> на сервере"
        f" <b>{html.escape(srv)}</b> пока нет активных объявлений.",
        reply_markup=kb_main_menu(),
    )

  safe_send_message(
      m.chat.id,
      f"📂 <b>Категория: {html.escape(category)}</b>\n🌐 Сервер: {srv}\nНайдено"
      f" объявлений: {len(results)}",
  )

  for row in results:
    aid = row["id"]
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
    fmt_text = f"{type_badge}\n{html.escape(text)}"
    if is_vip:
      fmt_text = f"👑 <b>[VIP]</b>\n{fmt_text}"

    if photo:
      safe_send_photo(m.chat.id, photo, caption=fmt_text, reply_markup=markup)
    else:
      safe_send_message(m.chat.id, fmt_text, reply_markup=markup)


def show_favorites(m):
  uid = m.from_user.id
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT ad_id FROM favorites WHERE user_id = ?", (uid,))
    favs = cur.fetchall()

  if not favs:
    return safe_send_message(
        m.chat.id,
        "❤️ У вас пока нет сохраненных объявлений в избранном.",
        reply_markup=kb_main_menu(),
    )

  safe_send_message(m.chat.id, "❤️ <b>Ваши сохраненные объявления:</b>")
  for f in favs:
    aid = f["ad_id"]
    with db_lock, get_db() as conn:
      cur = conn.cursor()
      cur.execute(
          "SELECT id, user_id, category, text, photo, is_vip, server, 'sale'"
          " as ad_type FROM active_ads WHERE id = ? UNION ALL SELECT id,"
          " user_id, category, text, photo, is_vip, server, 'buy' as ad_type"
          " FROM active_buy_ads WHERE id = ?",
          (aid, aid),
      )
      row = cur.fetchone()

    if not row:
      continue

    is_buy = row["ad_type"] == "buy"
    markup = ikb_ad_actions(aid, is_fav=True, user_id=uid, is_buy=is_buy)
    type_badge = "📥 [Скупка]" if is_buy else "📤 [Продажа]"
    fmt_text = (
        f"{type_badge} <b>{row['category']}</b> (Сервер: {row['server']})\n"
        f"{html.escape(row['text'])}"
    )

    if row["photo"]:
      safe_send_photo(m.chat.id, row["photo"], caption=fmt_text, reply_markup=markup)
    else:
      safe_send_message(m.chat.id, fmt_text, reply_markup=markup)


def show_my_ads(m):
  uid = m.from_user.id
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, server, category, text, 'active_sale' as status FROM"
        " active_ads WHERE user_id = ? UNION ALL SELECT id, server, category,"
        " text, 'active_buy' as status FROM active_buy_ads WHERE user_id = ?"
        " UNION ALL SELECT id, server, category, text, 'pending_sale' as"
        " status FROM pending_posts WHERE user_id = ? UNION ALL SELECT id,"
        " server, category, text, 'pending_buy' as status FROM"
        " pending_buy_posts WHERE user_id = ?",
        (uid, uid, uid, uid),
    )
    ads = cur.fetchall()

  if not ads:
    return safe_send_message(
        m.chat.id,
        "📋 У вас нет активных или находящихся на модерации публикаций.",
        reply_markup=kb_main_menu(),
    )

  text = "📋 <b>Ваши публикации:</b>\n\n"
  for row in ads:
    status_str = {
        "active_sale": "🟢 Активна (Продажа)",
        "active_buy": "🟢 Активна (Скупка)",
        "pending_sale": "⏳ На модерации (Продажа)",
        "pending_buy": "⏳ На модерации (Скупка)",
    }.get(row["status"], "Неизвестно")

    text += (
        f"• ID: <code>{row['id']}</code> | {status_str}\n🌐 Сервер:"
        f" <b>{row['server']}</b> | 📂 {row['category']}\n💬"
        f" {html.escape(row['text'][:50])}...\n\n"
    )

  safe_send_message(m.chat.id, text, reply_markup=kb_main_menu())


@bot.callback_query_handler(func=lambda c: c.data.startswith("fav_toggle_"))
def cb_fav_toggle(call):
  aid = int(call.data.replace("fav_toggle_", ""))
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
      msg = "❌ Удалено из избранного!"
    else:
      cur.execute(
          "INSERT INTO favorites (user_id, ad_id) VALUES (?, ?)", (uid, aid)
      )
      is_fav = True
      msg = "❤️ Добавлено в избранное!"

    cur.execute("SELECT 1 FROM active_buy_ads WHERE id = ?", (aid,))
    is_buy = bool(cur.fetchone())

  try:
    bot.answer_callback_query(call.id, msg)
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=ikb_ad_actions(
            aid, is_fav=is_fav, user_id=uid, is_buy=is_buy
        ),
    )
  except Exception:
    pass


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
    cur.execute(f"SELECT * FROM {table} WHERE id = ?", (aid,))
    row = cur.fetchone()
    if not row:
      try:
        return bot.answer_callback_query(
            call.id, "⚠️ Этот пост уже обработан или удален.", show_alert=True
        )
      except Exception:
        pass
      return
    cur.execute(f"DELETE FROM {table} WHERE id = ?", (aid,))

  try:
    bot.answer_callback_query(call.id, "🗑 Объявление удалено администратором!")
    bot.delete_message(call.message.chat.id, call.message.message_id)
  except Exception:
    pass


# ==========================================
# ПОДПИСКИ И ПОИСК
# ==========================================
def notify_subscribers(server: str, text: str, ad_id: int, is_buy: bool):
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
# ПОДАЧА ОБЪЯВЛЕНИЙ И РАБОЧИЕ ЧАСЫ
# ==========================================
def check_working_hours() -> bool:
  """Проверка рабочего времени радиоцентра.

  Запрещено отправлять объявления с 22:00:01 до 08:00:00. Разрешено после
  08:00:01 до 22:00:01.
  """
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
        reply_markup=kb_main_menu(),
    )

  if not check_working_hours() and not is_admin_or_owner(m.from_user):
    return safe_send_message(
        m.chat.id,
        "❌ <b>Отправка объявлений временно заблокирована!</b>\n\n"
        "🌙 Ночной режим активен. Радиоцентр принимает объявления строго с <b>08:00:01 до 22:00:01 МСК</b>.",
        reply_markup=kb_main_menu(),
    )

  update_state(uid, posting_ad={"step": "category", "is_buy": False})
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  for cat in CATEGORIES:
    markup.add(types.KeyboardButton(cat))
  markup.add(types.KeyboardButton("❌ Отменить действие"))
  safe_send_message(
      m.chat.id,
      f"📤 <b>Подача объявления о продаже</b>\n🌐 Сервер: {srv}\n\nВыберите"
      " категорию товара:",
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
        reply_markup=kb_main_menu(),
    )

  if not check_working_hours() and not is_admin_or_owner(m.from_user):
    return safe_send_message(
        m.chat.id,
        "❌ <b>Отправка объявлений временно заблокирована!</b>\n\n"
        "🌙 Ночной режим активен. Радиоцентр принимает объявления строго с <b>08:00:01 до 22:00:01 МСК</b>.",
        reply_markup=kb_main_menu(),
    )

  update_state(uid, posting_ad={"step": "category", "is_buy": True})
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  for cat in CATEGORIES:
    markup.add(types.KeyboardButton(cat))
  markup.add(types.KeyboardButton("❌ Отменить действие"))
  safe_send_message(
      m.chat.id,
      f"📥 <b>Подача объявления о скупке</b>\n🌐 Сервер: {srv}\n\nВыберите"
      " категорию товара:",
      reply_markup=markup,
  )


@bot.message_handler(
    func=lambda msg: get_state(msg.from_user.id).get("posting_ad", {}).get("step")
    == "category"
)
def process_ad_category(m):
  uid = m.from_user.id

  if not check_working_hours() and not is_admin_or_owner(m.from_user):
    clear_state(uid)
    return safe_send_message(
        m.chat.id,
        "❌ <b>Отправка объявлений временно заблокирована!</b>\n\n"
        "🌙 Ночной режим активен. Радиоцентр принимает объявления строго с <b>08:00:01 до 22:00:01 МСК</b>.",
        reply_markup=kb_main_menu(),
    )

  cat = m.text.strip()
  if cat not in CATEGORIES:
    return safe_send_message(
        m.chat.id,
        "⚠️ Пожалуйста, выберите категорию, используя кнопки на клавиатуре.",
    )

  st = get_state(uid)
  st["posting_ad"]["category"] = cat
  st["posting_ad"]["step"] = "text_or_photo"
  update_state(uid, posting_ad=st["posting_ad"])

  safe_send_message(
      m.chat.id,
      f"✍️ Вы выбрали категорию: <b>{cat}</b>\n\nТеперь введите текст"
      " объявления (укажите название товара, цену и условия связи). Можно"
      " прикрепить фото:",
      reply_markup=kb_cancel(),
  )


@bot.message_handler(
    content_types=["text", "photo"],
    func=lambda msg: get_state(msg.from_user.id).get("posting_ad", {}).get("step")
    == "text_or_photo",
)
def process_ad_text_or_photo(m):
  uid = m.from_user.id

  if not check_working_hours() and not is_admin_or_owner(m.from_user):
    clear_state(uid)
    return safe_send_message(
        m.chat.id,
        "❌ <b>Отправка объявлений временно заблокирована!</b>\n\n"
        "🌙 Ночной режим активен. Радиоцентр принимает объявления строго с <b>08:00:01 до 22:00:01 МСК</b>.",
        reply_markup=kb_main_menu(),
    )

  st = get_state(uid)
  post_data = st.get("posting_ad", {})
  category = post_data.get("category", CATEGORIES[0])

  text = m.text or m.caption
  if not text:
    return safe_send_message(
        m.chat.id, "⚠️ Обязательно укажите текст (или описание с фото)."
    )

  if not check_auto_moderation(text):
    clear_state(uid)
    return safe_send_message(
        m.chat.id,
        "🤬 Нельзя общаться матом! В вашем тексте обнаружены запрещенные слова. Подача отменена.",
        reply_markup=kb_main_menu(),
    )

  polished_text = text
  photo_id = m.photo[-1].file_id if m.photo else None

  st["posting_ad"]["polished_text"] = polished_text
  st["posting_ad"]["photo_id"] = photo_id
  st["posting_ad"]["step"] = "choose_ad_type"
  update_state(uid, posting_ad=st["posting_ad"])

  markup = types.InlineKeyboardMarkup(row_width=1)
  has_sub = is_user_premium(uid)
  
  if has_sub:
    markup.add(
        types.InlineKeyboardButton("👑 VIP-объявление (Бесплатно по подписке)", callback_data="ad_type_vip_sub"),
        types.InlineKeyboardButton("📄 Обычное объявление (Бесплатно)", callback_data="ad_type_regular")
    )
  else:
    markup.add(
        types.InlineKeyboardButton("👑 VIP-объявление (1 ⭐)", callback_data="ad_type_vip_paid"),
        types.InlineKeyboardButton("📄 Обычное объявление (Бесплатно)", callback_data="ad_type_regular")
    )

  safe_send_message(
      m.chat.id,
      f"📝 <b>Текст объявления:</b>\n\n{polished_text}\n\nВыберите тип объявления:",
      reply_markup=markup
  )


@bot.callback_query_handler(func=lambda c: c.data in ["ad_type_vip_sub", "ad_type_regular"])
def cb_publish_ad_free(call):
  uid = call.from_user.id
  st = get_state(uid)
  post_data = st.get("posting_ad")
  if not post_data:
    try:
      return bot.answer_callback_query(call.id, "⚠️ Данные объявления не найдены. Начните заново.")
    except Exception:
      pass
    return

  is_vip = 1 if call.data == "ad_type_vip_sub" else 0
  finalize_and_send_ad(uid, post_data, is_vip)
  try:
    bot.answer_callback_query(call.id, "✅ Объявление отправлено на модерацию!")
    bot.delete_message(call.message.chat.id, call.message.message_id)
  except Exception:
    pass


@bot.callback_query_handler(func=lambda c: c.data == "ad_type_vip_paid")
def cb_publish_ad_paid_vip(call):
  uid = call.from_user.id
  prices = [types.LabeledPrice(label="VIP Объявление", amount=1)]
  try:
    bot.send_invoice(
        chat_id=call.message.chat.id,
        title="VIP Объявление",
        description="Публикация VIP объявления в ленте за 1 звезду",
        invoice_payload="vip_single_ad",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="vip_ad",
    )
    bot.answer_callback_query(call.id)
  except Exception as e:
    try:
      bot.answer_callback_query(call.id, f"Ошибка счета: {e}", show_alert=True)
    except Exception:
      pass


@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
  bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@bot.message_handler(content_types=["successful_payment"])
def got_payment(m):
  uid = m.from_user.id
  payload = m.successful_payment.invoice_payload

  if payload == "premium_30":
    expires = time.time() + 30 * 86400
    with db_lock, get_db() as conn:
      cur = conn.cursor()
      cur.execute(
          "INSERT OR REPLACE INTO premium_users (user_id, expires_at) VALUES (?, ?)",
          (uid, expires),
      )
    safe_send_message(
        m.chat.id,
        "💎 <b>Поздравляем!</b> VIP-статус успешно активирован на 30 дней!",
        reply_markup=kb_main_menu(),
    )
  elif payload == "vip_single_ad":
    st = get_state(uid)
    post_data = st.get("posting_ad")
    if post_data:
      finalize_and_send_ad(uid, post_data, is_vip=1)
      safe_send_message(
          m.chat.id,
          "✅ Оплата прошла успешно! Ваше VIP-объявление отправлено на модерацию.",
          reply_markup=kb_main_menu(),
      )


def finalize_and_send_ad(uid, post_data, is_vip):
  is_buy = post_data.get("is_buy", False)
  category = post_data.get("category", CATEGORIES[0])
  polished_text = post_data.get("polished_text")
  photo_id = post_data.get("photo_id")
  srv = get_user_server(uid)

  table = "pending_buy_posts" if is_buy else "pending_posts"
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO {table} (user_id, username, server, category, text,"
        " photo, is_vip) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            uid,
            "",
            srv,
            category,
            polished_text,
            photo_id,
            is_vip,
        ),
    )
    pid = cur.lastrowid

  set_user_last_ad_time(uid, time.time())
  clear_state(uid)

  safe_send_message(
      uid,
      "✅ Ваше объявление успешно отправлено на модерацию редакторам!",
      reply_markup=kb_main_menu(),
  )

  markup = types.InlineKeyboardMarkup(row_width=2)
  acc_prefix = "mod_acc_buy_" if is_buy else "mod_acc_"
  rej_prefix = "mod_rej_buy_" if is_buy else "mod_rej_"
  bad_prefix = "mod_bad_buy_" if is_buy else "mod_bad_"
  
  markup.add(
      types.InlineKeyboardButton("✅ Одобрить", callback_data=f"{acc_prefix}{pid}"),
      types.InlineKeyboardButton("❌ Отклонить", callback_data=f"{rej_prefix}{pid}"),
  )
  markup.add(
      types.InlineKeyboardButton("⚠️ Плохой текст (Штраф админу)", callback_data=f"{bad_prefix}{pid}")
  )

  notif_text = (
      f"📋 <b>Новый пост #{pid}</b> ({'Скупка' if is_buy else 'Продажа'})\n"
      f"🌐 Сервер: {srv}\n📂 Категория: {category}\n👤 Автор ID: {uid}\n\n{polished_text}"
  )

  for adm in get_all_admin_ids():
    try:
      if photo_id:
        safe_send_photo(adm, photo_id, caption=notif_text, reply_markup=markup)
      else:
        safe_send_message(adm, notif_text, reply_markup=markup)
    except Exception:
      pass


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
          "⚠️ Вы не можете начать диалог сами с собой!",
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
      "💬 <b>Защищенный чат по сделке открыт!</b>\nВсе сообщения будут пересылаться автору объявления.",
      reply_markup=markup,
  )
  safe_send_message(
      seller_id,
      f"💬 <b>С вами хотят связаться по объявлению #{aid}!</b>\nНапишите ответное сообщение прямо сюда:",
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

  text = m.text or m.caption or "[Медиа/Фото]"

  if m.text and not check_auto_moderation(m.text):
    return safe_send_message(
        m.chat.id,
        "⚠️ Нельзя общаться матом! Сообщение не доставлено.",
        parse_mode=None,
    )

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
        m.chat.id, "⚠️ Этот диалог был завершен."
    )

  forward_text = (
      f"✉️ <b>Сообщение по объявлению #{aid}</b>\n\n{html.escape(text)}"
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
    safe_send_message(m.chat.id, "✔️ Доставлено.", parse_mode=None)
  except Exception as e:
    safe_send_message(m.chat.id, f"⚠️ Ошибка доставки: {e}", parse_mode=None)


# ==========================================
# БАНЫ И МОДЕРАЦИЯ АДМИНОВ
# ==========================================
def record_admin_error(admin_username: str, admin_id: int):
  if not admin_username or admin_username.lower() == OWNER_USERNAME.lower():
    return
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO editor_stats (username, count) VALUES (?, 1) ON"
        " CONFLICT(username) DO UPDATE SET count = count + 1",
        (admin_username.lower(),),
    )
    cur.execute(
        "SELECT count FROM editor_stats WHERE username = ?",
        (admin_username.lower(),),
    )
    row = cur.fetchone()
    if row and row["count"] >= 3:
      cur.execute(
          "DELETE FROM approved_admins WHERE user_id = ? OR LOWER(username) = ?",
          (admin_id, admin_username.lower()),
      )
      cur.execute("DELETE FROM editor_stats WHERE username = ?", (admin_username.lower(),))
      try:
        safe_send_message(admin_id, "⛔ Вы сняты с поста администратора за 3 ошибки при модерации.")
      except Exception:
        pass


def get_msk_time():
  try:
    return datetime.now(ZoneInfo("Europe/Moscow"))
  except Exception:
    return datetime.now()


def background_cleanup_ads():
  last_cleaned_date = None
  while True:
    time.sleep(5)
    try:
      now_msk = get_msk_time()
      current_time = now_msk.time()
      current_date = now_msk.date()

      if (
          current_time.hour == 7
          and current_time.minute == 50
          and current_time.second < 15
      ):
        if last_cleaned_date != current_date:
          with db_lock, get_db() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM active_ads")
            cur.execute("DELETE FROM active_buy_ads")
            cur.execute("DELETE FROM pending_posts")
            cur.execute("DELETE FROM pending_buy_posts")
          last_cleaned_date = current_date
    except Exception as e:
      logger.error(f"Ошибка фоновой авто-очистки: {e}")


threading.Thread(target=background_cleanup_ads, daemon=True).start()


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
        "INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('vc_rate', ?)",
        (str(rate),),
    )


def register_admin_chat(chat_id: int):
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO admin_chats (chat_id) VALUES (?)", (chat_id,))


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


def is_owner(user) -> bool:
  return bool(user and user.username and user.username.lower() == OWNER_USERNAME.lower())


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
        "SELECT 1 FROM approved_admins WHERE user_id = ? OR LOWER(username) = ?",
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
    cur.execute("SELECT last_ad_time FROM user_data WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    return row["last_ad_time"] if row else 0


def set_user_last_ad_time(user_id, t):
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "UPDATE user_data SET last_ad_time = ? WHERE user_id = ?", (t, user_id)
    )


def register_user(user_id, username=None):
  uname = username.lstrip("@").lower() if username else None
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO user_data (user_id, username, last_ad_time, server) VALUES (?, ?, 0, ?)",
        (user_id, uname, SERVERS[0]),
    )


def is_banned(user) -> bool:
  if not user:
    return False
  uname = user.username.lower().lstrip("@") if user.username else ""
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM bans WHERE (is_id = 1 AND target = ?) OR (is_id = 0 AND target = ?)",
        (str(user.id), uname),
    )
    res = cur.fetchone()
  return bool(res)


def verify_admin_callback(call) -> bool:
  if not is_admin_or_owner(call.from_user):
    try:
      bot.answer_callback_query(call.id, "⛔ Нет доступа!", show_alert=True)
    except Exception:
      pass
    return False
  return True


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
  m.row(types.KeyboardButton("💬 Связаться с менеджером"))
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
      types.KeyboardButton("💬 Связаться с менеджером"),
  )
  return m


def kb_cancel():
  return types.ReplyKeyboardMarkup(resize_keyboard=True).add(
      types.KeyboardButton("❌ Отменить действие")
  )


def ikb_chat_controls(aid: int):
  markup = types.InlineKeyboardMarkup(row_width=1)
  markup.add(
      types.InlineKeyboardButton("🛑 Завершить диалог", callback_data=f"stop_chat_{aid}"),
      types.InlineKeyboardButton("🔄 Возобновить", callback_data=f"resume_chat_{aid}"),
  )
  return markup


def ikb_ad_actions(aid: int, is_fav: bool = False, user_id: int = 0, is_buy: bool = False):
  markup = types.InlineKeyboardMarkup(row_width=2)
  fav_text = "❌ Убрать из избранного" if is_fav else "❤️ В избранное"
  markup.add(
      types.InlineKeyboardButton("✉️ Написать автору", callback_data=f"contact_seller_{aid}"),
      types.InlineKeyboardButton(fav_text, callback_data=f"fav_toggle_{aid}"),
  )
  if user_id and is_admin_or_owner_id(user_id):
    del_prefix = "admin_del_buy_" if is_buy else "admin_del_"
    markup.add(
        types.InlineKeyboardButton("🗑 Удалить (Админ)", callback_data=f"{del_prefix}{aid}")
    )
  return markup


# ==========================================
# ПЕРЕХВАТЧИКИ И НАВИГАЦИЯ
# ==========================================
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


def should_override_nav(msg):
  if not msg.text:
    return False
  if msg.text == "❌ Отменить действие":
    return True

  uid = msg.from_user.id
  st = get_state(uid)

  is_in_active_input = (
      st.get("posting_ad", {}).get("step") in ["category", "text_or_photo", "choose_ad_type"]
      or st.get("searching_keyword")
      or st.get("adding_subscription")
      or st.get("vc_setting_rate")
      or st.get("vc_conv_input")
      or st.get("vc_calc_step")
      or st.get("owner_broadcast_input")
      or st.get("admin_action_input")
  )

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
      "💬 Связаться с менеджером",
  ] + CATEGORIES

  if is_in_active_input and msg.text not in nav_buttons and msg.text not in SERVERS:
    return False

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
  elif m.text == "💬 Связаться с менеджером":
    contact_manager(m)
  elif m.text in CATEGORIES:
    show_category_ads(m)
  elif m.text in SERVERS:
    select_srv(m)


# ==========================================
# ОСНОВНЫЕ КОМАНДЫ И СПРАВКА
# ==========================================
def cancel_action(m):
  clear_state(m.from_user.id)
  safe_send_message(
      m.chat.id,
      "❌ Текущее действие отменено.",
      reply_markup=kb_main_menu(),
  )


@bot.message_handler(commands=["start"])
def cmd_start(m):
  try:
    bot.delete_message(m.chat.id, m.message_id)
  except Exception:
    pass

  register_user(m.from_user.id, m.from_user.username)

  if is_banned(m.from_user):
    return safe_send_message(
        m.chat.id, "⛔ Вы заблокированы.", reply_markup=types.ReplyKeyboardRemove()
    )

  if is_admin_or_owner(m.from_user):
    register_admin_chat(m.chat.id)

  update_state(m.from_user.id, changing_server=True)
  welcome_text = (
      "👋 <b>Добро пожаловать в официальный бот торговой площадки и радиоцентра Arizona RP!</b>\n\n"
      "📌 <b>Правильный формат объявления:</b>\n"
      "Предмет:\n"
      "Цена/бюджет:\n"
      "Какая лавка/нету:\n\n"
      "• Подача и модерация объявлений на всех серверах\n"
      "• Удобный поиск, избранное и система подписок на ключевые слова\n"
      "• Встроенный калькулятор валюты Vice City\n\n"
      "👇 <b>Выберите свой игровой сервер в меню ниже, чтобы начать работу:</b>"
  )
  safe_send_message(m.chat.id, welcome_text, reply_markup=kb_servers(), parse_mode="HTML")


@bot.message_handler(commands=["help"])
def cmd_help(m):
  try:
    bot.delete_message(m.chat.id, m.message_id)
  except Exception:
    pass

  help_text = (
      f"📖 <b>Справочник по боту и шаблон объявлений (@{BOT_USERNAME}):</b>\n\n"
      "📝 <b>Формат отправки объявления:</b>\n"
      "Предмет: [Название]\n"
      "Цена/бюджет: [Сумма]\n"
      "Какая лавка/нету: [Номер или нет]\n\n"
      "1️⃣ <b>Время работы:</b> Отправка разрешена строго с 08:00:01 до 22:00:01 МСК. Ночной режим блокирует подачу.\n"
      "2️⃣ <b>Модерация:</b> Все тексты автоматически проверяются на наличие запрещенных слов.\n"
      "3️⃣ <b>Безопасность:</b> Бот защищает игроков, а владелец (@bounqy) защищен от банов.\n"
      "4️⃣ <b>Функционал:</b> Используйте кнопки меню для управления серверами, поиска товаров, настроек подписок и калькулятора VC."
  )
  safe_send_message(m.chat.id, help_text, reply_markup=kb_main_menu(), parse_mode="HTML")


def change_server(m):
  update_state(m.from_user.id, changing_server=True)
  safe_send_message(m.chat.id, "👇 Выберите новый игровой сервер:", reply_markup=kb_servers())


def select_srv(m):
  srv = m.text
  uid = m.from_user.id
  set_user_server(uid, srv)
  safe_send_message(
      m.chat.id,
      f"✅ Сервер установлен: <b>{html.escape(srv)}</b>",
      reply_markup=kb_main_menu(),
  )


def how_bot_works(m):
  text = (
      f"📖 <b>О работе радиоцентра @{BOT_USERNAME}</b>\n\n"
      f"• Режим работы: с <b>08:00:01 до 22:00:01 МСК</b> ежедневно.\n"
      f"• Модерация: все объявления проходят проверку редакторами.\n"
      f"• Запрещено: оскорбления, мат, продажа виртуальной валюты за реальные деньги (реал) и любые мошеннические схемы.\n"
      f"• При нарушении правил система может заблокировать доступ."
  )
  safe_send_message(m.chat.id, text, reply_markup=kb_main_menu())


def info_premium(m):
  text = (
      "💎 <b>VIP-статус в боте (100 ⭐)</b>\n\n"
      "Привилегии подписки:\n"
      "• Кулдаун на подачу сокращен в 2 раза (1 минута вместо 2х).\n"
      "• До 20 уведомлений по поиску.\n"
      "• Автоматические VIP-объявления бесплатно."
  )
  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton(
          "💎 Купить VIP на 30 дней (100 ⭐)", callback_data="buy_premium_30"
      )
  )
  safe_send_message(m.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data == "buy_premium_30")
def cb_buy_premium_30(call):
  prices = [types.LabeledPrice(label="VIP Статус на 30 дней", amount=100)]
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
      bot.answer_callback_query(call.id, f"Ошибка: {e}", show_alert=True)
    except Exception:
      pass


# ==========================================
# КАЛЬКУЛЯТОР И КУРС VC
# ==========================================
def show_vc_menu(m):
  rate = get_vc_rate()
  text = (
      f"💱 <b>Курс обмена Vice City</b>\n\n"
      f"Текущий курс: <b>1 VC = {rate:,.0f} SA $</b>"
  )
  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton("🔄 Конвертер валют", callback_data="vc_conv_start"),
      types.InlineKeyboardButton("🧮 Калькулятор", callback_data="vc_calc_start"),
  )
  if is_admin_or_owner(m.from_user):
    markup.add(types.InlineKeyboardButton("⚙️ Изменить курс VC", callback_data="vc_set_rate_start"))
  safe_send_message(m.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data == "vc_set_rate_start")
def cb_vc_set_rate_start(call):
  if not verify_admin_callback(call):
    return
  update_state(call.from_user.id, vc_setting_rate=True)
  safe_send_message(call.message.chat.id, "⚙️ Введите новый курс (SA $ за 1 VC):", reply_markup=kb_cancel())


@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("vc_setting_rate"))
def process_vc_set_rate(m):
  uid = m.from_user.id
  clear_state(uid)
  try:
    new_rate = float(m.text.strip().replace(" ", "").replace(",", "."))
    if new_rate <= 0:
      raise ValueError()
  except ValueError:
    return safe_send_message(m.chat.id, "⚠️ Неверный формат курса.")
  set_vc_rate(new_rate)
  safe_send_message(m.chat.id, f"✅ Курс обновлен: <b>1 VC = {new_rate:,.0f} SA $</b>", reply_markup=kb_main_menu())


@bot.callback_query_handler(func=lambda c: c.data == "vc_conv_start")
def cb_vc_conv_start(call):
  update_state(call.from_user.id, vc_conv_input=True)
  safe_send_message(call.message.chat.id, "🔄 Введите сумму (например: <code>1500000</code> или <code>500vc</code>):", reply_markup=kb_cancel())


@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("vc_conv_input"))
def process_vc_conv(m):
  uid = m.from_user.id
  clear_state(uid)
  text = m.text.strip().lower().replace(" ", "").replace(",", ".")
  rate = get_vc_rate()
  try:
    if "vc" in text:
      val = float(text.replace("vc", ""))
      sa_val = val * rate
      res = f"🧮 {val:,.2f} VC = <b>{sa_val:,.0f} SA $</b>"
    else:
      val = float(text)
      vc_val = val / rate if rate > 0 else 0
      res = f"🧮 {val:,.0f} SA $ = <b>{vc_val:,.2f} VC</b>"
  except ValueError:
    return safe_send_message(m.chat.id, "⚠️ Неверный формат.")
  safe_send_message(m.chat.id, res, reply_markup=kb_main_menu())


@bot.callback_query_handler(func=lambda c: c.data == "vc_calc_start")
def cb_vc_calc_start(call):
  update_state(call.from_user.id, vc_calc_step="buy_price")
  safe_send_message(call.message.chat.id, "🧮 Введите цену покупки на своем сервере (в SA $):", reply_markup=kb_cancel())


@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("vc_calc_step") == "buy_price")
def process_calc_buy(m):
  uid = m.from_user.id
  try:
    val = float(m.text.strip().replace(" ", "").replace(",", "."))
  except ValueError:
    return safe_send_message(m.chat.id, "⚠️ Введите число.")
  st = get_state(uid)
  st["calc_buy"] = val
  st["vc_calc_step"] = "sell_price"
  update_state(uid, **st)
  safe_send_message(m.chat.id, "2️⃣ Введите цену продажи в Vice City (в VC $):", reply_markup=kb_cancel())


@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("vc_calc_step") == "sell_price")
def process_calc_sell(m):
  uid = m.from_user.id
  try:
    val = float(m.text.strip().replace(" ", "").replace(",", "."))
  except ValueError:
    return safe_send_message(m.chat.id, "⚠️ Введите число.")
  st = get_state(uid)
  buy_price = st.get("calc_buy", 0)
  clear_state(uid)
  rate = get_vc_rate()
  sell_price_sa = val * rate
  profit = sell_price_sa - buy_price
  percent = (profit / buy_price * 100) if buy_price > 0 else 0
  res = (
      f"📊 <b>Расчет сделки:</b>\n\n"
      f"• Покупка: <b>{buy_price:,.0f} SA $</b>\n"
      f"• Продажа в VC: <b>{val:,.2f} VC</b> (~{sell_price_sa:,.0f} SA $)\n"
      f"💰 Прибыль: <b>{profit:,.0f} SA $</b> ({percent:+.2f}%)"
  )
  safe_send_message(m.chat.id, res, reply_markup=kb_main_menu())


# ==========================================
# АДМИН-ПАНЕЛЬ И ФУНКЦИИ ВЛАДЕЛЬЦА
# ==========================================
def admin_panel(m):
  if not is_admin_or_owner(m.from_user):
    return safe_send_message(m.chat.id, "⛔ Нет доступа.", reply_markup=kb_main_menu())
  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton("📤 Модерация продаж", callback_data="admin_mod_sales"),
      types.InlineKeyboardButton("📥 Модерация скупки", callback_data="admin_mod_buys"),
  )
  if is_owner(m.from_user):
    markup.add(
        types.InlineKeyboardButton("📢 Рассылка", callback_data="owner_broadcast_start"),
        types.InlineKeyboardButton("📋 Логи админов", callback_data="owner_get_logs"),
    )
  safe_send_message(m.chat.id, "👑 <b>Панель администратора:</b>", reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data == "owner_broadcast_start")
def cb_owner_broadcast_start(call):
  if not is_owner(call.from_user):
    try:
      return bot.answer_callback_query(call.id, "⛔ Только для владельца!", show_alert=True)
    except Exception:
      pass
    return
  update_state(call.from_user.id, owner_broadcast_input=True)
  safe_send_message(call.message.chat.id, "📢 Введите текст для рассылки всем пользователям бота:", reply_markup=kb_cancel())


@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("owner_broadcast_input"))
def process_owner_broadcast(m):
  uid = m.from_user.id
  if not is_owner(m.from_user):
    clear_state(uid)
    return
  text = m.text
  clear_state(uid)

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM user_data")
    users = cur.fetchall()

  success = 0
  fail = 0
  safe_send_message(m.chat.id, f"🚀 Начинаю рассылку для {len(users)} пользователей...")

  for row in users:
    target_id = row["user_id"]
    try:
      safe_send_message(target_id, f"📢 <b>Объявление администрации:</b>\n\n{text}")
      success += 1
      time.sleep(0.05)
    except Exception:
      fail += 1

  safe_send_message(m.chat.id, f"✅ <b>Рассылка завершена!</b>\n\n• Успешно: {success}\n• Ошибок: {fail}", reply_markup=kb_main_menu())


@bot.callback_query_handler(func=lambda c: c.data == "owner_get_logs")
def cb_owner_get_logs(call):
  if not is_owner(call.from_user):
    try:
      return bot.answer_callback_query(call.id, "⛔ Только для владельца!", show_alert=True)
    except Exception:
      pass
    return

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT admin_username, action, target, timestamp FROM admin_action_logs ORDER BY id DESC LIMIT 20")
    logs = cur.fetchall()

  if not logs:
    try:
      return bot.answer_callback_query(call.id, "📭 Логи действий админов пусты.", show_alert=True)
    except Exception:
      pass

  text = "📋 <b>Последние лог-записи действий админов:</b>\n\n"
  for row in logs:
    dt = datetime.fromtimestamp(row["timestamp"]).strftime("%d.%m.%Y %H:%M")
    text += f"👤 <b>{row['admin_username']}</b> | {row['action']} ({row['target']}) — <i>{dt}</i>\n"

  safe_send_message(call.message.chat.id, text, reply_markup=kb_main_menu())


@bot.callback_query_handler(func=lambda c: c.data in ["admin_mod_sales", "admin_mod_buys"])
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
      return bot.answer_callback_query(call.id, "📭 Очередь пуста.", show_alert=True)
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
    bot.edit_message_text("📋 <b>Очередь модерации:</b>", call.message.chat.id, call.message.message_id, reply_markup=markup)
  except Exception:
    pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("mod_open_") or c.data.startswith("mod_open_buy_"))
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
      return bot.answer_callback_query(call.id, "⚠️ Этот пост уже обработан.", show_alert=True)
    except Exception:
      pass

  markup = types.InlineKeyboardMarkup(row_width=2)
  acc_prefix = "mod_acc_buy_" if is_buy else "mod_acc_"
  rej_prefix = "mod_rej_buy_" if is_buy else "mod_rej_"
  bad_prefix = "mod_bad_buy_" if is_buy else "mod_bad_"
  
  markup.add(
      types.InlineKeyboardButton("✅ Одобрить", callback_data=f"{acc_prefix}{pid}"),
      types.InlineKeyboardButton("❌ Отклонить", callback_data=f"{rej_prefix}{pid}"),
  )
  markup.add(
      types.InlineKeyboardButton("⚠️ Плохой текст (Штраф)", callback_data=f"{bad_prefix}{pid}")
  )

  text = f"🔍 <b>Пост #{pid}</b>\n🌐 Сервер: {post['server']}\n📂 Категория: {post['category']}\n\n{post['text']}"
  if post["photo"]:
    safe_send_photo(call.message.chat.id, post["photo"], caption=text, reply_markup=markup)
  else:
    safe_send_message(call.message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("mod_acc_")
    or c.data.startswith("mod_acc_buy_")
    or c.data.startswith("mod_rej_")
    or c.data.startswith("mod_rej_buy_")
    or c.data.startswith("mod_bad_")
    or c.data.startswith("mod_bad_buy_")
)
def cb_mod_decision(call):
  if not verify_admin_callback(call):
    return
  is_buy = "buy" in call.data
  
  if "acc" in call.data:
    action = "acc"
    prefix = "mod_acc_buy_" if is_buy else "mod_acc_"
  elif "bad" in call.data:
    action = "bad"
    prefix = "mod_bad_buy_" if is_buy else "mod_bad_"
  else:
    action = "rej"
    prefix = "mod_rej_buy_" if is_buy else "mod_rej_"

  pid = int(call.data.replace(prefix, ""))
  p_table = "pending_buy_posts" if is_buy else "pending_posts"
  a_table = "active_buy_ads" if is_buy else "active_ads"

  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {p_table} WHERE id = ?", (pid,))
    post = cur.fetchone()
    
    if not post:
      try:
        return bot.answer_callback_query(call.id, "⚠️ Этот пост уже обработан.", show_alert=True)
      except Exception:
        pass
      return

    cur.execute(f"DELETE FROM {p_table} WHERE id = ?", (pid,))

  log_admin_action(call.from_user.username or str(call.from_user.id), action, f"Post #{pid}")

  if action == "acc":
    with db_lock, get_db() as conn:
      cur = conn.cursor()
      cur.execute(
          f"INSERT INTO {a_table} (user_id, server, category, text, photo, is_vip, last_updated) VALUES (?, ?, ?, ?, ?, ?, ?)",
          (post["user_id"], post["server"], post["category"], post["text"], post["photo"], post["is_vip"], time.time()),
      )
      new_ad_id = cur.lastrowid
    notify_subscribers(post["server"], post["text"], new_ad_id, is_buy=is_buy)
    safe_send_message(post["user_id"], f"✅ Ваше объявление #{new_ad_id} опубликовано!")
  elif action == "bad":
    record_admin_error(call.from_user.username, call.from_user.id)
    safe_send_message(post["user_id"], "❌ Ваше объявление отклонено из-за некачественного текста.")
  else:
    safe_send_message(post["user_id"], "❌ Ваше объявление отклонено модератором.")

  try:
    bot.answer_callback_query(call.id, "✅ Решение применено!")
    bot.delete_message(call.message.chat.id, call.message.message_id)
  except Exception:
    pass


# ==========================================
# ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def show_average_prices(m):
  uid = m.from_user.id
  srv = get_user_server(uid)
  with db_lock, get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT category, COUNT(*) as cnt FROM active_ads WHERE server = ? GROUP BY category", (srv,))
    sales_stats = cur.fetchall()

  text = f"📊 <b>Анализ рынка на сервере {html.escape(srv)}</b>\n\n📤 <b>Продажи:</b>\n"
  if sales_stats:
    for row in sales_stats:
      text += f"- {row['category']}: {row['cnt']} объявлений\n"
  else:
    text += "<i>Нет активных объявлений.</i>\n"
  safe_send_message(m.chat.id, text, reply_markup=kb_main_menu())


def contact_manager(m):
  markup = types.InlineKeyboardMarkup()
  markup.add(types.InlineKeyboardButton("💬 Написать менеджеру", url=f"https://t.me/{MANAGER_USERNAME}"))
  safe_send_message(m.chat.id, f"💬 <b>Связь с менеджером:</b> @{MANAGER_USERNAME}", reply_markup=markup)


# ==========================================
# ЗАПУСК БОТА ЧЕРЕЗ LONG POLLING
# ==========================================
if __name__ == "__main__":
  logger.info("Бот запущен в режиме Long Polling...")
  bot.remove_webhook()
  bot.infinity_polling(skip_pending=True)
