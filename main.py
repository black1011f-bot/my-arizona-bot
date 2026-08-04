import os
import time
import threading
import logging
import sqlite3
import re
import html
import requests
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

# ==========================================
# ЛОГИРОВАНИЕ И КОНФИГУРАЦИЯ
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
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
    "🔥 Phoenix", "🌴 Tucson", "🌵 Scottdale", "⚜️ Chandler", "❄️ Brainburg", "🌊 Yuma",
    "✨ Saint-Rose", "🏛 Mesa", "❤️ Red-Rock", "🍀 Surprise", "⚡️ Prescott", "🌲 Glendale",
    "👑 Kingman", "⚓️ Winslow", "🌴 Payson", "💎 Gilbert", "🔥 Show-Low", "🌴 Casa-Grande",
    "📜 Page", "☀️ Sun-City", "👑 Queen-Creek", "🌵 Sedona", "🎄 Holiday", "🍀 Wednesday",
    "⚡️ Yava", "🌌 Faraway", "🎁 Christmas", "🐝 Bumble Bee", "🪞 Mirage", "💖 Love",
    "📱 Mobile I", "📱 Mobile II", "📱 Mobile III"
]

CATEGORIES = [
    "💍 Аксессуары и вещи",
    "🚗 Транспорт и тюнинг",
    "👕 Скины и охранники",
    "🏠 Недвижимость и бизнесы",
    "📦 Ресурсы и материалы"
]

