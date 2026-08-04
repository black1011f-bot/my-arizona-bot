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
        "help_text": "🛠 <b>Допомога, правила та розширений FAQ</b>",
        "how_it_works": "📖 <b>Довідник: Як працює бот і радіоцентр</b>",
        "vip_info": "💎 <b>Преміум-статус (VIP) у боті</b>\n\n{status_text}",
        "search_prompt": "🔍 <b>Пошук товару в базі оголошень:</b>\n\nНадішліть ключове слово:",
        "sub_prompt": "✍️ Надішліть ключове слово для відстеження:",
        "admin_app_prompt": "📝 <b>Електронна заява на пост редактора ЗМІ:</b>\n\nНадішліть ваш текст:",
    },
    "be": {
        "welcome": "🌟 <b>Вірыем! Звярніце ўвагу: мы не афіцыйны бот</b>, а незалежны памочнік для гульцоў Arizona RP...",
        "lang_changed": "✅ Мова паспяхова зменена на беларускую.",
        "btn_change_server": "🌐 Змяніць гульнявы сервер", "btn_change_lang": "🌐 Змяніць мову",
        "btn_accessories": "💍 Аксэсуары і рэчы", "btn_transport": "🚗 Транспарт і цюнінг", "btn_skins": "👕 Скіны і ахоўнікі", "btn_realestate": "🏠 Нерухомасць і бізнесы", "btn_resources": "📦 Рэсурсы і матэрыялы",
        "btn_sell": "📤 Прадаць тавар", "btn_buy": "📥 Скупіць тавар", "btn_vc_calc": "💱 Курс VC і калькулятар", "btn_find_ad": "🔍 Знайсці тавар у базе", "btn_favorites": "❤️ Захаваныя", "btn_notifications": "🔔 Паведамленні аб пошуку", "btn_my_ads": "📋 Мае публікацыі", "btn_avg_prices": "📊 Аналіз цэн на серверы", "btn_vip": "💎 VIP-статус", "btn_admin_panel": "👑 Адмін-панэль", "btn_become_editor": "📝 Стаць рэдактарам / адмінам", "btn_cancel": "❌ Скасаваць дзеянне", "btn_help": "📖 Даведка і правілы",
        "cat_accessories": "💍 Аксэсуары і рэчы", "cat_transport": "🚗 Транспарт і цюнінг", "cat_skins": "👕 Скіны і ахоўнікі", "cat_realestate": "🏠 Нерухомасць і бізнесы", "cat_resources": "📦 Рэсурсы і матэрыялы",
        "help_text": "🛠 Дапамога", "how_it_works": "📖 Даведнік", "vip_info": "💎 VIP\n\n{status_text}", "search_prompt": "🔍 Пошук:", "sub_prompt": "✍️ Падпіска:", "admin_app_prompt": "📝 Заява:"
    },
    "kk": {
        "welcome": "🌟 <b>Сәлем! Назар аударыңыз: біз ресми бот емеспіз</b>, Arizona RP ойыншыларына көмекшіміз...",
        "lang_changed": "✅ Тіл қазақ тіліне өзгертілді.",
        "btn_change_server": "🌐 Серверді өзгерту", "btn_change_lang": "🌐 Тілді өзгерту",
        "btn_accessories": "💍 Аксессуарлар", "btn_transport": "🚗 Көлік", "btn_skins": "👕 Скиндер", "btn_realestate": "🏠 Жылжымайтын мүлік", "btn_resources": "📦 Ресурстар",
        "btn_sell": "📤 Сату", "btn_buy": "📥 Сатып алу", "btn_vc_calc": "💱 VC курсы", "btn_find_ad": "🔍 Іздеу", "btn_favorites": "❤️ Сақталғандар", "btn_notifications": "🔔 Хабарламалар", "btn_my_ads": "📋 Менің жарияланымдарым", "btn_avg_prices": "📊 Бағаларды талдау", "btn_vip": "💎 VIP", "btn_admin_panel": "👑 Админ панелі", "btn_become_editor": "📝 Редактор болу", "btn_cancel": "❌ Болдырмау", "btn_help": "📖 Анықтама",
        "cat_accessories": "💍 Аксессуарлар", "cat_transport": "🚗 Көлік", "cat_skins": "👕 Скиндер", "cat_realestate": "🏠 Жылжымайтын мүлік", "cat_resources": "📦 Ресурстар",
        "help_text": "🛠 Көмек", "how_it_works": "📖 Анықтама", "vip_info": "💎 VIP\n\n{status_text}", "search_prompt": "🔍 Іздеу:", "sub_prompt": "✍️ Бақылау:", "admin_app_prompt": "📝 Өтініш:"
    },
    "uz": {
        "welcome": "🌟 <b>Salom! Biz rasmiy bot emasmiz</b>...", "lang_changed": "✅ Til o'zbek tiliga o'zgartirildi.",
        "btn_change_server": "🌐 Serverni o'zgartirish", "btn_change_lang": "🌐 Tilni o'zgartirish",
        "btn_accessories": "💍 Aksessuarlar", "btn_transport": "🚗 Transport", "btn_skins": "👕 Skinlar", "btn_realestate": "🏠 Ko'chmas mulk", "btn_resources": "📦 Resurslar",
        "btn_sell": "📤 Sotish", "btn_buy": "📥 Sotib olish", "btn_vc_calc": "💱 VC kursi", "btn_find_ad": "🔍 Topish", "btn_favorites": "❤️ Saqlanganlar", "btn_notifications": "🔔 Bildirishnomalar", "btn_my_ads": "📋 Mening nashrlarim", "btn_avg_prices": "📊 Narxlar tahlili", "btn_vip": "💎 VIP", "btn_admin_panel": "👑 Admin paneli", "btn_become_editor": "📝 Muharrir bo'lish", "btn_cancel": "❌ Bekor qilish", "btn_help": "📖 Yordam",
        "cat_accessories": "💍 Aksessuarlar", "cat_transport": "🚗 Transport", "cat_skins": "👕 Skinlar", "cat_realestate": "🏠 Ko'chmas mulk", "cat_resources": "📦 Resurslar",
        "help_text": "🛠 Yordam", "how_it_works": "📖 Qo'llanma", "vip_info": "💎 VIP\n\n{status_text}", "search_prompt": "🔍 Izlash:", "sub_prompt": "✍️ Kuzatish:", "admin_app_prompt": "📝 Ariza:"
    },
    "hy": {
        "welcome": "🌟 <b>Բարև ձեզ: Մենք պաշտոնական բոտ չենք</b>...", "lang_changed": "✅ Լեզուն փոխվեց հայերենի:",
        "btn_change_server": "🌐 Փոխել սերվերը", "btn_change_lang": "🌐 Փոխել լեզուն",
        "btn_accessories": "💍 Աքսեսուարներ", "btn_transport": "🚗 Տրանսպորտ", "btn_skins": "👕 Սկիններ", "btn_realestate": "🏠 Անշարժ գույք", "btn_resources": "📦 Ռեսուրսներ",
        "btn_sell": "📤 Վաճառել", "btn_buy": "📥 Գնել", "btn_vc_calc": "💱 VC հաշվիչ", "btn_find_ad": "🔍 Գտնել", "btn_favorites": "❤️ Պահպանվածներ", "btn_notifications": "🔔 Ծանուցումներ", "btn_my_ads": "📋 Իմ հրապարակումները", "btn_avg_prices": "📊 Գների վերլուծություն", "btn_vip": "💎 VIP", "btn_admin_panel": "👑 Ադմին վահանակ", "btn_become_editor": "📝 Դառնալ խմբագիր", "btn_cancel": "❌ Չեղարկել", "btn_help": "📖 Օգնություն",
        "cat_accessories": "💍 Աքսեսուարներ", "cat_transport": "🚗 Տրանսպորտ", "cat_skins": "👕 Սկիններ", "cat_realestate": "🏠 Անշարժ գույք", "cat_resources": "📦 Ռեսուրսներ",
        "help_text": "🛠 Օգնություն", "how_it_works": "📖 Ինչպես է աշխատում", "vip_info": "💎 VIP\n\n{status_text}", "search_prompt": "🔍 Որոնել:", "sub_prompt": "✍️ Հետևել:", "admin_app_prompt": "📝 Դիմում:"
    },
    "az": {
        "welcome": "🌟 <b>Salam! Biz rəsmi bot deyilik</b>...", "lang_changed": "✅ Dil dəyişdirildi.",
        "btn_change_server": "🌐 Serveri dəyişmək", "btn_change_lang": "🌐 Dili dəyişmək",
        "btn_accessories": "💍 Aksesuarlar", "btn_transport": "🚗 Nəqliyyat", "btn_skins": "👕 Skinlər", "btn_realestate": "🏠 Daşınmaz əmlak", "btn_resources": "📦 Resurslar",
        "btn_sell": "📤 Satmaq", "btn_buy": "📥 Almaq", "btn_vc_calc": "💱 VC kalkulyator", "btn_find_ad": "🔍 Axtarış", "btn_favorites": "❤️ Seçilmişlər", "btn_notifications": "🔔 Bildirişlər", "btn_my_ads": "📋 Mənim elanlarım", "btn_avg_prices": "📊 Qiymət təhlili", "btn_vip": "💎 VIP", "btn_admin_panel": "👑 Admin paneli", "btn_become_editor": "📝 Redaktor olmaq", "btn_cancel": "❌ Ləğv etmək", "btn_help": "📖 Kömək",
        "cat_accessories": "💍 Aksesuarlar", "cat_transport": "🚗 Nəqliyyat", "cat_skins": "👕 Skinlər", "cat_realestate": "🏠 Daşınmaz əmlak", "cat_resources": "📦 Resurslar",
        "help_text": "🛠 Kömək", "how_it_works": "📖 Bot necə işləyir", "vip_info": "💎 VIP\n\n{status_text}", "search_prompt": "🔍 Axtar:", "sub_prompt": "✍️ İzlə:", "admin_app_prompt": "📝 Ərizə:"
    },
    "ky": {
        "welcome": "🌟 <b>Салам! Биз расмий бот эмеспиз</b>...", "lang_changed": "✅ Тил өзгөртүлдү.",
        "btn_change_server": "🌐 Серверди өзгөртүү", "btn_change_lang": "🌐 Тилди өзгөртүү",
        "btn_accessories": "💍 Аксессуарлар", "btn_transport": "🚗 Унаа", "btn_skins": "👕 Скиндер", "btn_realestate": "🏠 Кыймылсыз мүлк", "btn_resources": "📦 Ресурстар",
        "btn_sell": "📤 Сатуу", "btn_buy": "📥 Сатып алуу", "btn_vc_calc": "💱 VC курсу", "btn_find_ad": "🔍 Издөө", "btn_favorites": "❤️ Сакталгандар", "btn_notifications": "🔔 Эскертмелер", "btn_my_ads": "📋 Менин жарыяларым", "btn_avg_prices": "📊 Бааларды талдоо", "btn_vip": "💎 VIP", "btn_admin_panel": "👑 Админ панели", "btn_become_editor": "📝 Редактор болуу", "btn_cancel": "❌ Жокко чыгаруу", "btn_help": "📖 Жардам",
        "cat_accessories": "💍 Аксессуарлар", "cat_transport": "🚗 Унаа", "cat_skins": "👕 Скиндер", "cat_realestate": "🏠 Кыймылсыз мүлк", "cat_resources": "📦 Ресурстар",
        "help_text": "🛠 Жардам", "how_it_works": "📖 Бот кандай иштейт", "vip_info": "💎 VIP\n\n{status_text}", "search_prompt": "🔍 Издөө:", "sub_prompt": "✍️ Көзөмөл:", "admin_app_prompt": "📝 Арыз:"
    },
    "tg": {
        "welcome": "🌟 <b>Салом! Мо боти расмӣ нестем</b>...", "lang_changed": "✅ Забон иваз шуд.",
        "btn_change_server": "🌐 Иваз кардани сервер", "btn_change_lang": "🌐 Иваз кардани забон",
        "btn_accessories": "💍 Лавозимот", "btn_transport": "🚗 Нақлиёт", "btn_skins": "👕 Пӯстҳо", "btn_realestate": "🏠 Амвол", "btn_resources": "📦 Захираҳо",
        "btn_sell": "📤 Фурӯш", "btn_buy": "📥 Харид", "btn_vc_calc": "💱 Қурби VC", "btn_find_ad": "🔍 Ёфтани мол", "btn_favorites": "❤️ Захирашудаҳо", "btn_notifications": "🔔 Огоҳиномаҳо", "btn_my_ads": "📋 Нашрияҳо", "btn_avg_prices": "📊 Таҳлили нархҳо", "btn_vip": "💎 VIP", "btn_admin_panel": "👑 Админ", "btn_become_editor": "📝 Муҳаррир шудан", "btn_cancel": "❌ Бекор кардан", "btn_help": "📖 Кӯмак",
        "cat_accessories": "💍 Лавозимот", "cat_transport": "🚗 Нақлиёт", "cat_skins": "👕 Пӯстҳо", "cat_realestate": "🏠 Амвол", "cat_resources": "📦 Захираҳо",
        "help_text": "🛠 Кӯмак", "how_it_works": "📖 Тарзи кор", "vip_info": "💎 VIP\n\n{status_text}", "search_prompt": "🔍 Ҷустуҷӯ:", "sub_prompt": "✍️ Пайгирӣ:", "admin_app_prompt": "📝 Ариза:"
    },
    "tk": {
        "welcome": "🌟 <b>Salam! Biz resmi bot däl</b>...", "lang_changed": "✅ Dil üýtgedildi.",
        "btn_change_server": "🌐 Serweri üýtgetmek", "btn_change_lang": "🌐 Dili üýtgetmek",
        "btn_accessories": "💍 Aksesuarlar", "btn_transport": "🚗 Ulag", "btn_skins": "👕 Skinler", "btn_realestate": "🏠 Emläk", "btn_resources": "📦 Serişdeler",
        "btn_sell": "📤 Satmak", "btn_buy": "📥 Satyn almak", "btn_vc_calc": "💱 VC bahasy", "btn_find_ad": "🔍 Gözlemek", "btn_favorites": "❤️ Ýazgydakylar", "btn_notifications": "🔔 Duýduryşlar", "btn_my_ads": "📋 Neşirlerim", "btn_avg_prices": "📊 Bahalar", "btn_vip": "💎 VIP", "btn_admin_panel": "👑 Admin", "btn_become_editor": "📝 Redaktor", "btn_cancel": "❌ Ýatyrmak", "btn_help": "📖 Ýardam",
        "cat_accessories": "💍 Aksesuarlar", "cat_transport": "🚗 Ulag", "cat_skins": "👕 Skinler", "cat_realestate": "🏠 Emläk", "cat_resources": "📦 Serişdeler",
        "help_text": "🛠 Ýardam", "how_it_works": "📖 Bot neneji işleýär", "vip_info": "💎 VIP\n\n{status_text}", "search_prompt": "🔍 Gözleg:", "sub_prompt": "✍️ İzlemek:", "admin_app_prompt": "📝 Ýüz tutma:"
    },
    "ro": {
        "welcome": "🌟 <b>Salut! Nu suntem un bot oficial</b>...", "lang_changed": "✅ Limba a fost schimbată.",
        "btn_change_server": "🌐 Schimbă serverul", "btn_change_lang": "🌐 Schimbă limba",
        "btn_accessories": "💍 Accesorii", "btn_transport": "🚗 Transport", "btn_skins": "👕 Skin-uri", "btn_realestate": "🏠 Imobiliare", "btn_resources": "📦 Resurse",
        "btn_sell": "📤 Vinde", "btn_buy": "📥 Cumpără", "btn_vc_calc": "💱 Calculator VC", "btn_find_ad": "🔍 Caută", "btn_favorites": "❤️ Favorite", "btn_notifications": "🔔 Notificări", "btn_my_ads": "📋 Publicațiile mele", "btn_avg_prices": "📊 Prețuri", "btn_vip": "💎 VIP", "btn_admin_panel": "👑 Admin", "btn_become_editor": "📝 Devino editor", "btn_cancel": "❌ Anulează", "btn_help": "📖 Ajutor",
        "cat_accessories": "💍 Accesorii", "cat_transport": "🚗 Transport", "cat_skins": "👕 Skin-uri", "cat_realestate": "🏠 Imobiliare", "cat_resources": "📦 Resurse",
        "help_text": "🛠 Ajutor", "how_it_works": "📖 Cum funcționează", "vip_info": "💎 VIP\n\n{status_text}", "search_prompt": "🔍 Caută:", "sub_prompt": "✍️ Urmărește:", "admin_app_prompt": "📝 Cerere:"
    },
    "ka": {
        "welcome": "🌟 <b>გამარჯობა! ჩვენ არ ვართ ოფიციალური ბოტი</b>...", "lang_changed": "✅ ენა შეიცვალა.",
        "btn_change_server": "🌐 სერვერის შეცვლა", "btn_change_lang": "🌐 ენის შეცვლა",
        "btn_accessories": "💍 აქსესუარები", "btn_transport": "🚗 ტრანსპორტი", "btn_skins": "👕 სკინები", "btn_realestate": "🏠 უძრავი ქონება", "btn_resources": "📦 რესურსები",
        "btn_sell": "📤 გაყიდვა", "btn_buy": "📥 ყიდვა", "btn_vc_calc": "💱 VC კალკულატორი", "btn_find_ad": "🔍 ძებნა", "btn_favorites": "❤️ შენახული", "btn_notifications": "🔔 შეტყობინებები", "btn_my_ads": "📋 ჩემი პუბლიკაციები", "btn_avg_prices": "📊 ფასების ანალიზი", "btn_vip": "💎 VIP", "btn_admin_panel": "👑 ადმინ პანელი", "btn_become_editor": "📝 რედაქტორი", "btn_cancel": "❌ გაუქმება", "btn_help": "📖 დახმარება",
        "cat_accessories": "💍 აქსესუარები", "cat_transport": "🚗 ტრანსპორტი", "cat_skins": "👕 სკინები", "cat_realestate": "🏠 უძრავი ქონება", "cat_resources": "📦 რესურსები",
        "help_text": "🛠 დახმარება", "how_it_works": "📖 როგორ მუშაობს", "vip_info": "💎 VIP\n\n{status_text}", "search_prompt": "🔍 ძებნა:", "sub_prompt": "✍️ თვალთვალი:", "admin_app_prompt": "📝 განაცხადი:"
    },
    "en": {
        "welcome": "🌟 <b>Hello! Please note: we are not an official bot</b>, but an independent assistant for Arizona RP players...",
        "lang_changed": "✅ Language successfully changed to English.",
        "btn_change_server": "🌐 Change game server", "btn_change_lang": "🌐 Change language",
        "btn_accessories": "💍 Accessories & items", "btn_transport": "🚗 Transport & tuning", "btn_skins": "👕 Skins & guards", "btn_realestate": "🏠 Real estate & businesses", "btn_resources": "📦 Resources & materials",
        "btn_sell": "📤 Sell item", "btn_buy": "📥 Buy item", "btn_vc_calc": "💱 VC rate & calculator", "btn_find_ad": "🔍 Search item in database", "btn_favorites": "❤️ Favorites", "btn_notifications": "🔔 Search notifications", "btn_my_ads": "📋 My publications", "btn_avg_prices": "📊 Server price analysis", "btn_vip": "💎 VIP status", "btn_admin_panel": "👑 Admin panel", "btn_become_editor": "📝 Become editor / admin", "btn_cancel": "❌ Cancel action", "btn_help": "📖 Help & rules",
        "cat_accessories": "💍 Accessories & items", "cat_transport": "🚗 Transport & tuning", "cat_skins": "👕 Skins & guards", "cat_realestate": "🏠 Real estate & businesses", "cat_resources": "📦 Resources & materials",
        "help_text": "🛠 Help & Rules", "how_it_works": "📖 How it works", "vip_info": "💎 VIP Status\n\n{status_text}", "search_prompt": "🔍 Search query:", "sub_prompt": "✍️ Keyword to track:", "admin_app_prompt": "📝 Application:"
    }
}

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
        ("🇷🇺 Русский", "lang_ru"), ("🇺🇦 Українська", "lang_uk"), ("🇧🇾 Беларуская", "lang_be"),
        ("🇰🇿 Қазақша", "lang_kk"), ("🇺🇿 O'zbekcha", "lang_uz"), ("🇦🇲 Հայերեն", "lang_hy"),
        ("🇦🇿 Azərbaycanca", "lang_az"), ("🇰🇬 Кыргызча", "lang_ky"), ("🇹🇯 Тоҷикӣ", "lang_tg"),
        ("🇹🇲 Türkmençe", "lang_tk"), ("🇲🇩 Română", "lang_ro"), ("🇬🇪 ქართული", "lang_ka"),
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
        cursor.execute('''CREATE TABLE IF NOT EXISTS active_ads (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, server TEXT, category TEXT, text TEXT, photo TEXT, is_vip INTEGER, last_updated REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS pending_posts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, server TEXT, category TEXT, text TEXT, photo TEXT, is_vip INTEGER, editing_by INTEGER, editing_since REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS active_buy_ads (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, server TEXT, category TEXT, text TEXT, photo TEXT, is_vip INTEGER, last_updated REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS pending_buy_posts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, server TEXT, category TEXT, text TEXT, photo TEXT, is_vip INTEGER, editing_by INTEGER, editing_since REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS chat_logs_history (id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id INTEGER, receiver_id INTEGER, text TEXT, timestamp REAL)''')

        for tbl in ["active_ads", "pending_posts", "active_buy_ads", "pending_buy_posts"]:
            try:
                cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN is_edited INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass

        cursor.execute('''CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT)''')
        cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('vc_rate', '95000')")
        cursor.execute('''CREATE TABLE IF NOT EXISTS bans (target TEXT PRIMARY KEY, is_id INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS editor_stats (username TEXT PRIMARY KEY, count INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS user_data (user_id INTEGER PRIMARY KEY, username TEXT, last_ad_time REAL, language TEXT DEFAULT 'ru')''')
        try:
            cursor.execute("ALTER TABLE user_data ADD COLUMN language TEXT DEFAULT 'ru'")
        except sqlite3.OperationalError:
            pass

        cursor.execute('''CREATE TABLE IF NOT EXISTS active_dialogs (buyer_id INTEGER, seller_id INTEGER, ad_id INTEGER, is_active INTEGER, PRIMARY KEY (buyer_id, seller_id, ad_id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS favorites (user_id INTEGER, ad_id INTEGER, PRIMARY KEY (user_id, ad_id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS keyword_subscriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, server TEXT, keyword TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS seller_reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER, buyer_id INTEGER, rating INTEGER, comment TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS premium_users (user_id INTEGER PRIMARY KEY, expires_at REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS admin_chats (chat_id INTEGER PRIMARY KEY)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS admin_apps (user_id INTEGER PRIMARY KEY, username TEXT, application_text TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS approved_admins (user_id INTEGER PRIMARY KEY, username TEXT)''')
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
        cur.execute("SELECT 1 FROM bans WHERE (is_id = 1 AND target = ?) OR (is_id = 0 AND target = ?)", (str(user.id), uname))
        res = cur.fetchone()
    return bool(res)

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

