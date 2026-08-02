import os
import time
import threading
from datetime import datetime, time as dtime
import telebot
from telebot import types

TOKEN = "8962696714:AAH5dYsLqlAqoLdVr5-sJH35OJnw1ttgpJ0"
bot = telebot.TeleBot(TOKEN)

user_states, user_data, active_ads, pending_posts = {}, {}, {}, {}
ads_lock = threading.Lock()
moderation_counter = 0

OWNER_USERNAME = "bounqy"
ADMIN_USERNAMES = ["bounqy31", "bounqy"]
MODERATION_CHAT_ID = -1001234567890
admins = {"server_1": set(), "server_2": set()}

SERVERS = [
    "🔥 Phoenix", "🌴 Tucson", "🌵 Scottdale", "⚜️ Chandler", "❄️ Brainburg", "🌊 Yuma",
    "✨ Saint-Rose", "🏛 Mesa", "❤️ Red-Rock", "🍀 Surprise", "⚡️ Prescott", "🌲 Glendale",
    "👑 Kingman", "⚓️ Winslow", "🌴 Payson", "💎 Gilbert", "🔥 Show-Low", "🌴 Casa-Grande",
    "📜 Page", "☀️ Sun-City", "👑 Queen-Creek", "🌵 Sedona", "🎄 Holiday", "🍀 Wednesday",
    "⚡️ Yava", "🌌 Faraway", "🎁 Christmas", "🐝 Bumble Bee", "🪞 Mirage", "💖 Love",
    "📱 Mobile I", "📱 Mobile II", "📱 Mobile III"
]

# --- ФОНОВЫЙ ПОТОК ОЧИСТКИ ---
def background_cleanup_ads():
    while True:
        time.sleep(30)
        now_time = datetime.now().time()
        is_outside_hours = not (dtime(8, 0) <= now_time <= dtime(22, 0))
        curr_t = time.time()
        
        with ads_lock:
            expired = [aid for aid, d in active_ads.items() if (curr_t - d["last_updated"] > 600) or is_outside_hours]
            for aid in expired:
                for sub_id, msg_id in list(active_ads[aid].get("message_ids_map", {}).items()):
                    try: bot.delete_message(sub_id, msg_id)
                    except: pass
                del active_ads[aid]

threading.Thread(target=background_cleanup_ads, daemon=True).start()

# --- ПРОВЕРКИ ПРАВ ---
def is_owner(u): return u.username and u.username.lower() == OWNER_USERNAME.lower()
def is_admin_or_owner(u): return u and (is_owner(u) or (u.username and u.username.lower() in [a.lower() for a in ADMIN_USERNAMES]))
def is_server_admin(uid, s_key): return uid in admins.get(s_key, set())
def check_working_hours(): return dtime(8, 0) <= datetime.now().time() <= dtime(22, 0)

# --- КЛАВИАТУРЫ ---
def kb_servers(admin_mode=False):
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for i in range(0, len(SERVERS), 2): m.add(*[types.KeyboardButton(s) for s in SERVERS[i:i+2]])
    m.add(types.KeyboardButton("🚫 Отмена" if admin_mode else "🛒 Подать объявление о продаже"), types.KeyboardButton("⚙️ Панель администратора" if not admin_mode else "нет"))
    return m

def kb_categories():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("💍 Аксы", "🏎 Все авто,воздушные,водные,тюнинг")
    m.add("🥼 Скины и Охранники", "🏡 Дома и Бизнесы")
    m.add("📦 Ресурсы и Оружие")
    m.add("🛒 Подать объявление о продаже", "⚙️ Панель администратора")
    m.add("🔄 Сменить сервер")
    return m

def kb_cancel():
    return types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("🚫 Отмена"))

def kb_admin_types():
    return types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2).add(
        "🚗 Продажа машины", "💍 Продажа акса", "🥼 Продажа скина", "🏡 Продажа недвижимости", "🚫 Отмена"
    )

# --- ОБРАБОТЧИКИ КОМАНД ---
@bot.message_handler(commands=['start'])
def cmd_start(m):
    bot.send_message(m.chat.id, "👇 НАЖМИ И ВЫБЕРИ СВОЙ СЕРВЕР 👇\n\n👋 Привет! Неофициальный бот с ценами Arizona RP!\n📢 Канал: @Bounty_Squad31", reply_markup=kb_servers())

