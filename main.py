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
MANAGER_NUMBER = os.getenv("MANAGER_NUMBER", "923351021321")  # FIX #26

MIN_DELIVERY_ORDER = 30.00
MIN_PICKUP_ORDER = 10.00
DELIVERY_CHARGE = 4.99
FREE_DELIVERY_THRESHOLD = 50.00  # FIX #17
POST_ORDER_WINDOW = 180  # FIX #20 — 3 min grace window after order

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
        "min_delivery": "⚠️ Minimum order for delivery is *$30*.\nAdd more items or choose *Store Pickup* (min $10).",
        "min_pickup": "⚠️ Minimum order for pickup is *$10*.\nPlease add more items.",
        "delivery_info": "🚚 *Home Delivery* — 30-45 mins\n   Min $30 | Fee $4.99 | FREE over $50!\n\n🏪 *Store Pickup* — 15-20 mins\n   Min $10",
        "save_room": "🍰 Save room for dessert?",
        "yes_dessert": "🍰 Yes, show desserts",
        "no_dessert": "✅ No, continue",
        "yes_combo": "✅ Yes! Add Combo",
        "no_combo": "❌ No Thanks",
        "cancelled": "❌ Order cancelled.\n\nType *menu* to start again.",
        "greeting_welcome": "Welcome to Wild Bites! 🍔 Ready to order?",  # FIX #35
        "add_more_items": "🍽️ Add More Items",  # FIX #16
        "back": "⬅️ Back",  # FIX #19
        "invalid_name": "Please enter your first name (2+ characters, letters). 😊",  # FIX #14
        "invalid_address": "Please share a complete address (street + city). Example: 123 Main St, New York",  # FIX #18
        "pick_burger_first": "🍔 Let's pick a burger first, then I'll add the combo for $4.99!",  # FIX #2
        "choose_burger_deal": "Which burger for your Smash Meal Deal? 🍔",  # FIX #3
        "choose_pizza_deal": "Which pizza for your Pizza + Wings Deal? 🍕",
        "choose_2pizzas": "Pick your first pizza for the Family Deal 🍕",
        "choose_2nd_pizza": "Great! Now pick your second pizza 🍕",
        "pick_bbq_sides": "Pick 2 sides for your BBQ plate:",  # FIX #10
        "pick_ribs_sides": "Pick 2 sides for Ribs Night Deal:",
        "side_mac": "🧀 Mac & Cheese",
        "side_fries": "🍟 Fries",
        "side_slaw": "🥬 Coleslaw",
        "side_salad": "🥗 Caesar Salad",
        "removed_item": "✅ Removed from cart",  # FIX #39
        "deal_added": "🔥 Deal added to cart!",
        "thanks_reply": "You're welcome! 😊 Type *menu* anytime to order again.",
        "bye_reply": "Goodbye! Enjoy your meal! 🍔",
        "delivery_note_will_add": "🚚 *Note:* +$4.99 delivery fee if you choose delivery (FREE over $50)",  # FIX #13
        "delivery_note_free": "✨ *You qualify for free delivery!*",
        "change_mind": "Changed your mind about delivery/pickup?",  # FIX #19
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
        "delivery_info": "🚚 *توصيل* — 30-45 دقيقة | حد أدنى $30 | رسوم $4.99 (مجاني فوق $50)\n\n🏪 *استلام* — 15-20 دقيقة | حد أدنى $10",
        "save_room": "🍰 هل تريد حلوى؟",
        "yes_dessert": "🍰 نعم",
        "no_dessert": "✅ لا، متابعة",
        "yes_combo": "✅ نعم! أضف الكومبو",
        "no_combo": "❌ لا شكراً",
        "cancelled": "❌ تم إلغاء الطلب.\n\nاكتب *menu* للبدء.",
        "greeting_welcome": "أهلاً بك في Wild Bites! 🍔 مستعد للطلب؟",
        "add_more_items": "🍽️ أضف المزيد",
        "back": "⬅️ رجوع",
        "invalid_name": "من فضلك أدخل اسمك (حرفان على الأقل). 😊",
        "invalid_address": "من فضلك أدخل عنواناً كاملاً (الشارع + المدينة).",
        "pick_burger_first": "🍔 دعنا نختار برجر أولاً، ثم أضيف الكومبو مقابل $4.99!",
        "choose_burger_deal": "أي برجر تختار للوجبة؟ 🍔",
        "choose_pizza_deal": "أي بيتزا للعرض؟ 🍕",
        "choose_2pizzas": "اختر البيتزا الأولى 🍕",
        "choose_2nd_pizza": "رائع! اختر البيتزا الثانية 🍕",
        "pick_bbq_sides": "اختر طبقين جانبيين:",
        "pick_ribs_sides": "اختر طبقين جانبيين للضلوع:",
        "side_mac": "🧀 ماك آند تشيز",
        "side_fries": "🍟 بطاطا مقلية",
        "side_slaw": "🥬 كول سلو",
        "side_salad": "🥗 سلطة سيزر",
        "removed_item": "✅ تمت الإزالة",
        "deal_added": "🔥 أضيف العرض!",
        "thanks_reply": "على الرحب! 😊 اكتب *menu* للطلب مجدداً.",
        "bye_reply": "مع السلامة! استمتع بوجبتك! 🍔",
        "delivery_note_will_add": "🚚 *ملاحظة:* +$4.99 رسوم توصيل (مجاني فوق $50)",
        "delivery_note_free": "✨ *توصيل مجاني!*",
        "change_mind": "غيرت رأيك في التوصيل/الاستلام؟",
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
        "delivery_info": "🚚 *होम डिलीवरी* — 30-45 मिनट | न्यूनतम $30 | शुल्क $4.99 ($50+ पर मुफ्त)\n\n🏪 *पिकअप* — 15-20 मिनट | न्यूनतम $10",
        "save_room": "🍰 मिठाई के लिए जगह?",
        "yes_dessert": "🍰 हाँ",
        "no_dessert": "✅ नहीं",
        "yes_combo": "✅ हाँ! कॉम्बो",
        "no_combo": "❌ नहीं",
        "cancelled": "❌ ऑर्डर रद्द।\n\n*menu* टाइप करें।",
        "greeting_welcome": "Wild Bites में आपका स्वागत है! 🍔 ऑर्डर के लिए तैयार?",
        "add_more_items": "🍽️ और जोड़ें",
        "back": "⬅️ वापस",
        "invalid_name": "कृपया अपना नाम दर्ज करें (2+ अक्षर)। 😊",
        "invalid_address": "कृपया पूरा पता दें (गली + शहर)।",
        "pick_burger_first": "🍔 पहले बर्गर चुनें, फिर $4.99 में कॉम्बो जोड़ूंगा!",
        "choose_burger_deal": "कौनसा बर्गर? 🍔",
        "choose_pizza_deal": "कौनसा पिज़्ज़ा? 🍕",
        "choose_2pizzas": "पहला पिज़्ज़ा चुनें 🍕",
        "choose_2nd_pizza": "दूसरा पिज़्ज़ा चुनें 🍕",
        "pick_bbq_sides": "2 साइड चुनें:",
        "pick_ribs_sides": "रिब्स के लिए 2 साइड चुनें:",
        "side_mac": "🧀 मैक & चीज़",
        "side_fries": "🍟 फ्राइज़",
        "side_slaw": "🥬 कोलस्लॉ",
        "side_salad": "🥗 सीज़र सलाद",
        "removed_item": "✅ हटा दिया गया",
        "deal_added": "🔥 डील जोड़ी गई!",
        "thanks_reply": "आपका स्वागत है! 😊 फिर से ऑर्डर के लिए *menu* टाइप करें।",
        "bye_reply": "अलविदा! अपने खाने का आनंद लें! 🍔",
        "delivery_note_will_add": "🚚 *नोट:* +$4.99 डिलीवरी शुल्क ($50+ पर मुफ्त)",
        "delivery_note_free": "✨ *मुफ्त डिलीवरी!*",
        "change_mind": "डिलीवरी/पिकअप बदलना चाहते हैं?",
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
        "delivery_info": "🚚 *Livraison* — 30-45 min | Min $30 | Frais $4.99 (gratuit dès $50)\n\n🏪 *Retrait* — 15-20 min | Min $10",
        "save_room": "🍰 Un dessert?",
        "yes_dessert": "🍰 Oui",
        "no_dessert": "✅ Non",
        "yes_combo": "✅ Oui! Combo",
        "no_combo": "❌ Non merci",
        "cancelled": "❌ Commande annulée.\n\nTapez *menu*.",
        "greeting_welcome": "Bienvenue chez Wild Bites! 🍔 Prêt à commander?",
        "add_more_items": "🍽️ Ajouter plus",
        "back": "⬅️ Retour",
        "invalid_name": "Entrez votre prénom (2+ caractères). 😊",
        "invalid_address": "Adresse complète svp (rue + ville).",
        "pick_burger_first": "🍔 Choisissez un burger d'abord, puis j'ajoute le combo à $4.99!",
        "choose_burger_deal": "Quel burger? 🍔",
        "choose_pizza_deal": "Quelle pizza? 🍕",
        "choose_2pizzas": "Première pizza 🍕",
        "choose_2nd_pizza": "Deuxième pizza 🍕",
        "pick_bbq_sides": "2 accompagnements:",
        "pick_ribs_sides": "2 accompagnements pour les ribs:",
        "side_mac": "🧀 Mac & Cheese",
        "side_fries": "🍟 Frites",
        "side_slaw": "🥬 Coleslaw",
        "side_salad": "🥗 Salade César",
        "removed_item": "✅ Retiré du panier",
        "deal_added": "🔥 Offre ajoutée!",
        "thanks_reply": "Avec plaisir! 😊 Tapez *menu* pour commander à nouveau.",
        "bye_reply": "Au revoir! Bon appétit! 🍔",
        "delivery_note_will_add": "🚚 *Note:* +$4.99 livraison (gratuit dès $50)",
        "delivery_note_free": "✨ *Livraison gratuite!*",
        "change_mind": "Changer livraison/retrait?",
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
        "delivery_info": "🚚 *Lieferung* — 30-45 Min | Min $30 | Gebühr $4.99 (frei ab $50)\n\n🏪 *Abholung* — 15-20 Min | Min $10",
        "save_room": "🍰 Dessert?",
        "yes_dessert": "🍰 Ja",
        "no_dessert": "✅ Nein",
        "yes_combo": "✅ Ja! Combo",
        "no_combo": "❌ Nein danke",
        "cancelled": "❌ Storniert.\n\nTippen Sie *menu*.",
        "greeting_welcome": "Willkommen bei Wild Bites! 🍔 Bereit zu bestellen?",
        "add_more_items": "🍽️ Mehr hinzufügen",
        "back": "⬅️ Zurück",
        "invalid_name": "Bitte Namen eingeben (min. 2 Zeichen). 😊",
        "invalid_address": "Bitte vollständige Adresse (Straße + Stadt).",
        "pick_burger_first": "🍔 Erst Burger wählen, dann Combo für $4.99!",
        "choose_burger_deal": "Welcher Burger? 🍔",
        "choose_pizza_deal": "Welche Pizza? 🍕",
        "choose_2pizzas": "Erste Pizza 🍕",
        "choose_2nd_pizza": "Zweite Pizza 🍕",
        "pick_bbq_sides": "2 Beilagen wählen:",
        "pick_ribs_sides": "2 Beilagen für Rippchen:",
        "side_mac": "🧀 Mac & Cheese",
        "side_fries": "🍟 Pommes",
        "side_slaw": "🥬 Krautsalat",
        "side_salad": "🥗 Caesar Salat",
        "removed_item": "✅ Entfernt",
        "deal_added": "🔥 Angebot hinzugefügt!",
        "thanks_reply": "Gern geschehen! 😊 Tippen Sie *menu* zum erneut Bestellen.",
        "bye_reply": "Auf Wiedersehen! Guten Appetit! 🍔",
        "delivery_note_will_add": "🚚 *Hinweis:* +$4.99 Liefergebühr (frei ab $50)",
        "delivery_note_free": "✨ *Gratis Lieferung!*",
        "change_mind": "Lieferart ändern?",
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
        "delivery_info": "🚚 *Доставка* — 30-45 мин | Мин $30 | Плата $4.99 (бесплатно от $50)\n\n🏪 *Самовывоз* — 15-20 мин | Мин $10",
        "save_room": "🍰 Десерт?",
        "yes_dessert": "🍰 Да",
        "no_dessert": "✅ Нет",
        "yes_combo": "✅ Да! Комбо",
        "no_combo": "❌ Нет",
        "cancelled": "❌ Отменено.\n\nНапишите *menu*.",
        "greeting_welcome": "Добро пожаловать в Wild Bites! 🍔 Готовы заказать?",
        "add_more_items": "🍽️ Добавить ещё",
        "back": "⬅️ Назад",
        "invalid_name": "Введите имя (2+ символа). 😊",
        "invalid_address": "Пожалуйста, полный адрес (улица + город).",
        "pick_burger_first": "🍔 Сначала выберите бургер, потом добавлю комбо за $4.99!",
        "choose_burger_deal": "Какой бургер? 🍔",
        "choose_pizza_deal": "Какая пицца? 🍕",
        "choose_2pizzas": "Первая пицца 🍕",
        "choose_2nd_pizza": "Вторая пицца 🍕",
        "pick_bbq_sides": "2 гарнира:",
        "pick_ribs_sides": "2 гарнира к рёбрам:",
        "side_mac": "🧀 Мак & чиз",
        "side_fries": "🍟 Картофель фри",
        "side_slaw": "🥬 Капустный салат",
        "side_salad": "🥗 Салат Цезарь",
        "removed_item": "✅ Удалено",
        "deal_added": "🔥 Акция добавлена!",
        "thanks_reply": "Пожалуйста! 😊 Напишите *menu* для нового заказа.",
        "bye_reply": "До свидания! Приятного аппетита! 🍔",
        "delivery_note_will_add": "🚚 *Примечание:* +$4.99 доставка (бесплатно от $50)",
        "delivery_note_free": "✨ *Бесплатная доставка!*",
        "change_mind": "Изменить доставка/самовывоз?",
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
        "delivery_info": "🚚 *外卖* — 30-45分钟 | 最低$30 | 费用$4.99 ($50以上免费)\n\n🏪 *自取* — 15-20分钟 | 最低$10",
        "save_room": "🍰 来份甜点?",
        "yes_dessert": "🍰 是的",
        "no_dessert": "✅ 不用",
        "yes_combo": "✅ 是! 套餐",
        "no_combo": "❌ 不了",
        "cancelled": "❌ 已取消。\n\n输入*menu*。",
        "greeting_welcome": "欢迎光临Wild Bites! 🍔 准备下单?",
        "add_more_items": "🍽️ 继续添加",
        "back": "⬅️ 返回",
        "invalid_name": "请输入姓名 (至少2个字符)。😊",
        "invalid_address": "请输入完整地址 (街道+城市)。",
        "pick_burger_first": "🍔 先选汉堡, 再加$4.99套餐!",
        "choose_burger_deal": "哪款汉堡? 🍔",
        "choose_pizza_deal": "哪款披萨? 🍕",
        "choose_2pizzas": "第一款披萨 🍕",
        "choose_2nd_pizza": "第二款披萨 🍕",
        "pick_bbq_sides": "选2份配菜:",
        "pick_ribs_sides": "肋排2份配菜:",
        "side_mac": "🧀 芝士通心粉",
        "side_fries": "🍟 薯条",
        "side_slaw": "🥬 卷心菜沙拉",
        "side_salad": "🥗 凯撒沙拉",
        "removed_item": "✅ 已移除",
        "deal_added": "🔥 优惠已添加!",
        "thanks_reply": "不客气! 😊 输入*menu*再次下单。",
        "bye_reply": "再见! 用餐愉快! 🍔",
        "delivery_note_will_add": "🚚 *注:* +$4.99配送费 ($50以上免费)",
        "delivery_note_free": "✨ *免费配送!*",
        "change_mind": "更改配送方式?",
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
        "delivery_info": "🚚 *ഡെലിവറി* — 30-45 മിനിറ്റ് | മിനിമം $30 | ഫീ $4.99 ($50+ സൗജന്യം)\n\n🏪 *പിക്കപ്പ്* — 15-20 മിനിറ്റ് | മിനിമം $10",
        "save_room": "🍰 ഡെസേർട്ട്?",
        "yes_dessert": "🍰 അതെ",
        "no_dessert": "✅ വേണ്ട",
        "yes_combo": "✅ അതെ! കൊമ്പോ",
        "no_combo": "❌ വേണ്ട",
        "cancelled": "❌ റദ്ദാക്കി.\n\n*menu* ടൈപ്പ്.",
        "greeting_welcome": "Wild Bites-ലേക്ക് സ്വാഗതം! 🍔 ഓർഡർ ചെയ്യാൻ തയ്യാറോ?",
        "add_more_items": "🍽️ കൂടുതൽ ചേർക്കൂ",
        "back": "⬅️ തിരികെ",
        "invalid_name": "പേര് നൽകുക (2+ അക്ഷരങ്ങൾ). 😊",
        "invalid_address": "പൂർണ്ണ വിലാസം (റോഡ് + നഗരം).",
        "pick_burger_first": "🍔 ആദ്യം ബർഗർ തിരഞ്ഞെടുക്കൂ, പിന്നെ $4.99-ന് കൊമ്പോ!",
        "choose_burger_deal": "ഏത് ബർഗർ? 🍔",
        "choose_pizza_deal": "ഏത് പിസ്സ? 🍕",
        "choose_2pizzas": "ആദ്യ പിസ്സ 🍕",
        "choose_2nd_pizza": "രണ്ടാം പിസ്സ 🍕",
        "pick_bbq_sides": "2 സൈഡ്സ്:",
        "pick_ribs_sides": "റിബ്സിന് 2 സൈഡ്സ്:",
        "side_mac": "🧀 മാക് & ചീസ്",
        "side_fries": "🍟 ഫ്രൈസ്",
        "side_slaw": "🥬 കോൾസ്ലോ",
        "side_salad": "🥗 സീസർ സലാഡ്",
        "removed_item": "✅ നീക്കി",
        "deal_added": "🔥 ഓഫർ ചേർത്തു!",
        "thanks_reply": "സ്വാഗതം! 😊 വീണ്ടും ഓർഡറിനായി *menu* ടൈപ്പ്.",
        "bye_reply": "ബൈ! ഭക്ഷണം ആസ്വദിക്കൂ! 🍔",
        "delivery_note_will_add": "🚚 *കുറിപ്പ്:* +$4.99 ഡെലിവറി ($50+ സൗജന്യം)",
        "delivery_note_free": "✨ *സൗജന്യ ഡെലിവറി!*",
        "change_mind": "ഡെലിവറി/പിക്കപ്പ് മാറ്റണോ?",
    },
}

