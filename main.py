import os
import re
import aiohttp
import traceback
import random
import time
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, HTMLResponse
import uvicorn

load_dotenv()

app = FastAPI()

VERIFY_TOKEN = os.getenv("WHATSAPP_WEBHOOK_VERIFICATION_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_SHEET_WEBHOOK = os.getenv("GOOGLE_SHEET_WEBHOOK", "")
MANAGER_NUMBER = "923351021321"

MIN_DELIVERY_ORDER = 30.00
MIN_PICKUP_ORDER = 10.00
DELIVERY_CHARGE = 4.99

print(f"Token: {WHATSAPP_TOKEN[:20] if WHATSAPP_TOKEN else 'MISSING'}...")
print(f"Phone ID: {WHATSAPP_PHONE_NUMBER_ID}")

LANG_NAMES = {
    "en": "English", "ar": "Arabic", "hi": "Hindi",
    "fr": "French", "de": "German", "ru": "Russian",
    "zh": "Chinese", "ml": "Malayalam",
}

STRINGS = {
    "en": {
        "menu_header": "🍽️ Wild Bites Restaurant",
        "craving": "What are you craving today? 😋\n\nTap a category below 👇",
        "browse": "📋 Browse Menu",
        "tap_add": "Tap any item to add to your cart! 👇",
        "ready": "Ready to place your order? 🚀",
        "checkout": "✅ Checkout",
        "view_cart": "🛒 View Cart",
        "add_more": "🍽️ Add More",
        "remove_one": "➖ Remove One",
        "add_one": "➕ Add One More",
        "order_summary": "📋 Order Summary",
        "confirm": "✅ Confirm Order",
        "cancel": "❌ Cancel",
        "delivery": "🚚 Home Delivery",
        "pickup": "🏪 Store Pickup",
        "cash": "💵 Cash",
        "card": "💳 Card",
        "apple_pay": "📱 Apple/Google Pay",
        "your_order": "📋 *Your Order:*",
        "total": "💰 *Total:",
        "subtotal": "💰 Subtotal:",
        "tax": "📊 Tax (8%):",
        "delivery_charge": "🚚 Delivery:",
        "grand_total": "💵 *Grand Total:",
        "added": "✅ Added to Cart!",
        "name_ask": "👤 *What's your name?* (First name is perfect 😊)",
        "address_ask": "What's your delivery address?\nExample: 123 Main St, New York, NY 10001",
        "address_saved": "✅ Got it! Now choose a payment method 👇",
        "order_confirmed": "🎉 *Order Confirmed",
        "ready_in": "⏱️ Ready in:",
        "thank_you": "Thank you for choosing Wild Bites! 🍔\nType *Hi* to order again!",
        "cart_empty": "🛒 Your cart is empty!\n\nType *menu* to browse options 😊",
        "min_delivery": "⚠️ Minimum order for delivery is *$30*.\n\nAdd more items or choose *Store Pickup* (min $10).",
        "min_pickup": "⚠️ Minimum order for pickup is *$10*.\n\nPlease add more items.",
        "delivery_info": "🚚 *Home Delivery* — 30-45 mins\n   Min order: $30 | Delivery fee: $4.99\n   Free delivery on orders over $50!\n\n🏪 *Store Pickup* — 15-20 mins\n   Min order: $10",
        "delayed": "Hey! Still there? 😊 I'm here to help — just tap a button or type anything!",
        "save_room": "🍰 Save room for dessert?",
        "yes_dessert": "🍰 Yes, show desserts",
        "no_dessert": "✅ No, continue",
        "yes_combo": "✅ Yes! Add Combo",
        "no_combo": "❌ No Thanks",
        "cancelled": "❌ Order cancelled.\n\nType *menu* to start again.",
    },
    "ar": {
        "menu_header": "🍽️ مطعم وايلد بايتس",
        "craving": "ماذا تريد اليوم؟ 😋\n\nاضغط على فئة أدناه 👇",
        "browse": "📋 تصفح القائمة",
        "tap_add": "اضغط على أي عنصر لإضافته! 👇",
        "ready": "هل أنت مستعد لتقديم طلبك؟ 🚀",
        "checkout": "✅ الدفع",
        "view_cart": "🛒 عرض السلة",
        "add_more": "🍽️ إضافة المزيد",
        "remove_one": "➖ إزالة واحدة",
        "add_one": "➕ إضافة أخرى",
        "order_summary": "📋 ملخص الطلب",
        "confirm": "✅ تأكيد الطلب",
        "cancel": "❌ إلغاء",
        "delivery": "🚚 توصيل للمنزل",
        "pickup": "🏪 استلام من المحل",
        "cash": "💵 نقداً",
        "card": "💳 بطاقة",
        "apple_pay": "📱 Apple/Google Pay",
        "your_order": "📋 *طلبك:*",
        "total": "💰 *المجموع:",
        "subtotal": "💰 المجموع الفرعي:",
        "tax": "📊 الضريبة (8%):",
        "delivery_charge": "🚚 رسوم التوصيل:",
        "grand_total": "💵 *المجموع الكلي:",
        "added": "✅ تمت الإضافة للسلة!",
        "name_ask": "👤 *ما اسمك؟*",
        "address_ask": "📍 ما هو عنوان التوصيل؟",
        "address_saved": "✅ تم حفظ العنوان! اختر طريقة الدفع 👇",
        "order_confirmed": "🎉 *تم تأكيد الطلب",
        "ready_in": "⏱️ جاهز في:",
        "thank_you": "شكراً لاختيارك Wild Bites! 🍔",
        "cart_empty": "🛒 سلتك فارغة!\n\nاكتب *menu* للتصفح",
        "min_delivery": "⚠️ الحد الأدنى للتوصيل *30$*",
        "min_pickup": "⚠️ الحد الأدنى للاستلام *10$*",
        "delivery_info": "🚚 *توصيل* — 30-45 دقيقة | حد أدنى $30 | رسوم $4.99\n\n🏪 *استلام* — 15-20 دقيقة | حد أدنى $10",
        "delayed": "مرحباً! هل ما زلت هنا؟ 😊",
        "save_room": "🍰 هل تريد حلوى؟",
        "yes_dessert": "🍰 نعم",
        "no_dessert": "✅ لا، متابعة",
        "yes_combo": "✅ نعم! أضف الكومبو",
        "no_combo": "❌ لا شكراً",
        "cancelled": "❌ تم إلغاء الطلب.\n\nاكتب *menu* للبدء.",
    },
    "hi": {
        "menu_header": "🍽️ वाइल्ड बाइट्स",
        "craving": "आज क्या खाना है? 😋\n\nनीचे एक कैटेगरी चुनें 👇",
        "browse": "📋 मेन्यू देखें",
        "tap_add": "कोई भी आइटम टैप करें! 👇",
        "ready": "ऑर्डर देने के लिए तैयार? 🚀",
        "checkout": "✅ चेकआउट",
        "view_cart": "🛒 कार्ट देखें",
        "add_more": "🍽️ और जोड़ें",
        "remove_one": "➖ एक हटाएं",
        "add_one": "➕ एक और जोड़ें",
        "order_summary": "📋 ऑर्डर सारांश",
        "confirm": "✅ कन्फर्म करें",
        "cancel": "❌ रद्द करें",
        "delivery": "🚚 होम डिलीवरी",
        "pickup": "🏪 पिकअप",
        "cash": "💵 नकद",
        "card": "💳 कार्ड",
        "apple_pay": "📱 Apple/Google Pay",
        "your_order": "📋 *आपका ऑर्डर:*",
        "total": "💰 *कुल:",
        "subtotal": "💰 उप-कुल:",
        "tax": "📊 टैक्स (8%):",
        "delivery_charge": "🚚 डिलीवरी:",
        "grand_total": "💵 *कुल राशि:",
        "added": "✅ कार्ट में जोड़ा!",
        "name_ask": "👤 *आपका नाम?*",
        "address_ask": "📍 डिलीवरी पता?",
        "address_saved": "✅ पता सेव! भुगतान चुनें 👇",
        "order_confirmed": "🎉 *ऑर्डर कन्फर्म",
        "ready_in": "⏱️ तैयार:",
        "thank_you": "Wild Bites चुनने के लिए धन्यवाद! 🍔",
        "cart_empty": "🛒 कार्ट खाली है!\n\n*menu* टाइप करें",
        "min_delivery": "⚠️ डिलीवरी के लिए न्यूनतम *$30*",
        "min_pickup": "⚠️ पिकअप के लिए न्यूनतम *$10*",
        "delivery_info": "🚚 *होम डिलीवरी* — 30-45 मिनट | न्यूनतम $30 | शुल्क $4.99\n\n🏪 *पिकअप* — 15-20 मिनट | न्यूनतम $10",
        "delayed": "नमस्ते! अभी भी यहाँ हैं? 😊",
        "save_room": "🍰 मिठाई के लिए जगह?",
        "yes_dessert": "🍰 हाँ",
        "no_dessert": "✅ नहीं",
        "yes_combo": "✅ हाँ! कॉम्बो",
        "no_combo": "❌ नहीं",
        "cancelled": "❌ ऑर्डर रद्द।\n\n*menu* टाइप करें।",
    },
    "fr": {
        "menu_header": "🍽️ Restaurant Wild Bites",
        "craving": "Qu'est-ce qui vous fait envie? 😋\n\nAppuyez sur une catégorie 👇",
        "browse": "📋 Parcourir le menu",
        "tap_add": "Appuyez sur un article! 👇",
        "ready": "Prêt à commander? 🚀",
        "checkout": "✅ Commander",
        "view_cart": "🛒 Voir panier",
        "add_more": "🍽️ Ajouter plus",
        "remove_one": "➖ Retirer un",
        "add_one": "➕ Ajouter un",
        "order_summary": "📋 Récapitulatif",
        "confirm": "✅ Confirmer",
        "cancel": "❌ Annuler",
        "delivery": "🚚 Livraison",
        "pickup": "🏪 Retrait",
        "cash": "💵 Espèces",
        "card": "💳 Carte",
        "apple_pay": "📱 Apple/Google Pay",
        "your_order": "📋 *Votre commande:*",
        "total": "💰 *Total:",
        "subtotal": "💰 Sous-total:",
        "tax": "📊 Taxe (8%):",
        "delivery_charge": "🚚 Livraison:",
        "grand_total": "💵 *Total général:",
        "added": "✅ Ajouté au panier!",
        "name_ask": "👤 *Votre prénom?*",
        "address_ask": "📍 Adresse de livraison?",
        "address_saved": "✅ Adresse enregistrée! Choisissez paiement 👇",
        "order_confirmed": "🎉 *Commande confirmée",
        "ready_in": "⏱️ Prêt dans:",
        "thank_you": "Merci d'avoir choisi Wild Bites! 🍔",
        "cart_empty": "🛒 Panier vide!\n\nTapez *menu*",
        "min_delivery": "⚠️ Minimum livraison: *30$*",
        "min_pickup": "⚠️ Minimum retrait: *10$*",
        "delivery_info": "🚚 *Livraison* — 30-45 min | Min $30 | Frais $4.99\n\n🏪 *Retrait* — 15-20 min | Min $10",
        "delayed": "Bonjour! Toujours là? 😊",
        "save_room": "🍰 Un dessert?",
        "yes_dessert": "🍰 Oui",
        "no_dessert": "✅ Non",
        "yes_combo": "✅ Oui! Combo",
        "no_combo": "❌ Non merci",
        "cancelled": "❌ Commande annulée.\n\nTapez *menu*.",
    },
    "de": {
        "menu_header": "🍽️ Wild Bites Restaurant",
        "craving": "Was möchten Sie heute? 😋\n\nKategorie auswählen 👇",
        "browse": "📋 Menü durchsuchen",
        "tap_add": "Artikel antippen! 👇",
        "ready": "Bereit zu bestellen? 🚀",
        "checkout": "✅ Bestellen",
        "view_cart": "🛒 Warenkorb",
        "add_more": "🍽️ Mehr hinzufügen",
        "remove_one": "➖ Entfernen",
        "add_one": "➕ Hinzufügen",
        "order_summary": "📋 Bestellübersicht",
        "confirm": "✅ Bestätigen",
        "cancel": "❌ Abbrechen",
        "delivery": "🚚 Lieferung",
        "pickup": "🏪 Abholung",
        "cash": "💵 Bargeld",
        "card": "💳 Karte",
        "apple_pay": "📱 Apple/Google Pay",
        "your_order": "📋 *Ihre Bestellung:*",
        "total": "💰 *Gesamt:",
        "subtotal": "💰 Zwischensumme:",
        "tax": "📊 MwSt (8%):",
        "delivery_charge": "🚚 Liefergebühr:",
        "grand_total": "💵 *Gesamtbetrag:",
        "added": "✅ Zum Warenkorb!",
        "name_ask": "👤 *Ihr Name?*",
        "address_ask": "📍 Lieferadresse?",
        "address_saved": "✅ Gespeichert! Zahlungsmethode 👇",
        "order_confirmed": "🎉 *Bestellung bestätigt",
        "ready_in": "⏱️ Bereit in:",
        "thank_you": "Danke für Ihre Wahl! 🍔",
        "cart_empty": "🛒 Warenkorb leer!\n\nTippen Sie *menu*",
        "min_delivery": "⚠️ Mindestbestellung Lieferung: *$30*",
        "min_pickup": "⚠️ Mindestbestellung Abholung: *$10*",
        "delivery_info": "🚚 *Lieferung* — 30-45 Min | Min $30 | Gebühr $4.99\n\n🏪 *Abholung* — 15-20 Min | Min $10",
        "delayed": "Hallo! Noch da? 😊",
        "save_room": "🍰 Dessert?",
        "yes_dessert": "🍰 Ja",
        "no_dessert": "✅ Nein",
        "yes_combo": "✅ Ja! Combo",
        "no_combo": "❌ Nein danke",
        "cancelled": "❌ Storniert.\n\nTippen Sie *menu*.",
    },
    "ru": {
        "menu_header": "🍽️ Ресторан Wild Bites",
        "craving": "Что хотите? 😋\n\nВыберите категорию 👇",
        "browse": "📋 Меню",
        "tap_add": "Нажмите на блюдо! 👇",
        "ready": "Готовы заказать? 🚀",
        "checkout": "✅ Оформить",
        "view_cart": "🛒 Корзина",
        "add_more": "🍽️ Добавить ещё",
        "remove_one": "➖ Убрать",
        "add_one": "➕ Добавить",
        "order_summary": "📋 Итог заказа",
        "confirm": "✅ Подтвердить",
        "cancel": "❌ Отмена",
        "delivery": "🚚 Доставка",
        "pickup": "🏪 Самовывоз",
        "cash": "💵 Наличные",
        "card": "💳 Карта",
        "apple_pay": "📱 Apple/Google Pay",
        "your_order": "📋 *Ваш заказ:*",
        "total": "💰 *Итого:",
        "subtotal": "💰 Подитог:",
        "tax": "📊 Налог (8%):",
        "delivery_charge": "🚚 Доставка:",
        "grand_total": "💵 *Итого:",
        "added": "✅ Добавлено!",
        "name_ask": "👤 *Как вас зовут?*",
        "address_ask": "📍 Адрес доставки?",
        "address_saved": "✅ Сохранено! Способ оплаты 👇",
        "order_confirmed": "🎉 *Заказ подтверждён",
        "ready_in": "⏱️ Готово через:",
        "thank_you": "Спасибо за выбор Wild Bites! 🍔",
        "cart_empty": "🛒 Корзина пуста!\n\nНапишите *menu*",
        "min_delivery": "⚠️ Минимальный заказ доставки: *$30*",
        "min_pickup": "⚠️ Минимальный заказ самовывоза: *$10*",
        "delivery_info": "🚚 *Доставка* — 30-45 мин | Мин $30 | Плата $4.99\n\n🏪 *Самовывоз* — 15-20 мин | Мин $10",
        "delayed": "Привет! Вы здесь? 😊",
        "save_room": "🍰 Десерт?",
        "yes_dessert": "🍰 Да",
        "no_dessert": "✅ Нет",
        "yes_combo": "✅ Да! Комбо",
        "no_combo": "❌ Нет",
        "cancelled": "❌ Отменено.\n\nНапишите *menu*.",
    },
    "zh": {
        "menu_header": "🍽️ Wild Bites餐厅",
        "craving": "今天想吃什么? 😋\n\n点击类别 👇",
        "browse": "📋 浏览菜单",
        "tap_add": "点击菜品添加! 👇",
        "ready": "准备下单? 🚀",
        "checkout": "✅ 结账",
        "view_cart": "🛒 购物车",
        "add_more": "🍽️ 继续添加",
        "remove_one": "➖ 减少",
        "add_one": "➕ 增加",
        "order_summary": "📋 订单摘要",
        "confirm": "✅ 确认",
        "cancel": "❌ 取消",
        "delivery": "🚚 外卖配送",
        "pickup": "🏪 到店自取",
        "cash": "💵 现金",
        "card": "💳 银行卡",
        "apple_pay": "📱 Apple/Google Pay",
        "your_order": "📋 *您的订单:*",
        "total": "💰 *总计:",
        "subtotal": "💰 小计:",
        "tax": "📊 税 (8%):",
        "delivery_charge": "🚚 配送费:",
        "grand_total": "💵 *总金额:",
        "added": "✅ 已添加!",
        "name_ask": "👤 *您的姓名?*",
        "address_ask": "📍 配送地址?",
        "address_saved": "✅ 已保存! 选择支付 👇",
        "order_confirmed": "🎉 *订单已确认",
        "ready_in": "⏱️ 准备时间:",
        "thank_you": "感谢选择Wild Bites! 🍔",
        "cart_empty": "🛒 购物车空!\n\n输入*menu*",
        "min_delivery": "⚠️ 外卖最低消费 *$30*",
        "min_pickup": "⚠️ 自取最低消费 *$10*",
        "delivery_info": "🚚 *外卖* — 30-45分钟 | 最低$30 | 费用$4.99\n\n🏪 *自取* — 15-20分钟 | 最低$10",
        "delayed": "您好! 还在吗? 😊",
        "save_room": "🍰 来份甜点?",
        "yes_dessert": "🍰 是的",
        "no_dessert": "✅ 不用",
        "yes_combo": "✅ 是! 套餐",
        "no_combo": "❌ 不了",
        "cancelled": "❌ 已取消。\n\n输入*menu*。",
    },
    "ml": {
        "menu_header": "🍽️ Wild Bites റെസ്റ്റോറൻ്റ്",
        "craving": "ഇന്ന് എന്ത് കഴിക്കണം? 😋\n\nഒരു വിഭാഗം തിരഞ്ഞെടുക്കൂ 👇",
        "browse": "📋 മെനു",
        "tap_add": "ഒരു ഇനം ടാപ്പ് ചെയ്യൂ! 👇",
        "ready": "ഓർഡർ നൽകാൻ തയ്യാറോ? 🚀",
        "checkout": "✅ ചെക്ക്ഔട്ട്",
        "view_cart": "🛒 കാർട്ട്",
        "add_more": "🍽️ കൂടുതൽ",
        "remove_one": "➖ നീക്കൂ",
        "add_one": "➕ ചേർക്കൂ",
        "order_summary": "📋 ഓർഡർ",
        "confirm": "✅ സ്ഥിരീകരിക്കൂ",
        "cancel": "❌ റദ്ദാക്കൂ",
        "delivery": "🚚 ഡെലിവറി",
        "pickup": "🏪 പിക്കപ്പ്",
        "cash": "💵 പണം",
        "card": "💳 കാർഡ്",
        "apple_pay": "📱 Apple/Google Pay",
        "your_order": "📋 *ഓർഡർ:*",
        "total": "💰 *ആകെ:",
        "subtotal": "💰 ഉപആകെ:",
        "tax": "📊 നികുതി (8%):",
        "delivery_charge": "🚚 ഡെലിവറി:",
        "grand_total": "💵 *മൊത്തം:",
        "added": "✅ ചേർത്തു!",
        "name_ask": "👤 *പേര്?*",
        "address_ask": "📍 വിലാസം?",
        "address_saved": "✅ സേവ് ചെയ്തു! പേയ്മെൻ്റ് 👇",
        "order_confirmed": "🎉 *ഓർഡർ സ്ഥിരീകരിച്ചു",
        "ready_in": "⏱️ തയ്യാർ:",
        "thank_you": "Wild Bites തിരഞ്ഞെടുത്തതിന് നന്ദി! 🍔",
        "cart_empty": "🛒 കാർട്ട് ശൂന്യം!\n\n*menu* ടൈപ്പ്",
        "min_delivery": "⚠️ ഡെലിവറി മിനിമം *$30*",
        "min_pickup": "⚠️ പിക്കപ്പ് മിനിമം *$10*",
        "delivery_info": "🚚 *ഡെലിവറി* — 30-45 മിനിറ്റ് | മിനിമം $30 | ഫീ $4.99\n\n🏪 *പിക്കപ്പ്* — 15-20 മിനിറ്റ് | മിനിമം $10",
        "delayed": "ഹലോ! ഇവിടെ ഉണ്ടോ? 😊",
        "save_room": "🍰 ഡെസേർട്ട്?",
        "yes_dessert": "🍰 അതെ",
        "no_dessert": "✅ വേണ്ട",
        "yes_combo": "✅ അതെ! കൊമ്പോ",
        "no_combo": "❌ വേണ്ട",
        "cancelled": "❌ റദ്ദാക്കി.\n\n*menu* ടൈപ്പ്.",
    },
}

def t(lang, key):
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, key))

