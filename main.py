import os
import time
import threading
import logging
from datetime import datetime, time as dtime
import telebot
from telebot import types

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==========================================
# 👇 ВСТАВЬТЕ СВОЙ ТОКЕН БОТА МЕЖДУ КАВЫЧКАМИ 👇
# ==========================================
TOKEN = '8916669266:AAEL2qZQajHu_ccWo-91XFmlLZRcUGl1klg'

if not TOKEN or TOKEN == '8916669266:AAEL2qZQajHu_ccWo-91XFmlLZRcUGl1klg':
    logger.error("8916669266:AAEL2qZQajHu_ccWo-91XFmlLZRcUGl1klg")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# Хранилища данных
user_states = {}
user_data = {}
active_ads = {}
pending_posts = {}
ads_lock = threading.Lock()
moderation_counter = 0

OWNER_USERNAME = "bounqy"
ADMIN_USERNAMES = ["bounqy31", "bounqy"]
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

def background_cleanup_ads():
    while True:
        time.sleep(30)
        now = datetime.now()
        now_time = now.time()
        curr_t = time.time()

        is_night = now_time >= dtime(22, 0, 22) or now_time < dtime(8, 0, 0)
        is_morning_clean = dtime(8, 0, 0) <= now_time <= dtime(8, 5, 22)

        with ads_lock:
            expired_ids = []
            for aid, data in active_ads.items():
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
                logger.info(f"Объявление {aid} удалено.")

threading.Thread(target=background_cleanup_ads, daemon=True).start()

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
    if now_time < dtime(8, 0, 0) or now_time > dtime(22, 0, 22):
        return False
    return True

def kb_servers():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for i in range(0, len(SERVERS), 2): 
        m.add(*[types.KeyboardButton(s) for s in SERVERS[i:i+2]])
    m.add(types.KeyboardButton("🛒 Подать объявление о продаже"), types.KeyboardButton("👑 Админ"))
    return m

def kb_categories():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("💍 Аксы", "🏎 Все авто,воздушные,водные,тюнинг")
    m.add("🥼 Скины и Охранники", "🏡 Дом и Бизнес")
    m.add("📦 Ресурсы и Оружие")
    m.add("🛒 Подать объявление о продаже")
    m.add("🔄 Сменить сервер", "👑 Админ")
    return m

def kb_cancel():
    return types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("🚫 Отмена"))

def get_category_key(text):
    t = text.lower()
    if "акс" in t: return "💍 Аксы"
    if "авто" in t or "тюнинг" in t: return "🏎 Все авто,воздушные,водные,тюнинг"
    if "скин" in t or "охранник" in t: return "🥼 Скины и Охранники"
    if "дом" in t or "бизнес" in t or "недвиж" in t: return "🏡 Дом и Бизнес"
    if "ресурс" in t or "оружие" in t: return "📦 Ресурсы и Оружие"
    return "💍 Аксы"

@bot.message_handler(commands=['start'])
def cmd_start(m):
    text = (
        "🛡 **Безопасность:**\n\n"
        "👇 НАЖМИ И ВЫБЕРИ СВОЙ СЕРВЕР 👇\n\n"
        "👋 Привет! Это неофициальный бот с ценами для Arizona RP!\n"
        "📈 Выбирай сервер из списка и узнавай актуальные цены с ЦР и АБ.\n\n"
        "🔒 МЫ НИКОГДА не просим пароли, пин-коды или данные от аккаунта!\n"
        "🎁 Бот абсолютно бесплатный — мы НЕ просим деньги за работу.\n\n"
        "📢 Наш Telegram-канал: @Bounty_Squad31\n\n"
        "🤝 Спасибо, что используешь нашего бота! Удачных сделок! 🍀"
    )
    bot.send_message(m.chat.id, text, parse_mode="Markdown", reply_markup=kb_servers())

@bot.message_handler(commands=['admin'])
def cmd_admin(m):
    if is_admin_or_owner(m.from_user):
        bot.send_message(m.chat.id, "👑 Панель администратора: Авторизован.")
    else:
        bot.send_message(m.chat.id, "⛔ Нет доступа.")

@bot.message_handler(func=lambda msg: msg.text in SERVERS)
def select_srv(m):
    user_states[m.from_user.id] = {"server": m.text}
    bot.send_message(m.chat.id, f"Сервер {m.text} выбран! Выберите категорию:", reply_markup=kb_categories())

@bot.message_handler(func=lambda msg: msg.text == "🔄 Сменить сервер")
def ch_srv(m): 
    bot.send_message(m.chat.id, "Выберите ваш сервер:", reply_markup=kb_servers())

@bot.message_handler(func=lambda msg: msg.text == "🚫 Отмена")
def cancel_all(m):
    user_states.pop(m.from_user.id, None)
    user_data.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, "Главное меню:", reply_markup=kb_categories())