def t(lang, key):
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, key))

customer_sessions = {}
last_message_time = {}
saved_orders = {}
customer_order_lookup = {}  # FIX #22 — now list of order_ids per customer
manager_pending = {}
customer_profiles = {}

def new_session(sender=None, table_number=None):
    profile = customer_profiles.get(sender, {}) if sender else {}
    is_returning = bool(profile.get("name"))
    return {
        "stage": "returning" if is_returning else "lang_select",
        "lang": profile.get("lang", "en"),
        "order": {},
        "delivery_type": profile.get("delivery_type", ""),
        "table_number": table_number,
        "order_type": "dine_in" if table_number else "",
        "address": profile.get("address", ""),
        "name": profile.get("name", ""),
        "payment": profile.get("payment", ""),
        "last_added": None,
        "current_cat": None,
        "conversation": [],
        "upsell_declined_types": set(),  # FIX #9
        "upsell_shown_for": set(),  # FIX #4
        "order_id": None,
        "deal_context": None,  # FIX #3
        "post_order_at": 0,  # FIX #20
        # REMOVED: pending_combo (FIX #38), delay_warned (FIX #36), _last_text (FIX #37)
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
    # FIX #27 — store item_ids AND quantities
    profile = customer_profiles.get(sender, {"order_history": []})
    if "order_history" not in profile:
        profile["order_history"] = []
    profile["order_history"].append({
        "order_id": order_id,
        "items": [
            {"item_id": k, "name": v["item"]["name"], "qty": v["qty"]}
            for k, v in order_items.items()
        ],
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
            # Support both new (dict) and legacy (string) format
            name = item.get("name") if isinstance(item, dict) else item
            if name:
                item_counts[name] = item_counts.get(name, 0) + 1
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

# FIX #3 — deal composition rules
DEAL_RULES = {
    "DL1": {"requires": "burger_in_cart"},
    "DL2": {"picks": ["burger"]},
    "DL3": {"picks": ["pizza"]},
    "DL4": {"picks": ["pizza", "pizza"]},
    "DL5": {"picks": ["2sides"]},
    "DL6": {"picks": []},
}

BBQ_NEEDS_SIDES = {"BB1", "BB2", "BB4", "BB5"}  # FIX #10

SIDE_CHOICES = {
    "MAC": "Mac & Cheese",
    "FRIES": "Fries",
    "SLAW": "Coleslaw",
    "SALAD": "Caesar Salad",
}

MENU_SUMMARY = """
Wild Bites Restaurant Menu (US):
Deals, Burgers, Pizza, BBQ, Fish, Drinks, Sides, Desserts
Delivery: min $30, fee $4.99, free over $50 | Pickup: min $10
Hours: 10am-11pm daily
"""

def get_order_total(order):
    return sum(v["item"]["price"] * v["qty"] for v in order.values())

def get_delivery_fee(subtotal, delivery_type):
    # FIX #17 — free delivery over $50
    if delivery_type != "delivery":
        return 0.0
    if subtotal >= FREE_DELIVERY_THRESHOLD:
        return 0.0
    return DELIVERY_CHARGE

def get_order_text(order):
    if not order:
        return "Empty cart"
    lines = []
    for v in order.values():
        item = v["item"]
        base = f"{item['emoji']} {item['name']} x{v['qty']} — ${item['price'] * v['qty']:.2f}"
        lines.append(base)
        # FIX #3, #10 — show deal components and sides (use simple indent, WhatsApp-safe)
        for comp in v.get("components", []):
            lines.append(f"  • {comp}")
        for side in v.get("sides", []):
            lines.append(f"  • Side: {side}")
    return "\n".join(lines)

def find_item(item_id):
    for cat_key, cat_data in MENU.items():
        if item_id in cat_data["items"]:
            return cat_key, cat_data["items"][item_id]
    return None, None

def has_any_side(order): return any(k.startswith("SD") for k in order)
def has_any_drink(order): return any(k.startswith("DR") for k in order)
def has_any_dessert(order): return any(k.startswith("DS") for k in order)  # FIX #11
def has_any_main(order):  # FIX #5
    return any(k.startswith(("FF", "PZ", "BB", "FS")) for k in order)
def is_burger(item_id): return item_id.startswith("FF")
def is_pizza(item_id): return item_id.startswith("PZ")

def truncate_title(title, max_len=24):
    # FIX #7 — WhatsApp list title 24-char limit
    if len(title) <= max_len:
        return title
    return title[:max_len - 1] + "…"

def safe_btn(text, max_len=20):
    # WhatsApp button title 20-char limit
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"

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
    # EXPANDED: catch "how much time", "not arrived", "how long", "kab aayega" etc.
    keywords = [
        "order status", "where is my order", "where's my order",
        "wheres my order", "order update", "ready yet", "track my order",
        "how much time", "how long will", "how long it", "how long does",
        "not arrived", "not delivered", "not came", "didn't arrive", "didnt arrive",
        "haven't received", "havent received", "where's my food", "wheres my food",
        "where is my food", "where is my", "where's my",
        "when will", "kitna time", "kab aayega", "kab aaega", "kahan hai",
        "arrive", "arriving", "eta", "status of my",
    ]
    if any(w in text_lower for w in keywords):
        return True
    # Also catch explicit order number mentions: #12345, order 12345, my order #12345
    if re.search(r'(order|#)\s*#?\s*\d{5}', text_lower):
        return True
    return False

def extract_order_number(text):
    """Extract 5-digit order number from customer text."""
    m = re.search(r'\b(\d{5})\b', text or "")
    return int(m.group(1)) if m else None

def is_valid_name(text):
    # FIX #14
    t = text.strip()
    if len(t) < 2 or len(t) > 30:
        return False
    # reject button-like IDs (ALL_CAPS_UNDERSCORES)
    if re.match(r"^[A-Z_]+$", t):
        return False
    # reject common commands
    lower = t.lower()
    if lower in ["menu", "hi", "hello", "hey", "start", "back", "cancel", "help",
                 "yes", "no", "ok", "thanks", "thank you", "restart", "reset"]:
        return False
    # must contain at least one letter (supports Arabic/Hindi/CJK/Malayalam)
    if not re.search(r"[A-Za-z\u0600-\u06FF\u0900-\u097F\u4e00-\u9fff\u0D00-\u0D7F]", t):
        return False
    return True

def is_valid_address(text):
    # FIX #18
    t = text.strip()
    if len(t) < 8:
        return False
    lower = t.lower()
    has_digit = bool(re.search(r"\d", t))
    has_comma = "," in t
    has_word = any(w in lower for w in ["street", "st", "road", "rd", "ave", "avenue",
                                          "lane", "ln", "drive", "dr", "block", "building", "apt"])
    return has_digit or has_comma or has_word

def is_thanks(text_lower):
    return any(w in text_lower for w in ["thanks", "thank you", "thx", "ty"])

def is_bye(text_lower):
    return text_lower in ["bye", "goodbye", "cya", "see ya"]

def is_menu_request(text_lower):
    # FIX #34
    return text_lower in ["menu", "show menu", "see menu", "browse menu", "main menu",
                           "show me menu", "the menu"] or text_lower.startswith("menu ")


@app.get("/generate-qr/{table_number}")
async def generate_qr(table_number: int):
    """Generate QR code for a specific table"""
    import qrcode
    import io
    from base64 import b64encode
    
    # QR mein table ID + unique token encode karo
    qr_data = f"https://your-bot-domain.com/order?table={table_number}&session={random.randint(10000, 99999)}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save as base64
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return {
        "table_number": table_number,
        "qr_link": qr_data,
        "image_base64": b64encode(img_io.getvalue()).decode()
    }

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
                
                # ✅ CHECK IF QR SCAN (table param in text)
                table_match = re.search(r'table=(\d+)', text)
                if table_match:
                    table_num = int(table_match.group(1))
                    # New session with table
                    customer_sessions[sender] = new_session(sender, table_number=table_num)
                    session = customer_sessions[sender]
                    session["stage"] = "lang_select"
                    session["order_type"] = "dine_in"
                    await send_language_selection(sender)
                    return
                
                # FIX #25 — manager check REMOVED. Only ai-agent handles manager replies.
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
    try:
        await _handle_flow_inner(sender, text, is_button)
    except Exception as e:
        print(f"❌ handle_flow CRASHED for {sender} text={text!r}: {e}\n{traceback.format_exc()}")
        # Try to recover — send user something useful
        try:
            session = get_session(sender)
            lang = session.get("lang", "en")
            if session.get("order"):
                await send_cart_view(sender, session["order"], lang)
            else:
                await send_text_message(sender, "Sorry, something glitched on our end. Type *menu* to continue. 🙏")
        except Exception as inner:
            print(f"❌ Recovery also failed: {inner}")

async def _handle_flow_inner(sender, text, is_button=False):
    session = get_session(sender)
    stage = session["stage"]
    lang = session.get("lang", "en")
    text_lower = text.lower().strip()

    # FIX #20 — post_order window: handle as order-related for 3 mins
    if stage == "post_order":
        elapsed = time.time() - session.get("post_order_at", 0)
        if elapsed > POST_ORDER_WINDOW:
            customer_sessions[sender] = new_session(sender)
            session = customer_sessions[sender]
            stage = session["stage"]
        else:
            if is_order_status_query(text_lower):
                await handle_order_status(sender, session, lang, text)
                return
            if is_thanks(text_lower):
                await send_text_message(sender, t(lang, "thanks_reply"))
                return
            if is_bye(text_lower):
                await send_text_message(sender, t(lang, "bye_reply"))
                return
            if is_menu_request(text_lower) or text_lower in ["hi", "hello", "hey", "start"]:
                # customer wants to order again — reset session
                customer_sessions[sender] = new_session(sender)
                session = customer_sessions[sender]
                stage = session["stage"]
                # fall through to normal flow
            else:
                # unknown — AI reply only (no auto menu push)
                reply = await get_ai_response(sender, text, lang, session)
                await send_text_message(sender, reply)
                return

    # Hard reset
    if text_lower in ["restart", "reset", "start over", "clear"]:
        customer_sessions[sender] = new_session(sender)
        customer_sessions[sender]["stage"] = "lang_select"
        await send_language_selection(sender)
        return

    # FIX #23 — order status only when NOT in active ordering stages
    ordering_stages = {"items", "qty_control", "upsell_check", "upsell_combo", "confirm",
                       "get_name", "address", "delivery", "payment", "deal_build",
                       "bbq_sides", "repeat_confirm"}
    if is_order_status_query(text_lower) and stage not in ordering_stages:
        await handle_order_status(sender, session, lang, text)
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
                last_items_raw = last.get("items", [])
                names = []
                for it in last_items_raw:
                    if isinstance(it, dict):
                        names.append(f"{it['name']} x{it.get('qty', 1)}")
                    else:
                        names.append(it)
                last_items = ", ".join(names)
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
            await send_text_message(sender, "Sure! What's your new delivery address?")
        elif text == "REPEAT_CONFIRM":
            # FIX #27 — use item_id + qty
            profile = customer_profiles.get(sender, {})
            history = profile.get("order_history", [])
            if history:
                last_items = history[-1].get("items", [])
                for it in last_items:
                    if isinstance(it, dict):
                        iid = it.get("item_id")
                        qty = it.get("qty", 1)
                        if iid:
                            _cat, item = find_item(iid)
                            if item:
                                session["order"][iid] = {"item": item, "qty": qty}
                    else:
                        # legacy: match by name
                        for cat_data in MENU.values():
                            for item_id, item in cat_data["items"].items():
                                if item["name"] == it:
                                    session["order"][item_id] = {"item": item, "qty": 1}
            if session["order"]:
                # FIX #28 — still go via summary so min-order check happens at delivery choice
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
        if not is_valid_address(text):  # FIX #18
            await send_text_message(sender, t(lang, "invalid_address"))
            return
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
            # FIX #35 — hardcoded greeting, no AI call
            await send_text_message(sender, t(lang, "greeting_welcome"))
            await send_main_menu(sender, session["order"], lang)
        else:
            await send_language_selection(sender)
        return

    # ── UNIVERSAL BUTTONS ───────────────────────────────
    if text in ["SHOW_MENU", "BACK_MENU", "ADD_MORE"]:
        session["stage"] = "menu"
        await send_main_menu(sender, session["order"], lang)
        return

    # FIX #19 — back from payment to delivery choice
    if text == "BACK_TO_DELIVERY":
        session["stage"] = "delivery"
        session["delivery_type"] = ""
        await send_delivery_buttons(sender, session.get("name", ""), lang)
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

    # ── DEAL BUILD FLOW (FIX #3) ─────────────────────────
    if stage == "deal_build" and session.get("deal_context"):
        ctx = session["deal_context"]
        if text.startswith("DEAL_PICK_"):
            picked_id = text.replace("DEAL_PICK_", "").upper()
            _cat, picked_item = find_item(picked_id)
            if picked_item:
                ctx["picks"].append({"item_id": picked_id, "name": picked_item["name"]})
                needs = ctx["needs"]
                if len(ctx["picks"]) >= len(needs):
                    await finalize_deal(sender, session, lang)
                else:
                    next_kind = needs[len(ctx["picks"])]
                    await prompt_deal_pick(sender, session, next_kind, lang)
            return
        # Fallback — re-prompt current pick
        needs = ctx["needs"]
        if len(ctx["picks"]) < len(needs):
            await prompt_deal_pick(sender, session, needs[len(ctx["picks"])], lang)
        return

    # ── BBQ SIDES FLOW (FIX #10) ─────────────────────────
    if stage == "bbq_sides" and session.get("deal_context"):
        ctx = session["deal_context"]
        if text.startswith("SIDE_"):
            side_key = text.replace("SIDE_", "")
            if side_key in SIDE_CHOICES:
                ctx.setdefault("sides", []).append(SIDE_CHOICES[side_key])
                if len(ctx["sides"]) >= ctx.get("sides_needed", 2):
                    await finalize_bbq_sides(sender, session, lang)
                else:
                    await prompt_bbq_sides(sender, session, lang)
            return
        await prompt_bbq_sides(sender, session, lang)
        return

    # ── ITEM ADD ─────────────────────────────────────────
    if text.startswith("ADD_"):
        item_id = text.replace("ADD_", "").upper()
        cat, found_item = find_item(item_id)
        if not found_item:
            return

        # STUCK-STAGE GUARD: if user is tapping a new ADD_ button, they've moved on from
        # any pending upsell/deal prompt. Clean stale state so we don't drop messages.
        if stage in {"upsell_combo", "upsell_check"}:
            session.pop("_pending_upsell_type", None)
            session["stage"] = "items"
            stage = "items"

        # FIX #2 — DL1 requires burger in cart
        if item_id == "DL1":
            has_burger = any(k.startswith("FF") for k in session["order"])
            if not has_burger:
                await send_text_message(sender, t(lang, "pick_burger_first"))
                session["stage"] = "items"
                session["current_cat"] = "fastfood"
                session["deal_context"] = {"deal_id": "DL1_PENDING"}
                await send_category_items(sender, "fastfood", session["order"], lang)
                return
            if "DL1" in session["order"]:
                session["order"]["DL1"]["qty"] += 1
            else:
                session["order"]["DL1"] = {"item": found_item, "qty": 1}
            session["last_added"] = "DL1"
            session["stage"] = "qty_control"
            await send_text_message(sender, t(lang, "deal_added"))
            await send_qty_control(sender, "DL1", found_item, session["order"], lang)
            return

        # FIX #3 — multi-component deals
        if item_id in ["DL2", "DL3", "DL4", "DL5"]:
            rule = DEAL_RULES[item_id]
            session["stage"] = "deal_build"
            session["deal_context"] = {
                "deal_id": item_id,
                "deal_item": found_item,
                "needs": list(rule.get("picks", [])),
                "picks": [],
            }
            if rule.get("picks"):
                await prompt_deal_pick(sender, session, rule["picks"][0], lang)
            else:
                await finalize_deal(sender, session, lang)
            return

        if item_id == "DL6":
            # fixed composition — add directly
            if "DL6" in session["order"]:
                session["order"]["DL6"]["qty"] += 1
            else:
                session["order"]["DL6"] = {"item": found_item, "qty": 1, "components": ["Fish & Chips", "Soda"]}
            session["last_added"] = "DL6"
            session["stage"] = "qty_control"
            await send_text_message(sender, t(lang, "deal_added"))
            await send_qty_control(sender, "DL6", found_item, session["order"], lang)
            return

        # FIX #10 — BBQ items needing 2 sides
        if item_id in BBQ_NEEDS_SIDES:
            if item_id in session["order"]:
                session["order"][item_id]["qty"] += 1
                session["last_added"] = item_id
                session["stage"] = "qty_control"
                await send_qty_control(sender, item_id, found_item, session["order"], lang)
                return
            # fresh add — trigger sides picker
            session["order"][item_id] = {"item": found_item, "qty": 1, "sides": []}
            session["last_added"] = item_id
            session["stage"] = "bbq_sides"
            session["deal_context"] = {
                "deal_id": "BBQ_SIDES",
                "target_item_id": item_id,
                "sides_needed": 2,
                "sides": [],
            }
            await prompt_bbq_sides(sender, session, lang)
            return

        # Normal item add
        if item_id in session["order"]:
            session["order"][item_id]["qty"] += 1
        else:
            session["order"][item_id] = {"item": found_item, "qty": 1}
        session["last_added"] = item_id
        session["stage"] = "qty_control"

        # FIX #2 continued — DL1 pending? attach after burger added
        if (is_burger(item_id)
                and (session.get("deal_context") or {}).get("deal_id") == "DL1_PENDING"):
            dl1_item = MENU["deals"]["items"]["DL1"]
            if "DL1" in session["order"]:
                session["order"]["DL1"]["qty"] += 1
            else:
                session["order"]["DL1"] = {"item": dl1_item, "qty": 1}
            session["deal_context"] = None
            await send_text_message(sender, t(lang, "deal_added"))
            await send_qty_control(sender, item_id, found_item, session["order"], lang)
            return

        # FIX #4, #5, #8, #9 — smart upsells
        declined = session.get("upsell_declined_types", set())
        shown = session.get("upsell_shown_for", set())

        # Burger combo upsell: only on FIRST burger, no side/drink already, not declined, not combo-ed
        if (is_burger(item_id)
                and "burger_combo" not in declined
                and item_id not in shown
                and not has_any_side(session["order"])
                and not has_any_drink(session["order"])
                and "DL1" not in session["order"]):
            burgers_count = sum(1 for k in session["order"] if k.startswith("FF"))
            if burgers_count == 1:  # this is the first burger
                session["upsell_shown_for"].add(item_id)
                await send_quick_combo_upsell(sender, lang)
                return

        # Pizza wings upsell: no side, no declined
        if (is_pizza(item_id)
                and "pizza_wings" not in declined
                and item_id not in shown
                and "SD4" not in session["order"]
                and not has_any_side(session["order"])):
            session["upsell_shown_for"].add(item_id)
            await send_quick_upsell(sender, "SD4", "🍗 Add 6 wings with your pizza? Most people do! 😄", lang, "pizza_wings")
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
                    # FIX #39 — confirm removal, go to menu
                    removed_name = session["order"][item_id]["item"]["name"]
                    del session["order"][item_id]
                    await send_text_message(sender, f"{t(lang, 'removed_item')}: {removed_name}")
                    session["stage"] = "menu"
                    await send_main_menu(sender, session["order"], lang)
                    return
        if item_id and item_id in session["order"]:
            await send_qty_control(sender, item_id, session["order"][item_id]["item"], session["order"], lang)
        else:
            session["stage"] = "menu"
            await send_main_menu(sender, session["order"], lang)
        return

    # ── UPSELL ───────────────────────────────────────────
    if text == "SKIP_UPSELL":
        # FIX #9 — mark specific type declined
        ctx_type = session.get("_pending_upsell_type", "generic")
        session["upsell_declined_types"].add(ctx_type)
        session.pop("_pending_upsell_type", None)
        last = session.get("last_added")
        session["stage"] = "qty_control"
        if last and last in session["order"]:
            await send_qty_control(sender, last, session["order"][last]["item"], session["order"], lang)
        else:
            await send_main_menu(sender, session["order"], lang)
        return

    if text == "ADD_COMBO_DL1":
        deal_item = MENU["deals"]["items"]["DL1"]
        if "DL1" not in session["order"]:
            session["order"]["DL1"] = {"item": deal_item, "qty": 1}
        session.pop("_pending_upsell_type", None)
        last = session.get("last_added")
        session["stage"] = "qty_control"
        if last and last in session["order"]:
            await send_qty_control(sender, last, session["order"][last]["item"], session["order"], lang)
        else:
            await send_cart_view(sender, session["order"], lang)
        return

    # ── CHECKOUT ─────────────────────────────────────────
    if text == "CHECKOUT":
        if session["order"]:
            # FIX #11 — skip dessert upsell if dessert already in cart
            if (has_any_dessert(session["order"])
                    or "dessert" in session.get("upsell_declined_types", set())):
                session["stage"] = "confirm"
                await send_order_summary(sender, session["order"], lang)
            else:
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
            session["upsell_declined_types"].add("dessert")  # FIX #9
            session["stage"] = "confirm"
            await send_order_summary(sender, session["order"], lang)
        return

    # ── CONFIRM / CANCEL ─────────────────────────────────
    if text == "CONFIRM_ORDER":
        # FIX #15 — skip name ask if already known
        if session.get("name"):
            session["stage"] = "delivery"
            await send_delivery_buttons(sender, session["name"], lang)
        else:
            session["stage"] = "get_name"
            await send_text_message(sender, t(lang, "name_ask"))
        return

    if text == "CANCEL_ORDER":
        customer_sessions[sender] = new_session(sender)
        await send_text_message(sender, t(lang, "cancelled"))
        return


    # ✅ DINE-IN OPTION
    if text == "DINE_IN":
        session["delivery_type"] = "dine_in"
        table_num = session.get("table_number", "?")
        session["stage"] = "payment"
        await send_text_message(sender, f"🍽️ Perfect! Table {table_num} noted.\n\nNow choose payment method 👇")
        await send_payment_buttons(sender, session.get("name", ""), lang)
        return

        # ── DELIVERY / PICKUP ────────────────────────────────
    if text in ["DELIVERY", "PICKUP"]:
        total = get_order_total(session["order"])
        if text == "DELIVERY":
            if total < MIN_DELIVERY_ORDER:
                # FIX #16 — give add-more option
                await send_min_order_warning(sender, "delivery", lang)
                return
            session["delivery_type"] = "delivery"
            # FIX #15 — skip address if already saved
            if session.get("address"):
                session["stage"] = "payment"
                await send_text_message(sender, f"✅ Delivering to: {session['address']}")
                await send_payment_buttons(sender, session.get("name", ""), lang)
            else:
                session["stage"] = "address"
                await send_text_message(sender, f"📍 {t(lang, 'address_ask')}")
        else:
            if total < MIN_PICKUP_ORDER:
                await send_min_order_warning(sender, "pickup", lang)
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
        # FIX #20 — do NOT wipe session; enter post_order window
        session["stage"] = "post_order"
        session["post_order_at"] = time.time()
        return

    # ── STAGE TEXT ───────────────────────────────────────
    if stage == "get_name":
        if not is_valid_name(text):  # FIX #14
            await send_text_message(sender, t(lang, "invalid_name"))
            return
        session["name"] = text.strip().title()[:30]
        session["stage"] = "delivery"
        await send_delivery_buttons(sender, session["name"], lang)
        return

    if stage == "address":
        if not is_valid_address(text):  # FIX #18
            await send_text_message(sender, t(lang, "invalid_address"))
            return
        session["address"] = text.strip()
        session["stage"] = "payment"
        await send_text_message(sender, t(lang, "address_saved"))
        await send_payment_buttons(sender, session.get("name", ""), lang)
        return

    # ── GREETINGS ─────────────────────────────────────────
    if text_lower in ["hi", "hello", "hey", "start", "salam", "hola"]:
        if stage == "lang_select":
            await send_language_selection(sender)
        else:
            session["stage"] = "menu"
            # FIX #35 — hardcoded greeting, no AI
            await send_text_message(sender, t(lang, "greeting_welcome"))
            await send_main_menu(sender, session["order"], lang)
        return

    # FIX #34 — expand menu match
    if is_menu_request(text_lower):
        session["stage"] = "menu"
        await send_main_menu(sender, session["order"], lang)
        return

    # FIX #32 — exclude ALL checkout stages from category auto-routing
    cat_guess = guess_category(text_lower)
    protected_stages = {"get_name", "address", "payment", "delivery", "confirm",
                         "upsell_check", "upsell_combo", "bbq_sides", "deal_build"}
    if cat_guess and stage not in protected_stages:
        session["stage"] = "items"
        session["current_cat"] = cat_guess
        await send_category_items(sender, cat_guess, session["order"], lang)
        return

    # ── AI FALLBACK ───────────────────────────────────────
    # FIX #30 — pass conversation history
    # FIX #31 — removed auto menu suggestion
    session["conversation"].append({"role": "user", "content": text})
    reply = await get_ai_response(sender, text, lang, session)
    session["conversation"].append({"role": "assistant", "content": reply})
    session["conversation"] = session["conversation"][-8:]  # last 4 exchanges
    await send_text_message(sender, reply)

async def handle_order_status(sender, session, lang, text):
    # Try to extract order number from customer's message first
    order_id = extract_order_number(text)

    # Then fall back to session / lookup
    if not order_id:
        order_id = session.get("order_id")
    if not order_id:
        orders_list = customer_order_lookup.get(sender, [])
        if orders_list:
            order_id = orders_list[-1]

    if not order_id:
        await send_text_message(
            sender,
            "I don't see an active order for you. Type *menu* to place a new order! 😊"
        )
        return

    order_data = saved_orders.get(order_id)
    customer_name = (order_data or {}).get("customer_name", "")
    greet = f"Hi {customer_name}! " if customer_name else ""

    if not order_data:
        # Order number given but we don't have data — still reassure + escalate
        await send_text_message(
            sender,
            f"{greet}Let me check on order #{order_id} with our team right away! 🔍\n\n"
            f"I'll get back to you in a moment. Thank you for your patience! 🙏"
        )
        await notify_manager_status(order_id, sender, reason="Data missing")
        return

    elapsed_min = (time.time() - order_data["timestamp"]) / 60
    delivery_type = order_data.get("delivery_type", "pickup")
    expected_max = 45 if delivery_type == "delivery" else 20
    expected_min = 30 if delivery_type == "delivery" else 15

    elapsed_int = int(elapsed_min)

    # Case 1: Within expected time range — reassure with accurate ETA
    if elapsed_min < expected_min:
        remaining = expected_min - elapsed_int
        msg = (
            f"{greet}Your order #{order_id} is being prepared! 🍳\n\n"
            f"⏱️ *Expected in about {remaining}-{expected_max - elapsed_int} more minutes*\n\n"
            f"Our kitchen is working on it right now. Thanks for your patience! 😊"
        )
        await send_text_message(sender, msg)
        return

    # Case 2: Between min and max — approaching delivery
    if elapsed_min < expected_max:
        remaining = expected_max - elapsed_int
        if delivery_type == "delivery":
            msg = (
                f"{greet}Your order #{order_id} should be arriving any moment now! 🚚\n\n"
                f"⏱️ *Around {max(1, remaining)} more minutes* to reach you.\n\n"
                f"If it doesn't arrive soon, I'll check with the driver. Almost there! 😊"
            )
        else:
            msg = (
                f"{greet}Your order #{order_id} should be ready any moment! 🏪\n\n"
                f"⏱️ *Around {max(1, remaining)} more minutes*.\n\n"
                f"Feel free to head over — we'll have it hot and ready! 😊"
            )
        await send_text_message(sender, msg)
        return

    # Case 3: OVERDUE — apologize, reassure, escalate to manager urgently
    delay = elapsed_int - expected_max
    if delivery_type == "delivery":
        msg = (
            f"{greet}I'm really sorry your order #{order_id} hasn't arrived yet! 🙏\n\n"
            f"⏱️ It's been *{elapsed_int} minutes* — about {delay} mins longer than expected.\n\n"
            f"I'm reaching out to our team right now to check on the driver. "
            f"You'll have an update in the next few minutes. Thank you for your patience! 💚"
        )
    else:
        msg = (
            f"{greet}Sorry for the wait on order #{order_id}! 🙏\n\n"
            f"⏱️ It's been *{elapsed_int} minutes* — about {delay} mins longer than expected.\n\n"
            f"Let me check with the kitchen right now. I'll update you shortly! 💚"
        )
    await send_text_message(sender, msg)
    await notify_manager_status(order_id, sender, reason=f"OVERDUE by {delay} mins — customer waiting")

async def send_manager_action_list(order_id, customer_number, header_text, body_text, footer_text="Tap action to update customer"):
    """Send interactive list message to manager with one-tap status actions."""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}

    # WhatsApp limits: header ≤ 60 chars, body ≤ 1024 chars, footer ≤ 60 chars
    if len(body_text) > 1000:
        body_text = body_text[:997] + "…"
    if len(header_text) > 60:
        header_text = header_text[:59] + "…"
    if len(footer_text) > 60:
        footer_text = footer_text[:59] + "…"

    # IDs encode action so ai-agent can parse and forward to /manager-update
    rows = [
        {
            "id": f"MGR_{order_id}_READY",
            "title": "✅ Ready",
            "description": "Food is ready (pickup) / out for delivery"
        },
        {
            "id": f"MGR_{order_id}_OUTFORDELIVERY",
            "title": "🚚 Out for Delivery",
            "description": "Driver on the way to customer"
        },
        {
            "id": f"MGR_{order_id}_DELAYED15",
            "title": "⏱️ Delayed 15 min",
            "description": "Needs 15 more minutes"
        },
        {
            "id": f"MGR_{order_id}_DELAYED30",
            "title": "⏱️ Delayed 30 min",
            "description": "Needs 30 more minutes"
        },
        {
            "id": f"MGR_{order_id}_CANCELLED",
            "title": "❌ Cancelled",
            "description": "Cancel this order"
        },
    ]

    payload = {
        "messaging_product": "whatsapp",
        "to": MANAGER_NUMBER,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header_text},
            "body": {"text": body_text},
            "footer": {"text": footer_text},
            "action": {
                "button": "Update Status",
                "sections": [{
                    "title": f"Order #{order_id}",
                    "rows": rows
                }]
            }
        }
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, headers=headers) as r:
                resp = await r.text()
                if r.status >= 400:
                    print(f"❌ Manager list send FAILED {r.status}: {resp[:500]}")
                    # Fallback — send plain text with typed commands so manager isn't stuck
                    fallback = (
                        f"{body_text}\n\n"
                        f"Reply with:\n"
                        f"ORDER#{order_id} READY\n"
                        f"ORDER#{order_id} OUT FOR DELIVERY\n"
                        f"ORDER#{order_id} DELAYED 15\n"
                        f"ORDER#{order_id} CANCELLED"
                    )
                    await send_whatsapp_to_number(MANAGER_NUMBER, fallback)
                else:
                    print(f"Manager interactive list sent for #{order_id}")
    except Exception as e:
        print(f"❌ Manager list exception: {e}")

