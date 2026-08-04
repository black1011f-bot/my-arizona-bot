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
    },
    "be": {
        "welcome": "🌟 <b>Прывітанне! Звярніце ўвагу: мы не афіцыйны бот</b>, а незалежны памочнік для гульцоў Arizona RP...\n\n👇 <b>Для пачатку працы выберыце свой гульнявы сервер ніжэй:</b>",
        "lang_changed": "✅ Мова паспяхова зменена на беларускую.",
        "btn_change_server": "🌐 Змяніць гульнявы сервер",
        "btn_change_lang": "🌐 Змяніць мову",
        "btn_accessories": "💍 Аксэсуары і рэчы",
        "btn_transport": "🚗 Транспарт і цюнінг",
        "btn_skins": "👕 Скіны і ахоўнікі",
        "btn_realestate": "🏠 Нерухомасць і бізнесы",
        "btn_resources": "📦 Рэсурсы і матэрыялы",
        "btn_sell": "📤 Прадаць тавар",
        "btn_buy": "📥 Скупіць тавар",
        "btn_vc_calc": "💱 Курс VC і калькулятар",
        "btn_find_ad": "🔍 Знайсці тавар у базе",
        "btn_favorites": "❤️ Захаваныя",
        "btn_notifications": "🔔 Апавяшчэнні аб пошуку",
        "btn_my_ads": "📋 Мае публікацыі",
        "btn_avg_prices": "📊 Аналіз цэн на серверы",
        "btn_vip": "💎 VIP-статус",
        "btn_admin_panel": "👑 Адмін-панэль",
        "btn_become_editor": "📝 Стаць рэдактарам / адмінам",
        "btn_cancel": "❌ Адмяніць дзеянне",
        "btn_help": "📖 Даведка і правілы",
        "cat_accessories": "💍 Аксэсуары і рэчы",
        "cat_transport": "🚗 Транспарт і цюнінг",
        "cat_skins": "👕 Скіны і ахоўнікі",
        "cat_realestate": "🏠 Нерухомасць і бізнесы",
        "cat_resources": "📦 Рэсурсы і матэрыялы",
    },
    "kk": {
        "welcome": "🌟 <b>Сәлем! Назар аударыңыз: біз ресми бот емеспіз</b>, Arizona RP ойыншыларына арналған тәуелсіз көмекшіміз...\n\n👇 <b>Жұмысты бастау үшін төменден өз ойын серверіңізді таңдаңыз:</b>",
        "lang_changed": "✅ Тіл қазақ тіліне сәтті өзгертілді.",
        "btn_change_server": "🌐 Ойын серверін ауыстыру",
        "btn_change_lang": "🌐 Тілді өзгерту",
        "btn_accessories": "💍 Аксессуарлар мен заттар",
        "btn_transport": "🚗 Көлік және тюнинг",
        "btn_skins": "👕 Скиндер мен күзетшілер",
        "btn_realestate": "🏠 Жылжымайтын мүлік пен бизнес",
        "btn_resources": "📦 Ресурстар мен материалдар",
        "btn_sell": "📤 Тауарды сату",
        "btn_buy": "📥 Тауарды сатып алу",
        "btn_vc_calc": "💱 VC курсы және калькулятор",
        "btn_find_ad": "🔍 Базадан тауар табу",
        "btn_favorites": "❤️ Сақталғандар",
        "btn_notifications": "🔔 Іздеу хабарламалары",
        "btn_my_ads": "📋 Менің жарияланымдарым",
        "btn_avg_prices": "📊 Сервердегі бағаларды талдау",
        "btn_vip": "💎 VIP-статус",
        "btn_admin_panel": "👑 Әкімші панелі",
        "btn_become_editor": "📝 Редактор / админ болу",
        "btn_cancel": "❌ Әрекетті болдырмау",
        "btn_help": "📖 Анықтама және ережелер",
        "cat_accessories": "💍 Аксессуарлар мен заттар",
        "cat_transport": "🚗 Көлік және тюнинг",
        "cat_skins": "👕 Скиндер мен күзетшілер",
        "cat_realestate": "🏠 Жылжымайтын мүлік пен бизнес",
        "cat_resources": "📦 Ресурстар мен материалдар",
    },
    "uz": {
        "welcome": "🌟 <b>Salom! Diqqat qiling: biz rasmiy bot emasmiz</b>, Arizona RP o'yinchilari uchun mustaqil yordamchimiz...\n\n👇 <b>Ishni boshlash uchun quyidan o'yin serveringizni tanlang:</b>",
        "lang_changed": "✅ Til o'zbek tiliga muvaffaqiyatli o'zgartirildi.",
        "btn_change_server": "🌐 O'yin serverini o'zgartirish",
        "btn_change_lang": "🌐 Tilni o'zgartirish",
        "btn_accessories": "💍 Aksessuarlar va buyumlar",
        "btn_transport": "🚗 Transport va тюнинг",
        "btn_skins": "👕 Skinlar va qo'riqchilar",
        "btn_realestate": "🏠 Ko'chmas mulk va biznes",
        "btn_resources": "📦 Resurslar va materiallar",
        "btn_sell": "📤 Tovarni sotish",
        "btn_buy": "📥 Tovarni sotib olish",
        "btn_vc_calc": "💱 VC kursi va kalkulyator",
        "btn_find_ad": "🔍 Bazadan tovar topish",
        "btn_favorites": "❤️ Saqlanganlar",
        "btn_notifications": "🔔 Qidiruv bildirishnomalari",
        "btn_my_ads": "📋 Mening e'lonlarim",
        "btn_avg_prices": "📊 Serverdagi narxlar tahlili",
        "btn_vip": "💎 VIP-status",
        "btn_admin_panel": "👑 Admin panel",
        "btn_become_editor": "📝 Muharrir / admin bo'lish",
        "btn_cancel": "❌ Amalni bekor qilish",
        "btn_help": "📖 Yordam va qoidalar",
        "cat_accessories": "💍 Aksessuarlar va buyumlar",
        "cat_transport": "🚗 Transport va тюнинг",
        "cat_skins": "👕 Skinlar va qo'riqchilar",
        "cat_realestate": "🏠 Ko'chmas mulk va biznes",
        "cat_resources": "📦 Resurslar va materiallar",
    },
    "hy": {
        "welcome": "🌟 <b>Բարև ձեզ: Ուշադրություն դարձրեք. մենք պաշտոնական բոտ չենք</b>, այլ անկախ օգնական Arizona RP խաղացողների համար...\n\n👇 <b>Սկսելու համար ընտրեք ձեր խաղային սերվերը ստորև:</b>",
        "lang_changed": "✅ Լեզուն հաջողությամբ փոխվեց հայերենի:",
        "btn_change_server": "🌐 Փոխել խաղային սերվերը",
        "btn_change_lang": "🌐 Փոխել լեզուն",
        "btn_accessories": "💍 Աքսեսուարներ և իրեր",
        "btn_transport": "🚗 Տրանսպորտ և թյունինգ",
        "btn_skins": "👕 Սկիններ և պահակներ",
        "btn_realestate": "🏠 Անշարժ գույք և բիզնես",
        "btn_resources": "📦 Ռեսուրսներ և նյութեր",
        "btn_sell": "📤 Վաճառել ապրանք",
        "btn_buy": "📥 Գնել ապրանք",
        "btn_vc_calc": "💱 VC փոխարժեք և հաշվիչ",
        "btn_find_ad": "🔍 Գտնել ապրանք բազայում",
        "btn_favorites": "❤️ Ընտրանիներ",
        "btn_notifications": "🔔 Որոնման ծանուցումներ",
        "btn_my_ads": "📋 Իմ հրապարակումները",
        "btn_avg_prices": "📊 Գների վերլուծություն սերվերում",
        "btn_vip": "💎 VIP կարգավիճակ",
        "btn_admin_panel": "👑 Ադմին պանել",
        "btn_become_editor": "📝 Դառնալ խմբագիր / ադմին",
        "btn_cancel": "❌ Չեղարկել գործողությունը",
        "btn_help": "📖 Օգնություն և կանոններ",
        "cat_accessories": "💍 Աքսեսուարներ և իրեր",
        "cat_transport": "🚗 Տրանսպորտ և թյունինգ",
        "cat_skins": "👕 Սկիններ և պահակներ",
        "cat_realestate": "🏠 Անշարժ գույք և բիզնես",
        "cat_resources": "📦 Ռեսուրսներ և նյութեր",
    },
    "az": {
        "welcome": "🌟 <b>Salam! Diqqət edin: biz rəsmi bot deyilik</b>, Arizona RP oyunçuları üçün müstəqil köməkçiyik...\n\n👇 <b>Başlamaq üçün aşağıdan oyun serverinizi seçin:</b>",
        "lang_changed": "✅ Dil uğurla Azərbaycan dilinə dəyişdirildi.",
        "btn_change_server": "🌐 Oyun serverini dəyişdir",
        "btn_change_lang": "🌐 Dili dəyişdir",
        "btn_accessories": "💍 Aksesuarlar və əşyalar",
        "btn_transport": "🚗 Nəqliyyat və tüning",
        "btn_skins": "👕 Skinlər və mühafizəçilər",
        "btn_realestate": "🏠 Daşınmaz əmlak və biznes",
        "btn_resources": "📦 Resurslar və materiallar",
        "btn_sell": "📤 Məhsul sat",
        "btn_buy": "📥 Məhsul al",
        "btn_vc_calc": "💱 VC məzənnəsi və kalkulyator",
        "btn_find_ad": "🔍 Bazada məhsul tap",
        "btn_favorites": "❤️ Seçilmişlər",
        "btn_notifications": "🔔 Axtarış bildirişləri",
        "btn_my_ads": "📋 Mənim elanlarım",
        "btn_avg_prices": "📊 Serverdə qiymət analizi",
        "btn_vip": "💎 VIP status",
        "btn_admin_panel": "👑 Admin panel",
        "btn_become_editor": "📝 Redaktor / admin ol",
        "btn_cancel": "❌ Əməliyyatı ləğv et",
        "btn_help": "📖 Kömək və qaydalar",
        "cat_accessories": "💍 Aksesuarlar və əşyalar",
        "cat_transport": "🚗 Nəqliyyat və tüning",
        "cat_skins": "👕 Skinlər və mühafizəçilər",
        "cat_realestate": "🏠 Daşınmaz əmlak və biznes",
        "cat_resources": "📦 Resurslar və materiallar",
    },
    "ky": {
        "welcome": "🌟 <b>Салам! Көңүл буруңуз: биз расмий бот эмеспиз</b>, Arizona RP оюнчулары үчүн көз карандысыз жардамчыбыз...\n\n👇 <b>Баштоо үчүн төмөндөн өз оюн сервериңизди тандаңыз:</b>",
        "lang_changed": "✅ Тил кыргыз тилине ийгиликтүү өзгөртүлдү.",
        "btn_change_server": "🌐 Оюн серверин өзгөртүү",
        "btn_change_lang": "🌐 Тилди өзгөртүү",
        "btn_accessories": "💍 Аксессуарлар жана буюмдар",
        "btn_transport": "🚗 Унаа жана тюнинг",
        "btn_skins": "👕 Скиндер жана сакчылар",
        "btn_realestate": "🏠 Кыймылсыз мүлк жана бизнес",
        "btn_resources": "📦 Ресурстар жана материалдар",
        "btn_sell": "📤 Товар сатуу",
        "btn_buy": "📥 Товар сатып алуу",
        "btn_vc_calc": "💱 VC курсу жана калькулятор",
        "btn_find_ad": "🔍 Базадан товар табуу",
        "btn_favorites": "❤️ Сакталгандар",
        "btn_notifications": "🔔 Издөө эскертмелери",
        "btn_my_ads": "📋 Менин жарыяларым",
        "btn_avg_prices": "📊 Сервердеги бааларды талдоо",
        "btn_vip": "💎 VIP-статус",
        "btn_admin_panel": "👑 Администратор панели",
        "btn_become_editor": "📝 Редактор / админ болуу",
        "btn_cancel": "❌ Аракетти жокко чыгаруу",
        "btn_help": "📖 Жардам жана эрежелер",
        "cat_accessories": "💍 Аксессуарлар жана буюмдар",
        "cat_transport": "🚗 Унаа жана тюнинг",
        "cat_skins": "👕 Скиндер жана сакчылар",
        "cat_realestate": "🏠 Кыймылсыз мүлк жана бизнес",
        "cat_resources": "📦 Ресурстар жана материалдар",
    },
    "tg": {
        "welcome": "🌟 <b>Салом! Диққат кунед: мо боти расмӣ нестем</b>, балки ёвари мустақил барои бозингарони Arizona RP ҳастем...\n\n👇 <b>Барои оғоз кардан сервери бозии худро аз зер интихоб кунед:</b>",
        "lang_changed": "✅ Забон бомуваффақият ба тоҷикӣ иваз карда шуд.",
        "btn_change_server": "🌐 Иваз кардани сервери бозӣ",
        "btn_change_lang": "🌐 Иваз кардани забон",
        "btn_accessories": "💍 Лавозимот ва ашё",
        "btn_transport": "🚗 Нақлиёт ва тюнинг",
        "btn_skins": "👕 Пӯстҳо ва муҳофизон",
        "btn_realestate": "🏠 Амволи ғайриманқул ва бизнес",
        "btn_resources": "📦 Сарватҳо ва мавод",
        "btn_sell": "📤 Фурӯхтани мол",
        "btn_buy": "📥 Харидани мол",
        "btn_vc_calc": "💱 Қурби VC ва калькулятор",
        "btn_find_ad": "🔍 Ёфтани мол дар база",
        "btn_favorites": "❤️ Дӯстдоштаҳо",
        "btn_notifications": "🔔 Огоҳиномаҳои ҷустуҷӯ",
        "btn_my_ads": "📋 Эълонҳои ман",
        "btn_avg_prices": "📊 Таҳлили нархҳо дар сервер",
        "btn_vip": "💎 Статуси VIP",
        "btn_admin_panel": "👑 Панели админ",
        "btn_become_editor": "📝 Муҳаррир / админ шудан",
        "btn_cancel": "❌ Бекор кардани амал",
        "btn_help": "📖 Кӯмак ва қоидаҳо",
        "cat_accessories": "💍 Лавозимот ва ашё",
        "cat_transport": "🚗 Нақлиёт ва тюнинг",
        "cat_skins": "👕 Пӯстҳо ва муҳофизон",
        "cat_realestate": "🏠 Амволи ғайриманқул ва бизнес",
        "cat_resources": "📦 Сарватҳо ва мавод",
    },
    "tk": {
        "welcome": "🌟 <b>Salam! Üns beriň: biz resmi bot däl</b>, Arizona RP oýunçylary üçin garaşsyz kömekçi...\n\n👇 <b>Başlamak üçin aşakdan oýun serweriňizi saýlaň:</b>",
        "lang_changed": "✅ Dil üstünlikli türkmen diline üýtgedildi.",
        "btn_change_server": "🌐 Oýun serwerini üýtgetmek",
        "btn_change_lang": "🌐 Dili üýtgetmek",
        "btn_accessories": "💍 Aksesuarlar we zatlar",
        "btn_transport": "🚗 Transport we tüning",
        "btn_skins": "👕 Skinler we goraýjylar",
        "btn_realestate": "🏠 Daşlaşdyrylmaýan emläk we biznes",
        "btn_resources": "📦 Resurslar we materiallar",
        "btn_sell": "📤 Haryt satmak",
        "btn_buy": "📥 Haryt satyn almak",
        "btn_vc_calc": "💱 VC kursy we kalkulýator",
        "btn_find_ad": "🔍 Bazasdan haryt tapmak",
        "btn_favorites": "❤️ Halananlar",
        "btn_notifications": "🔔 Gözleg duýduryşlary",
        "btn_my_ads": "📋 Meniň bildirişlerim",
        "btn_avg_prices": "📊 Serwerdäki bahalaryň derňewi",
        "btn_vip": "💎 VIP status",
        "btn_admin_panel": "👑 Admin panel",
        "btn_become_editor": "📝 Redaktor / admin bolmak",
        "btn_cancel": "❌ Hereketi ýatyrmak",
        "btn_help": "📖 Kömek we düzgünler",
        "cat_accessories": "💍 Aksesuarlar we zatlar",
        "cat_transport": "🚗 Transport we tüning",
        "cat_skins": "👕 Skinler we goraýjylar",
        "cat_realestate": "🏠 Daşlaşdyrylmaýan emläk we biznes",
        "cat_resources": "📦 Resurslar we materiallar",
    },
    "ro": {
        "welcome": "🌟 <b>Salut! Vă rugăm să rețineți: nu suntem un bot oficial</b>, ci un asistent independent pentru jucătorii Arizona RP...\n\n👇 <b>Pentru a începe, selectați serverul de joc de mai jos:</b>",
        "lang_changed": "✅ Limba a fost schimbată cu succes în română.",
        "btn_change_server": "🌐 Schimbă serverul de joc",
        "btn_change_lang": "🌐 Schimbă limba",
        "btn_accessories": "💍 Accesorii și obiecte",
        "btn_transport": "🚗 Transport și tuning",
        "btn_skins": "👕 Skin-uri și gărzi",
        "btn_realestate": "🏠 Imobiliare și afaceri",
        "btn_resources": "📦 Resurse și materiale",
        "btn_sell": "📤 Vinde produs",
        "btn_buy": "📥 Cumpără produs",
        "btn_vc_calc": "💱 Curs VC și calculator",
        "btn_find_ad": "🔍 Găsește produs în baza de date",
        "btn_favorites": "❤️ Favorite",
        "btn_notifications": "🔔 Notificări de căutare",
        "btn_my_ads": "📋 Publicațiile mele",
        "btn_avg_prices": "📊 Analiza prețurilor pe server",
        "btn_vip": "💎 Statut VIP",
        "btn_admin_panel": "👑 Panou admin",
        "btn_become_editor": "📝 Deveniți editor / admin",
        "btn_cancel": "❌ Anulează acțiunea",
        "btn_help": "📖 Ajutor și reguli",
        "cat_accessories": "💍 Accesorii și obiecte",
        "cat_transport": "🚗 Transport și tuning",
        "cat_skins": "👕 Skin-uri și gărzi",
        "cat_realestate": "🏠 Imobiliare și afaceri",
        "cat_resources": "📦 Resurse și materiale",
    },
    "ka": {
        "welcome": "🌟 <b>გამარჯობა! ყურადღება მიაქციეთ: ჩვენ არ ვართ ოფიციალური ბოტი</b>, არამედ დამოუკიდებელი დამხმარე Arizona RP მოთამაშეებისთვის...\n\n👇 <b>დასაწყებად აირჩიეთ თქვენი თამაშის სერვერი ქვემოთ:</b>",
        "lang_changed": "✅ ენა წარმატებით შეიცვალა ქართულად.",
        "btn_change_server": "🌐 თამაშის სერვერის შეცვლა",
        "btn_change_lang": "🌐 ენის შეცვლა",
        "btn_accessories": "💍 აქსესუარები და ნივთები",
        "btn_transport": "🚗 ტრანსპორტი და ტიუნინგი",
        "btn_skins": "👕 სკინები და მცველები",
        "btn_realestate": "🏠 უძრავი ქონება და ბიზნესი",
        "btn_resources": "📦 რესურსები და მასალები",
        "btn_sell": "📤 საქონლის გაყიდვა",
        "btn_buy": "📥 საქონლის ყიდვა",
        "btn_vc_calc": "💱 VC კურსი და კალკულატორი",
        "btn_find_ad": "🔍 საქონლის ძებნა ბაზაში",
        "btn_favorites": "❤️ რჩეულები",
        "btn_notifications": "🔔 ძიების შეტყობინებები",
        "btn_my_ads": "📋 ჩემი პუბლიკაციები",
        "btn_avg_prices": "📊 ფასების ანალიზი სერვერზე",
        "btn_vip": "💎 VIP სტატუსი",
        "btn_admin_panel": "👑 ადმინ პანელი",
        "btn_become_editor": "📝 რედაქტორ / ადმინ გახდომა",
        "btn_cancel": "❌ მოქმედების გაუქმება",
        "btn_help": "📖 დახმარება და წესები",
        "cat_accessories": "💍 აქსესუარები და ნივთები",
        "cat_transport": "🚗 ტრანსპორტი და ტიუნინგი",
        "cat_skins": "👕 სკინები და მცველები",
        "cat_realestate": "🏠 უძრავი ქონება და ბიზნესი",
        "cat_resources": "📦 რესურსები და მასალები",
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
    set_user_lang(call.from_user.id, lang)
    try:
        bot.answer_callback_query(call.id, TRANSLATIONS.get(lang, TRANSLATIONS["ru"]).get("lang_changed", "Language updated!"))
    except Exception:
        pass
    cmd_start(call.message)

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

def get_seller_rating_info(seller_id: int) -> str:
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT AVG(rating), COUNT(rating) FROM seller_reviews WHERE seller_id = ?", (seller_id,))
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
        cur.execute("SELECT last_ad_time FROM user_data WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else 0

def set_user_last_ad_time(user_id, t):
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO user_data (user_id, last_ad_time) VALUES (?, ?)", (user_id, t))
        conn.commit()

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

def clean_server_name(server: str) -> str:
    return server.split(' ', 1)[-1] if ' ' in server else server

# ==========================================
# КЛАВИАТУРЫ (С ПОДДЕРЖКОЙ ПЕРЕВОДОВ)
# ==========================================
def kb_servers(user_id: int):
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for i in range(0, len(SERVERS), 2): 
        m.add(*[types.KeyboardButton(s) for s in SERVERS[i:i+2]])
    m.add(types.KeyboardButton(get_text(user_id, "btn_help")))
    m.add(types.KeyboardButton(get_text(user_id, "btn_vip")), types.KeyboardButton(get_text(user_id, "btn_admin_panel")))
    m.add(types.KeyboardButton(get_text(user_id, "btn_become_editor")), types.KeyboardButton(get_text(user_id, "btn_change_lang")))
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
# УМНЫЙ МИДДЛВЕЙР НАВИГАЦИИ (С УЧЕТОМ ЯЗЫКОВ)
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
        
    if "posting_ad" in st or "posting_buy_ad" in st:
        p_key = "posting_ad" if "posting_ad" in st else "posting_buy_ad"
        step = st[p_key].get("step")
        all_cats = []
        for t in TRANSLATIONS.values():
            all_cats.extend([t.get("cat_accessories"), t.get("cat_transport"), t.get("cat_skins"), t.get("cat_realestate"), t.get("cat_resources")])
        if step == "category" and (msg.text in CATEGORIES or msg.text in all_cats):
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
    
    # Категории
    all_cats_map = {
        tr.get("cat_accessories"): CATEGORIES[0],
        tr.get("cat_transport"): CATEGORIES[1],
        tr.get("cat_skins"): CATEGORIES[2],
        tr.get("cat_realestate"): CATEGORIES[3],
        tr.get("cat_resources"): CATEGORIES[4],
    }
    
    if text in all_cats_map or text in CATEGORIES:
        if get_state(uid).get("viewing_buy_categories"):
            show_buy_ads_category(m)
        else:
            show_ads_category(m)
        return
    elif text in SERVERS:
        return select_srv(m)

    if text in [tr.get("btn_change_server"), "🌐 Сменить игровой сервер"]:
        return change_server(m)
    elif text in [tr.get("btn_change_lang"), "🌐 Сменить язык"]:
        return select_language_command(m)
    elif text in [tr.get("btn_help"), "📖 Справка и правила"]:
        return how_bot_works(m)
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
        return cancel_action(m)
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
# ОСНОВНЫЕ КОМАНДЫ (С ВЫБОРОМ ЯЗЫКА И ПРИВЕТСТВИЕМ)
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
    help_text = (
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
    )
    safe_send_message(m.chat.id, help_text, reply_markup=kb_main_menu(m.from_user.id))

def change_server(m):
    uid = m.from_user.id
    safe_send_message(m.chat.id, "👇 Выберите новый игровой сервер:", reply_markup=kb_servers(uid))

def select_srv(m):
    srv = m.text
    uid = m.from_user.id
    update_state(uid, server=srv)
    safe_send_message(m.chat.id, f"✅ Игровой сервер установлен: <b>{html.escape(srv)}</b>", reply_markup=kb_main_menu(uid))

def how_bot_works(m):
    text = (
        "📖 <b>Справочник: Как работает бот и радиоцентр</b>\n\n"
        "1. <b>Подача объявления:</b> Выбирается тип (продажа/скупка), сервер, категория и текст.\n"
        "2. <b>Проверка редакторами:</b> Редакторы проверяют материалы с 08:00:01 до 22:00:01 МСК.\n"
        "3. <b>Публикация:</b> Одобренное объявление уходит в ленту.\n"
        "4. <b>Инструменты VC:</b> Полноценный курс, конвертер и калькулятор прибыли для перекупщиков."
    )
    safe_send_message(m.chat.id, text)

# ==========================================
# УПРАВЛЕНИЕ ИЗБРАННЫМ И СВОИМИ ПУБЛИКАЦИЯМИ
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
# ПОИСК ТОВАРОВ И УВЕДОМЛЕНИЯ ПО ПОДПИСКАМ
# ==========================================
def start_search(m):
    uid = m.from_user.id
    update_state(uid, searching_keyword=True)
    safe_send_message(
        m.chat.id,
        "🔍 <b>Поиск товара в базе объявлений:</b>\n\n"
        "Отправьте ключевое слово или название предмета для поиска (например: <code>аксессуар</code>, <code>нимб</code>, <code>дом</code>):",
        reply_markup=kb_cancel(uid)
    )

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
    safe_send_message(call.message.chat.id, "✍️ Отправьте ключевое слово или фразу для отслеживания (например: <code>скин</code> или <code>нимб</code>):", reply_markup=kb_cancel(uid))

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
def cb_sub_del(call):
    sub_id = int(call.data.replace("sub_del_", ""))
    uid = call.from_user.id

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM keyword_subscriptions WHERE id = ? AND user_id = ?", (sub_id, uid))
        conn.commit()

    try:
        bot.answer_callback_query(call.id, "✅ Подписка удалена!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

def notify_subscribers(server, text, aid, is_buy, photo, publisher_id):
    lower_text = text.lower()
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT user_id, keyword FROM keyword_subscriptions WHERE server = ?", (server,))
        subs = cur.fetchall()

    notified_users = set()
    for sub_uid, kw in subs:
        if sub_uid != publisher_id and sub_uid not in notified_users and kw in lower_text:
            notified_users.add(sub_uid)
            type_label = "📥 [Скупка]" if is_buy else "📤 [Продажа]"
            notif_msg = f"🔔 <b>Найдено совпадение по вашему ключевому слову «{html.escape(kw)}»!</b>\n\n{type_label} [{html.escape(server)}]:\n{html.escape(text)}"
            markup = ikb_ad_actions(aid, is_fav=False, user_id=sub_uid, is_buy=is_buy)
            try:
                if photo:
                    safe_send_photo(sub_uid, photo, caption=notif_msg, reply_markup=markup)
                else:
                    safe_send_message(sub_uid, notif_msg, reply_markup=markup)
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление по подписке пользователю {sub_uid}: {e}")

# ==========================================
# ЧАТЫ И СВЯЗЬ С ПРОДАВЦОМ
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("contact_seller_"))
def cb_contact_seller(call):
    aid = int(call.data.split("_")[2])
    buyer_id = call.from_user.id
    
    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, server FROM active_ads WHERE id = ?", (aid,))
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT user_id, server FROM active_buy_ads WHERE id = ?", (aid,))
            row = cur.fetchone()

    if not row:
        return bot.answer_callback_query(call.id, "⚠️ Объявление уже неактивно или удалено!", show_alert=True)
    
    seller_id = row[0]
    if buyer_id == seller_id:
        return bot.answer_callback_query(call.id, "⚠️ Вы не можете написать сами себе!", show_alert=True)

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO active_dialogs (buyer_id, seller_id, ad_id, is_active) VALUES (?, ?, ?, 1)", (buyer_id, seller_id, aid))
        conn.commit()

    update_state(buyer_id, active_chat_with=seller_id, active_chat_aid=aid)
    update_state(seller_id, active_chat_with=buyer_id, active_chat_aid=aid)

    try:
        bot.answer_callback_query(call.id, "✅ Защищенный чат открыт!")
    except Exception:
        pass

    safe_send_message(buyer_id, "💬 <b>Диалог с автором объявления открыт.</b> Все ваши сообщения будут передаваться продавцу. Отправьте сообщение ниже:", reply_markup=ikb_chat_controls(aid))
    safe_send_message(seller_id, f"💬 <b>Новый покупатель написал вам по объявлению (ID: {aid})!</b> Можете отвечать прямо в этот чат:", reply_markup=ikb_chat_controls(aid))

@bot.callback_query_handler(func=lambda c: c.data.startswith("stop_chat_") or c.data.startswith("resume_chat_"))
def cb_chat_control(call):
    is_stop = "stop_chat_" in call.data
    aid = int(call.data.split("_")[2])
    uid = call.from_user.id

    if is_stop:
        clear_state(uid)
        try:
            bot.answer_callback_query(call.id, "🛑 Диалог завершен.")
        except Exception:
            pass
        safe_send_message(call.message.chat.id, "🛑 Диалог с продавцом/покупателем завершен.", reply_markup=kb_main_menu(uid))
    else:
        try:
            bot.answer_callback_query(call.id, "🔄 Диалог возобновлен.")
        except Exception:
            pass
        safe_send_message(call.message.chat.id, "🔄 Диалог активен. Можете продолжать общение.", reply_markup=kb_cancel(uid))

@bot.message_handler(func=lambda m: get_state(m.from_user.id).get("active_chat_with"))
def process_active_chat_message(m):
    uid = m.from_user.id
    st = get_state(uid)
    target_id = st.get("active_chat_with")
    text = m.text

    if text == "❌ Отменить действие" or text in [t.get("btn_cancel") for t in TRANSLATIONS.values()]:
        clear_state(uid)
        return safe_send_message(m.chat.id, "❌ Диалог завершен.", reply_markup=kb_main_menu(uid))

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO chat_logs_history (sender_id, receiver_id, text, timestamp) VALUES (?, ?, ?, ?)", 
                    (uid, target_id, text, time.time()))
        conn.commit()

    try:
        safe_send_message(target_id, f"✉️ <b>Сообщение от собеседника:</b>\n{html.escape(text)}")
        safe_send_message(uid, "✅ Сообщение доставлено.")
    except Exception:
        safe_send_message(uid, "⚠️ Не удалось доставить сообщение. Возможно, пользователь заблокировал бота.")

# ==========================================
# АДМИН-ПАНЕЛЬ И ЛОГИ
# ==========================================
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

@bot.callback_query_handler(func=lambda c: c.data == "admin_manage_active_ads")
def cb_admin_manage_active_ads(call):
    if not verify_admin_callback(call):
        return
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, server, category, text FROM active_ads ORDER BY id DESC LIMIT 15")
        active_sales = cur.fetchall()
        cur.execute("SELECT id, server, category, text FROM active_buy_ads ORDER BY id DESC LIMIT 15")
        active_buys = cur.fetchall()

    if not active_sales and not active_buys:
        return safe_send_message(call.message.chat.id, "📭 Активных объявлений в базе нет.")

    markup = types.InlineKeyboardMarkup(row_width=1)
    for aid, srv, cat, text in active_sales:
        markup.add(types.InlineKeyboardButton(f"🗑 [Продажа | {srv}] ID {aid}: {text[:22]}...", callback_data=f"admin_del_{aid}"))
    for aid, srv, cat, text in active_buys:
        markup.add(types.InlineKeyboardButton(f"🗑 [Скупка | {srv}] ID {aid}: {text[:22]}...", callback_data=f"admin_del_buy_{aid}"))

    safe_send_message(call.message.chat.id, "📋 <b>Управление активными объявлениями:</b>\nНажмите на объявление, чтобы удалить/отменить его:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "owner_export_logs")
def cb_owner_export_logs(call):
    if not is_owner(call.from_user):
        return bot.answer_callback_query(call.id, "⛔ Функция доступна только владельцу @bounqy!", show_alert=True)
    
    try:
        bot.answer_callback_query(call.id, "📦 Формирование файла логов...")
    except Exception:
        pass

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT sender_id, receiver_id, text, timestamp FROM chat_logs_history ORDER BY id DESC LIMIT 1000")
        logs = cur.fetchall()

    log_content = "=== ЛОГИ ЧАТОВ БОТА СМИ ===\n\n"
    for sender, receiver, text, ts in logs:
        dt_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        log_content += f"[{dt_str}] От: {sender} | Кому: {receiver}\nТекст: {text}\n{'-'*40}\n"

    file_path = "chat_logs.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(log_content)

    with open(file_path, "rb") as f:
        bot.send_document(call.message.chat.id, f, caption="📂 <b>Актуальные логи чатов системы.</b>")
    
    if os.path.exists(file_path):
        os.remove(file_path)

@bot.callback_query_handler(func=lambda c: c.data == "owner_manage_admins")
def cb_owner_manage_admins(call):
    if not is_owner(call.from_user):
        return bot.answer_callback_query(call.id, "⛔ Доступно только владельцу @bounqy!", show_alert=True)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Назначить админа", callback_data="owner_add_admin_prompt"),
        types.InlineKeyboardButton("➖ Снять с админки", callback_data="owner_remove_admin_prompt")
    )
    safe_send_message(call.message.chat.id, "👑 <b>Управление администраторским составом:</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["owner_add_admin_prompt", "owner_remove_admin_prompt"])
def cb_admin_action_prompt(call):
    if not is_owner(call.from_user):
        return
    action_type = "add_admin" if "add" in call.data else "remove_admin"
    update_state(call.from_user.id, owner_action=action_type)
    safe_send_message(call.message.chat.id, "✍️ Отправьте <b>User ID</b> или <b>Username</b> пользователя:", reply_markup=kb_cancel(call.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data == "owner_manage_bans")
def cb_owner_manage_bans(call):
    if not is_owner(call.from_user):
        return bot.answer_callback_query(call.id, "⛔ Доступно только владельцу @bounqy!", show_alert=True)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("⛔ Забанить", callback_data="owner_ban_prompt"),
        types.InlineKeyboardButton("🟢 Разбанить", callback_data="owner_unban_prompt")
    )
    safe_send_message(call.message.chat.id, "⛔ <b>Управление черным списком (баны):</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["owner_ban_prompt", "owner_unban_prompt"])
def cb_ban_action_prompt(call):
    if not is_owner(call.from_user):
        return
    action_type = "ban_user" if "ban" in call.data and "un" not in call.data else "unban_user"
    update_state(call.from_user.id, owner_action=action_type)
    safe_send_message(call.message.chat.id, "✍️ Отправьте <b>User ID</b> или <b>Username</b> целевого пользователя:", reply_markup=kb_cancel(call.from_user.id))

@bot.message_handler(func=lambda m: "owner_action" in get_state(m.from_user.id))
def process_owner_actions(m):
    if not is_owner(m.from_user):
        clear_state(m.from_user.id)
        return
    
    uid = m.from_user.id
    st = get_state(uid)
    action = st.get("owner_action")
    target_input = m.text.strip().lstrip('@').lower()
    clear_state(uid)

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        if action == "add_admin":
            target_id = int(target_input) if target_input.isdigit() else 0
            cur.execute("SELECT user_id, username FROM user_data WHERE user_id = ? OR LOWER(username) = ?", (target_id, target_input))
            row = cur.fetchone()
            if row:
                cur.execute("INSERT OR IGNORE INTO approved_admins (user_id, username) VALUES (?, ?)", (row[0], row[1]))
                conn.commit()
                safe_send_message(m.chat.id, f"✅ Пользователь @{row[1]} (ID: {row[0]}) назначен администратором!", reply_markup=kb_main_menu(m.from_user.id))
                safe_send_message(row[0], "🎉 Поздравляем! Владелец @bounqy назначил вас администратором бота.")
            else:
                safe_send_message(m.chat.id, "⚠️ Пользователь не найден в базе данных бота.", reply_markup=kb_main_menu(m.from_user.id))

        elif action == "remove_admin":
            cur.execute("DELETE FROM approved_admins WHERE user_id = ? OR LOWER(username) = ?", (target_input, target_input))
            conn.commit()
            safe_send_message(m.chat.id, f"✅ Пользователь {target_input} снят с поста администратора.", reply_markup=kb_main_menu(m.from_user.id))

        elif action == "ban_user":
            is_id = 1 if target_input.isdigit() else 0
            cur.execute("INSERT OR REPLACE INTO bans (target, is_id) VALUES (?, ?)", (target_input, is_id))
            conn.commit()
            safe_send_message(m.chat.id, f"⛔ Пользователь {target_input} успешно заблокирован в боте.", reply_markup=kb_main_menu(m.from_user.id))

        elif action == "unban_user":
            cur.execute("DELETE FROM bans WHERE target = ?", (target_input,))
            conn.commit()
            safe_send_message(m.chat.id, f"🟢 Пользователь {target_input} разблокирован.", reply_markup=kb_main_menu(m.from_user.id))

# ==========================================
# ПОДАЧА ЗАЯВКИ НА ПОСТ РЕДАКТОРА
# ==========================================
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
    safe_send_message(
        m.chat.id,
        "📝 <b>Электронное заявление на пост редактора СМИ (Arizona RP Style)</b>\n\n"
        "Пожалуйста, заполните заявку в свободной форме. Укажите:\n"
        "• Ваш игровой ник и сервер\n"
        "• Ваш возраст и часовой пояс\n"
        "• Опыт работы в СМИ / почему хотите занять этот пост\n\n"
        "<i>Отправьте ваш текст ответным сообщением в чат:</i>",
        reply_markup=kb_cancel(uid)
    )

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

    safe_send_message(m.chat.id, "✅ Ваша заявка на пост редактора успешно отправлена владельцу @bounqy и редакции! Ожидайте рассмотрения.", reply_markup=kb_main_menu(uid))

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

@bot.callback_query_handler(func=lambda c: c.data.startswith("accept_admin_app_") or c.data.startswith("reject_admin_app_"))
def cb_handle_admin_app(call):
    if not is_owner(call.from_user) and not is_admin_or_owner(call.from_user):
        try:
            bot.answer_callback_query(call.id, "⛔ У вас нет прав для рассмотрения заявок!", show_alert=True)
        except Exception:
            pass
        return

    is_accept = "accept_admin_app_" in call.data
    prefix = "accept_admin_app_" if is_accept else "reject_admin_app_"
    target_uid = int(call.data.replace(prefix, ""))

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT username FROM admin_apps WHERE user_id = ?", (target_uid,))
        row = cur.fetchone()
        target_uname = row[0] if row else "user"
        cur.execute("DELETE FROM admin_apps WHERE user_id = ?", (target_uid,))
        
        if is_accept:
            cur.execute("INSERT OR IGNORE INTO approved_admins (user_id, username) VALUES (?, ?)", (target_uid, target_uname))
        conn.commit()

    try:
        bot.answer_callback_query(call.id, "✅ Заявка принята!" if is_accept else "❌ Заявка отклонена!")
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
    except Exception:
        pass

    if is_accept:
        safe_send_message(target_uid, "🎉 <b>Поздравляем! Ваша заявка на пост редактора одобрена владелицем @bounqy!</b> Теперь вам доступны функции модерации и админ-панель.", reply_markup=kb_main_menu(target_uid))
        try:
            safe_send_message(call.message.chat.id, f"✅ Кандидат @{html.escape(target_uname)} успешно назначен редактором/администратором.")
        except Exception:
            pass
    else:
        safe_send_message(target_uid, "❌ К сожалению, ваша заявка на пост редактора была отклонена руководящим составом.")
        try:
            safe_send_message(call.message.chat.id, f"❌ Заявка кандидата @{html.escape(target_uname)} отклонена.")
        except Exception:
            pass

def info_premium(m):
    is_prem = is_user_premium(m.from_user.id)
    status_text = "✅ <b>Ваш VIP-статус активен!</b>" if is_prem else "❌ <b>У вас нет активного VIP-статуса.</b>"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Купить VIP (50 Звезд / 30 дней)", pay=True, callback_data="buy_vip_stars"))

    text = (
        f"💎 <b>Премиум-статус (VIP) в боте</b>\n\n"
        f"{status_text}\n\n"
        "Преимущества VIP статуса:\n"
        "• Значок премиум-аккаунта в ваших объявлениях\n"
        "• Приоритетное размещение товаров\n\n"
        "Стоимость: <b>50 Telegram Stars</b> на 30 дней."
    )
    safe_send_message(m.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "buy_vip_stars")
def send_invoice_vip(call):
    prices = [types.LabeledPrice(label="VIP Статус на 30 дней", amount=50)]
    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title="Премиум-статус VIP",
            description="Покупка VIP статуса в боте СМИ на 30 дней",
            invoice_payload="vip_subscription_30_days",
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="buy_vip"
        )
    except Exception as e:
        try:
            bot.answer_callback_query(call.id, f"Ошибка создания счета: {e}", show_alert=True)
        except Exception:
            pass

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    try:
        bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    except Exception:
        pass

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    payload = message.successful_payment.invoice_payload
    uid = message.from_user.id
    if payload == "vip_subscription_30_days":
        expires = time.time() + 30 * 86400
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO premium_users (user_id, expires_at) VALUES (?, ?)", (uid, expires))
            conn.commit()
        safe_send_message(message.chat.id, "🎉 Поздравляем! Вы успешно приобрели VIP-статус на 30 дней!", reply_markup=kb_main_menu(uid))
    elif payload == "vip_single_ad_pub" or payload == "vip_single_buy_pub":
        st = get_state(uid)
        p_data = st.get("posting_ad") or st.get("posting_buy_ad")
        if p_data:
            p_data["is_vip"] = 1
            is_buy_flag = "posting_buy_ad" in st
            finish_posting(message.chat.id, uid, message.from_user.username, p_data.get("photo_id"), is_buy=is_buy_flag)
        else:
            safe_send_message(message.chat.id, "✅ Оплата прошла, но данные сессии сбросились. Начните заново.", reply_markup=kb_main_menu(uid))

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

# ==========================================
# КАЛЬКУЛЯТОР И КУРС VICE CITY (VC)
# ==========================================
def show_vc_menu(m):
    rate = get_vc_rate()
    uid = m.from_user.id
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💱 Конвертер валют (Вирты ⇄ VC)", callback_data="vc_conv_start"),
        types.InlineKeyboardButton("📈 Калькулятор выгоды перекупа", callback_data="vc_calc_start"),
    )
    if is_admin_or_owner(m.from_user):
        markup.add(types.InlineKeyboardButton("⚙️ Изменить курс VC (Админ)", callback_data="vc_set_rate_start"))

    text = (
        f"💱 <b>Финансовый центр Vice City & Экономика Arizona</b>\n\n"
        f"📊 Текущий установленный курс:\n"
        f"• <b>1 VC Dollar = {format_price(rate)} вирт</b>\n\n"
        f"Выберите необходимый инструмент ниже:"
    )
    safe_send_message(m.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "vc_conv_start")
def cb_vc_conv_start(call):
    uid = call.from_user.id
    update_state(uid, vc_conv_input=True)
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    safe_send_message(
        call.message.chat.id, 
        "💱 <b>Конвертер валют VC:</b>\n\n"
        "Отправьте сумму для перевода.\n"
        "• Чтобы перевести <i>вирты в VC</i>, просто отправьте число вирт (например: <code>15000000</code> или <code>50кк</code>).\n"
        "• Чтобы перевести <i>VC в вирты</i>, добавьте суффикс vc (например: <code>450vc</code>).",
        reply_markup=kb_cancel(uid)
    )

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("vc_conv_input"))
def process_vc_conversion(m):
    uid = m.from_user.id
    clear_state(uid)
    text = m.text.strip().lower()
    rate = get_vc_rate()

    try:
        if "vc" in text:
            val_str = re.sub(r'[^0-9.]', '', text)
            vc_val = float(val_str)
            reg_val = vc_val * rate
            result_text = (
                f"💱 <b>Результат конвертации:</b>\n\n"
                f"💎 <b>{vc_val:,.1f} VC</b> = 💵 <b>{format_price(reg_val)} вирт</b>\n"
                f"<i>(Курс: 1 VC = {format_price(rate)} вирт)</i>"
            )
        else:
            multiplier = 1
            clean_text = text.replace(',', '.')
            if "ккк" in clean_text or "млрд" in clean_text:
                multiplier = 1_000_000_000
                clean_text = re.sub(r'[^0-9.]', '', clean_text)
            elif "кк" in clean_text or "млн" in clean_text:
                multiplier = 1_000_000
                clean_text = re.sub(r'[^0-9.]', '', clean_text)
            elif "к" in clean_text or "тыс" in clean_text:
                multiplier = 1_000
                clean_text = re.sub(r'[^0-9.]', '', clean_text)
            else:
                clean_text = re.sub(r'[^0-9.]', '', clean_text)

            val = float(clean_text) * multiplier
            vc_res = val / rate
            result_text = (
                f"💱 <b>Результат конвертации:</b>\n\n"
                f"💵 <b>{format_price(val)} вирт</b> = 💎 <b>{vc_res:,.2f} VC</b>\n"
                f"<i>(Курс: 1 VC = {format_price(rate)} вирт)</i>"
            )
        safe_send_message(m.chat.id, result_text, reply_markup=kb_main_menu(uid))
    except Exception:
        safe_send_message(m.chat.id, "⚠️ Неверный формат числа. Попробуйте снова через меню конвертера.", reply_markup=kb_main_menu(uid))