def ikb_ad_actions(aid, is_fav=False, user_id=None, is_buy=False):
    markup = types.InlineKeyboardMarkup(row_width=2)
    fav_text = "❤️ В избранном" if is_fav else "❤️ В избранное"
    markup.add(
        types.InlineKeyboardButton(fav_text, callback_data=f"fav_toggle_{aid}"),
        types.InlineKeyboardButton("✉️ Написать автору", callback_data=f"contact_seller_{aid}")
    )
    return markup

# ==========================================
# ПЕРЕХВАТЧИК ДЛЯ ЗАБЛОКИРОВАННЫХ ПОЛЬЗОВАТЕЛЕЙ
# ==========================================
@bot.message_handler(func=lambda m: is_banned(m.from_user))
def blocked_user_message(m):
    safe_send_message(m.chat.id, "⛔ <b>Вы заблокированы в системе модерации.</b>", reply_markup=types.ReplyKeyboardRemove())

@bot.callback_query_handler(func=lambda c: is_banned(c.from_user))
def blocked_user_callback(c):
    try:
        bot.answer_callback_query(c.id, "⛔ Вы заблокированы в системе!", show_alert=True)
    except Exception:
        pass

# ==========================================
# УМНЫЙ МИДДЛВЕЙР НАВИГАЦИИ И КАТЕГОРИИ
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

    if any(st.get(k) for k in ["admin_editing_pid", "admin_editing_buy_pid", "applying_admin", "vc_setting_rate", "vc_calc_step", "searching_keyword", "adding_subscription", "creating_ad_type", "creating_ad_cat", "creating_ad_text"]):
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
        cat_name = all_cats_map.get(text, text)
        return show_category_ads(m, cat_name)
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
        return start_add_ad(m)
    elif text in [tr.get("btn_buy"), "📥 Скупить товар"]:
        return start_add_buy_ad(m)
    elif text in [tr.get("btn_vc_calc"), "💱 Курс VC и калькулятор"]:
        return show_vc_menu(m)
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
    uid = m.from_user.id
    register_user(uid, m.from_user.username)
    
    if is_banned(m.from_user):
        return safe_send_message(m.chat.id, "⛔ Вы заблокированы в системе модерации.", reply_markup=types.ReplyKeyboardRemove())
        
    if is_admin_or_owner(m.from_user):
        register_admin_chat(m.chat.id)
    
    welcome_text = get_text(uid, "welcome")
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
    welcome_text = get_text(uid, "welcome")
    safe_send_message(m.chat.id, welcome_text, reply_markup=kb_servers(uid))