# ==========================================
# СИСТЕМА ПЕРЕВОДОВ (ЯЗЫКИ СНГ + АНГЛИЙСКИЙ)
# ==========================================
TRANSLATIONS = {
    "ru": {
        "welcome": "🌟 <b>Привет! Обратите внимание: мы не официальный бот</b>, а независимый помощник для игроков Arizona RP. Мы помогаем игрокам находить аксессуары, транспорт, недвижимость и другие ценные вещи, а также следить за экономикой и курсами.\n\n🔒 <b>Безопасность:</b> Мы <b>никогда</b> не просим пароли от игровых аккаунтов или личные данные!\n\n⏱ <b>Режим работы радиоцентра:</b> ежедневно с <b>08:00:01 до 22:00:01 МСК</b>.\n\n👇 <b>Для начала работы выберите свой игровой сервер ниже:</b>",
        "lang_changed": "✅ Язык успешно изменен на русский.",
        "btn_change_server": "🌐 Сменить игровой сервер",
        "btn_change_lang": "🌐 Сменить язык",
        "btn_accessories": "💍 Аксессуары и вещи",
        "btn_transport": "🚗 Транспорт и тюнинг",
        "btn_skins": "👕 Скины и охранники",
        "btn_realestate": "🏠 Недвижимость и бизнесы",
        "btn_resources": "📦 Ресурсы и материалы",
        "btn_sell": "📤 Продать товар",
        "btn_buy": "📥 Скупить товар",
        "btn_vc_calc": "💱 Курс VC и калькулятор",
        "btn_find_ad": "🔍 Найти товар в базе",
        "btn_favorites": "❤️ Сохраненные",
        "btn_notifications": "🔔 Уведомления о поиске",
        "btn_my_ads": "📋 Мои публикации",
        "btn_avg_prices": "📊 Анализ цен на сервере",
        "btn_vip": "💎 VIP-статус",
        "btn_admin_panel": "👑 Админ-панель",
        "btn_become_editor": "📝 Стать редактором / админом",
        "btn_cancel": "❌ Отменить действие",
        "btn_help": "📖 Справка и правила",
        "cat_accessories": "💍 Аксессуары и вещи",
        "cat_transport": "🚗 Транспорт и тюнинг",
        "cat_skins": "👕 Скины и охранники",
        "cat_realestate": "🏠 Недвижимость и бизнесы",
        "cat_resources": "📦 Ресурсы и материалы",
        "help_text": (
            "🛠 <b>Помощь, правила и расширенный FAQ</b>\n\n"
            "❓ <b>1. Как подать объявление о продаже или скупке?</b>\n"
            "💡 <i>Выберите нужный игровой сервер в главном меню -> Нажмите «📤 Продать товар» или «📥 Скупить товар» -> Выберите категорию -> Введите товар, цену и условия -> Отправьте на модерацию редакторам.</i>\n\n"
            "❓ <b>2. Сколько времени модераторы проверяют заявки?</b>\n"
            "💡 <i>Обычно проверка занимает от силы пару минут, если редактора находятся в сети. Вы получите уведомление в чат сразу после публикации или отклонения объявления.</i>\n\n"
            "❓ <b>3. Как изменить или удалить уже опубликованное объявление?</b>\n"
            "💡 <i>В личном кабинете или разделе управления объявлениями вы можете в любой момент снять товар с публикации, изменить цену или обновить описание.</i>\n\n"
            "❓ <b>4. Как работает калькулятор Vice City и конвертер валют?</b>\n"
            "💡 <i>В разделе «💱 Курс VC и калькулятор» можно мгновенно переводить вирты в VC-баксы по актуальному курсу, а также рассчитывать выгоду перелетов и чистую прибыль с учетом комиссий.</i>\n\n"
            "❓ <b>5. Как безопасно связаться с продавцом или покупателем?</b>\n"
            "💡 <i>Под карточкой каждого активного объявления есть кнопка «✉️ Написать автору». Она открывает защищенный внутренний чат для обсуждения всех деталей сделки.</i>\n\n"
            "❓ <b>6. Каковы главные правила подачи объявлений и модерации?</b>\n"
            "💡 <i>Запрещено указывать нереалистичные цены, использовать нецензурную лексику, рекламировать сторонние ресурсы или нарушать правила проекта. Нарушители могут получить бан в боте.</i>\n\n"
            "❓ <b>7. Что делать, если мое объявление отклонили?</b>\n"
            "💡 <i>В системном уведомлении об отклонении всегда указана причина. Чаще всего это опечатки, отсутствие конкретики или нарушение правил. Просто исправьте текст и отправьте его повторно.</i>\n\n"
            "❓ <b>8. Куда обращаться при обнаружении багов или технических неполадок?</b>\n"
            "💡 <i>Если бот завис, работает некорректно или вы нашли ошибку, обязательно напишите об этом в наше официальное сообщество ВКонтакте: <b>@bountyarz</b>. Наша команда оперативно всё проверит!</i>\n\n"
            "⏱ <b>Дополнительная информация:</b> Радиоцентр и редакция работают ежедневно с <b>08:00:01 до 22:00:01 МСК</b>."
        ),
        "how_it_works": (
            "📖 <b>Справочник: Как работает бот и радиоцентр</b>\n\n"
            "1. <b>Подача объявления:</b> Выбирается тип (продажа/скупка), сервер, категория и текст.\n"
            "2. <b>Проверка редакторами:</b> Редакторы проверяют материалы с 08:00:01 до 22:00:01 МСК.\n"
            "3. <b>Публикация:</b> Одобренное объявление уходит в ленту.\n"
            "4. <b>Инструменты VC:</b> Полноценный курс, конвертер и калькулятор прибыли для перекупщиков."
        ),
        "vip_info": (
            "💎 <b>Премиум-статус (VIP) в боте</b>\n\n"
            "{status_text}\n\n"
            "Преимущества VIP статуса:\n"
            "• Значок премиум-аккаунта в ваших объявлениях\n"
            "• Приоритетное размещение товаров\n\n"
            "Стоимость: <b>50 Telegram Stars</b> на 30 дней."
        ),
        "search_prompt": "🔍 <b>Поиск товара в базе объявлений:</b>\n\nОтправьте ключевое слово или название предмета для поиска (например: <code>аксессуар</code>, <code>нимб</code>, <code>дом</code>):",
        "sub_prompt": "✍️ Отправьте ключевое слово или фразу для отслеживания (например: <code>скин</code> или <code>нимб</code>):",
        "admin_app_prompt": (
            "📝 <b>Электронное заявление на пост редактора СМИ (Arizona RP Style)</b>\n\n"
            "Пожалуйста, заполните заявку в свободной форме. Укажите:\n"
            "• Ваш игровой ник и сервер\n"
            "• Ваш возраст и часовой пояс\n"
            "• Опыт работы в СМИ / почему хотите занять этот пост\n\n"
            "<i>Отправьте ваш текст ответным сообщением в чат:</i>"
        ),
    },
    "uk": {
        "welcome": "🌟 <b>Привіт! Зверніть увагу: ми не офіційний бот</b>, а незалежний помічник для гравців Arizona RP. Ми допомагаємо гравцям знаходити аксесуари, транспорт, нерухомість та інші цінні речі, а також стежити за економікою та курсами.\n\n🔒 <b>Безпека:</b> Ми <b>ніколи</b> не просимо паролі від ігрових акаунтів або особисті дані!\n\n⏱ <b>Режим роботи радіоцентру:</b> щодня з <b>08:00:01 до 22:00:01 МСК</b>.\n\n👇 <b>Для початку роботи виберіть свій ігровий сервер нижче:</b>",
        "lang_changed": "✅ Мову успішно змінено на українську.",
        "btn_change_server": "🌐 Змінити ігровий сервер",
        "btn_change_lang": "🌐 Змінити мову",
        "btn_accessories": "💍 Аксесуари та речі",
        "btn_transport": "🚗 Транспорт і тюнінг",
        "btn_skins": "👕 Скіни та охоронці",
        "btn_realestate": "🏠 Нерухомість і бізнеси",
        "btn_resources": "📦 Ресурси та матеріали",
        "btn_sell": "📤 Продати товар",
        "btn_buy": "📥 Скупити товар",
        "btn_vc_calc": "💱 Курс VC та калькулятор",
        "btn_find_ad": "🔍 Знайти товар у базі",
        "btn_favorites": "❤️ Збережені",
        "btn_notifications": "🔔 Сповіщення про пошук",
        "btn_my_ads": "📋 Мої публікації",
        "btn_avg_prices": "📊 Аналіз цін на сервері",
        "btn_vip": "💎 VIP-статус",
        "btn_admin_panel": "👑 Адмін-панель",
        "btn_become_editor": "📝 Стати редактором / адміном",
        "btn_cancel": "❌ Скасувати дію",
        "btn_help": "📖 Довідка та правила",
        "cat_accessories": "💍 Аксесуари та речі",
        "cat_transport": "🚗 Транспорт і тюнінг",
        "cat_skins": "👕 Скіни та охоронці",
        "cat_realestate": "🏠 Нерухомість і бізнеси",
        "cat_resources": "📦 Ресурси та матеріали",
        "help_text": (
            "🛠 <b>Допомога, правила та розширений FAQ</b>\n\n"
            "❓ <b>1. Як подати оголошення про продаж чи скуповування?</b>\n"
            "💡 <i>Виберіть потрібний ігровий сервер у головному меню -> Натисніть «📤 Продати товар» або «📥 Скупити товар» -> Виберіть категорію -> Введіть товар, ціну та умови -> Надішліть на модерацію редакторам.</i>\n\n"
            "❓ <b>2. Скільки часу модератори перевіряють заявки?</b>\n"
            "💡 <i>Зазвичай перевірка займає кілька хвилин, якщо редактори в мережі. Ви отримаєте сповіщення в чат одразу після публікації чи відхилення оголошення.</i>\n\n"
            "❓ <b>3. Як змінити чи видалити вже опубліковане оголошення?</b>\n"
            "💡 <i>В особистому кабінеті або розділі управління оголошеннями ви можете будь-якої хвилини зняти товар з публікації, змінити ціну або оновити опис.</i>\n\n"
            "❓ <b>4. Як працює калькулятор Vice City та конвертер валют?</b>\n"
            "💡 <i>У розділі «💱 Курс VC та калькулятор» можна миттєво переводити вірти у VC-бакси за актуальним курсом, а також розраховувати вигоду перельотів та чистий прибуток з урахуванням комісій.</i>\n\n"
            "❓ <b>5. Як безпечно зв'язатися з продавцем чи покупцем?</b>\n"
            "💡 <i>Під карткою кожного активного оголошення є кнопка «✉️ Написати автору». Вона відкриває захищений внутрішній чат для обговорення всіх деталей угоди.</i>\n\n"
            "❓ <b>6. Які головні правила подачі оголошень та модерації?</b>\n"
            "💡 <i>Заборонено вказувати нереалістичні ціни, використовувати нецензурну лексику, рекламувати сторонні ресурси або порушувати правила проєкту. Порушники можуть отримати бан у боті.</i>\n\n"
            "❓ <b>7. Що робити, якщо моє оголошення відхилили?</b>\n"
            "💡 <i>У системному сповіщенні про відхилення завжди вказано причину. Найчастіше це друкарські помилки, відсутність конкретики чи порушення правил. Просто виправте текст і надішліть його повторно.</i>\n\n"
            "❓ <b>8. Куди звертатися у разі виявлення багів чи технічних неполадок?</b>\n"
            "💡 <i>Якщо бот завис, працює некоректно або ви знайшли помилку, обов'язково напишіть про це в нашу офіційну спільноту: <b>@bountyarz</b>. Наша команда оперативно все перевірить!</i>\n\n"
            "⏱ <b>Додаткова інформація:</b> Радіоцентр та редакція працюють щодня з <b>08:00:01 до 22:00:01 МСК</b>."
        ),
        "how_it_works": (
            "📖 <b>Довідник: Як працює бот і радіоцентр</b>\n\n"
            "1. <b>Подача оголошення:</b> Вибирається тип (продаж/скупка), сервер, категорія та текст.\n"
            "2. <b>Перевірка редакторами:</b> Редактори перевіряють матеріали з 08:00:01 до 22:00:01 МСК.\n"
            "3. <b>Публікація:</b> Схвалене оголошення йде у стрічку.\n"
            "4. <b>Інструменти VC:</b> Повноцінний курс, конвертер та калькулятор прибутку для перекупників."
        ),
        "vip_info": (
            "💎 <b>Преміум-статус (VIP) у боті</b>\n\n"
            "{status_text}\n\n"
            "Переваги VIP статусу:\n"
            "• Значок преміум-акаунта у ваших оголошеннях\n"
            "• Пріоритетне розміщення товарів\n\n"
            "Вартість: <b>50 Telegram Stars</b> на 30 днів."
        ),
        "search_prompt": "🔍 <b>Пошук товару в базі оголошень:</b>\n\nНадішліть ключове слово або назву предмета для пошуку (наприклад: <code>аксесуар</code>, <code>німб</code>, <code>будинок</code>):",
        "sub_prompt": "✍️ Надішліть ключове слово або фразу для відстеження (наприклад: <code>скін</code> або <code>німб</code>):",
        "admin_app_prompt": (
            "📝 <b>Електронна заява на пост редактора ЗМІ (Arizona RP Style)</b>\n\n"
            "Будь ласка, заповніть заявку у вільній формі. Вкажіть:\n"
            "• Ваш ігровий нік і сервер\n"
            "• Ваш вік і часовий пояс\n"
            "• Досвід роботи в ЗМІ / чому хочете обійняти цей пост\n\n"
            "<i>Надішліть ваш текст відповідним повідомленням у чат:</i>"
        ),
    },
    "en": {
        "welcome": "🌟 <b>Hello! Please note: we are not an official bot</b>, but an independent assistant for Arizona RP players. We help players find accessories, transport, real estate, and other valuable items, as well as track economy and rates.\n\n🔒 <b>Security:</b> We <b>never</b> ask for account passwords or personal data!\n\n⏱ <b>Radio center working hours:</b> daily from <b>08:00:01 to 22:00:01 MSK</b>.\n\n👇 <b>To get started, select your game server below:</b>",
        "lang_changed": "✅ Language successfully changed to English.",
        "btn_change_server": "🌐 Change game server",
        "btn_change_lang": "🌐 Change language",
        "btn_accessories": "💍 Accessories & items",
        "btn_transport": "🚗 Transport & tuning",
        "btn_skins": "👕 Skins & guards",
        "btn_realestate": "🏠 Real estate & businesses",
        "btn_resources": "📦 Resources & materials",
        "btn_sell": "📤 Sell item",
        "btn_buy": "📥 Buy item",
        "btn_vc_calc": "💱 VC rate & calculator",
        "btn_find_ad": "🔍 Search item in database",
        "btn_favorites": "❤️ Favorites",
        "btn_notifications": "🔔 Search notifications",
        "btn_my_ads": "📋 My publications",
        "btn_avg_prices": "📊 Server price analysis",
        "btn_vip": "💎 VIP status",
        "btn_admin_panel": "👑 Admin panel",
        "btn_become_editor": "📝 Become editor / admin",
        "btn_cancel": "❌ Cancel action",
        "btn_help": "📖 Help & rules",
        "cat_accessories": "💍 Accessories & items",
        "cat_transport": "🚗 Transport & tuning",
        "cat_skins": "👕 Skins & guards",
        "cat_realestate": "🏠 Real estate & businesses",
        "cat_resources": "📦 Resources & materials",
        "help_text": "🛠 <b>Help, Rules & FAQ</b>\n\nUse the menu buttons to navigate the bot, submit ads, or check rates.",
        "how_it_works": "📖 <b>How the bot and radio center work</b>...",
        "vip_info": "💎 <b>VIP Status in bot</b>\n\n{status_text}",
        "search_prompt": "🔍 <b>Search item in database:</b>\n\nSend keyword or item name:",
        "sub_prompt": "✍️ Send keyword to track:",
        "admin_app_prompt": "📝 <b>Editor application form:</b>\n\nSend your details:",
    }
}