@bot.callback_query_handler(func=lambda c: c.data == "vc_calc_start")
def cb_vc_calc_start(call):
    uid = call.from_user.id
    update_state(uid, vc_calc_step="server_price")
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    safe_send_message(
        call.message.chat.id,
        "📈 <b>Калькулятор выгоды перекупщика (Перелет на Vice City)</b>\n\n"
        "Шаг 1 из 2: Введите цену товара на <b>вашем сервере</b> (в виртах, например: <code>45000000</code> или <code>45кк</code>):",
        reply_markup=kb_cancel(uid)
    )

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("vc_calc_step") == "server_price")
def process_calc_server_price(m):
    uid = m.from_user.id
    text = m.text.strip().lower()
    try:
        multiplier = 1
        clean_text = text.replace(',', '.')
        if "ккк" in clean_text or "млрд" in clean_text:
            multiplier = 1_000_000_000
            clean_text = re.sub(r'[^0-9.]', '', clean_text)
        elif "кк" in clean_text or "млн" in clean_text:
            multiplier = 1_000_000
            clean_text = re.sub(r'[^0-9.]', '', clean_text)
        elif "к" in clean_text or "тыс" in clean_text:
            multiplier = 1_000
            clean_text = re.sub(r'[^0-9.]', '', clean_text)
        else:
            clean_text = re.sub(r'[^0-9.]', '', clean_text)

        server_price = float(clean_text) * multiplier
        update_state(uid, vc_calc_server_price=server_price, vc_calc_step="vc_price")

        safe_send_message(
            m.chat.id,
            "📈 Шаг 2 из 2: Введите цену продажи этого же товара на <b>Vice City</b> (в VC долл., например: <code>550</code>):",
            reply_markup=kb_cancel(uid)
        )
    except Exception:
        safe_send_message(m.chat.id, "⚠️ Ошибка ввода суммы. Введите число (например, 50кк или 50000000):", reply_markup=kb_cancel(uid))