def select_srv(m):
    srv = m.text
    uid = m.from_user.id
    update_state(uid, server=srv)
    safe_send_message(m.chat.id, f"✅ Игровой сервер установлен: <b>{html.escape(srv)}</b>", reply_markup=kb_main_menu(uid))

# ==========================================
# ПРОСМОТР КАТЕГОРИЙ И ОБЪЯВЛЕНИЙ
# ==========================================
def show_category_ads(m, category: str):
    uid = m.from_user.id
    srv = get_state(uid).get("server", "Phoenix")

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, user_id, text, photo, is_vip FROM active_ads WHERE server = ? AND category = ? ORDER BY id DESC LIMIT 10", (srv, category))
        sales = cur.fetchall()
        cur.execute("SELECT id, user_id, text, photo, is_vip FROM active_buy_ads WHERE server = ? AND category = ? ORDER BY id DESC LIMIT 10", (srv, category))
        buys = cur.fetchall()

    if not sales and not buys:
        return safe_send_message(m.chat.id, f"📂 В категории <b>{html.escape(category)}</b> на сервере <b>{html.escape(srv)}</b> пока нет активных объявлений.", reply_markup=kb_main_menu(uid))

    safe_send_message(m.chat.id, f"📂 <b>Категория: {html.escape(category)}</b> | Сервер: <b>{html.escape(srv)}</b>")

    for aid, author_id, text, photo, is_vip in sales:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM favorites WHERE user_id = ? AND ad_id = ?", (uid, aid))
            is_fav = bool(cur.fetchone())
        markup = ikb_ad_actions(aid, is_fav=is_fav, user_id=uid, is_buy=False)
        fmt_text = f"📤 <b>[Продажа]</b>\n{html.escape(text)}"
        if photo:
            safe_send_photo(m.chat.id, photo, caption=fmt_text, reply_markup=markup)
        else:
            safe_send_message(m.chat.id, fmt_text, reply_markup=markup)

    for aid, author_id, text, photo, is_vip in buys:
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM favorites WHERE user_id = ? AND ad_id = ?", (uid, aid))
            is_fav = bool(cur.fetchone())
        markup = ikb_ad_actions(aid, is_fav=is_fav, user_id=uid, is_buy=True)
        fmt_text = f"📥 <b>[Скупка]</b>\n{html.escape(text)}"
        if photo:
            safe_send_photo(m.chat.id, photo, caption=fmt_text, reply_markup=markup)
        else:
            safe_send_message(m.chat.id, fmt_text, reply_markup=markup)