async def notify_manager(customer_number, session, order_id):
    order = session.get("order", {})
    total = get_order_total(order)
    tax = total * 0.08
    delivery_charge = get_delivery_fee(total, session.get("delivery_type"))  # FIX #17
    grand_total = total + tax + delivery_charge
    order_text = get_order_text(order)
    lang_name = LANG_NAMES.get(session.get("lang", "en"), "English")

    location_line = (
        f"📍 Delivery: {session.get('address', '')}"
        if session.get("delivery_type") == "delivery"
        else "🏪 Pickup"
    )
    eta_line = "30-45 mins" if session.get("delivery_type") == "delivery" else "15-20 mins"

    body_text = (
        f"🔔 *NEW ORDER #{order_id}*\n\n"
        f"👤 {session.get('name', 'N/A')}\n"
        f"📱 +{customer_number}\n"
        f"🌐 {lang_name}\n\n"
        f"{order_text}\n\n"
        f"Subtotal: ${total:.2f}\n"
        f"Tax: ${tax:.2f}\n"
        f"Delivery: ${delivery_charge:.2f}\n"
        f"*Total: ${grand_total:.2f}*\n\n"
        f"{location_line}\n"
        f"💳 {session.get('payment', 'N/A')}\n"
        f"⏱️ ETA: {eta_line}"
    )

    await send_manager_action_list(
        order_id=order_id,
        customer_number=customer_number,
        header_text=f"🔔 New Order #{order_id}",
        body_text=body_text,
        footer_text="Tap Update Status when ready"
    )
    print(f"Manager notified: #{order_id}")