@bot.message_handler(func=lambda msg: get_state(msg.from_user.id).get("vc_calc_step") == "vc_price")
def process_calc_vc_price(m):
    uid = m.from_user.id
    st = get_state(uid)
    server_price = st.get("vc_calc_server_price", 0)
    clear_state(uid)

    try:
        vc_price = float(re.sub(r'[^0-9.]', '', m.text.replace(',', '.')))
        rate = get_vc_rate()

        vc_price_in_reg = vc_price * rate
        profit_reg = vc_price_in_reg - server_price
        
        flight_cost = 500_000
        net_profit = profit_reg - flight_cost

        status_emoji = "🟢 <b>ВЫГОДНО!</b>" if net_profit > 0 else "🔴 <b>НЕ ВЫГОДНО (В МИНУСЕ)</b>"

        report = (
            f"📊 <b>Анализ выгоды перелета на Vice City:</b>\n\n"
            f"• Цена на вашем сервере: <b>{format_price(server_price)}</b>\n"
            f"• Цена на Vice City: <b>{vc_price:,.1f} VC</b> ({format_price(vc_price_in_reg)})\n"
            f"• Расходы на перелет/комиссию: ~{format_price(flight_cost)}\n\n"
            f"💰 Чистая прибыль: <b>{format_price(net_profit)}</b>\n"
            f"{status_emoji}"
        )
        safe_send_message(m.chat.id, report, reply_markup=kb_main_menu(uid))
    except Exception:
        safe_send_message(m.chat.id, "⚠️ Ошибка ввода цены на VC. Попробуйте заново через меню калькулятора.", reply_markup=kb_main_menu(uid))