# ==========================================
# ПОДАЧА ОБЪЯВЛЕНИЙ (ПРОДАЖА И СКУПКА)
# ==========================================
def start_add_ad(m):
    uid = m.from_user.id
    srv = get_state(uid).get("server")
    if not srv:
        return safe_send_message(m.chat.id, "⚠️ Сначала выберите игровой сервер!", reply_markup=kb_servers(uid))
    
    update_state(uid, creating_ad_type="sale")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    for cat in CATEGORIES:
        markup.add(types.KeyboardButton(cat))
    markup.add(types.KeyboardButton(get_text(uid, "btn_cancel")))
    safe_send_message(m.chat.id, "📤 <b>Подача объявления о продаже:</b>\n\nВыберите категорию товара:", reply_markup=markup)

def start_add_buy_ad(m):
    uid = m.from_user.id
    srv = get_state(uid).get("server")
    if not srv:
        return safe_send_message(m.chat.id, "⚠️ Сначала выберите игровой сервер!", reply_markup=kb_servers(uid))
    
    update_state(uid, creating_ad_type="buy")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    for cat in CATEGORIES:
        markup.add(types.KeyboardButton(cat))
    markup.add(types.KeyboardButton(get_text(uid, "btn_cancel")))
    safe_send_message(m.chat.id, "📥 <b>Подача объявления о скупке:</b>\n\nВыберите категорию товара:", reply_markup=markup)