customer_sessions = {}
last_message_time = {}
saved_orders = {}
customer_order_lookup = {}
manager_pending = {}
customer_profiles = {}

def new_session(sender=None):
    profile = customer_profiles.get(sender, {}) if sender else {}
    is_returning = bool(profile.get("name"))
    return {
        "stage": "returning" if is_returning else "lang_select",
        "lang": profile.get("lang", "en"),
        "order": {},
        "delivery_type": profile.get("delivery_type", ""),
        "address": profile.get("address", ""),
        "name": profile.get("name", ""),
        "payment": profile.get("payment", ""),
        "last_added": None,
        "current_cat": None,
        "pending_combo": [],
        "conversation": [],
        "upsell_declined": False,
        "order_id": None,
        "delay_warned": False,
        "_last_text": "",
        "deal_context": None,
    }

def get_session(sender):
    if sender not in customer_sessions:
        customer_sessions[sender] = new_session(sender)
    return customer_sessions[sender]

def save_profile(sender, session):
    if session.get("name"):
        profile = customer_profiles.get(sender, {"order_history": []})
        profile.update({
            "name": session.get("name", ""),
            "address": session.get("address", ""),
            "lang": session.get("lang", "en"),
            "delivery_type": session.get("delivery_type", ""),
            "payment": session.get("payment", ""),
        })
        if "order_history" not in profile:
            profile["order_history"] = []
        customer_profiles[sender] = profile