@bot.callback_query_handler(func=lambda c: c.data == "vc_set_rate_start")
def cb_vc_set_rate_start(call):
    if not verify_admin_callback(call):
        return
    uid = call.from_user.id
    update_state(uid, vc_setting_rate=True)
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    safe_send_message(call.message.chat.id, "⚙️ Введите новый актуальный курс 1 VC в виртах (например: <code>95000</code>):", reply_markup=kb_cancel(uid))

@bot.message_handler(func=lambda msg: "vc_setting_rate" in get_state(msg.from_user.id))
def process_set_vc_rate(m):
    if not is_admin_or_owner(m.from_user):
        clear_state(m.from_user.id)
        return
    uid = m.from_user.id
    clear_state(uid)

    try:
        new_rate = float(re.sub(r'[^0-9.]', '', m.text.replace(',', '.')))
        if new_rate <= 0:
            raise ValueError()
        set_vc_rate(new_rate)
        safe_send_message(m.chat.id, f"✅ Курс успешно обновлен! Теперь 1 VC = <b>{format_price(new_rate)} вирт</b>.", reply_markup=kb_main_menu(uid))
    except Exception:
        safe_send_message(m.chat.id, "⚠️ Ошибка. Введите положительное число (например, 95000).", reply_markup=kb_main_menu(uid))