# (Для остальных языков белоруского, казахского и т.д. можно аналогично добавить ключи help_text, how_it_works, vip_info и т.д. Если их нет, get_text автоматически вернет русский вариант в качестве запасного).

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
# ФУНКЦИИ ЯЗЫКОВ И ПЕРЕВОДОВ
# ==========================================
def get_user_lang(user_id: int) -> str:
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT language FROM user_data WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row[0] if row and row[0] else "ru"

def set_user_lang(user_id: int, lang: str):
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE user_data SET language = ? WHERE user_id = ?", (lang, user_id))
        conn.commit()

def get_text(user_id: int, key: str) -> str:
    lang = get_user_lang(user_id)
    if lang not in TRANSLATIONS:
        lang = "ru"
    return TRANSLATIONS[lang].get(key, TRANSLATIONS["ru"].get(key, key))

def ikb_languages():
    markup = types.InlineKeyboardMarkup(row_width=3)
    langs = [
        ("🇷🇺 Русский", "lang_ru"),
        ("🇺🇦 Українська", "lang_uk"),
        ("🇧🇾 Беларуская", "lang_be"),
        ("🇰🇿 Қазақша", "lang_kk"),
        ("🇺🇿 O'zbekcha", "lang_uz"),
        ("🇦🇲 Հայերեն", "lang_hy"),
        ("🇦🇿 Azərbaycanca", "lang_az"),
        ("🇰🇬 Кыргызча", "lang_ky"),
        ("🇹🇯 Тоҷикӣ", "lang_tg"),
        ("🇹🇲 Türkmençe", "lang_tk"),
        ("🇲🇩 Română", "lang_ro"),
        ("🇬🇪 ქართული", "lang_ka"),
        ("🇬🇧 English", "lang_en"),
    ]
    for text, cdata in langs:
        markup.add(types.InlineKeyboardButton(text, callback_data=cdata))
    return markup