async def notify_manager_status(order_id, customer_number, reason="Customer inquiry"):
    order_data = saved_orders.get(order_id, {})
    customer_name = order_data.get("customer_name", "Customer")
    delivery_type = order_data.get("delivery_type", "pickup")
    address = order_data.get("address", "")
    elapsed_min = 0
    if order_data.get("timestamp"):
        elapsed_min = int((time.time() - order_data["timestamp"]) / 60)

    location_line = f"📍 {address}" if address and delivery_type == "delivery" else "🏪 Pickup"

    body_text = (
        f"⚠️ *CUSTOMER WAITING — #{order_id}*\n\n"
        f"👤 {customer_name}\n"
        f"📱 +{customer_number}\n"
        f"⏱️ Placed *{elapsed_min} min ago*\n"
        f"🚚 {delivery_type.title()}\n"
        f"{location_line}\n\n"
        f"📢 {reason}"
    )

    await send_manager_action_list(
        order_id=order_id,
        customer_number=customer_number,
        header_text=f"⚠️ Waiting — #{order_id}",
        body_text=body_text,
        footer_text="Tap to update customer now"
    )

# FIX #25 — handle_manager_reply REMOVED. Manager replies live only in ai-agent.

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
    delivery_charge = get_delivery_fee(total, session.get("delivery_type"))  # FIX #17
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
    # FIX #22 — append to list, not overwrite
    customer_order_lookup.setdefault(customer_number, []).append(order_id)
    customer_order_lookup[customer_number] = customer_order_lookup[customer_number][-10:]
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