def add_to_order_history(sender, order_id, order_items):
    profile = customer_profiles.get(sender, {"order_history": []})
    if "order_history" not in profile:
        profile["order_history"] = []
    profile["order_history"].append({
        "order_id": order_id,
        "items": [v["item"]["name"] for v in order_items.values()],
        "timestamp": time.time()
    })
    profile["order_history"] = profile["order_history"][-5:]
    customer_profiles[sender] = profile

def get_favorite_items(sender):
    profile = customer_profiles.get(sender, {})
    history = profile.get("order_history", [])
    if not history:
        return []
    item_counts = {}
    for order in history:
        for item in order.get("items", []):
            item_counts[item] = item_counts.get(item, 0) + 1
    sorted_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)
    return [item for item, count in sorted_items[:3]]

MENU = {
    "deals": {
        "name": "🔥 Deals (Best Value)",
        "items": {
            "DL1": {"name": "Burger Combo Add-on", "price": 4.99, "emoji": "🔥", "desc": "Add fries + soda to any burger"},
            "DL2": {"name": "Double Smash Meal Deal", "price": 18.99, "emoji": "🍔", "desc": "Smash burger + fries + soda"},
            "DL3": {"name": "Pizza + Wings Deal", "price": 21.99, "emoji": "🍕", "desc": "Any pizza + 6 wings"},
            "DL4": {"name": "Family Pizza Deal", "price": 29.99, "emoji": "👨‍👩‍👧‍👦", "desc": "2 pizzas + 2 sodas"},
            "DL5": {"name": "Ribs Night Deal", "price": 21.99, "emoji": "🍖", "desc": "Half rack + 2 sides + soda"},
            "DL6": {"name": "Fish & Chips Combo", "price": 18.49, "emoji": "🐟", "desc": "Fish & chips + soda"},
        }
    },
    "fastfood": {
        "name": "🍔 Burgers & Fast Food",
        "items": {
            "FF1": {"name": "Classic Smash Burger", "price": 12.99, "emoji": "🍔", "desc": "Double patty, special sauce, lettuce"},
            "FF2": {"name": "Crispy Chicken Sandwich", "price": 11.99, "emoji": "🍗", "desc": "Crispy fried chicken, pickles, mayo"},
            "FF3": {"name": "BBQ Bacon Burger", "price": 14.99, "emoji": "🥓", "desc": "Beef patty, bacon, BBQ sauce"},
            "FF4": {"name": "Veggie Delight Burger", "price": 10.99, "emoji": "🥬", "desc": "Plant-based patty, avocado"},
            "FF5": {"name": "Spicy Jalapeno Burger", "price": 13.99, "emoji": "🌶️", "desc": "Beef patty, jalapenos, pepper jack"},
        }
    },
    "pizza": {
        "name": "🍕 Pizza (12 inch)",
        "items": {
            "PZ1": {"name": "Margherita Classic", "price": 13.99, "emoji": "🍕", "desc": "Fresh mozzarella, tomato, basil"},
            "PZ2": {"name": "BBQ Chicken Pizza", "price": 15.99, "emoji": "🍗", "desc": "Grilled chicken, BBQ sauce"},
            "PZ3": {"name": "Meat Lovers Supreme", "price": 17.99, "emoji": "🥩", "desc": "Pepperoni, sausage, beef, bacon"},
            "PZ4": {"name": "Veggie Garden Pizza", "price": 14.99, "emoji": "🥦", "desc": "Bell peppers, mushrooms, olives"},
            "PZ5": {"name": "Buffalo Chicken Pizza", "price": 16.99, "emoji": "🔥", "desc": "Buffalo sauce, chicken, ranch"},
        }
    },
    "bbq": {
        "name": "🍖 BBQ",
        "items": {
            "BB1": {"name": "Half Rack Ribs", "price": 18.99, "emoji": "🍖", "desc": "Smoky ribs, BBQ glaze + 2 sides"},
            "BB2": {"name": "Full Rack Ribs", "price": 29.99, "emoji": "🍖", "desc": "Full rack + 2 sides"},
            "BB3": {"name": "Pulled Pork Sandwich", "price": 12.99, "emoji": "🥪", "desc": "Slow-cooked pork, slaw, BBQ"},
            "BB4": {"name": "Smoked Brisket Plate", "price": 19.99, "emoji": "🥩", "desc": "Sliced brisket + 2 sides"},
            "BB5": {"name": "BBQ Chicken Plate", "price": 16.99, "emoji": "🍗", "desc": "BBQ chicken + 2 sides"},
        }
    },
    "fish": {
        "name": "🐟 Fish & Seafood",
        "items": {
            "FS1": {"name": "Fish & Chips (Cod)", "price": 15.99, "emoji": "🐟", "desc": "Beer-battered cod, fries, tartar"},
            "FS2": {"name": "Blackened Salmon Plate", "price": 19.99, "emoji": "🍣", "desc": "Rice + salad, lemon butter"},
            "FS3": {"name": "Shrimp Basket", "price": 16.99, "emoji": "🍤", "desc": "Crispy shrimp, fries, cocktail sauce"},
            "FS4": {"name": "Fish Sandwich", "price": 13.49, "emoji": "🥪", "desc": "Fried cod, lettuce, pickles"},
        }
    },
    "sides": {
        "name": "🍟 Sides & Snacks",
        "items": {
            "SD1": {"name": "Crispy French Fries", "price": 3.99, "emoji": "🍟", "desc": "Golden crispy, seasoned salt"},
            "SD2": {"name": "Onion Rings", "price": 4.99, "emoji": "⭕", "desc": "Beer battered, crispy"},
            "SD3": {"name": "Mac & Cheese Bites", "price": 5.99, "emoji": "🧀", "desc": "Creamy inside, crispy outside"},
            "SD4": {"name": "Chicken Wings (6pc)", "price": 8.99, "emoji": "🍗", "desc": "Buffalo or BBQ sauce"},
            "SD5": {"name": "Loaded Nachos", "price": 7.99, "emoji": "🌮", "desc": "Cheese, jalapenos, sour cream"},
            "SD6": {"name": "Caesar Salad", "price": 6.99, "emoji": "🥗", "desc": "Romaine, croutons, parmesan"},
        }
    },
    "drinks": {
        "name": "🥤 Drinks & Shakes",
        "items": {
            "DR1": {"name": "Coca Cola", "price": 2.99, "emoji": "🥤", "desc": "Ice cold, 16oz"},
            "DR2": {"name": "Pepsi", "price": 2.99, "emoji": "🥤", "desc": "Ice cold, 16oz"},
            "DR3": {"name": "Fresh Orange Juice", "price": 4.99, "emoji": "🍊", "desc": "Freshly squeezed, 12oz"},
            "DR4": {"name": "Mango Lassi", "price": 5.99, "emoji": "🥭", "desc": "Fresh mango, yogurt"},
            "DR5": {"name": "Strawberry Milkshake", "price": 6.99, "emoji": "🍓", "desc": "Real strawberries, thick"},
            "DR6": {"name": "Lemonade", "price": 3.99, "emoji": "🍋", "desc": "Fresh squeezed, 16oz"},
            "DR7": {"name": "Iced Coffee", "price": 4.99, "emoji": "☕", "desc": "Cold brew, milk, sugar"},
            "DR8": {"name": "Water (Bottle)", "price": 1.99, "emoji": "💧", "desc": "500ml spring water"},
        }
    },
    "desserts": {
        "name": "🍰 Desserts",
        "items": {
            "DS1": {"name": "Chocolate Lava Cake", "price": 6.99, "emoji": "🍫", "desc": "Warm gooey center, vanilla ice cream"},
            "DS2": {"name": "NY Cheesecake", "price": 5.99, "emoji": "🍰", "desc": "Classic NY style, strawberry"},
            "DS3": {"name": "Oreo Milkshake", "price": 7.99, "emoji": "🥛", "desc": "Thick shake, crushed Oreos"},
            "DS4": {"name": "Brownie Sundae", "price": 6.99, "emoji": "🍨", "desc": "Warm brownie, vanilla, choc sauce"},
        }
    }
}