@bot.callback_query_handler(func=lambda c: c.data.startswith("lang_"))
def cb_set_language(call):
    lang = call.data.replace("lang_", "")
    uid = call.from_user.id
    set_user_lang(uid, lang)
    
    success_msg = TRANSLATIONS.get(lang, TRANSLATIONS["ru"]).get("lang_changed", "Language updated!")
    try:
        bot.answer_callback_query(call.id, success_msg)
    except Exception:
        pass
        
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"{success_msg}\n\n👇 Выберите игровой сервер ниже:",
            reply_markup=None
        )
    except Exception:
        pass

    welcome_text = get_text(uid, "welcome")
    safe_send_message(call.message.chat.id, welcome_text, reply_markup=kb_servers(uid))

# ==========================================
# БЕЗОПАСНАЯ ОТПРАВКА СООБЩЕНИЙ (HTML)
# ==========================================
def safe_send_message(chat_id, text, parse_mode="HTML", reply_markup=None):
    try:
        return bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)
    except ApiTelegramException as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        return bot.send_message(chat_id, text, parse_mode=None, reply_markup=reply_markup)

def safe_send_photo(chat_id, photo, caption, parse_mode="HTML", reply_markup=None):
    try:
        return bot.send_photo(chat_id, photo, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)
    except ApiTelegramException as e:
        logger.error(f"Ошибка отправки фото: {e}")
        return bot.send_photo(chat_id, photo, caption=caption, parse_mode=None, reply_markup=reply_markup)