@bot.message_handler(func=lambda m: get_state(m.from_user.id).get("creating_ad_type") and not get_state(m.from_user.id).get("creating_ad_cat"))
def process_ad_category(m):
    uid = m.from_user.id
    cat = m.text.strip()
    if cat not in CATEGORIES:
        return safe_send_message(m.chat.id, "⚠️ Пожалуйста, выберите категорию с помощью кнопок ниже.")
    
    update_state(uid, creating_ad_cat=cat)
    safe_send_message(m.chat.id, f"✍️ Отправьте текст вашего объявления (и прикрепите фото, если нужно):\n\n<i>Категория: {cat}</i>", reply_markup=kb_cancel(uid))

@bot.message_handler(content_types=['text', 'photo'], func=lambda m: get_state(m.from_user.id).get("creating_ad_cat") and not get_state(m.from_user.id).get("creating_ad_text"))
def process_ad_content(m):
    uid = m.from_user.id
    st = get_state(uid)
    ad_type = st.get("creating_ad_type")
    cat = st.get("creating_ad_cat")
    srv = st.get("server", "Phoenix")
    uname = m.from_user.username or "Без юзернейма"

    text = m.caption if m.photo else m.text
    if not text:
        return safe_send_message(m.chat.id, "⚠️ Текст объявления не может быть пустым. Отправьте описание.")

    photo_id = m.photo[-1].file_id if m.photo else None
    is_vip = 1 if is_user_premium(uid) else 0

    table = "pending_buy_posts" if ad_type == "buy" else "pending_posts"

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute(f"INSERT INTO {table} (user_id, username, server, category, text, photo, is_vip) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (uid, uname, srv, cat, text, photo_id, is_vip))
        pid = cur.lastrowid
        conn.commit()

    clear_state(uid)
    safe_send_message(m.chat.id, "✅ Ваше объявление успешно отправлено редакторам на модерацию!", reply_markup=kb_main_menu(uid))

    # Уведомление редакторов
    markup = types.InlineKeyboardMarkup(row_width=2)
    approve_cb = f"approve_buy_ad_{pid}" if ad_type == "buy" else f"approve_ad_{pid}"
    reject_cb = f"reject_buy_ad_{pid}" if ad_type == "buy" else f"reject_ad_{pid}"
    markup.add(
        types.InlineKeyboardButton("✅ Одобрить", callback_data=approve_cb),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=reject_cb)
    )

    notif_text = (
        f"🚨 <b>Новая заявка на публикацию ({'Скупка' if ad_type == 'buy' else 'Продажа'})!</b>\n\n"
        f"👤 Автор: @{html.escape(uname)} (ID: <code>{uid}</code>)\n"
        f"🌐 Сервер: <b>{html.escape(srv)}</b>\n"
        f"📂 Категория: <b>{html.escape(cat)}</b>\n\n"
        f"📄 <b>Текст:</b>\n{html.escape(text)}"
    )

    for admin_id in get_all_admin_ids():
        try:
            if photo_id:
                safe_send_photo(admin_id, photo_id, caption=notif_text, reply_markup=markup)
            else:
                safe_send_message(admin_id, notif_text, reply_markup=markup)
        except Exception as e:
            logger.error(f"Не удалось отправить заявку админу {admin_id}: {e}")