UPSELL_COMBOS = {
    "FF1": ["SD1", "DR1"], "FF2": ["SD1", "DR1"], "FF3": ["SD2", "DR1"],
    "PZ1": ["SD4", "DR6"], "PZ3": ["SD4", "DR1"], "FS1": ["DR1"],
}

# ── FOOD IMAGES (Imgur hosted — replace with your own!) ─────────────
IMAGES = {
    # Restaurant banner
    "banner": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800&q=80",

    # Category images
    "deals":    "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=800&q=80",
    "fastfood": "https://images.unsplash.com/photo-1551782450-a2132b4ba21d?w=800&q=80",
    "pizza":    "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=800&q=80",
    "bbq":      "https://images.unsplash.com/photo-1544025162-d76538b2a681?w=800&q=80",
    "fish":     "https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?w=800&q=80",
    "sides":    "https://images.unsplash.com/photo-1576107232684-1279f390859f?w=800&q=80",
    "drinks":   "https://images.unsplash.com/photo-1544145945-f90425340c7e?w=800&q=80",
    "desserts": "https://images.unsplash.com/photo-1563805042-7684c019e1cb?w=800&q=80",

    # Item images — Burgers
    "FF1": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=800&q=80",
    "FF2": "https://images.unsplash.com/photo-1562967914-608f82629710?w=800&q=80",
    "FF3": "https://images.unsplash.com/photo-1553979459-d2229ba7433b?w=800&q=80",
    "FF4": "https://images.unsplash.com/photo-1520072959219-c595dc870360?w=800&q=80",
    "FF5": "https://images.unsplash.com/photo-1594212699903-ec8a3eca50f5?w=800&q=80",

    # Item images — Pizza
    "PZ1": "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=800&q=80",
    "PZ2": "https://images.unsplash.com/photo-1565299507177-b0ac66763828?w=800&q=80",
    "PZ3": "https://images.unsplash.com/photo-1534308983496-4fabb1a015ee?w=800&q=80",
    "PZ4": "https://images.unsplash.com/photo-1571407970349-bc81e7e96d47?w=800&q=80",
    "PZ5": "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=800&q=80",

    # Item images — BBQ
    "BB1": "https://images.unsplash.com/photo-1544025162-d76538b2a681?w=800&q=80",
    "BB2": "https://images.unsplash.com/photo-1529193591184-b1d58069ecdd?w=800&q=80",
    "BB3": "https://images.unsplash.com/photo-1621852004158-f3bc188ace2d?w=800&q=80",
    "BB4": "https://images.unsplash.com/photo-1558030137-a56c1b004fa3?w=800&q=80",
    "BB5": "https://images.unsplash.com/photo-1567620832903-9fc6debc209f?w=800&q=80",

    # Item images — Fish
    "FS1": "https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?w=800&q=80",
    "FS2": "https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=800&q=80",
    "FS3": "https://images.unsplash.com/photo-1565680018434-b513d5e5fd47?w=800&q=80",
    "FS4": "https://images.unsplash.com/photo-1551782450-17144efb9c50?w=800&q=80",

    # Item images — Sides
    "SD1": "https://images.unsplash.com/photo-1576107232684-1279f390859f?w=800&q=80",
    "SD2": "https://images.unsplash.com/photo-1639024471283-03518883512d?w=800&q=80",
    "SD3": "https://images.unsplash.com/photo-1473093295043-cdd812d0e601?w=800&q=80",
    "SD4": "https://images.unsplash.com/photo-1527477396000-e27163b481c2?w=800&q=80",
    "SD5": "https://images.unsplash.com/photo-1548811591-e280de0cce14?w=800&q=80",
    "SD6": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=800&q=80",

    # Item images — Drinks
    "DR1": "https://images.unsplash.com/photo-1554866585-cd94860890b7?w=800&q=80",
    "DR2": "https://images.unsplash.com/photo-1553361371-9b22f78e8b1d?w=800&q=80",
    "DR3": "https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?w=800&q=80",
    "DR4": "https://images.unsplash.com/photo-1571068316344-75bc76f77890?w=800&q=80",
    "DR5": "https://images.unsplash.com/photo-1553361371-9b22f78e8b1d?w=800&q=80",
    "DR6": "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=800&q=80",
    "DR7": "https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=800&q=80",
    "DR8": "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=800&q=80",

    # Item images — Desserts
    "DS1": "https://images.unsplash.com/photo-1563805042-7684c019e1cb?w=800&q=80",
    "DS2": "https://images.unsplash.com/photo-1567171466295-4afa63d45416?w=800&q=80",
    "DS3": "https://images.unsplash.com/photo-1572490122747-3968b75cc699?w=800&q=80",
    "DS4": "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?w=800&q=80",

    # Other screens
    "order_confirm": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800&q=80",
    "delivery":      "https://images.unsplash.com/photo-1587745416684-47953f16f02f?w=800&q=80",
    "welcome_back":  "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=800&q=80",
}