@bot.message_handler(func=lambda msg: msg.text == "🛒 Подать объявление о продаже")
def ask_sub(m):
    if not check_working_hours():
        return bot.send_message(m.chat.id, "❌ После 22:00:22 МСК подача объявлений заблокирована до утреннего возобновления!")
    
    uid = m.from_user.id
    if uid in user_data and "last_ad_time" in user_data[uid]:
        if time.time() - user_data[uid]["last_ad_time"] < 600:
            remaining = int(600 - (time.time() - user_data[uid]["last_ad_time"]))
            return bot.send_message(m.chat.id, f"❌ Кулдаун! Подождите еще {remaining // 60} мин. {remaining % 60} сек. перед отправкой нового объявления.")

    if uid not in user_states or "server" not in user_states[uid]:
        return bot.send_message(m.chat.id, "⚠️ Сначала выберите сервер из главного меню!", reply_markup=kb_servers())

    instructions = (
        "📖 **Система подачи объявлений:**\n\n"
        "1. **Выбор сервера и категории**\n"
        f"   * Вы зашли на сервер **{user_states[uid].get('server')}**.\n"
        "   * В меню вы выбрали категорию товара (**машины**, **аксессуары** и т. д.).\n"
        "   * В разделе можно посмотреть уже существующие объявления.\n\n"
        "2. **Создание объявления**\n"
        "   * **Шаг 1:** Сервер выбран.\n"
        "   * **Шаг 2:** Категория определена.\n"
        "   * **Шаг 3:** Загружаете фото и указываете цену.\n"
        "   * **Шаг 4:** Отправляете объявление на проверку.\n\n"
        "3. **Модерация и публикация**\n"
        "   * Модератор проверяет вашу заявку и одобряет её.\n"
        "   * После одобрения объявление автоматически публикуется в выбранном разделе.\n\n"
        "👇 **Отправьте одним сообщением фото, текст описания и цену:**"
    )
    
    user_states[uid]["step"] = "waiting_for_submission"
    bot.send_message(m.chat.id, instructions, parse_mode="Markdown", reply_markup=kb_cancel())
    bot.register_next_step_handler(m, process_sub)

def process_sub(m):
    global moderation_counter
    uid = m.from_user.id
    if m.text == "🚫 Отмена":
        if uid in user_states: user_states[uid].pop("step", None)
        return bot.send_message(m.chat.id, "Отменено.", reply_markup=kb_categories())
    
    photo = m.photo[-1].file_id if m.photo else None
    text = m.caption or m.text
    if not photo and not text:
        return bot.send_message(m.chat.id, "❌ Пустое сообщение. Попробуйте снова.")

    if uid not in user_states:
        user_states[uid] = {"server": "Phoenix"}
    
    server_name = user_states[uid].get("server", "Phoenix")
    user_states[uid].pop("step", None)

    if uid not in user_data: user_data[uid] = {}
    user_data[uid]["last_ad_time"] = time.time()

    moderation_counter += 1
    uname = m.from_user.username or "Без юзернейма"
    cat = get_category_key(text or "")
    
    pending_posts[moderation_counter] = {
        "user_id": uid, "username": uname, "photo": photo, 
        "text": text or "Без описания", "category": cat, "server": server_name
    }

    markup = types.InlineKeyboardMarkup(row_width=1).add(
        types.InlineKeyboardButton("📝 Редакция", callback_data=f"edit_{moderation_counter}"),
        types.InlineKeyboardButton("✅ Принять", callback_data=f"owner_approve_{moderation_counter}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{moderation_counter}")
    )
    
    f_text = f"🚨 Новая заявка #{moderation_counter}\n🌐 Сервер: {server_name}\n📂 Категория: {cat}\n👤 От: {uid} (@{uname})\n\n📦:\n{text or ''}"
    target = MODERATION_CHAT_ID if MODERATION_CHAT_ID != -1001234567890 else m.chat.id
    
    try:
        if photo: bot.send_photo(target, photo, caption=f_text, reply_markup=markup)
        else: bot.send_message(target, f_text, reply_markup=markup)
    except:
        bot.send_message(m.chat.id, f_text, reply_markup=markup)
        
    bot.send_message(m.chat.id, "✅ Заявка отправлена на модерацию!", reply_markup=kb_categories())

@bot.message_handler(func=lambda msg: msg.text == "👑 Админ")
def admin_panel(m):
    u = m.from_user
    if not is_admin_or_owner(u):
        return bot.send_message(m.chat.id, "⛔ У вас нет доступа к админ-панели.")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📋 Ожидающие заявки", callback_data="show_pending_list"))
    bot.send_message(m.chat.id, f"⚙️ Панель управления\nСтатус: {'Владелец' if is_owner(u) else 'Админ'}", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in CATEGORIES)