# ==========================================
# МОДЕРАЦИЯ ОБЪЯВЛЕНИЙ РЕДАКТОРАМИ
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("approve_ad_") or c.data.startswith("approve_buy_ad_") or c.data.startswith("reject_ad_") or c.data.startswith("reject_buy_ad_"))
def cb_moderate_ad(call):
    if not is_admin_or_owner(call.from_user):
        return bot.answer_callback_query(call.id, "⛔ Нет доступа!", show_alert=True)

    is_buy = "buy" in call.data
    is_approve = "approve" in call.data
    prefix = "approve_buy_ad_" if is_buy and is_approve else ("approve_ad_" if is_approve else ("reject_buy_ad_" if is_buy else "reject_ad_"))
    pid = int(call.data.replace(prefix, ""))
    
    pending_table = "pending_buy_posts" if is_buy else "pending_posts"
    active_table = "active_buy_ads" if is_buy else "active_ads"

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT user_id, server, category, text, photo, is_vip FROM {pending_table} WHERE id = ?", (pid,))
        row = cur.fetchone()
        if not row:
            try:
                bot.answer_callback_query(call.id, "⚠️ Объявление уже обработано или не найдено!", show_alert=True)
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass
            return

        author_id, srv, cat, text, photo, is_vip = row

        if is_approve:
            cur.execute(f"INSERT INTO {active_table} (user_id, server, category, text, photo, is_vip, last_updated) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (author_id, srv, cat, text, photo, is_vip, time.time()))
            cur.execute(f"DELETE FROM {pending_table} WHERE id = ?", (pid,))
            conn.commit()
            
            try:
                bot.answer_callback_query(call.id, "✅ Объявление одобрено и опубликовано!")
                bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=call.message.caption + "\n\n<b>[ОДОБРЕНО ✅]</b>", reply_markup=None)
            except Exception:
                try:
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=call.message.text + "\n\n<b>[ОДОБРЕНО ✅]</b>", reply_markup=None)
                except Exception:
                    pass

            safe_send_message(author_id, f"🎉 Ваше объявление на сервере <b>{html.escape(srv)}</b> было успешно проверено и опубликовано!")
        else:
            cur.execute(f"DELETE FROM {pending_table} WHERE id = ?", (pid,))
            conn.commit()
            try:
                bot.answer_callback_query(call.id, "❌ Объявление отклонено.")
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass
            safe_send_message(author_id, f"❌ Ваше объявление на сервере <b>{html.escape(srv)}</b> было отклонено редактором.")