MENU_SUMMARY = """
Wild Bites Restaurant Menu (US):
Deals, Burgers, Pizza, BBQ, Fish, Drinks, Sides, Desserts
Delivery: min $30, fee $4.99, free over $50 | Pickup: min $10
Hours: 10am-11pm daily
"""

def get_order_total(order):
    return sum(v["item"]["price"] * v["qty"] for v in order.values())

def get_order_text(order):
    if not order:
        return "Empty cart"
    lines = [f"{v['item']['emoji']} {v['item']['name']} x{v['qty']} — ${v['item']['price'] * v['qty']:.2f}"
             for v in order.values()]
    return "\n".join(lines)

def find_item(item_id):
    for cat_key, cat_data in MENU.items():
        if item_id in cat_data["items"]:
            return cat_key, cat_data["items"][item_id]
    return None, None

def has_any_side(order): return any(k.startswith("SD") for k in order)
def has_any_drink(order): return any(k.startswith("DR") for k in order)
def is_burger(item_id): return item_id.startswith("FF")
def is_pizza(item_id): return item_id.startswith("PZ")
def is_fish(item_id): return item_id.startswith("FS")

def guess_category(text_lower):
    if any(w in text_lower for w in ["deal", "combo", "offer"]): return "deals"
    if any(w in text_lower for w in ["burger", "smash", "bacon", "chicken sandwich"]): return "fastfood"
    if any(w in text_lower for w in ["pizza", "pepperoni", "margherita"]): return "pizza"
    if any(w in text_lower for w in ["bbq", "ribs", "brisket"]): return "bbq"
    if any(w in text_lower for w in ["fish", "salmon", "shrimp"]): return "fish"
    if any(w in text_lower for w in ["drink", "coke", "pepsi", "shake"]): return "drinks"
    if any(w in text_lower for w in ["dessert", "cake", "brownie"]): return "desserts"
    if any(w in text_lower for w in ["fries", "wings", "nachos", "side"]): return "sides"
    return None

def is_order_status_query(text_lower):
    return any(w in text_lower for w in ["order status", "where is my order", "how long", "my order", "order update", "ready yet", "wheres my"])

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(params.get("hub.challenge", ""))
    return PlainTextResponse("Forbidden", status_code=403)

@app.post("/webhook")
async def handle_webhook(request: Request):
    data = await request.json()
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            message = entry["messages"][0]
            sender = message["from"]
            msg_type = message.get("type", "")
            last_message_time[sender] = time.time()

            if msg_type == "text":
                text = message["text"]["body"].strip()
                print(f"MSG: {text} from {sender}")

                # Check if this is manager replying with order update
                if sender == MANAGER_NUMBER:
                    await handle_manager_reply(text)
                    return

                await handle_flow(sender, text)
            elif msg_type == "interactive":
                interactive = message["interactive"]
                if interactive["type"] == "button_reply":
                    btn_id = interactive["button_reply"]["id"]
                    print(f"BTN: {btn_id} from {sender}")
                    await handle_flow(sender, btn_id, is_button=True)
                elif interactive["type"] == "list_reply":
                    list_id = interactive["list_reply"]["id"]
                    print(f"LIST: {list_id} from {sender}")
                    await handle_flow(sender, list_id, is_button=True)
    except Exception as e:
        print(f"ERROR: {e}\n{traceback.format_exc()}")
    return {"status": "ok"}