async def get_ai_response(sender, user_message, lang="en", session=None, extra_instruction=""):
    lang_name = LANG_NAMES.get(lang, "English")
    system_prompt = f"""You are Alex, a friendly customer service rep at Wild Bites Restaurant.
IMPORTANT: Always reply in {lang_name} only. Never mention you are AI.
Be warm, casual, helpful. Max 3 sentences. Use emojis naturally.
Hours: 10am-11pm. Delivery min $30 + $4.99 fee (free over $50). Pickup min $10.
{MENU_SUMMARY}
{extra_instruction}
If customer seems confused or stuck, guide them to next step clearly."""

    # FIX #30 — include conversation history
    messages = [{"role": "system", "content": system_prompt}]
    if session and session.get("conversation"):
        messages.extend(session["conversation"][-6:])
    messages.append({"role": "user", "content": user_message})

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": messages,
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
        # Fallback in customer's language
        return t(lang, "greeting_welcome")

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
            "header": {"type": "text", "text": "🍽️ Wild Bites Restaurant"},
            "body": {"text": f"{t(lang, 'menu_header')}\n{t(lang, 'craving')}{cart_text}"},
            "footer": {"text": "Fast Delivery | Fresh Food | Best Value"},
            "action": {
                "button": t(lang, "browse"),
                "sections": [
                    # FIX #33 — clearer category descriptions
                    {"title": "Start Here", "rows": [
                        {"id": "CAT_DEALS", "title": "Deals (Best Value)", "description": "Combo meals & bundles"},
                    ]},
                    {"title": "Main Course", "rows": [
                        {"id": "CAT_FASTFOOD", "title": "Burgers & Fast Food", "description": "Smash, chicken, BBQ bacon"},
                        {"id": "CAT_PIZZA", "title": "Pizza (12 inch)", "description": "Margherita, BBQ, Meat Lovers"},
                        {"id": "CAT_BBQ", "title": "BBQ", "description": "Ribs, brisket, pulled pork"},
                        {"id": "CAT_FISH", "title": "Fish & Seafood", "description": "Cod, salmon, shrimp"},
                    ]},
                    {"title": "Extras", "rows": [
                        {"id": "CAT_SIDES", "title": "Sides & Snacks", "description": "Fries, wings, nachos"},
                        {"id": "CAT_DRINKS", "title": "Drinks & Shakes", "description": "Sodas, shakes, juices"},
                        {"id": "CAT_DESSERTS", "title": "Desserts", "description": "Cake, cheesecake, sundae"},
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
        # FIX #7 — safe title truncation; move qty indicator to description
        title_base = f"{item['emoji']} {item['name']}"
        title = truncate_title(title_base, 24)
        desc_prefix = f"✓ In cart x{in_cart} · " if in_cart else ""
        desc_text = f"{desc_prefix}${item['price']:.2f} - {item['desc']}"
        if len(desc_text) > 72:
            desc_text = desc_text[:71] + "…"
        rows.append({
            "id": f"ADD_{item_id}",
            "title": title,
            "description": desc_text
        })

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": truncate_title(cat["name"], 60)},
            "body": {"text": f"{cat['name']}\n{t(lang, 'tap_add')}{cart_text}"},
            "footer": {"text": "Tap to add to cart"},
            "action": {"button": "Select Item", "sections": [{"title": truncate_title(cat["name"], 24), "rows": rows}]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()
            print(f"Category sent: {cat_key}")

async def send_qty_control(sender, item_id, item, order, lang="en"):
    # FIX #6 — ONE message only; Checkout button included directly
    qty = order.get(item_id, {}).get("qty", 1)
    subtotal = item["price"] * qty
    total = get_order_total(order)
    order_text = get_order_text(order)

    body_text = (
        f"*{item['name']}*\n"
        f"Qty: {qty} x ${item['price']:.2f} = *${subtotal:.2f}*\n\n"
        f"{t(lang, 'your_order')}\n{order_text}\n\n"
        f"{t(lang, 'total')} ${total:.2f}*"
    )
    if len(body_text) > 1000:
        body_text = body_text[:997] + "…"

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": truncate_title(f"{item['emoji']} {item['name']}", 60)},
            "body": {"text": body_text},
            "footer": {"text": f"Tap Checkout to complete"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "QTY_MINUS", "title": safe_btn(t(lang, "remove_one"))}},
                {"type": "reply", "reply": {"id": "ADD_MORE", "title": safe_btn(t(lang, "add_more"))}},
                {"type": "reply", "reply": {"id": "CHECKOUT", "title": safe_btn(f"{t(lang, 'checkout')} ${total:.2f}")}},
            ]}
        }
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, headers=headers) as r:
                resp = await r.text()
                if r.status >= 400:
                    print(f"❌ send_qty_control FAILED {r.status}: {resp[:500]}")
                    # Fallback: send cart view instead so customer isn't stuck
                    await send_cart_view(sender, order, lang)
    except Exception as e:
        print(f"❌ send_qty_control EXCEPTION: {e}")
        await send_cart_view(sender, order, lang)