# ==========================================
# ПОДАЧА И МОДЕРАЦИЯ ОБЪЯВЛЕНИЙ
# ==========================================
def start_add_ad(m):
    _start_posting_flow(m, is_buy=False)

def start_add_buy_ad(m):
    _start_posting_flow(m, is_buy=True)

def _start_posting_flow(m, is_buy: bool):
    register_user(m.from_user.id, m.from_user.username)
    if is_banned(m.from_user):
        return safe_send_message(m.chat.id, "⛔ Вы заблокированы.", reply_markup=types.ReplyKeyboardRemove())
    
    if not check_working_hours():
        return safe_send_message(m.chat.id, "⏱ Радиоцентр закрыт! Режим работы: с 08:00:01 до 22:00:01 МСК.")

    uid = m.from_user.id
    last_t = get_user_last_ad_time(uid)
    
    if not is_admin_or_owner(m.from_user) and not is_user_premium(uid):
        if time.time() - last_t < 120:
            left = int(120 - (time.time() - last_t))
            return safe_send_message(m.chat.id, f"⏳ КД 2 минуты! Подождите еще {left} сек. перед подачей нового объявления.")

    srv = get_state(uid).get("server", "Phoenix")
    state_key = "posting_buy_ad" if is_buy else "posting_ad"
    update_state(uid, **{state_key: {"step": "category", "server": srv, "is_buy": is_buy}})
    
    m_kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m_kb.add(types.KeyboardButton(get_text(uid, "cat_accessories")), types.KeyboardButton(get_text(uid, "cat_transport")))
    m_kb.add(types.KeyboardButton(get_text(uid, "cat_skins")), types.KeyboardButton(get_text(uid, "cat_realestate")))
    m_kb.add(types.KeyboardButton(get_text(uid, "cat_resources")))
    m_kb.add(types.KeyboardButton(get_text(uid, "btn_cancel")))
    
    ad_type_str = "скупку" if is_buy else "продажу"
    safe_send_message(m.chat.id, f"📂 Выберите категорию товара для объявления на <b>{ad_type_str}</b> (сервер: <b>{html.escape(srv)}</b>):", reply_markup=m_kb)