# ==========================================
# КАЛЬКУЛЯТОР И КУРС VICE CITY
# ==========================================
def show_vc_menu(m):
    uid = m.from_user.id
    rate = get_vc_rate()
    text = (
        f"💱 <b>Курс обмена и калькулятор Vice City</b>\n\n"
        f"• Текущий курс обмена (за 1 VC$): <b>{rate:,.0f} вирт</b>\n\n"
        f"Используйте кнопки ниже для конвертации:"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔄 Вирты ➡️ VC$", callback_data="vc_calc_to_vc"),
        types.InlineKeyboardButton("🔄 VC$ ➡️ Вирты", callback_data="vc_calc_to_virt")
    )
    safe_send_message(m.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["vc_calc_to_vc", "vc_calc_to_virt"])
def cb_vc_calc_prompt(call):
    uid = call.from_user.id
    is_to_vc = call.data == "vc_calc_to_vc"
    update_state(uid, vc_calc_step="waiting_amount", vc_calc_to_vc=is_to_vc)
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    prompt = "💰 Введите сумму в виртах для перевода в VC$:" if is_to_vc else "💰 Введите сумму в VC$ для перевода в вирты:"
    safe_send_message(call.message.chat.id, prompt, reply_markup=kb_cancel(uid))

@bot.message_handler(func=lambda m: get_state(m.from_user.id).get("vc_calc_step") == "waiting_amount")
def process_vc_calculation(m):
    uid = m.from_user.id
    st = get_state(uid)
    clear_state(uid)

    try:
        amount = float(m.text.strip().replace(',', '').replace('.', ''))
    except ValueError:
        return safe_send_message(m.chat.id, "⚠️ Пожалуйста, введите корректное число.")

    rate = get_vc_rate()
    is_to_vc = st.get("vc_calc_to_vc", True)

    if is_to_vc:
        vc_result = amount / rate
        result_text = f"💱 <b>Результат конвертации:</b>\n\n{amount:,.0f} вирт = <b>{vc_result:,.2f} VC$</b>\n(Курс: {rate:,.0f} вирт за 1 VC$)"
    else:
        virt_result = amount * rate
        result_text = f"💱 <b>Результат конвертации:</b>\n\n{amount:,.2f} VC$ = <b>{virt_result:,.0f} вирт</b>\n(Курс: {rate:,.0f} вирт за 1 VC$)"

    safe_send_message(m.chat.id, result_text, reply_markup=kb_main_menu(uid))

# Изменение курса VC администратором
@bot.callback_query_handler(func=lambda c: c.data == "vc_set_rate_start")
def cb_vc_set_rate_start(call):
    if not is_admin_or_owner(call.from_user):
        return bot.answer_callback_query(call.id, "⛔ Нет доступа!", show_alert=True)
    uid = call.from_user.id
    update_state(uid, vc_setting_rate=True)
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    safe_send_message(call.message.chat.id, f"⚙️ Введите новый курс вирт за 1 VC$ (текущий: {get_vc_rate():,.0f}):", reply_markup=kb_cancel(uid))

@bot.message_handler(func=lambda m: get_state(m.from_user.id).get("vc_setting_rate"))
def process_vc_set_rate(m):
    uid = m.from_user.id
    clear_state(uid)
    try:
        new_rate = float(m.text.strip().replace(',', ''))
        if new_rate <= 0:
            raise ValueError()
    except ValueError:
        return safe_send_message(m.chat.id, "⚠️ Неверный формат числа.")

    set_vc_rate(new_rate)
    safe_send_message(m.chat.id, f"✅ Курс VC успешно обновлен! Новый курс: <b>{new_rate:,.0f} вирт</b>", reply_markup=kb_main_menu(uid))

# ==========================================
# ВНУТРЕННИЙ ЧАТ (СВЯЗЬ С АВТОРОМ ОБЪЯВЛЕНИЯ)
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("contact_seller_"))
def cb_contact_seller(call):
    aid = int(call.data.replace("contact_seller_", ""))
    uid = call.from_user.id

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, server, text FROM active_ads WHERE id = ?", (aid,))
        row = cur.fetchone()
        is_buy = False
        if not row:
            cur.execute("SELECT user_id, server, text FROM active_buy_ads WHERE id = ?", (aid,))
            row = cur.fetchone()
            is_buy = True

    if not row:
        return bot.answer_callback_query(call.id, "⚠️ Объявление не найдено или уже удалено!", show_alert=True)

    seller_id, srv, text = row
    if seller_id == uid:
        return bot.answer_callback_query(call.id, "⚠️ Вы не можете писать сами себе!", show_alert=True)

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO active_dialogs (buyer_id, seller_id, ad_id, is_active) VALUES (?, ?, ?, 1)", (uid, seller_id, aid))
        conn.commit()

    try:
        bot.answer_callback_query(call.id, "✉️ Чат открыт! Отправьте сообщение в чат.")
    except Exception:
        pass

    update_state(uid, active_chat_with=seller_id, active_chat_aid=aid)
    safe_send_message(call.message.chat.id, f"✉️ <b>Защищенный чат с автором объявления ID {aid} открыт.</b>\nНапишите ваше сообщение ответным сообщением:", reply_markup=kb_cancel(uid))