async def send_quick_combo_upsell(sender, lang="en"):
    session = get_session(sender)
    session["stage"] = "upsell_combo"
    session["_pending_upsell_type"] = "burger_combo"  # FIX #9
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
                {"type": "reply", "reply": {"id": "ADD_COMBO_DL1", "title": safe_btn(t(lang, "yes_combo"))}},
                {"type": "reply", "reply": {"id": "SKIP_UPSELL", "title": safe_btn(t(lang, "no_combo"))}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

async def send_quick_upsell(sender, item_id, message, lang="en", upsell_type="generic"):
    session = get_session(sender)
    session["stage"] = "upsell_combo"
    session["_pending_upsell_type"] = upsell_type  # FIX #9
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": message},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": f"ADD_{item_id}", "title": safe_btn(t(lang, "yes_combo"))}},
                {"type": "reply", "reply": {"id": "SKIP_UPSELL", "title": safe_btn(t(lang, "no_combo"))}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

async def send_dessert_upsell(sender, order, lang="en"):
    total = get_order_total(order)
    # FIX #12 — build from MENU so it works for every language
    ds = MENU["desserts"]["items"]
    dessert_line = " | ".join([f"{v['emoji']} {v['name']} ${v['price']:.2f}" for v in list(ds.values())[:3]])
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "🍽️ Wild Bites Restaurant"},
            "body": {"text": f"{t(lang, 'save_room')}\n{t(lang, 'subtotal')} ${total:.2f}\n\n{dessert_line}"},
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "YES_UPSELL", "title": safe_btn(t(lang, "yes_dessert"))}},
                {"type": "reply", "reply": {"id": "NO_UPSELL", "title": safe_btn(t(lang, "no_dessert"))}},
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
            "header": {"type": "text", "text": "🍽️ Wild Bites Restaurant"},
            "body": {"text": f"{order_text}\n\n{t(lang, 'subtotal')} ${total:.2f}"},
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "CHECKOUT", "title": safe_btn(f"{t(lang, 'checkout')} ${total:.2f}")}},
                {"type": "reply", "reply": {"id": "ADD_MORE", "title": safe_btn(t(lang, "add_more"))}},
                {"type": "reply", "reply": {"id": "CANCEL_ORDER", "title": safe_btn(t(lang, "cancel"))}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

async def send_order_summary(sender, order, lang="en"):
    total = get_order_total(order)
    tax = total * 0.08
    # FIX #13 — disclose potential delivery fee up front
    if total >= FREE_DELIVERY_THRESHOLD:
        delivery_note = "\n" + t(lang, "delivery_note_free")
    else:
        delivery_note = "\n" + t(lang, "delivery_note_will_add")
    grand_total = total + tax
    order_text = get_order_text(order)

    body_text = (
        f"{order_text}\n\n"
        f"{t(lang, 'subtotal')} ${total:.2f}\n"
        f"{t(lang, 'tax')} ${tax:.2f}\n"
        f"{t(lang, 'grand_total')} ${grand_total:.2f}*"
        f"{delivery_note}"
    )
    if len(body_text) > 1000:
        body_text = body_text[:997] + "…"

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "🍽️ Wild Bites Restaurant"},
            "body": {"text": body_text},
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "CONFIRM_ORDER", "title": safe_btn(t(lang, "confirm"))}},
                {"type": "reply", "reply": {"id": "ADD_MORE", "title": safe_btn(t(lang, "add_more"))}},
                {"type": "reply", "reply": {"id": "CANCEL_ORDER", "title": safe_btn(t(lang, "cancel"))}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

async def send_delivery_buttons(sender, name, lang="en"):
    session = get_session(sender)
    table_num = session.get("table_number")
    
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    
    # ✅ DINE-IN KE LIYE ALAG BUTTONS
    if table_num:
        body_text = f"Hey {name}! You're at Table {table_num} 🍽️\n\nReady to order?"
        buttons = [
            {"type": "reply", "reply": {"id": "DINE_IN", "title": safe_btn(t(lang, "dine_in"))}},
            {"type": "reply", "reply": {"id": "PICKUP", "title": safe_btn("Takeaway")}},
        ]
    else:
        body_text = f"Hey {name}! Delivery or Pickup?\n\n{t(lang, 'delivery_info')}"
        buttons = [
            {"type": "reply", "reply": {"id": "DELIVERY", "title": safe_btn(t(lang, "delivery"))}},
            {"type": "reply", "reply": {"id": "PICKUP", "title": safe_btn(t(lang, "pickup"))}},
        ]
    
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "🍽️ Wild Bites Restaurant"},
            "body": {"text": body_text},
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {"buttons": buttons}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