def cancel_action(m):
    uid = m.from_user.id
    st = get_state(uid)
    
    pid = st.get("admin_editing_pid") or st.get("admin_editing_buy_pid")
    if pid:
        table_name = "pending_buy_posts" if "admin_editing_buy_pid" in st else "pending_posts"
        with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute(f"UPDATE {table_name} SET editing_by = 0, editing_since = 0 WHERE id = ?", (pid,))
            conn.commit()

    clear_state(uid)
    safe_send_message(m.chat.id, "❌ Действие отменено.", reply_markup=kb_main_menu(uid))

@bot.message_handler(func=lambda msg: "posting_ad" in get_state(msg.from_user.id) or "posting_buy_ad" in get_state(msg.from_user.id), content_types=['text', 'photo'])
def process_posting_flow(m):
    uid = m.from_user.id
    st = get_state(uid)
    is_buy = "posting_buy_ad" in st
    p_key = "posting_buy_ad" if is_buy else "posting_ad"
    p_data = st.get(p_key, {})
    step = p_data.get("step")

    if step == "category":
        if m.content_type != 'text':
            return safe_send_message(m.chat.id, "⚠️ Пожалуйста, выберите категорию с помощью кнопок ниже.")
        
        cat_text = m.text
        lang = get_user_lang(uid)
        tr = TRANSLATIONS.get(lang, TRANSLATIONS["ru"])
        all_cats_map = {
            tr.get("cat_accessories"): CATEGORIES[0],
            tr.get("cat_transport"): CATEGORIES[1],
            tr.get("cat_skins"): CATEGORIES[2],
            tr.get("cat_realestate"): CATEGORIES[3],
            tr.get("cat_resources"): CATEGORIES[4],
        }
        
        cat = all_cats_map.get(cat_text, cat_text)
        if cat not in CATEGORIES:
            return safe_send_message(m.chat.id, "⚠️ Выберите категорию из предложенных вариантов.")
            
        p_data["category"] = cat
        p_data["step"] = "text"
        update_state(uid, **{p_key: p_data})
        
        prompt_text = "✍️ Введите текст объявления о скупке (что скупаете, бюджет и условия) <b>или сразу отправьте фотографию с описанием</b>:" if is_buy else "✍️ Введите текст объявления о продаже (описание товара, цену и условия) <b>или сразу отправьте фотографию с описанием</b>:"
        return safe_send_message(m.chat.id, prompt_text, reply_markup=kb_cancel(uid))

    elif step == "text":
        text = ""
        photo_id = None

        if m.content_type == 'photo':
            photo_id = m.photo[-1].file_id
            text = m.caption if m.caption else "Товар по фотографии"
        elif m.content_type == 'text':
            text = m.text
        else:
            return safe_send_message(m.chat.id, "⚠️ Пожалуйста, отправьте текст объявления или фото с описанием.")

        if not check_auto_moderation(text):
            return safe_send_message(m.chat.id, "⚠️ Текст содержит запрещенные слова или ссылки. Пожалуйста, исправьте его.")
        
        p_data["text"] = text
        p_data["photo_id"] = photo_id
        update_state(uid, **{p_key: p_data})
        
        ask_vip_choice_generic(m, photo_id)