async def handle_flow(sender, text, is_button=False):
    session = get_session(sender)
    stage = session["stage"]
    lang = session.get("lang", "en")
    text_lower = text.lower().strip()
    session["delay_warned"] = False
    session["_last_text"] = text  # Store for order number extraction

    # Hard reset
    if text_lower in ["restart", "reset", "start over", "clear"]:
        customer_sessions[sender] = new_session(sender)
        customer_sessions[sender]["stage"] = "lang_select"
        await send_language_selection(sender)
        return

    # Order status check
    if is_order_status_query(text_lower):
        await handle_order_status(sender, session, lang)
        return

    # RETURNING CUSTOMER
    if stage == "returning":
        profile = customer_profiles.get(sender, {})
        name = profile.get("name", "")
        favorites = get_favorite_items(sender)
        fav_text = f"\n\nYou usually order: {', '.join(favorites)} " if favorites else ""
        session["stage"] = "returning_choice"
        await send_returning_customer_menu(sender, name, fav_text, lang)
        return

    if stage == "returning_choice":
        if text == "REPEAT_ORDER":
            profile = customer_profiles.get(sender, {})
            history = profile.get("order_history", [])
            if history:
                last = history[-1]
                last_items = ", ".join(last.get("items", []))
                addr = session.get("address", "")
                await send_repeat_order_confirm(sender, last_items, addr, lang)
                session["stage"] = "repeat_confirm"
            else:
                session["stage"] = "menu"
                await send_main_menu(sender, session["order"], lang)
        elif text in ["NEW_ORDER", "REPEAT_ADD_MORE"]:
            session["stage"] = "menu"
            await send_main_menu(sender, session["order"], lang)
        elif text == "CHANGE_ADDRESS":
            session["stage"] = "address_update"
            await send_text_message(sender, "Sure! What's your new delivery address? ")
        elif text == "REPEAT_CONFIRM":
            profile = customer_profiles.get(sender, {})
            history = profile.get("order_history", [])
            if history:
                last_items = history[-1].get("items", [])
                for cat_data in MENU.values():
                    for item_id, item in cat_data["items"].items():
                        if item["name"] in last_items:
                            session["order"][item_id] = {"item": item, "qty": 1}
            if session["order"]:
                session["stage"] = "confirm"
                await send_order_summary(sender, session["order"], lang)
            else:
                session["stage"] = "menu"
                await send_main_menu(sender, session["order"], lang)
        else:
            session["stage"] = "menu"
            await send_main_menu(sender, session["order"], lang)
        return

    if stage == "address_update":
        session["address"] = text.strip()
        save_profile(sender, session)
        await send_text_message(sender, f"Address updated! {text}")
        session["stage"] = "menu"
        await send_main_menu(sender, session["order"], lang)
        return

    # ── LANGUAGE SELECTION ──────────────────────────────
    if stage == "lang_select":
        lang_map = {
            "LANG_EN": "en", "LANG_AR": "ar", "LANG_HI": "hi",
            "LANG_FR": "fr", "LANG_DE": "de", "LANG_RU": "ru",
            "LANG_ZH": "zh", "LANG_ML": "ml"
        }
        if text in lang_map:
            session["lang"] = lang_map[text]
            lang = lang_map[text]
            session["stage"] = "menu"
            greeting = await get_ai_response(sender, "Hello", lang, "User just selected their language. Give one warm welcome line.")
            await send_text_message(sender, greeting)
            await send_main_menu(sender, session["order"], lang)
        else:
            await send_language_selection(sender)
        return

    # ── UNIVERSAL BUTTONS ───────────────────────────────
    if text in ["SHOW_MENU", "BACK_MENU", "ADD_MORE"]:
        session["stage"] = "menu"
        await send_main_menu(sender, session["order"], lang)
        return

    # Quick remove command
    m_remove = re.match(r"^(remove|delete)\s+([a-z0-9]+)$", text_lower)
    if m_remove:
        item_id = m_remove.group(2).upper()
        if item_id in session["order"]:
            del session["order"][item_id]
        await send_cart_view(sender, session["order"], lang)
        return

    # ── CATEGORY BUTTONS ────────────────────────────────
    cat_map = {
        "CAT_DEALS": "deals", "CAT_FASTFOOD": "fastfood", "CAT_PIZZA": "pizza",
        "CAT_BBQ": "bbq", "CAT_FISH": "fish", "CAT_SIDES": "sides",
        "CAT_DRINKS": "drinks", "CAT_DESSERTS": "desserts",
    }
    if text in cat_map:
        session["stage"] = "items"
        session["current_cat"] = cat_map[text]
        await send_category_items(sender, cat_map[text], session["order"], lang)
        return

    # ── ITEM ADD ─────────────────────────────────────────
    if text.startswith("ADD_"):
        item_id = text.replace("ADD_", "").upper()
        cat, found_item = find_item(item_id)
        if found_item:
            if item_id in session["order"]:
                session["order"][item_id]["qty"] += 1
            else:
                session["order"][item_id] = {"item": found_item, "qty": 1}
            session["last_added"] = item_id
            session["stage"] = "qty_control"

            if item_id in ["BB1", "BB2", "BB4", "BB5"]:
                await send_text_message(sender, "Pick 2 sides: mac & cheese, fries, coleslaw, or salad 😄")

            if not session.get("upsell_declined", False):
                if is_burger(item_id) and not (has_any_side(session["order"]) and has_any_drink(session["order"])) and len(session["order"]) <= 2:
                    await send_quick_combo_upsell(sender, lang)
                    return
                if is_pizza(item_id) and "SD4" not in session["order"] and len(session["order"]) <= 2:
                    await send_quick_upsell(sender, "SD4", "🍗 Add 6 wings with your pizza? Most people do! 😄", lang)
                    return

            await send_qty_control(sender, item_id, found_item, session["order"], lang)
        return

    # ── QTY ──────────────────────────────────────────────
    if text in ["QTY_PLUS", "QTY_MINUS"]:
        item_id = session.get("last_added")
        if item_id and item_id in session["order"]:
            if text == "QTY_PLUS":
                session["order"][item_id]["qty"] += 1
            else:
                if session["order"][item_id]["qty"] > 1:
                    session["order"][item_id]["qty"] -= 1
                else:
                    del session["order"][item_id]
        if item_id and item_id in session["order"]:
            await send_qty_control(sender, item_id, session["order"][item_id]["item"], session["order"], lang)
        else:
            session["stage"] = "menu"
            await send_main_menu(sender, session["order"], lang)
        return

    # ── UPSELL ───────────────────────────────────────────
    if text == "SKIP_UPSELL":
        session["upsell_declined"] = True
        last = session.get("last_added")
        if last and last in session["order"]:
            await send_qty_control(sender, last, session["order"][last]["item"], session["order"], lang)
        else:
            await send_main_menu(sender, session["order"], lang)
        return

    if text == "ADD_COMBO_DL1":
        deal_item = MENU["deals"]["items"]["DL1"]
        if "DL1" not in session["order"]:
            session["order"]["DL1"] = {"item": deal_item, "qty": 1}
        last = session.get("last_added")
        if last and last in session["order"]:
            await send_qty_control(sender, last, session["order"][last]["item"], session["order"], lang)
        else:
            await send_cart_view(sender, session["order"], lang)
        return

    # ── CHECKOUT ─────────────────────────────────────────
    if text == "CHECKOUT":
        if session["order"]:
            session["stage"] = "upsell_check"
            await send_dessert_upsell(sender, session["order"], lang)
        else:
            await send_text_message(sender, t(lang, "cart_empty"))
            await send_main_menu(sender, session["order"], lang)
        return

    if text == "VIEW_CART":
        await send_cart_view(sender, session["order"], lang)
        return

    # ── DESSERT UPSELL ───────────────────────────────────
    if text in ["YES_UPSELL", "NO_UPSELL"]:
        if text == "YES_UPSELL":
            session["stage"] = "items"
            session["current_cat"] = "desserts"
            await send_category_items(sender, "desserts", session["order"], lang)
        else:
            session["stage"] = "confirm"
            await send_order_summary(sender, session["order"], lang)
        return

    # ── CONFIRM / CANCEL ─────────────────────────────────
    if text == "CONFIRM_ORDER":
        session["stage"] = "get_name"
        await send_text_message(sender, t(lang, "name_ask"))
        return

    if text == "CANCEL_ORDER":
        customer_sessions[sender] = new_session(sender)
        await send_text_message(sender, t(lang, "cancelled"))
        return

    # ── DELIVERY / PICKUP ────────────────────────────────
    if text in ["DELIVERY", "PICKUP"]:
        total = get_order_total(session["order"])
        if text == "DELIVERY":
            if total < MIN_DELIVERY_ORDER:
                await send_text_message(sender, t(lang, "min_delivery"))
                await send_delivery_buttons(sender, session.get("name", ""), lang)
                return
            session["delivery_type"] = "delivery"
            session["stage"] = "address"
            await send_text_message(sender, f"📍 {t(lang, 'address_ask')}")
        else:
            if total < MIN_PICKUP_ORDER:
                await send_text_message(sender, t(lang, "min_pickup"))
                await send_delivery_buttons(sender, session.get("name", ""), lang)
                return
            session["delivery_type"] = "pickup"
            session["stage"] = "payment"
            await send_payment_buttons(sender, session.get("name", ""), lang)
        return

    # ── PAYMENT ──────────────────────────────────────────
    if text in ["CASH", "CARD", "APPLE_PAY"]:
        payment_map = {"CASH": t(lang, "cash"), "CARD": t(lang, "card"), "APPLE_PAY": t(lang, "apple_pay")}
        session["payment"] = payment_map[text]
        order_id = await send_order_confirmed(sender, session, lang)
        session["order_id"] = order_id
        save_profile(sender, session)
        add_to_order_history(sender, order_id, session["order"])
        await notify_manager(sender, session, order_id)
        await save_to_sheet(sender, session, order_id)
        customer_sessions[sender] = new_session(sender)
        return

    # ── STAGE TEXT ───────────────────────────────────────
    if stage == "get_name":
        session["name"] = text.strip().title()[:30]
        session["stage"] = "delivery"
        await send_delivery_buttons(sender, session["name"], lang)
        return

    if stage == "address":
        session["address"] = text.strip()
        session["stage"] = "payment"
        await send_text_message(sender, t(lang, "address_saved"))
        await send_payment_buttons(sender, session.get("name", ""), lang)
        return

    # ── GREETINGS ─────────────────────────────────────────
    if text_lower in ["hi", "hello", "hey", "start", "salam", "hola"]:
        if stage in ["lang_select", "ai_chat"]:
            await send_language_selection(sender)
        else:
            session["stage"] = "menu"
            greeting = await get_ai_response(sender, text, lang, "One warm greeting line only.")
            await send_text_message(sender, greeting)
            await send_main_menu(sender, session["order"], lang)
        return

    if text_lower == "menu":
        session["stage"] = "menu"
        await send_main_menu(sender, session["order"], lang)
        return

    # ── INTENT ROUTING ────────────────────────────────────
    cat_guess = guess_category(text_lower)
    if cat_guess and stage not in ["get_name", "address"]:
        session["stage"] = "items"
        session["current_cat"] = cat_guess
        await send_category_items(sender, cat_guess, session["order"], lang)
        return

    # ── AI FALLBACK ───────────────────────────────────────
    reply = await get_ai_response(sender, text, lang)
    await send_text_message(sender, reply)
    session["conversation"].append(text)
    if len(session["conversation"]) >= 2:
        await send_menu_suggestion(sender, lang)
        session["conversation"] = []

async def handle_order_status(sender, session, lang):
    # First check session, then permanent lookup
    order_id = session.get("order_id") or customer_order_lookup.get(sender)

    # Check if message contains order number directly
    import re as _re
    order_match = _re.search(r'\b(\d{5})\b', session.get("_last_text", ""))
    if order_match:
        order_id = int(order_match.group(1))

    if not order_id:
        await send_text_message(sender, "I don't see an active order for you. Type *menu* to place a new order! 😊")
        return

    order_data = saved_orders.get(order_id)
    if not order_data:
        await send_text_message(sender, f"Let me check on order #{order_id} for you! 🔍")
        await notify_manager_status(order_id, sender)
        return

    elapsed = (time.time() - order_data["timestamp"]) / 60
    delivery_type = order_data.get("delivery_type", "pickup")
    expected = 45 if delivery_type == "delivery" else 20

    if elapsed < expected:
        remaining = int(expected - elapsed)
        await send_text_message(sender, f"🍳 Your order #{order_id} is being prepared!\n\n⏱️ About {remaining} more minutes.\n\nHang tight! 😊")
    else:
        await send_text_message(sender, f"🔍 Checking on your order #{order_id} with our team... I'll update you shortly! 😊")
        await notify_manager_status(order_id, sender)

async def notify_manager(customer_number, session, order_id):
    order = session.get("order", {})
    total = get_order_total(order)
    tax = total * 0.08
    delivery_charge = DELIVERY_CHARGE if session.get("delivery_type") == "delivery" else 0
    grand_total = total + tax + delivery_charge
    order_text = get_order_text(order)
    lang_name = LANG_NAMES.get(session.get("lang", "en"), "English")

    msg = f"""🔔 *NEW ORDER #{order_id}*

👤 {session.get('name', 'N/A')}
📱 +{customer_number}
🌐 Language: {lang_name}

{order_text}

Subtotal: ${total:.2f}
Tax: ${tax:.2f}
Delivery: ${delivery_charge:.2f}
*Total: ${grand_total:.2f}*

{'Delivery: ' + session.get('address', '') if session.get('delivery_type') == 'delivery' else 'Pickup'}
Payment: {session.get('payment', 'N/A')}
ETA: {'30-45 mins' if session.get('delivery_type') == 'delivery' else '15-20 mins'}"""

    reply_guide = (
        f"\n\nTo update customer, reply:\n"
        f"ORDER#{order_id} READY\n"
        f"ORDER#{order_id} OUT FOR DELIVERY\n"
        f"ORDER#{order_id} DELAYED 15\n"
        f"ORDER#{order_id} CANCELLED"
    )
    await send_whatsapp_to_number(MANAGER_NUMBER, msg + reply_guide)
    print(f"Manager notified: #{order_id}")