def show_ads(m):
    uid = m.from_user.id
    srv = user_states.get(uid, {}).get("server", "Не выбран")
    cat_name = m.text
    
    with ads_lock: 
        ads_list = [ad for ad in active_ads.values() if ad.get("category") == cat_name and ad.get("server") == srv]
    
    bot.send_message(m.chat.id, f"📊 Раздел: {cat_name}\n🌐 Сервер: {srv}\n\n" + ("🛒 Актуальные предложения:" if ads_list else "В разделе пока нет объявлений для этого сервера."))
    for aid, ad in active_ads.items():
        if ad.get("category") == cat_name and ad.get("server") == srv:
            card = f"📢 Товар\n\n{ad['text']}\n\n👤 Публикация"
            try:
                if ad.get("photo"): sent = bot.send_photo(m.chat.id, ad["photo"], caption=card)
                else: sent = bot.send_message(m.chat.id, card)
                ad["subscribers"].add(m.chat.id)
                ad["message_ids_map"][m.chat.id] = sent.message_id
            except:
                pass

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    global pending_posts
    data, u = call.data, call.from_user

    if data.startswith("edit_"):
        pid = int(data.split('_')[1])
        if not is_admin_or_owner(u): 
            return bot.answer_callback_query(call.id, "⛔ Редактировать могут только админы!", show_alert=True)
        user_states[u.id] = {"editing": pid}
        bot.answer_callback_query(call.id)
        return bot.send_message(call.message.chat.id, f"✏️ Введите новый текст для заявки #{pid}:", reply_markup=kb_cancel())

    if data.startswith("owner_approve_"):
        pid = int(data.split('_')[2])
        if not is_owner(u): 
            return bot.answer_callback_query(call.id, "⛔ Только для владельца!", show_alert=True)
        if pid not in pending_posts: 
            return bot.answer_callback_query(call.id, "Заявка не найдена.")
        if not check_working_hours(): 
            return bot.answer_callback_query(call.id, "❌ Публикация после 22:00:22 запрещена!", show_alert=True)

        post = pending_posts.pop(pid)
        chan = "@Bounty_Squad31"
        p_text = f"🛒 Новое объявление!\n🌐 Сервер: {post['server']}\n\n{post['text']}\n\n👤 Продавец: @{post['username']}"
        try:
            if post["photo"]: sent = bot.send_photo(chan, post["photo"], caption=p_text)
            else: sent = bot.send_message(chan, p_text)
                
            with ads_lock:
                active_ads[pid] = {
                    "text": p_text, "photo": post["photo"], "server": post["server"],
                    "editor": f"@{u.username}" if u.username else u.first_name, 
                    "last_updated": time.time(), "category": post["category"],
                    "subscribers": {chan[1:]}, "message_ids_map": {chan: sent.message_id}
                }
            bot.answer_callback_query(call.id, "Опубликовано!")
            if call.message.caption:
                bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption="✅ Одобрено владельцем", reply_markup=None)
            else:
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="✅ Одобрено", reply_markup=None)
            
            try: bot.send_message(post["user_id"], "🎉 Ваша заявка одобрена и опубликована!")
            except: pass
        except Exception as e:
            bot.answer_callback_query(call.id, f"Ошибка: {e}", show_alert=True)

    elif data.startswith("reject_"):
        pid = int(data.split('_')[1])
        if not is_admin_or_owner(u): 
            return bot.answer_callback_query(call.id, "Нет прав.", show_alert=True)
        if pid in pending_posts:
            p_info = pending_posts.pop(pid)
            bot.answer_callback_query(call.id, "Отклонено.")
            try:
                if call.message.caption:
                    bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption="❌ Отклонено", reply_markup=None)
                else:
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="❌ Отклонено", reply_markup=None)
                bot.send_message(p_info["user_id"], "❌ Ваша заявка была отклонена.")
            except: pass

    elif data == "show_pending_list":
        bot.answer_callback_query(call.id, f"Ожидающих заявок: {len(pending_posts)}", show_alert=True)

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states and "editing" in user_states[msg.from_user.id])
def process_editing(m):
    uid = m.from_user.id
    pid = user_states[uid].get("editing")
    user_states[uid].pop("editing", None)
    
    if m.text == "🚫 Отмена":
        return bot.send_message(m.chat.id, "Отменено.", reply_markup=kb_categories())

    if pid in pending_posts:
        pending_posts[pid]["text"] = m.text
        bot.send_message(m.chat.id, f"✅ Текст заявки #{pid} успешно изменен редакцией!", reply_markup=kb_categories())
    else:
        bot.send_message(m.chat.id, "❌ Заявка уже обработана или не найдена.", reply_markup=kb_categories())

if __name__ == '__main__':
    bot.remove_webhook()
    print("🚀 Бот по ТЗ Arizona RP запущен!")
    bot.infinity_polling(skip_pending=True)