# ==========================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
# ==========================================
def init_db():
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
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
        ''')
        
        cursor.execute('''
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
        ''')

        cursor.execute('''
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
        ''')
        
        cursor.execute('''
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
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_logs_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                receiver_id INTEGER,
                text TEXT,
                timestamp REAL
            )
        ''')

        for tbl in ["active_ads", "pending_posts", "active_buy_ads", "pending_buy_posts"]:
            try:
                cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN is_edited INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('vc_rate', '95000')")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bans (
                target TEXT PRIMARY KEY,
                is_id INTEGER
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS editor_stats (
                username TEXT PRIMARY KEY,
                count INTEGER
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_data (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                last_ad_time REAL,
                language TEXT DEFAULT 'ru'
            )
        ''')
        try:
            cursor.execute("ALTER TABLE user_data ADD COLUMN language TEXT DEFAULT 'ru'")
        except sqlite3.OperationalError:
            pass

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_dialogs (
                buyer_id INTEGER,
                seller_id INTEGER,
                ad_id INTEGER,
                is_active INTEGER,
                PRIMARY KEY (buyer_id, seller_id, ad_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER,
                ad_id INTEGER,
                PRIMARY KEY (user_id, ad_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keyword_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                server TEXT,
                keyword TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seller_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER,
                buyer_id INTEGER,
                rating INTEGER,
                comment TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS premium_users (
                user_id INTEGER PRIMARY KEY,
                expires_at REAL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_chats (
                chat_id INTEGER PRIMARY KEY
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_apps (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                application_text TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS approved_admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT
            )
        ''')

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
                    logger.info(f"Ночная очистка объявлений выполнена в {current_time} МСК.")
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
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(f"{YT_CHANNEL_URL}/live", headers=headers, allow_redirects=True, timeout=15)
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
                            logger.error(f"Не удалось отправить уведомление о стриме в чат {chat_id}: {e}")
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
        cur.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('vc_rate', ?)", (str(rate),))
        conn.commit()

def register_admin_chat(chat_id: int):
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO admin_chats (chat_id) VALUES (?)", (chat_id,))
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

def is_owner(user) -> bool:
    return bool(user and user.username and user.username.lower() == OWNER_USERNAME.lower())

def is_admin_or_owner(user) -> bool:
    if not user: 
        return False
    if is_owner(user): 
        return True
    uname = user.username.lower().lstrip('@') if user.username else ""
    if uname in ADMIN_USERNAMES:
        return True
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM approved_admins WHERE user_id = ? OR LOWER(username) = ?", (user.id, uname))
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
            uname = row[0].lower().lstrip('@')
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
        cur.execute("SELECT expires_at FROM premium_users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
    return bool(row and row[0] > time.time())

def get_user_last_ad_time(user_id):
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT last_ad_time FROM user_data WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else 0

def register_user(user_id, username=None):
    uname = username.lstrip('@').lower() if username else None
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO user_data (user_id, username, last_ad_time, language) VALUES (?, ?, 0, 'ru')", (user_id, uname))
        if uname:
            cur.execute("UPDATE user_data SET username = ? WHERE user_id = ?", (uname, user_id))
        conn.commit()

def is_banned(user) -> bool:
    if not user:
        return False
    uname = user.username.lower().lstrip('@') if user.username else ""
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM bans WHERE (is_id = 1 AND target = ?) OR (is_id = 0 AND target = ?)", 
                    (str(user.id), uname))
        res = cur.fetchone()
    return bool(res)

def verify_admin_callback(call) -> bool:
    if not is_admin_or_owner(call.from_user):
        try:
            bot.answer_callback_query(call.id, "⛔ Нет доступа к функциям СМИ!", show_alert=True)
        except Exception:
            pass
        return False
    return True

# ==========================================
# КЛАВИАТУРЫ
# ==========================================
def kb_servers(user_id: int):
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for i in range(0, len(SERVERS), 2): 
        m.add(*[types.KeyboardButton(s) for s in SERVERS[i:i+2]])
    m.add(types.KeyboardButton(get_text(user_id, "btn_help")))
    m.add(types.KeyboardButton(get_text(user_id, "btn_vip")), types.KeyboardButton(get_text(user_id, "btn_admin_panel")))
    m.add(
        types.KeyboardButton(get_text(user_id, "btn_become_editor")), 
        types.KeyboardButton(get_text(user_id, "btn_change_lang")),
        types.KeyboardButton(get_text(user_id, "btn_change_server"))
    )
    return m

def kb_main_menu(user_id: int):
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add(types.KeyboardButton(get_text(user_id, "btn_change_server")), types.KeyboardButton(get_text(user_id, "btn_change_lang")))
    m.add(types.KeyboardButton(get_text(user_id, "btn_accessories")), types.KeyboardButton(get_text(user_id, "btn_transport")))
    m.add(types.KeyboardButton(get_text(user_id, "btn_skins")), types.KeyboardButton(get_text(user_id, "btn_realestate")))
    m.add(types.KeyboardButton(get_text(user_id, "btn_resources")))
    m.add(types.KeyboardButton(get_text(user_id, "btn_sell")), types.KeyboardButton(get_text(user_id, "btn_buy")))
    m.add(types.KeyboardButton(get_text(user_id, "btn_vc_calc")))
    m.add(types.KeyboardButton(get_text(user_id, "btn_find_ad")), types.KeyboardButton(get_text(user_id, "btn_favorites")))
    m.add(types.KeyboardButton(get_text(user_id, "btn_notifications")), types.KeyboardButton(get_text(user_id, "btn_my_ads")))
    m.add(types.KeyboardButton(get_text(user_id, "btn_avg_prices")))
    m.add(types.KeyboardButton(get_text(user_id, "btn_vip")))
    m.add(types.KeyboardButton(get_text(user_id, "btn_admin_panel")), types.KeyboardButton(get_text(user_id, "btn_become_editor")))
    return m

def kb_cancel(user_id: int):
    return types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton(get_text(user_id, "btn_cancel")))

# ==========================================
# ПЕРЕХВАТЧИК ДЛЯ ЗАБЛОКИРОВАННЫХ ПОЛЬЗОВАТЕЛЕЙ
# ==========================================
@bot.message_handler(func=lambda m: is_banned(m.from_user))
def blocked_user_message(m):
    safe_send_message(
        m.chat.id, 
        "⛔ <b>Вы заблокированы в системе модерации.</b> Ваши кнопки отключены, и доступ к функциям бота ограничен.", 
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.callback_query_handler(func=lambda c: is_banned(c.from_user))
def blocked_user_callback(c):
    try:
        bot.answer_callback_query(c.id, "⛔ Вы заблокированы в системе и не можете использовать бота!", show_alert=True)
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

    if msg.text.startswith('/'):
        return True

    for t in TRANSLATIONS.values():
        if msg.text == t.get("btn_cancel"):
            return True

    if "admin_editing_pid" in st or "admin_editing_buy_pid" in st or "admin_editing_active_aid" in st or "applying_admin" in st or "vc_setting_rate" in st or "vc_calc_step" in st or "vc_conv_input" in st or "admin_action" in st or "editing_active_ad_id" in st or "searching_keyword" in st or "adding_subscription" in st:
        return False
        
    all_nav_texts = set(SERVERS)
    for t in TRANSLATIONS.values():
        for k, v in t.items():
            if k.startswith("btn_") or k.startswith("cat_"):
                all_nav_texts.add(v)

    return msg.text in all_nav_texts

@bot.message_handler(func=should_override_nav)
def handle_navigation_override(m):
    uid = m.from_user.id
    text = m.text
    clear_state(uid)
    
    if text == '/start':
        return cmd_start(m)
    elif text == '/help':
        return cmd_help(m)
        
    lang = get_user_lang(uid)
    tr = TRANSLATIONS.get(lang, TRANSLATIONS["ru"])
    
    all_cats_map = {
        tr.get("cat_accessories"): CATEGORIES[0],
        tr.get("cat_transport"): CATEGORIES[1],
        tr.get("cat_skins"): CATEGORIES[2],
        tr.get("cat_realestate"): CATEGORIES[3],
        tr.get("cat_resources"): CATEGORIES[4],
    }
    
    if text in all_cats_map or text in CATEGORIES:
        return
    elif text in SERVERS:
        return select_srv(m)

    if text in [tr.get("btn_change_server"), "🌐 Сменить игровой сервер"]:
        return change_server(m)
    elif text in [tr.get("btn_change_lang"), "🌐 Сменить язык"]:
        return select_language_command(m)
    elif text in [tr.get("btn_help"), "📖 Справка и правила"]:
        return cmd_help(m)
    elif text in [tr.get("btn_vip"), "💎 VIP-статус"]:
        return info_premium(m)
    elif text in [tr.get("btn_avg_prices"), "📊 Анализ цен на сервере"]:
        return show_average_prices(m)
    elif text in [tr.get("btn_sell"), "📤 Продать товар"]:
        return start_add_ad(m) if 'start_add_ad' in globals() else None
    elif text in [tr.get("btn_buy"), "📥 Скупить товар"]:
        return start_add_buy_ad(m) if 'start_add_buy_ad' in globals() else None
    elif text in [tr.get("btn_vc_calc"), "💱 Курс VC и калькулятор"]:
        return show_vc_menu(m) if 'show_vc_menu' in globals() else None
    elif text in [tr.get("btn_cancel"), "❌ Отменить действие"]:
        return
    elif text in [tr.get("btn_my_ads"), "📋 Мои публикации"]:
        return show_my_ads(m)
    elif text in [tr.get("btn_favorites"), "❤️ Сохраненные"]:
        return show_favorites(m)
    elif text in [tr.get("btn_find_ad"), "🔍 Найти товар в базе"]:
        return start_search(m)
    elif text in [tr.get("btn_notifications"), "🔔 Уведомления о поиске"]:
        return manage_subscriptions(m)
    elif text in [tr.get("btn_admin_panel"), "👑 Админ-панель"]:
        return admin_panel(m)
    elif text in [tr.get("btn_become_editor"), "📝 Стать редактором / админом"]:
        return start_admin_application(m)

# ==========================================
# ОСНОВНЫЕ КОМАНДЫ (С МУЛЬТИЯЗЫЧНОСТЬЮ)
# ==========================================
@bot.message_handler(commands=['start'])
def cmd_start(m):
    register_user(m.from_user.id, m.from_user.username)
    
    if is_banned(m.from_user):
        return safe_send_message(m.chat.id, "⛔ Вы заблокированы в системе модерации.", reply_markup=types.ReplyKeyboardRemove())
        
    if is_admin_or_owner(m.from_user):
        register_admin_chat(m.chat.id)
    
    uid = m.from_user.id
    welcome_text = get_text(uid, "welcome")
    
    safe_send_message(m.chat.id, "🌐 <b>Вы можете сменить язык в любой момент:</b> / You can change language at any time:", reply_markup=ikb_languages())
    safe_send_message(m.chat.id, welcome_text, reply_markup=kb_servers(uid))

def select_language_command(m):
    safe_send_message(
        m.chat.id,
        "🌐 Пожалуйста, выберите язык / Please select your language / Тілді таңдаңыз:",
        reply_markup=ikb_languages()
    )

@bot.message_handler(commands=['help'])
def cmd_help(m):
    uid = m.from_user.id
    help_text = get_text(uid, "help_text")
    safe_send_message(m.chat.id, help_text, reply_markup=kb_main_menu(uid))

def change_server(m):
    uid = m.from_user.id
    safe_send_message(m.chat.id, "👇 Выберите новый игровой сервер:", reply_markup=kb_servers(uid))

def select_srv(m):
    srv = m.text
    uid = m.from_user.id
    update_state(uid, server=srv)
    safe_send_message(m.chat.id, f"✅ Игровой сервер установлен: <b>{html.escape(srv)}</b>", reply_markup=kb_main_menu(uid))

def how_bot_works(m):
    uid = m.from_user.id
    text = get_text(uid, "how_it_works")
    safe_send_message(m.chat.id, text, reply_markup=kb_main_menu(uid))

# ==========================================
# ИЗБРАННОЕ И МОИ ПУБЛИКАЦИИ
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("fav_toggle_"))
def cb_fav_toggle(call):
    aid = int(call.data.split("_")[2])
    uid = call.from_user.id

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM favorites WHERE user_id = ? AND ad_id = ?", (uid, aid))
        exists = cur.fetchone()
        if exists:
            cur.execute("DELETE FROM favorites WHERE user_id = ? AND ad_id = ?", (uid, aid))
            is_fav = False
            try:
                bot.answer_callback_query(call.id, "❌ Удалено из избранного")
            except Exception:
                pass
        else:
            cur.execute("INSERT INTO favorites (user_id, ad_id) VALUES (?, ?)", (uid, aid))
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

    # ikb_ad_actions вызывается если определена в проекте
    markup = ikb_ad_actions(aid, is_fav=is_fav, user_id=uid, is_buy=is_buy) if 'ikb_ad_actions' in globals() else None
    try:
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)
    except Exception:
        pass

def show_favorites(m):
    uid = m.from_user.id
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT ad_id FROM favorites WHERE user_id = ?", (uid,))
        favs = cur.fetchall()

    if not favs:
        return safe_send_message(m.chat.id, "❤️ У вас пока нет сохраненных (избранных) объявлений.", reply_markup=kb_main_menu(uid))

    safe_send_message(m.chat.id, "❤️ <b>Ваши сохраненные объявления:</b>")
    for (aid,) in favs:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, user_id, server, category, text, photo, is_vip FROM active_ads WHERE id = ?", (aid,))
            row = cur.fetchone()
            is_buy = False
            if not row:
                cur.execute("SELECT id, user_id, server, category, text, photo, is_vip FROM active_buy_ads WHERE id = ?", (aid,))
                row = cur.fetchone()
                is_buy = True

        if row:
            _, _, _, _, text, photo, _ = row
            markup = ikb_ad_actions(aid, is_fav=True, user_id=uid, is_buy=is_buy) if 'ikb_ad_actions' in globals() else None
            fmt_text = html.escape(text)
            if photo:
                safe_send_photo(m.chat.id, photo, caption=fmt_text, reply_markup=markup)
            else:
                safe_send_message(m.chat.id, fmt_text, reply_markup=markup)

def show_my_ads(m):
    uid = m.from_user.id
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, server, category, text FROM active_ads WHERE user_id = ?", (uid,))
        sales = cur.fetchall()
        cur.execute("SELECT id, server, category, text FROM active_buy_ads WHERE user_id = ?", (uid,))
        buys = cur.fetchall()

    if not sales and not buys:
        return safe_send_message(m.chat.id, "📋 У вас нет активных опубликованных объявлений.", reply_markup=kb_main_menu(uid))

    markup = types.InlineKeyboardMarkup(row_width=1)
    for aid, srv, cat, text in sales:
        markup.add(types.InlineKeyboardButton(f"🗑 [Продажа | {srv}] ID {aid}: {text[:25]}...", callback_data=f"my_del_sale_{aid}"))
    for aid, srv, cat, text in buys:
        markup.add(types.InlineKeyboardButton(f"🗑 [Скупка | {srv}] ID {aid}: {text[:25]}...", callback_data=f"my_del_buy_{aid}"))

    safe_send_message(m.chat.id, "📋 <b>Ваши активные публикации:</b>\nНажмите на объявление, чтобы удалить его:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("my_del_sale_") or c.data.startswith("my_del_buy_"))
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
                bot.answer_callback_query(call.id, "⚠️ Ошибка или объявление не принадлежит вам!", show_alert=True)
            except Exception:
                pass

# ==========================================
# ПОИСК ТОВАРОВ И ПОДПИСКИ
# ==========================================
def start_search(m):
    uid = m.from_user.id
    update_state(uid, searching_keyword=True)
    safe_send_message(m.chat.id, get_text(uid, "search_prompt"), reply_markup=kb_cancel(uid))

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("searching_keyword"))
def process_search_keyword(m):
    uid = m.from_user.id
    clear_state(uid)
    query = m.text.strip().lower()

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, server, category, text, photo, is_vip FROM active_ads WHERE LOWER(text) LIKE ? OR LOWER(category) LIKE ? ORDER BY id DESC LIMIT 10", (f"%{query}%", f"%{query}%"))
        sales = cur.fetchall()
        cur.execute("SELECT id, server, category, text, photo, is_vip FROM active_buy_ads WHERE LOWER(text) LIKE ? OR LOWER(category) LIKE ? ORDER BY id DESC LIMIT 10", (f"%{query}%", f"%{query}%"))
        buys = cur.fetchall()

    if not sales and not buys:
        return safe_send_message(m.chat.id, f"🔍 По запросу «<b>{html.escape(query)}</b>» ничего не найдено.", reply_markup=kb_main_menu(uid))

    safe_send_message(m.chat.id, f"🔍 <b>Результаты поиска по запросу:</b> «{html.escape(query)}»")

    for aid, srv, cat, text, photo, is_vip in sales:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM favorites WHERE user_id = ? AND ad_id = ?", (uid, aid))
            is_fav = bool(cur.fetchone())
        markup = ikb_ad_actions(aid, is_fav=is_fav, user_id=uid, is_buy=False) if 'ikb_ad_actions' in globals() else None
        fmt_text = f"📤 <b>[Продажа | {srv}]</b>\n{html.escape(text)}"
        if photo:
            safe_send_photo(m.chat.id, photo, caption=fmt_text, reply_markup=markup)
        else:
            safe_send_message(m.chat.id, fmt_text, reply_markup=markup)

    for aid, srv, cat, text, photo, is_vip in buys:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM favorites WHERE user_id = ? AND ad_id = ?", (uid, aid))
            is_fav = bool(cur.fetchone())
        markup = ikb_ad_actions(aid, is_fav=is_fav, user_id=uid, is_buy=True) if 'ikb_ad_actions' in globals() else None
        fmt_text = f"📥 <b>[Скупка | {srv}]</b>\n{html.escape(text)}"
        if photo:
            safe_send_photo(m.chat.id, photo, caption=fmt_text, reply_markup=markup)
        else:
            safe_send_message(m.chat.id, fmt_text, reply_markup=markup)

def manage_subscriptions(m):
    uid = m.from_user.id
    srv = get_state(uid).get("server", "Phoenix")

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, keyword, server FROM keyword_subscriptions WHERE user_id = ?", (uid,))
        subs = cur.fetchall()

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("➕ Добавить ключевое слово", callback_data="sub_add_prompt"))
    for sub_id, kw, sub_srv in subs:
        markup.add(types.InlineKeyboardButton(f"❌ Удалить: {kw} [{sub_srv}]", callback_data=f"sub_del_{sub_id}"))

    text = (
        f"🔔 <b>Уведомления о поиске (Подписки на ключевые слова)</b>\n\n"
        f"Когда кто-то опубликует объявление, содержащее ваше ключевое слово, вы получите уведомление в боте.\n"
        f"Текущие подписки:"
    )
    safe_send_message(m.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "sub_add_prompt")
def cb_sub_add_prompt(call):
    uid = call.from_user.id
    update_state(uid, adding_subscription=True)
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    safe_send_message(call.message.chat.id, get_text(uid, "sub_prompt"), reply_markup=kb_cancel(uid))

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("adding_subscription"))
def process_add_subscription(m):
    uid = m.from_user.id
    srv = get_state(uid).get("server", "Phoenix")
    kw = m.text.strip().lower()
    clear_state(uid)

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO keyword_subscriptions (user_id, server, keyword) VALUES (?, ?, ?)", (uid, srv, kw))
        conn.commit()

    safe_send_message(m.chat.id, f"✅ Подписка на ключевое слово «<b>{html.escape(kw)}</b>» для сервера <b>{html.escape(srv)}</b> успешно добавлена!", reply_markup=kb_main_menu(uid))

# ==========================================
# ИНФО О ВИП И ЗАЯВКИ НА РЕДАКТОРА
# ==========================================
def info_premium(m):
    uid = m.from_user.id
    is_prem = is_user_premium(uid)
    status_text = "✅ <b>Ваш VIP-статус активен!</b>" if is_prem else "❌ <b>У вас нет активного VIP-статуса.</b>"
    text = get_text(uid, "vip_info").format(status_text=status_text)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Купить VIP (50 Звезд / 30 дней)", pay=True, callback_data="buy_vip_stars"))
    safe_send_message(m.chat.id, text, reply_markup=markup)

def start_admin_application(m):
    uid = m.from_user.id
    if is_admin_or_owner(m.from_user):
        return safe_send_message(m.chat.id, "👑 Вы уже являетесь администратором / владельцем бота!", reply_markup=kb_main_menu(uid))
    
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM admin_apps WHERE user_id = ?", (uid,))
        if cur.fetchone():
            return safe_send_message(m.chat.id, "⏳ Ваша заявка на пост редактора уже находится на рассмотрении руководства.", reply_markup=kb_main_menu(uid))

    update_state(uid, applying_admin="waiting_text")
    safe_send_message(m.chat.id, get_text(uid, "admin_app_prompt"), reply_markup=kb_cancel(uid))

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("applying_admin") == "waiting_text")
def process_admin_application(m):
    uid = m.from_user.id
    uname = m.from_user.username or "Без юзернейма"
    app_text = m.text.strip()
    clear_state(uid)

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO admin_apps (user_id, username, application_text) VALUES (?, ?, ?)", (uid, uname, app_text))
        conn.commit()

    safe_send_message(m.chat.id, "✅ Ваша заявка на пост редактора успешно отправлена владельцу и редакции! Ожидайте рассмотрения.", reply_markup=kb_main_menu(uid))

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Принять (Назначить админом)", callback_data=f"accept_admin_app_{uid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_admin_app_{uid}")
    )

    notif_text = (
        "📝 <b>Новая заявка на пост редактора / администратора!</b>\n\n"
        f"👤 Кандидат: @{html.escape(uname)} (ID: <code>{uid}</code>)\n\n"
        f"📄 <b>Текст заявки:</b>\n{html.escape(app_text)}"
    )

    admin_recipients = get_all_admin_ids()
    for chat_id in admin_recipients:
        try:
            safe_send_message(chat_id, notif_text, reply_markup=markup)
        except Exception as e:
            logger.error(f"Не удалось отправить заявку админу {chat_id}: {e}")

def show_average_prices(m):
    uid = m.from_user.id
    srv = get_state(uid).get("server", "Phoenix")

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT category, text FROM active_ads WHERE server = ?", (srv,))
        ads = cur.fetchall()

    if not ads:
        return safe_send_message(
            m.chat.id, 
            f"📊 На сервере <b>{html.escape(srv)}</b> пока недостаточно данных для расчета средних цен.", 
            reply_markup=kb_main_menu(uid)
        )

    category_prices = {cat: [] for cat in CATEGORIES}

    for cat, text in ads:
        if cat in category_prices:
            numbers = re.findall(r'\d+', text.replace(',', '').replace('.', ''))
            for num_str in numbers:
                val = int(num_str)
                if 100 <= val <= 1000000000:
                    category_prices[cat].append(val)

    report = f"📊 <b>Динамические средние цены на сервере {html.escape(srv)}:</b>\n\n"
    
    for cat in CATEGORIES:
        prices = category_prices[cat]
        if prices:
            avg_val = sum(prices) / len(prices)
            min_val = min(prices)
            max_val = max(prices)
            
            report += f"📂 <b>{cat}</b>:\n"
            report += f"• Средняя цена: <b>{format_price(avg_val)}</b>\n"
            report += f"• Диапазон: от {format_price(min_val)} до {format_price(max_val)}\n"
            report += f"• Учтено объявлений: {len(prices)}\n\n"
        else:
            report += f"📂 <b>{cat}</b>:\n• <i>Нет данных о ценах</i>\n\n"

    safe_send_message(m.chat.id, report, reply_markup=kb_main_menu(uid))

def format_price(val: float) -> str:
    if val >= 1_000_000_000:
        return f"{val / 1_000_000_000:.1f}ккк (млрд)"
    elif val >= 1_000_000:
        return f"{val / 1_000_000:.1f}кк (млн)"
    elif val >= 1_000:
        return f"{val / 1_000:.1f}к (тыс)"
    return f"{int(val)}"

def admin_panel(m):
    if not is_admin_or_owner(m.from_user):
        return safe_send_message(m.chat.id, "⛔ Нет доступа к панели администратора.", reply_markup=kb_main_menu(m.from_user.id))
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📋 Управление активными объявлениями", callback_data="admin_manage_active_ads"),
        types.InlineKeyboardButton("✏️ Модерация объявлений", callback_data="admin_edit_ads_menu"),
        types.InlineKeyboardButton("⚙️ Изменить курс VC", callback_data="vc_set_rate_start")
    )

    if is_owner(m.from_user):
        markup.add(
            types.InlineKeyboardButton("📂 Выгрузить логи чатов (.txt)", callback_data="owner_export_logs"),
            types.InlineKeyboardButton("👑 Управление администраторами", callback_data="owner_manage_admins"),
            types.InlineKeyboardButton("⛔ Бан / Разбан пользователя", callback_data="owner_manage_bans")
        )

    safe_send_message(m.chat.id, "👑 <b>Панель администратора / редактора:</b>", reply_markup=markup)

if __name__ == '__main__':
    logger.info("Бот запущен с поддержкой мультиязычности!")
    bot.infinity_polling(skip_pending=True)