@bot.message_handler(commands=['admin'])
def cmd_admin(m):
    bot.send_message(m.chat.id, "👑 **Панель администратора:** Авторизован." if is_admin_or_owner(m.from_user) else "⛔ Нет доступа.", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text in SERVERS)
def select_srv(m):
    if user_states.get(m.from_user.id) == "admin_choosing_server":
        user_data[m.from_user.id]["server"] = m.text
        user_states[m.from_user.id] = "admin_entering_price_and_desc"
        bot.send_message(m.chat.id, "Введите описание и сумму товара (текстом или с фото):", reply_markup=kb_cancel())
    else:
        user_states[m.chat.id] = m.text
        bot.send_message(m.chat.id, f"Сервер **{m.text}** выбран! Выберите категорию:", parse_mode="Markdown", reply_markup=kb_categories())

@bot.message_handler(func=lambda msg: msg.text == "🔄 Сменить сервер")
def ch_srv(m): bot.send_message(m.chat.id, "Выберите ваш сервер:", reply_markup=kb_servers())

@bot.message_handler(func=lambda msg: msg.text == "🚫 Отмена")
def cancel_all(m):
    user_states.pop(m.from_user.id, None)
    user_data.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, "Главное меню:", reply_markup=kb_categories())

@bot.message_handler(func=lambda msg: msg.text == "🛒 Подать объявление о продаже")
def ask_sub(m):
    if not check_working_hours():
        return bot.send_message(m.chat.id, "❌ Подача объявлений разрешена только с 08:00 до 22:00!")
    user_states[m.from_user.id] = "waiting_for_submission"
    bot.send_message(m.chat.id, "Отправьте **одним сообщением** фото и описание:", parse_mode="Markdown", reply_markup=kb_cancel())
    bot.register_next_step_handler(m, process_sub)

def process_sub(m):
    global moderation_counter
    user_states.pop(m.from_user.id, None)
    if m.text == "🚫 Отмена": return bot.send_message(m.chat.id, "Отменено.", reply_markup=kb_categories())
    
    photo = m.photo[-1].file_id if m.photo else None
    text = m.caption or m.text
    if not photo and not text: return bot.send_message(m.chat.id, "❌ Пустое сообщение. Попробуйте снова.")

    moderation_counter += 1
    uname = m.from_user.username or "Без юзернейма"
    pending_posts[moderation_counter] = {"user_id": m.from_user.id, "username": uname, "photo": photo, "text": text or "Без описания"}

    markup = types.InlineKeyboardMarkup(row_width=1).add(
        types.InlineKeyboardButton("1️⃣ Заявки на админа", callback_data=f"admin_apps_{moderation_counter}"),
        types.InlineKeyboardButton("2️⃣ Редакция", callback_data=f"edit_{moderation_counter}"),
        types.InlineKeyboardButton("3️⃣ Принять (Только для владельца)", callback_data=f"owner_approve_{moderation_counter}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{moderation_counter}")
    )
    
    f_text = f"🚨 **Новая заявка #{moderation_counter}**\n👤 От: `{m.from_user.id}` (@{uname})\n\n📦:\n{text or ''}"
    target = MODERATION_CHAT_ID if MODERATION_CHAT_ID != -1001234567890 else m.chat.id
    
    try:
        bot.send_photo(target, photo, caption=f_text, parse_mode="Markdown", reply_markup=markup) if photo else bot.send_message(target, f_text, parse_mode="Markdown", reply_markup=markup)
    except:
        bot.send_message(m.chat.id, f_text, parse_mode="Markdown", reply_markup=markup)
        
    bot.send_message(m.chat.id, "✅ Заявка отправлена на модерацию!", reply_markup=kb_categories())

@bot.message_handler(func=lambda msg: msg.text == "⚙️ Панель администратора")
def admin_panel(m):
    u = m.from_user
    if not (is_admin_or_owner(u) or any(is_server_admin(u.id, s) for s in admins)):
        return bot.send_message(m.chat.id, "У вас нет доступа.")
    
    markup = types.InlineKeyboardMarkup()
    if is_owner(u):
        markup.add(types.InlineKeyboardButton("➕ Назначить админа", callback_data="owner_add_adm"), types.InlineKeyboardButton("➖ Снять админа", callback_data="owner_rem_adm"))
    markup.add(types.InlineKeyboardButton("📝 Создать пост (Админ)", callback_data="admin_create_post"), types.InlineKeyboardButton("📋 Ожидающие заявки", callback_data="show_pending_list"))
    bot.send_message(m.chat.id, f"⚙️ **Панель управления**\nСтатус: {'Владелец' if is_owner(u) else 'Админ'}", parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in ["💍 Аксы", "🏎 Все авто,воздушные,водные,тюнинг", "🥼 Скины и Охранники", "🏡 Дома и Бизнесы", "📦 Ресурсы и Оружие"])