async def send_min_order_warning(sender, dtype, lang="en"):
    # FIX #16 — min-order warning with Add More + alt option
    key = "min_delivery" if dtype == "delivery" else "min_pickup"
    alt_id = "PICKUP" if dtype == "delivery" else "DELIVERY"
    alt_label = t(lang, "pickup") if dtype == "delivery" else t(lang, "delivery")

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": t(lang, key)},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "ADD_MORE", "title": safe_btn(t(lang, "add_more_items"))}},
                {"type": "reply", "reply": {"id": alt_id, "title": safe_btn(alt_label)}},
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
                {"type": "reply", "reply": {"id": "CASH", "title": safe_btn(t(lang, "cash"))}},
                {"type": "reply", "reply": {"id": "CARD", "title": safe_btn(t(lang, "card"))}},
                {"type": "reply", "reply": {"id": "APPLE_PAY", "title": safe_btn(t(lang, "apple_pay"))}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

    # FIX #19 — separate Back button
    back_payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": t(lang, "change_mind")},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "BACK_TO_DELIVERY", "title": safe_btn(t(lang, "back"))}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=back_payload, headers=headers) as r:
            _ = await r.text()

async def send_order_confirmed(sender, session_data, lang="en"):
    order = session_data.get("order", {})
    total = get_order_total(order)
    tax = total * 0.08
    delivery_charge = get_delivery_fee(total, session_data.get("delivery_type"))  # FIX #17
    grand_total = total + tax + delivery_charge
    order_text = get_order_text(order)
    delivery_type = session_data.get("delivery_type", "pickup")

    # FIX #21 — guarantee unique order_id
    while True:
        order_id = random.randint(10000, 99999)
        if order_id not in saved_orders:
            break

    if delivery_type == "dine_in":
        table_num = session_data.get("table_number", "?")
        location_text = f"🍽️ Table {table_num}"
        eta = "10-15 minutes"
    else:
        eta = "30-45 minutes" if delivery_type == "delivery" else "15-20 minutes"
        location_text = f"{'Delivery: ' + session_data.get('address', '') if delivery_type == 'delivery' else 'Store Pickup'}"
    
    delivery_fee_line = f"\n{t(lang, 'delivery_charge')} ${delivery_charge:.2f}" if delivery_charge > 0 else ""

    msg = f"""{t(lang, 'order_confirmed')}, {session_data.get('name', 'Customer')}! #{order_id}*

{order_text}

{t(lang, 'subtotal')} ${total:.2f}
{t(lang, 'tax')} ${tax:.2f}{delivery_fee_line}
{t(lang, 'grand_total')} ${grand_total:.2f}*

{location_text}
Payment: {session_data.get('payment', '')}
{t(lang, 'ready_in')} *{eta}*

{t(lang, 'thank_you')}"""

    await send_text_message(sender, msg)
    return order_id

async def send_returning_customer_menu(sender, name, fav_text, lang="en"):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": "🍽️ Wild Bites Restaurant"},
            "body": {"text": f"Welcome back, {name}! Great to see you again!{fav_text}\n\nWhat would you like to do today?"},
            "footer": {"text": "Wild Bites Restaurant"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": "REPEAT_ORDER", "title": safe_btn("Repeat Last Order")}},
                {"type": "reply", "reply": {"id": "NEW_ORDER", "title": safe_btn("New Order")}},
                {"type": "reply", "reply": {"id": "CHANGE_ADDRESS", "title": safe_btn("Change Address")}},
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
                {"type": "reply", "reply": {"id": "REPEAT_CONFIRM", "title": safe_btn("Yes, Same Order!")}},
                {"type": "reply", "reply": {"id": "REPEAT_ADD_MORE", "title": safe_btn("Add More Items")}},
                {"type": "reply", "reply": {"id": "NEW_ORDER", "title": safe_btn("Start Fresh")}},
            ]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()
            print("Repeat order confirm sent")

# ── DEAL FLOW HELPERS (FIX #3) ─────────────────────────────
async def prompt_deal_pick(sender, session, kind, lang="en"):
    ctx = session["deal_context"]
    deal_id = ctx["deal_id"]

    if kind == "burger":
        cat_key = "fastfood"
        prompt_key = "choose_burger_deal"
    elif kind == "pizza":
        already = sum(1 for p in ctx["picks"] if p.get("item_id", "").startswith("PZ"))
        cat_key = "pizza"
        if deal_id == "DL4":
            prompt_key = "choose_2nd_pizza" if already >= 1 else "choose_2pizzas"
        else:
            prompt_key = "choose_pizza_deal"
    elif kind == "2sides":
        # DL5: use same sides picker as BBQ
        session["stage"] = "bbq_sides"
        ctx["sides_needed"] = 2
        ctx.setdefault("sides", [])
        await prompt_bbq_sides(sender, session, lang)
        return
    else:
        return

    cat = MENU[cat_key]
    rows = []
    for item_id, item in cat["items"].items():
        title = truncate_title(f"{item['emoji']} {item['name']}", 24)
        desc = f"${item['price']:.2f} - {item['desc']}"
        if len(desc) > 72:
            desc = desc[:71] + "…"
        rows.append({
            "id": f"DEAL_PICK_{item_id}",
            "title": title,
            "description": desc,
        })

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": truncate_title(ctx["deal_item"]["name"], 60)},
            "body": {"text": t(lang, prompt_key)},
            "footer": {"text": "Deal Builder"},
            "action": {"button": "Select", "sections": [{"title": truncate_title(cat["name"], 24), "rows": rows}]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

async def finalize_deal(sender, session, lang="en"):
    ctx = session["deal_context"]
    deal_id = ctx["deal_id"]
    deal_item = ctx["deal_item"]
    components = [p["name"] for p in ctx.get("picks", [])]

    # Deal-specific extras
    if deal_id == "DL2":
        components = components + ["Fries", "Soda"]
    elif deal_id == "DL3":
        components = components + ["6 Wings"]
    elif deal_id == "DL4":
        components = components + ["2 Sodas"]

    order_entry = {"item": deal_item, "qty": 1, "components": components}

    # Unique key so multiple deals don't collide
    key = deal_id
    n = 1
    while key in session["order"]:
        n += 1
        key = f"{deal_id}#{n}"
    session["order"][key] = order_entry
    session["last_added"] = key

    session["deal_context"] = None
    session["stage"] = "qty_control"
    await send_text_message(sender, t(lang, "deal_added"))
    await send_qty_control(sender, key, deal_item, session["order"], lang)

# ── BBQ SIDES HELPERS (FIX #10) ────────────────────────────
async def prompt_bbq_sides(sender, session, lang="en"):
    ctx = session["deal_context"]
    picked_so_far = ctx.get("sides", [])
    needed = ctx.get("sides_needed", 2)
    remaining = needed - len(picked_so_far)
    prompt_key = "pick_ribs_sides" if ctx.get("deal_id") == "DL5" else "pick_bbq_sides"
    progress = f" ({len(picked_so_far)}/{needed} picked)" if picked_so_far else ""

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    rows = [
        {"id": "SIDE_MAC", "title": truncate_title(t(lang, "side_mac"), 24), "description": "Creamy and cheesy"},
        {"id": "SIDE_FRIES", "title": truncate_title(t(lang, "side_fries"), 24), "description": "Crispy golden"},
        {"id": "SIDE_SLAW", "title": truncate_title(t(lang, "side_slaw"), 24), "description": "Fresh crunch"},
        {"id": "SIDE_SALAD", "title": truncate_title(t(lang, "side_salad"), 24), "description": "Classic greens"},
    ]
    payload = {
        "messaging_product": "whatsapp", "to": sender, "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": "🍖 Choose Your Sides"},
            "body": {"text": f"{t(lang, prompt_key)}{progress}"},
            "footer": {"text": f"Pick {remaining} more"},
            "action": {"button": "Pick Side", "sections": [{"title": "Sides", "rows": rows}]}
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            _ = await r.text()

async def finalize_bbq_sides(sender, session, lang="en"):
    ctx = session["deal_context"]
    sides = ctx.get("sides", [])

    if ctx.get("deal_id") == "DL5":
        # Ribs Night Deal
        deal_item = MENU["deals"]["items"]["DL5"]
        components = ["Half Rack Ribs"] + sides + ["Soda"]
        key = "DL5"
        n = 1
        while key in session["order"]:
            n += 1
            key = f"DL5#{n}"
        session["order"][key] = {"item": deal_item, "qty": 1, "components": components}
        session["last_added"] = key
        session["deal_context"] = None
        session["stage"] = "qty_control"
        await send_text_message(sender, t(lang, "deal_added"))
        await send_qty_control(sender, key, deal_item, session["order"], lang)
        return

    # Plain BBQ item with sides
    target_id = ctx.get("target_item_id")
    if target_id and target_id in session["order"]:
        session["order"][target_id]["sides"] = sides
        session["last_added"] = target_id
        session["stage"] = "qty_control"
        session["deal_context"] = None
        item = session["order"][target_id]["item"]
        await send_text_message(sender, f"✅ Sides locked in: {', '.join(sides)}")
        await send_qty_control(sender, target_id, item, session["order"], lang)

async def send_text_message(to, message):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": message}}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, headers=headers) as r:
                resp = await r.text()
                if r.status >= 400:
                    print(f"❌ send_text_message FAILED {r.status}: {resp[:500]}")
                else:
                    print(f"Text sent to {to}")
    except Exception as e:
        print(f"❌ send_text_message EXCEPTION: {e}")

@app.post("/manager-update")
async def manager_update(request: Request):
    """Receive manager order status updates from AI agent"""
    data = await request.json()
    order_id_str = str(data.get("order_id", ""))
    status = data.get("status", "").upper()
    print(f"Manager update: Order #{order_id_str} -> {status}")

    try:
        order_id = int(order_id_str)
        customer_number = manager_pending.get(order_id)
        if not customer_number:
            print(f"No customer for order #{order_id}")
            return {"status": "not_found"}

        order_data = saved_orders.get(order_id, {})
        customer_name = order_data.get("customer_name", "Customer")

        if "READY" in status and "DELIVERY" not in status:
            if order_data.get("delivery_type") == "pickup":
                msg = f"Great news, {customer_name}! Your order #{order_id} is *READY for pickup!* Please come collect it"
            else:
                msg = f"Great news, {customer_name}! Your order #{order_id} is ready and *OUT FOR DELIVERY* Should arrive in 15-20 minutes!"
        elif "OUT FOR DELIVERY" in status or "ON THE WAY" in status:
            msg = f"Hey {customer_name}! Your order #{order_id} is *on the way!* Should arrive in 15-20 minutes!"
        elif "DELAYED" in status:
            # Support both "DELAYED 15" (typed) and "DELAYED15" (button id)
            delay_match = re.search(r'DELAYED\s*(\d+)', status)
            delay_time = delay_match.group(1) + " minutes" if delay_match else "a little longer"
            msg = f"Hi {customer_name}, your order #{order_id} will take *{delay_time}* more than expected. Sorry for the wait! 🙏"
        elif "CANCELLED" in status:
            msg = f"Hi {customer_name}, unfortunately order #{order_id} has been *cancelled*. Please contact us for a refund."
        else:
            msg = f"Update on your order #{order_id}: {status}"

        await send_whatsapp_to_number(str(customer_number), msg)
        print(f"Customer {customer_number} updated for order #{order_id}")

        # Send confirmation back to manager so they know the tap was received
        try:
            status_label = status
            if "READY" in status and "DELIVERY" not in status:
                status_label = "READY"
            elif "OUT FOR DELIVERY" in status:
                status_label = "OUT FOR DELIVERY"
            elif "DELAYED" in status:
                m = re.search(r'DELAYED\s*(\d+)', status)
                status_label = f"DELAYED {m.group(1)} min" if m else "DELAYED"
            elif "CANCELLED" in status:
                status_label = "CANCELLED"
            confirm_msg = f"✅ Order #{order_id} marked as *{status_label}*\n\nCustomer {customer_name} has been notified."
            await send_whatsapp_to_number(MANAGER_NUMBER, confirm_msg)
        except Exception as e:
            print(f"Manager confirmation send failed: {e}")

        return {"status": "ok"}
    except Exception as e:
        print(f"Manager update error: {e}")
        return {"status": "error"}

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
    uvicorn.run(app, host="0.0.0.0", port=port)