def ask_vip_choice_generic(m, photo_id):
    uid = m.from_user.id
    st = get_state(uid)
    is_buy = "posting_buy_ad" in st
    p_key = "posting_buy_ad" if is_buy else "posting_ad"
    p_data = st.get(p_key, {})
    p_data["photo_id"] = photo_id
    update_state(uid, **{p_key: p_data})

    markup = types.InlineKeyboardMarkup(row_width=1)
    callback_suffix = "_buy" if is_buy else ""
    if is_user_premium(uid):
        markup.add(types.InlineKeyboardButton(f"👑 Опубликовать как VIP (Бесплатно)", callback_data=f"post_as_vip_free{callback_suffix}"))
    else:
        markup.add(types.InlineKeyboardButton(f"💎 Подать как VIP-объявление (1 Звезда)", pay=True, callback_data=f"buy_single_vip_star{callback_suffix}"))
    markup.add(types.InlineKeyboardButton(f"📄 Опубликовать как обычное (бесплатно)", callback_data=f"post_as_regular{callback_suffix}"))

    safe_send_message(m.chat.id, "💎 <b>Выберите формат публикации вашего объявления:</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["post_as_vip_free", "post_as_regular", "post_as_vip_free_buy", "post_as_regular_buy"])
def callback_publish_choice(call):
    uid = call.from_user.id
    st = get_state(uid)
    is_buy = "_buy" in call.data
    p_key = "posting_buy_ad" if is_buy else "posting_ad"
    p_data = st.get(p_key)
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if not p_data:
        return safe_send_message(call.message.chat.id, "⚠️ Данные объявления устарели. Начните подачу заново.", reply_markup=kb_main_menu(uid))

    is_vip = 1 if "vip_free" in call.data else 0
    p_data["is_vip"] = is_vip
    finish_posting(call.message.chat.id, uid, call.from_user.username, p_data.get("photo_id"), is_buy=is_buy)

@bot.callback_query_handler(func=lambda c: c.data in ["buy_single_vip_star", "buy_single_vip_star_buy"])
def callback_buy_single_vip(call):
    is_buy = "_buy" in call.data
    payload = "vip_single_buy_pub" if is_buy else "vip_single_ad_pub"
    prices = [types.LabeledPrice(label="VIP Объявление (разовое)", amount=1)]
    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title="Разовое VIP-объявление",
            description="Публикация объявления с VIP-статусом за 1 Telegram Star",
            invoice_payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="buy_single_vip"
        )
    except Exception as e:
        try:
            bot.answer_callback_query(call.id, f"Ошибка создания счета: {e}", show_alert=True)
        except Exception:
            pass