def show_ads(m):
    srv = user_states.get(m.chat.id, "Не выбран")
    with ads_lock: ads_list = list(active_ads.values())
    
    bot.send_message(m.chat.id, f"📊 Раздел: **{m.text}**\n🌐 Сервер: **{srv}**\n\n" + ("🛒 **Актуальные предложения:**" if ads_list else "В разделе пока нет объявлений."), parse_mode="Markdown")
    for ad_id, ad in active_ads.items():
        card = f"📢 **Товар**\n\n{ad['text']}\n\n👤 Админ: {ad['editor']}"
        sent = bot.send_photo(m.chat.id, ad["photo"], caption=card, parse_mode="Markdown") if ad.get("photo") else bot.send_message(m.chat.id, card, parse_mode="Markdown")
        ad["subscribers"].add(m.chat.id)
        ad["message_ids_map"][m.chat.id] = sent.message_id

# --- ОБРАБОТКА CALLBACK КНОПОК ---
@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    global pending_posts
    data, u = call.data, call.from_user

    if data == "admin_create_post":
        if not is_admin_or_owner(u): return bot.answer_callback_query(call.id, "Недостаточно прав.", show_alert=True)
        user_states[u.id], user_data[u.id] = "admin_choosing_type", {}
        bot.answer_callback_query(call.id)
        return bot.send_message(call.message.chat.id, "Выберите тип товара:", reply_markup=kb_admin_types())

    if data.startswith("admin_apps_"):
        return bot.answer_callback_query(call.id, text=f"Заявка #{data.split('_')[2]}", show_alert=True)

    if data.startswith("edit_"):
        pid = int(data.split('_')[1])
        if not is_admin_or_owner(u): return bot.answer_callback_query(call.id, "⛔ Редактировать могут только админы!", show_alert=True)
        user_states[u.id] = f"editing_post_{pid}"
        bot.answer_callback_query(call.id)
        return bot.send_message(call.message.chat.id, f"✏️ Введите новый текст для заявки #{pid}:", reply_markup=kb_cancel())

    if data.startswith("owner_approve_"):
        pid = int(data.split('_')[2])
        if not is_owner(u): return bot.answer_callback_query(call.id, "⛔ Только для владельца!", show_alert=True)
        if pid not in pending_posts: return bot.answer_callback_query(call.id, "Заявка не найдена.")
        if not check_working_hours(): return bot.answer_callback_query(call.id, "❌ Публикация с 08:00 до 22:00!", show_alert=True)

        post = pending_posts.pop(pid)
        chan = "@Bounty_Squad31"
        p_text = f"🛒 **Новое объявление!**\n\n{post['text']}\n\n👤 Продавец: @{post['username']}"
        try:
            sent = bot.send_photo(chan, post["photo"], caption=p_text, parse_mode="Markdown") if post["photo"] else bot.send_message(chan, p_text, parse_mode="Markdown")
            with ads_lock:
                active_ads[pid] = {"text": p_text, "photo": post["photo"], "editor": f"@{u.username}" if u.username else u.first_name, "last_updated": time.time(), "subscribers": {chan[1:]}, "message_ids_map": {chan: sent.message_id}}
            bot.answer_callback_query(call.id, "Опубликовано!")
            bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption="✅ Одобрено владельцем", reply_markup=None) if call.message.caption else bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="✅ Одобрено", reply_markup=None)
            try: bot.send_message(post["user_id"], "🎉 Ваша заявка одобрена и опубликована!")
            except: pass
        except Exception as e:
            bot.answer_callback_query(call.id, f"Ошибка: {e}", show_alert=True)

    elif data.startswith("reject_"):
        pid = int(data.split('_')[1])
        if not is_admin_or_owner(u): return bot.answer_callback_query(call.id, "Нет прав.", show_alert=True)
        if pid in pending_posts:
            p_info = pending_posts.pop(pid)
            bot.answer_callback_query(call.id, "Отклонено.")
            try:
                bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption="❌ Отклонено", reply_markup=None) if call.message.caption else bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="❌ Отклонено", reply_markup=None)
                bot.send_message(p_info["user_id"], "❌ Ваша заявка была отклонена.")
            except: pass

    elif data == "owner_add_adm":
        if is_owner(u):
            msg = bot.send_message(call.message.chat.id, "Отправьте ID и сервер (`12345 server_1`):", parse_mode="Markdown")
            bot.register_next_step_handler(msg, lambda m: admins.get(m.text.split()[1], set()).add(int(m.text.split()[0])) if is_owner(m.from_user) else None)
    elif data == "show_pending_list":
        bot.answer_callback_query(call.id, f"Ожидающих заявок: {len(pending_posts)}", show_alert=True)