async def notify_manager_status(order_id, customer_number):
    await send_whatsapp_to_number(MANAGER_NUMBER, f"⚠️ Customer +{customer_number} asking about Order #{order_id}. Please update!")

async def handle_manager_reply(text):
    """
    Manager sends: ORDER#54535 READY
    Or: ORDER#54535 DELAYED 20 minutes
    Or: ORDER#54535 OUT FOR DELIVERY
    """
    import re as _re
    # Extract order number from manager message
    match = _re.search(r'ORDER#?(\d{5})', text.upper())
    if not match:
        print(f"Manager message not an order update: {text}")
        return

    order_id = int(match.group(1))
    customer_number = manager_pending.get(order_id)

    if not customer_number:
        print(f"No customer found for order #{order_id}")
        return

    order_data = saved_orders.get(order_id, {})
    customer_name = order_data.get("customer_name", "Customer")

    # Parse status
    text_upper = text.upper()
    if "READY" in text_upper and "DELIVERY" not in text_upper:
        if order_data.get("delivery_type") == "pickup":
            msg = f"Great news, {customer_name}! 🎉\n\nYour order #{order_id} is *READY for pickup!* 🏪\n\nPlease come collect it at your earliest convenience! 😊"
        else:
            msg = f"Great news, {customer_name}! 🎉\n\nYour order #{order_id} is ready and *OUT FOR DELIVERY* 🚚\n\nShould arrive in 15-20 minutes!"
    elif "OUT FOR DELIVERY" in text_upper or "ON THE WAY" in text_upper:
        msg = f"Hey {customer_name}! 🚚\n\nYour order #{order_id} is *on the way!*\n\nShould arrive in 15-20 minutes! 😊"
    elif "DELAYED" in text_upper:
        # Extract delay time if mentioned
        delay_match = _re.search(r'DELAYED\s+(\d+)', text_upper)
        delay_time = delay_match.group(1) + " minutes" if delay_match else "a little longer"
        msg = f"Hi {customer_name}, just a heads up! ⏱️\n\nYour order #{order_id} will take *{delay_time}* more than expected.\n\nWe apologize for the wait! 🙏"
    elif "CANCELLED" in text_upper:
        msg = f"Hi {customer_name}, we're sorry! 😔\n\nUnfortunately order #{order_id} has been *cancelled.*\n\nPlease contact us for a refund or to reorder."
    else:
        # Forward raw message as update
        msg = f"Update on your order #{order_id}: {text}"

    await send_whatsapp_to_number(customer_number, msg)
    print(f"Manager update sent to customer {customer_number} for order #{order_id}")

async def send_whatsapp_to_number(to_number, message):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": message}}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, headers=headers) as r:
                print(f"Sent to {to_number}: {r.status}")
    except Exception as e:
        print(f"Error: {e}")

async def save_to_sheet(customer_number, session, order_id):
    order = session.get("order", {})
    total = get_order_total(order)
    tax = total * 0.08
    delivery_charge = DELIVERY_CHARGE if session.get("delivery_type") == "delivery" else 0
    grand_total = total + tax + delivery_charge
    items_list = [f"{v['item']['name']} x{v['qty']}" for v in order.values()]

    data = {
        "order_id": str(order_id),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "customer_name": session.get("name", ""),
        "customer_number": f"+{customer_number}",
        "items": ", ".join(items_list),
        "subtotal": round(total, 2),
        "tax": round(tax, 2),
        "delivery_charge": round(delivery_charge, 2),
        "grand_total": round(grand_total, 2),
        "delivery_type": session.get("delivery_type", ""),
        "address": session.get("address", ""),
        "payment": session.get("payment", ""),
        "language": session.get("lang", "en"),
        "status": "New"
    }

    saved_orders[order_id] = {**data, "timestamp": time.time()}
    customer_order_lookup[customer_number] = order_id
    manager_pending[order_id] = customer_number
    print(f"Order #{order_id} linked to customer {customer_number}")

    if GOOGLE_SHEET_WEBHOOK:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(GOOGLE_SHEET_WEBHOOK, json=data) as r:
                    print(f"Sheet saved: {r.status}")
        except Exception as e:
            print(f"Sheet error: {e}")
    else:
        print(f"Order saved locally: #{order_id}")

async def get_ai_response(sender, user_message, lang="en", extra_instruction=""):
    lang_name = LANG_NAMES.get(lang, "English")
    system_prompt = f"""You are Alex, a friendly customer service rep at Wild Bites Restaurant.
IMPORTANT: Always reply in {lang_name} only. Never mention you are AI.
Be warm, casual, helpful. Max 3 sentences. Use emojis naturally.
Hours: 10am-11pm. Delivery min $30 + $4.99 fee (free over $50). Pickup min $10.
{MENU_SUMMARY}
{extra_instruction}
If customer seems confused or stuck, guide them to next step clearly."""

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7,
        "max_tokens": 150
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers) as r:
                result = await r.json()
                return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"AI Error: {e}")
        return "Hey! Sorry about that 😊 How can I help?"