def finish_posting(chat_id: int, user_id: int, username: str, photo_id: str, is_buy: bool):
    st = get_state(user_id)
    p_key = "posting_buy_ad" if is_buy else "posting_ad"
    p_data = st.get(p_key)
    if not p_data:
        return

    srv = p_data["server"]
    cat = p_data["category"]
    text = p_data["text"]
    is_vip = p_data.get("is_vip", 0)
    uname = username if username else "Без юзернейма"

    table_name = "pending_buy_posts" if is_buy else "pending_posts"

    with db_lock, sqlite3.connect(DB_NAME, timeout=10.0) as conn:
        cur = conn.cursor()
        cur.execute(f'''
            INSERT INTO {table_name} (user_id, username, server, category, text, photo, is_vip, editing_by, editing_since, is_edited)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
        ''', (user_id, uname, srv, cat, text, photo_id, is_vip))
        pid = cur.lastrowid
        conn.commit()

    clear_state(user_id)
    set_user_last_ad_time(user_id, time.time())

    type_title = "скупку" if is_buy else "продажу"
    safe_send_message(chat_id, f"✅ Объявление на <b>{type_title}</b> отправлено на модерацию редакторам!", reply_markup=kb_main_menu(user_id))

    action_prefix = "mod_buy_" if is_buy else "mod_"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Одобрить", callback_data=f"{action_prefix}accept_{pid}"),
        types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"{action_prefix}edit_{pid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"{action_prefix}reject_{pid}")
    )

    preview = format_smi_post(srv, cat, text, uname, uname if uname != "Без юзернейма" else "", is_vip, user_id, is_buy=is_buy)
    
    admin_recipients = get_all_admin_ids()
    for admin_chat_id in admin_recipients:
        try:
            if photo_id:
                safe_send_photo(admin_chat_id, photo_id, caption=(f"📥 <b>Новая заявка на скупку (ID: {pid}):</b>\n\n{preview}" if is_buy else f"📥 <b>Новая заявка на продажу (ID: {pid}):</b>\n\n{preview}"), reply_markup=markup)
            else:
                safe_send_message(admin_chat_id, (f"📥 <b>Новая заявка на скупку (ID: {pid}):</b>\n\n{preview}" if is_buy else f"📥 <b>Новая заявка на продажу (ID: {pid}):</b>\n\n{preview}"), reply_markup=markup)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin_chat_id}: {e}")

# ==========================================
# ОБРАБОТЧИКИ МОДЕРАЦИИ И ЗАПУСК
# ==========================================
# (Остальной функционал модерации и запуск бота сохраняется без изменений)

if __name__ == "__main__":
    logger.info("Бот СМИ запущен и работает...")
    bot.infinity_polling(skip_pending=True)