# --- ШАГИ СОЗДАНИЯ ПОСТА АДМИНОМ И РЕДАКТИРОВАНИЯ ---
@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id, "").startswith("editing_post_") or user_states.get(msg.from_user.id) in ["admin_choosing_type", "admin_entering_price_and_desc"])
def multi_steps(m):
    uid = m.from_user.id
    state = user_states.get(uid, "")
    
    if m.text == "🚫 Отмена":
        user_states.pop(uid, None); user_data.pop(uid, None)
        return bot.send_message(m.chat.id, "Отменено.", reply_markup=kb_categories())

    if state.startswith("editing_post_"):
        pid = int(state.split("_")[2])
        user_states.pop(uid, None)
        adm_name = f"@{m.from_user.username}" if m.from_user.username else m.from_user.first_name
        with ads_lock:
            if pid in active_ads:
                ad = active_ads[pid]
                ad["text"], ad["editor"], ad["last_updated"] = m.text, adm_name, time.time()
                upd_card = f"📢 **Объявление (Отредактировано)**\n\n{m.text}\n\n👤 Админ: {adm_name}"
                for sub_id, msg_id in list(ad["message_ids_map"].items()):
                    try:
                        bot.edit_message_caption(chat_id=sub_id, message_id=msg_id, caption=upd_card, parse_mode="Markdown") if ad.get("photo") else bot.edit_message_text(chat_id=sub_id, message_id=msg_id, text=upd_card, parse_mode="Markdown")
                    except: pass
        return bot.send_message(m.chat.id, "✅ Успешно отредактировано!", reply_markup=kb_categories())

    if state == "admin_choosing_type":
        t_map = {"🚗 Продажа машины": "Продажа машины", "💍 Продажа акса": "Продажа аксессуара", "🥼 Продажа скина": "Продажа скина", "🏡 Продажа недвижимости": "Продажа недвижимости"}
        if m.text not in t_map: return bot.send_message(m.chat.id, "❌ Выберите тип кнопкой.")
        user_data[uid] = {"item_type": t_map[m.text]}
        user_states[uid] = "admin_choosing_server"
        return bot.send_message(m.chat.id, "Теперь выберите сервер:", reply_markup=kb_servers(admin_mode=True))

    if state == "admin_entering_price_and_desc":
        if not check_working_hours():
            user_states.pop(uid, None); user_data.pop(uid, None)
            return bot.send_message(m.chat.id, "❌ Публикация разрешена только с 08:00 до 22:00!", reply_markup=kb_categories())
        
        d = user_data.pop(uid, {})
        user_states.pop(uid, None)
        global moderation_counter
        moderation_counter += 1
        
        photo = m.photo[-1].file_id if m.photo else None
        text = m.caption or m.text or "Без описания"
        f_text = f"🛒 **{d.get('item_type', 'Товар')}**\n🌐 Сервер: **{d.get('server', 'Не указан')}**\n\n{text}\n\n👑 Опубликовано администратором"
        chan = "@Bounty_Squad31"
        
        try:
            sent = bot.send_photo(chan, photo, caption=f_text, parse_mode="Markdown") if photo else bot.send_message(chan, f_text, parse_mode="Markdown")
            with ads_lock:
                active_ads[moderation_counter] = {"text": f_text, "photo": photo, "editor": f"@{m.from_user.username}" if m.from_user.username else m.from_user.first_name, "last_updated": time.time(), "subscribers": {chan[1:]}, "message_ids_map": {chan: sent.message_id}}
            bot.send_message(m.chat.id, "✅ Опубликовано в канал!", reply_markup=kb_categories())
        except Exception as e:
            bot.send_message(m.chat.id, f"❌ Ошибка: {e}", reply_markup=kb_categories())

# Запуск
if __name__ == '__main__':
    bot.remove_webhook()
    print("🚀 Бот успешно запущен (оптимизированная версия)!")
    bot.infinity_polling(skip_pending=True)