@bot.message_handler(func=lambda m: get_state(m.from_user.id).get("active_chat_with"))
def process_internal_chat_message(m):
    uid = m.from_user.id
    st = get_state(uid)
    seller_id = st.get("active_chat_with")
    aid = st.get("active_chat_aid")

    text = m.text.strip()
    if not text:
        return

    forward_text = f"✉️ <b>Новое сообщение по объявлению ID {aid}:</b>\n\n{html.escape(text)}"
    try:
        safe_send_message(seller_id, forward_text)
        safe_send_message(uid, "✅ Сообщение доставлено автору.")
    except Exception as e:
        safe_send_message(uid, "⚠️ Не удалось доставить сообщение (возможно, пользователь заблокировал бота).")

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

    markup = ikb_ad_actions(aid, is_fav=is_fav, user_id=uid, is_buy=is_buy)
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
        markup = ikb_ad_actions(aid, is_fav=is_fav, user_id=uid, is_buy=False)
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
        cur.execute("SELECT id, keyword, server FROM keyword_subscriptions WHERE user_id = ?", (uid,))
        subs = cur.fetchall()

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("➕ Добавить ключевое слово", callback_data="sub_add_prompt"))
    for sub_id, kw, sub_srv in subs:
        markup.add(types.InlineKeyboardButton(f"❌ Удалить: {kw} [{sub_srv}]", callback_data=f"sub_del_{sub_id}"))

    text = "🔔 <b>Уведомления о поиске (Подписки на ключевые слова)</b>\n\nТекущие подписки:"
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

@bot.callback_query_handler(func=lambda c: c.data.startswith("sub_del_"))
def cb_sub_delete(call):
    sub_id = int(call.data.replace("sub_del_", ""))
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM keyword_subscriptions WHERE id = ?", (sub_id,))
        conn.commit()
    try:
        bot.answer_callback_query(call.id, "✅ Подписка удалена")
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

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

    safe_send_message(m.chat.id, "✅ Ваша заявка на пост редактора успешно отправлена! Ожидайте рассмотрения.", reply_markup=kb_main_menu(uid))

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Принять", callback_data=f"accept_admin_app_{uid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_admin_app_{uid}")
    )

    notif_text = f"📝 <b>Новая заявка на пост редактора!</b>\n\n👤 Кандидат: @{html.escape(uname)} (ID: <code>{uid}</code>)\n\n📄 <b>Текст:</b>\n{html.escape(app_text)}"

    for chat_id in get_all_admin_ids():
        try:
            safe_send_message(chat_id, notif_text, reply_markup=markup)
        except Exception as e:
            logger.error(f"Не удалось отправить заявку админу {chat_id}: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("accept_admin_app_") or c.data.startswith("reject_admin_app_"))
def cb_admin_application_action(call):
    if not is_admin_or_owner(call.from_user):
        return bot.answer_callback_query(call.id, "⛔ Нет доступа!", show_alert=True)

    is_accept = "accept" in call.data
    target_uid = int(call.data.replace("accept_admin_app_" if is_accept else "reject_admin_app_", ""))

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT username FROM admin_apps WHERE user_id = ?", (target_uid,))
        row = cur.fetchone()
        uname = row[0] if row else "user"
        cur.execute("DELETE FROM admin_apps WHERE user_id = ?", (target_uid,))
        if is_accept:
            cur.execute("INSERT OR IGNORE INTO approved_admins (user_id, username) VALUES (?, ?)", (target_uid, uname))
        conn.commit()

    try:
        bot.answer_callback_query(call.id, "✅ Заявка обработана!")
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=call.message.text + f"\n\n<b>[{'ОДОБРЕНО ✅' if is_accept else 'ОТКЛОНЕНО ❌'}]</b>", reply_markup=None)
    except Exception:
        pass

    if is_accept:
        safe_send_message(target_uid, "🎉 Поздравляем! Ваша заявка на пост редактора/администратора была одобрена.")
    else:
        safe_send_message(target_uid, "❌ К сожалению, ваша заявка на пост редактора была отклонена.")

def show_average_prices(m):
    uid = m.from_user.id
    srv = get_state(uid).get("server", "Phoenix")

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT category, text FROM active_ads WHERE server = ?", (srv,))
        ads = cur.fetchall()

    if not ads:
        return safe_send_message(m.chat.id, f"📊 На сервере <b>{html.escape(srv)}</b> пока недостаточно данных для расчета средних цен.", reply_markup=kb_main_menu(uid))

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
            report += f"📂 <b>{cat}</b>:\n• Средняя: <b>{format_price(avg_val)}</b> (Учтено: {len(prices)})\n\n"
        else:
            report += f"📂 <b>{cat}</b>:\n• <i>Нет данных</i>\n\n"

    safe_send_message(m.chat.id, report, reply_markup=kb_main_menu(uid))

def format_price(val: float) -> str:
    if val >= 1_000_000_000:
        return f"{val / 1_000_000_000:.1f} млрд"
    elif val >= 1_000_000:
        return f"{val / 1_000_000:.1f} млн"
    elif val >= 1_000:
        return f"{val / 1_000:.1f} тыс"
    return f"{int(val)}"

def admin_panel(m):
    if not is_admin_or_owner(m.from_user):
        return safe_send_message(m.chat.id, "⛔ Нет доступа к панели администратора.", reply_markup=kb_main_menu(m.from_user.id))
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("⚙️ Изменить курс VC", callback_data="vc_set_rate_start")
    )
    safe_send_message(m.chat.id, "👑 <b>Панель администратора / редактора:</b>", reply_markup=markup)

if __name__ == '__main__':
    logger.info("Бот запущен с исправленной логикой мультиязычности и работы кнопок!")
    bot.infinity_polling(skip_pending=True)