async def send_language_selection(sender):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": "🍽️ Wild Bites Restaurant"},
            "body": {"text": "Welcome! Please choose your language:\n\nمرحباً | स्वागत | Bienvenue | Willkommen"},
            "footer": {"text": "Language Selection"},
            "action": {
                "button": "🌐 Choose Language",
                "sections": [{"title": "Languages", "rows": [
                    {"id": "LANG_EN", "title": "🇺🇸 English", "description": "Continue in English"},
                    {"id": "LANG_AR", "title": "🇸🇦 العربية", "description": "الاستمرار بالعربية"},
                    {"id": "LANG_HI", "title": "🇮🇳 हिन्दी", "description": "हिंदी में जारी रखें"},
                    {"id": "LANG_FR", "title": "🇫🇷 Français", "description": "Continuer en français"},
                    {"id": "LANG_DE", "title": "🇩🇪 Deutsch", "description": "Auf Deutsch fortfahren"},
                    {"id": "LANG_RU", "title": "🇷🇺 Русский", "description": "Продолжить на русском"},
                    {"id": "LANG_ZH", "title": "🇨🇳 中文", "description": "继续中文"},
                    {"id": "LANG_ML", "title": "🇮🇳 Malayalam", "description": "മലയാളം"},
                ]}]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()
            print("Language selection sent")

async def send_main_menu(sender, current_order=None, lang="en"):
    current_order = current_order or {}
    total = get_order_total(current_order)
    cart_text = ""
    if current_order:
        count = sum(v["qty"] for v in current_order.values())
        cart_text = f"\n\n🛒 {count} item(s) — ${total:.2f}"

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "image", "image": {"link": IMAGES["banner"]}},
            "body": {"text": f"{t(lang, 'menu_header')}\n{t(lang, 'craving')}{cart_text}"},
            "footer": {"text": "Fast Delivery | Fresh Food | Best Value"},
            "action": {
                "button": t(lang, "browse"),
                "sections": [
                    {"title": "Start Here", "rows": [
                        {"id": "CAT_DEALS", "title": "Deals (Best Value)", "description": "Combos & bundles"},
                    ]},
                    {"title": "Main Course", "rows": [
                        {"id": "CAT_FASTFOOD", "title": "Burgers & Fast Food", "description": "From $10.99"},
                        {"id": "CAT_PIZZA", "title": "Pizza (12 inch)", "description": "From $13.99"},
                        {"id": "CAT_BBQ", "title": "BBQ", "description": "Ribs, brisket, pulled pork"},
                        {"id": "CAT_FISH", "title": "Fish & Seafood", "description": "From $13.49"},
                    ]},
                    {"title": "Extras", "rows": [
                        {"id": "CAT_SIDES", "title": "Sides & Snacks", "description": "From $3.99"},
                        {"id": "CAT_DRINKS", "title": "Drinks & Shakes", "description": "From $1.99"},
                        {"id": "CAT_DESSERTS", "title": "Desserts", "description": "From $5.99"},
                    ]},
                ]
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()
            print("Main menu sent")

async def send_category_items(sender, cat_key, current_order, lang="en"):
    cat = MENU[cat_key]
    total = get_order_total(current_order)
    cart_text = f"\n\n🛒 ${total:.2f}" if current_order else ""
    rows = []
    for item_id, item in cat["items"].items():
        in_cart = current_order.get(item_id, {}).get("qty", 0)
        cart_indicator = f" x{in_cart}" if in_cart else ""
        rows.append({
            "id": f"ADD_{item_id}",
            "title": f"{item['emoji']} {item['name']}{cart_indicator}",
            "description": f"${item['price']:.2f} - {item['desc']}"
        })

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    cat_img = IMAGES.get(cat_key, IMAGES["banner"])
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "image", "image": {"link": cat_img}},
            "body": {"text": f"{cat['name']}\n{t(lang, 'tap_add')}{cart_text}"},
            "footer": {"text": "Tap to add to cart"},
            "action": {"button": "Select Item", "sections": [{"title": cat["name"], "rows": rows}]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()
            print(f"Category sent: {cat_key}")

async def send_qty_control(sender, item_id, item, order, lang="en"):
    qty = order.get(item_id, {}).get("qty", 1)
    subtotal = item["price"] * qty
    total = get_order_total(order)
    order_text = get_order_text(order)

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "image", "image": {"link": IMAGES.get(item_id, IMAGES["fastfood"])}},
            "body": {"text": f"*{item['name']}*\nQty: {qty} x ${item['price']:.2f} = *${subtotal:.2f}*\n\n{t(lang, 'your_order')}\n{order_text}\n\n{t(lang, 'total')} ${total:.2f}*"},
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "QTY_MINUS", "title": t(lang, "remove_one")}},
                {"type": "reply", "reply": {"id": "QTY_PLUS", "title": t(lang, "add_one")}},
                {"type": "reply", "reply": {"id": "ADD_MORE", "title": t(lang, "add_more")}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

    await send_checkout_prompt(sender, total, lang)

async def send_checkout_prompt(sender, total, lang="en"):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": t(lang, "ready")},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "CHECKOUT", "title": f"{t(lang, 'checkout')} ${total:.2f}"}},
                {"type": "reply", "reply": {"id": "VIEW_CART", "title": t(lang, "view_cart")}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

async def send_quick_combo_upsell(sender, lang="en"):
    session = get_session(sender)
    session["stage"] = "upsell_combo"
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "Make it a Combo?"},
            "body": {"text": "Add Fries + Soda for only *$4.99 more!*\n\nMost customers add this! 😍"},
            "footer": {"text": "Best value"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "ADD_COMBO_DL1", "title": t(lang, "yes_combo")}},
                {"type": "reply", "reply": {"id": "SKIP_UPSELL", "title": t(lang, "no_combo")}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

async def send_quick_upsell(sender, item_id, message, lang="en"):
    session = get_session(sender)
    session["stage"] = "upsell_combo"
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": message},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": f"ADD_{item_id}", "title": t(lang, "yes_combo")}},
                {"type": "reply", "reply": {"id": "SKIP_UPSELL", "title": t(lang, "no_combo")}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

async def send_dessert_upsell(sender, order, lang="en"):
    total = get_order_total(order)
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "image", "image": {"link": IMAGES["desserts"]}},
            "body": {"text": f"{t(lang, 'save_room')}\nOrder: ${total:.2f}\n\n🍫 Lava Cake $6.99 | 🍰 Cheesecake $5.99 | 🍨 Brownie Sundae $6.99"},
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "YES_UPSELL", "title": t(lang, "yes_dessert")}},
                {"type": "reply", "reply": {"id": "NO_UPSELL", "title": t(lang, "no_dessert")}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

async def send_cart_view(sender, order, lang="en"):
    if not order:
        await send_text_message(sender, t(lang, "cart_empty"))
        return
    total = get_order_total(order)
    order_text = get_order_text(order)
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "image", "image": {"link": IMAGES["order_confirm"]}},
            "body": {"text": f"{order_text}\n\n{t(lang, 'subtotal')} ${total:.2f}"},
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "CHECKOUT", "title": f"{t(lang, 'checkout')} ${total:.2f}"}},
                {"type": "reply", "reply": {"id": "ADD_MORE", "title": t(lang, "add_more")}},
                {"type": "reply", "reply": {"id": "CANCEL_ORDER", "title": t(lang, "cancel")}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

async def send_order_summary(sender, order, lang="en"):
    total = get_order_total(order)
    tax = total * 0.08
    grand_total = total + tax
    order_text = get_order_text(order)
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "image", "image": {"link": IMAGES["order_confirm"]}},
            "body": {"text": f"{order_text}\n\n{t(lang, 'subtotal')} ${total:.2f}\n{t(lang, 'tax')} ${tax:.2f}\n{t(lang, 'grand_total')} ${grand_total:.2f}*"},
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "CONFIRM_ORDER", "title": t(lang, "confirm")}},
                {"type": "reply", "reply": {"id": "ADD_MORE", "title": t(lang, "add_more")}},
                {"type": "reply", "reply": {"id": "CANCEL_ORDER", "title": t(lang, "cancel")}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

async def send_delivery_buttons(sender, name, lang="en"):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "image", "image": {"link": IMAGES["delivery"]}},
            "body": {"text": f"Hey {name}! Delivery or Pickup?\n\n{t(lang, 'delivery_info')}"},
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "DELIVERY", "title": t(lang, "delivery")}},
                {"type": "reply", "reply": {"id": "PICKUP", "title": t(lang, "pickup")}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

async def send_payment_buttons(sender, name, lang="en"):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "Payment Method"},
            "body": {"text": "Choose your payment:"},
            "footer": {"text": "100% Secure"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "CASH", "title": t(lang, "cash")}},
                {"type": "reply", "reply": {"id": "CARD", "title": t(lang, "card")}},
                {"type": "reply", "reply": {"id": "APPLE_PAY", "title": t(lang, "apple_pay")}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

async def send_order_confirmed(sender, session_data, lang="en"):
    order = session_data.get("order", {})
    total = get_order_total(order)
    tax = total * 0.08
    delivery_charge = DELIVERY_CHARGE if session_data.get("delivery_type") == "delivery" else 0
    grand_total = total + tax + delivery_charge
    order_text = get_order_text(order)
    delivery_type = session_data.get("delivery_type", "pickup")
    order_id = random.randint(10000, 99999)
    eta = "30-45 minutes" if delivery_type == "delivery" else "15-20 minutes"
    delivery_fee_line = f"\n{t(lang, 'delivery_charge')} ${delivery_charge:.2f}" if delivery_charge > 0 else ""

    msg = f"""{t(lang, 'order_confirmed')}, {session_data.get('name', 'Customer')}! #{order_id}*

{order_text}

{t(lang, 'subtotal')} ${total:.2f}
{t(lang, 'tax')} ${tax:.2f}{delivery_fee_line}
{t(lang, 'grand_total')} ${grand_total:.2f}*

{'Delivery: ' + session_data.get('address', '') if delivery_type == 'delivery' else 'Store Pickup'}
Payment: {session_data.get('payment', '')}
{t(lang, 'ready_in')} *{eta}*

{t(lang, 'thank_you')}"""

    await send_text_message(sender, msg)
    return order_id

async def send_menu_suggestion(sender, lang="en"):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "Hungry? Tap to browse our menu! 🍔"},
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {"buttons": [{"type": "reply", "reply": {"id": "SHOW_MENU", "title": "Menu"}}]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

async def send_returning_customer_menu(sender, name, fav_text, lang="en"):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "image", "image": {"link": IMAGES["welcome_back"]}},
            "body": {"text": f"Welcome back, {name}! Great to see you again!{fav_text}\n\nWhat would you like to do today?"},
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "REPEAT_ORDER", "title": "Repeat Last Order"}},
                {"type": "reply", "reply": {"id": "NEW_ORDER", "title": "New Order"}},
                {"type": "reply", "reply": {"id": "CHANGE_ADDRESS", "title": "Change Address"}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()
            print("Returning customer menu sent")

async def send_repeat_order_confirm(sender, last_items, address, lang="en"):
    addr_text = f"\nDelivery to: {address}" if address else "\nPickup from store"
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "Repeat Last Order?"},
            "body": {"text": f"Your last order was:\n{last_items}{addr_text}\n\nWant the same again?"},
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "REPEAT_CONFIRM", "title": "Yes, Same Order!"}},
                {"type": "reply", "reply": {"id": "REPEAT_ADD_MORE", "title": "Add More Items"}},
                {"type": "reply", "reply": {"id": "NEW_ORDER", "title": "Start Fresh"}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()
            print("Repeat order confirm sent")

async def send_text_message(to, message):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": message}}
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()
            print(f"Text sent to {to}")

@app.post("/twilio-call")
async def twilio_call(request: Request):
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice">Welcome to Wild Bites. Please WhatsApp us to order. Thank you!</Say>
</Response>"""
    return HTMLResponse(content=twiml, media_type="application/xml")

@app.post("/twilio-sms")
async def twilio_sms(request: Request):
    form = await request.form()
    print(f"SMS: {form.get('Body')} from {form.get('From')}")
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")