# flow.py - Complete conversation logic for restaurant bot
import time
import random
import re
import traceback
from db import (
    customer_sessions, saved_ orders, customer_profiles,
    customer_order_lookup, manager_pending
)
from config import (
    POST_ORDER_WINDOW, MIN_DELIVERY_ORDER, MIN_PICKUP_ORDER,
    LANG_NAMES, FREE_DELIVERY_THRESHOLD, DELIVERY_CHARGE
)
from strings import t
from utils import (
    get_order_total, get_delivery_fee, get_order_text, find_item,
    is_burger, is_pizza, has_any_side, has_any_drink, has_any_dessert,
    is_valid_name, is_valid_address, is_order_status_query, is_thanks, is_bye,
    is_menu_request, guess_category, extract_order_number, truncate_title, safe_btn
)
from whatsapp_handlers import (
    send_text_message, send_language_selection, send_main_menu,
    send_category_items, send_qty_control, send_cart_view,
    send_order_summary, send_delivery_buttons, send_payment_buttons,
    send_order_confirmed, send_quick_combo_upsell, send_quick_upsell,
    send_dessert_upsell, send_min_order_warning, send_returning_customer_menu,
    send_repeat_order_confirm, send_manager_action_list, send_whatsapp_to_number
)
from stripe_utils import create_stripe_checkout_session
from ai_utils import get_ai_response
from menu_data import MENU

# Global constants that were originally in main.py
DEAL_RULES = {
    "DL1": {"requires": "burger_in_cart"},
    "DL2": {"picks": ["burger"]},
    "DL3": {"picks": ["pizza"]},
    "DL4": {"picks": ["pizza", "pizza"]},
    "DL5": {"picks": ["2sides"]},
    "DL6": {"picks": []},
}

BBQ_NEEDS_SIDES = {"BB1", "BB2", "BB4", "BB5"}

SIDE_CHOICES = {
    "MAC": "Mac & Cheese",
    "FRIES": "Fries",
    "SLAW": "Coleslaw",
    "SALAD": "Caesar Salad",
}

# ========== Session management ==========
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
        "upsell_declined_types": set(),
        "upsell_shown_for": set(),
        "order_id": None,
        "deal_context": None,
        "post_order_at": 0,
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
            name = item.get("name") if isinstance(item, dict) else item
            if name:
                item_counts[name] = item_counts.get(name, 0) + 1
    sorted_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)
    return [item for item, count in sorted_items[:3]]

# ========== Deal and side helpers ==========
async def prompt_deal_pick(sender, session, kind, lang="en"):
    import aiohttp
    from config import WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID
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
    if deal_id == "DL2":
        components = components + ["Fries", "Soda"]
    elif deal_id == "DL3":
        components = components + ["6 Wings"]
    elif deal_id == "DL4":
        components = components + ["2 Sodas"]
    order_entry = {"item": deal_item, "qty": 1, "components": components}
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

async def prompt_bbq_sides(sender, session, lang="en"):
    import aiohttp
    from config import WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID
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
    target_id = ctx.get("target_item_id")
    if target_id and target_id in session["order"]:
        session["order"][target_id]["sides"] = sides
        session["last_added"] = target_id
        session["stage"] = "qty_control"
        session["deal_context"] = None
        item = session["order"][target_id]["item"]
        await send_text_message(sender, f"✅ Sides locked in: {', '.join(sides)}")
        await send_qty_control(sender, target_id, item, session["order"], lang)

# ========== Main flow handler ==========
async def _handle_flow_inner(sender, text, is_button=False):
    session = get_session(sender)
    stage = session["stage"]
    lang = session.get("lang", "en")
    text_lower = text.lower().strip()

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
                customer_sessions[sender] = new_session(sender)
                session = customer_sessions[sender]
                stage = session["stage"]
            else:
                reply = await get_ai_response(sender, text, lang, session)
                await send_text_message(sender, reply)
                return

    if text_lower in ["restart", "reset", "start over", "clear"]:
        customer_sessions[sender] = new_session(sender)
        customer_sessions[sender]["stage"] = "lang_select"
        await send_language_selection(sender)
        return

    ordering_stages = {"items", "qty_control", "upsell_check", "upsell_combo", "confirm",
                       "get_name", "address", "delivery", "payment", "deal_build",
                       "bbq_sides", "repeat_confirm"}
    if is_order_status_query(text_lower) and stage not in ordering_stages:
        await handle_order_status(sender, session, lang, text)
        return

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
            profile = customer_profiles.get(sender, {})
            history = profile.get("order_history", [])
            if history:
                last_items = history[-1].get("items", [])
                for it in last_items:
                    if isinstance(it, dict):
                        iid = it.get("item_id")
                        qty = it.get("qty", 1)
                        if iid:
                            _cat, item = find_item(iid, MENU)
                            if item:
                                session["order"][iid] = {"item": item, "qty": qty}
                    else:
                        for cat_data in MENU.values():
                            for item_id, item in cat_data["items"].items():
                                if item["name"] == it:
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
        if not is_valid_address(text):
            await send_text_message(sender, t(lang, "invalid_address"))
            return
        session["address"] = text.strip()
        save_profile(sender, session)
        await send_text_message(sender, f"Address updated! {text}")
        session["stage"] = "menu"
        await send_main_menu(sender, session["order"], lang)
        return

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
            await send_text_message(sender, t(lang, "greeting_welcome"))
            await send_main_menu(sender, session["order"], lang)
        else:
            await send_language_selection(sender)
        return

    if text in ["SHOW_MENU", "BACK_MENU", "ADD_MORE"]:
        session["stage"] = "menu"
        await send_main_menu(sender, session["order"], lang)
        return

    if text == "BACK_TO_DELIVERY":
        session["stage"] = "delivery"
        session["delivery_type"] = ""
        await send_delivery_buttons(sender, session.get("name", ""), lang)
        return

    m_remove = re.match(r"^(remove|delete)\s+([a-z0-9]+)$", text_lower)
    if m_remove:
        item_id = m_remove.group(2).upper()
        if item_id in session["order"]:
            del session["order"][item_id]
        await send_cart_view(sender, session["order"], lang)
        return

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

    if stage == "deal_build" and session.get("deal_context"):
        ctx = session["deal_context"]
        if text.startswith("DEAL_PICK_"):
            picked_id = text.replace("DEAL_PICK_", "").upper()
            _cat, picked_item = find_item(picked_id, MENU)
            if picked_item:
                ctx["picks"].append({"item_id": picked_id, "name": picked_item["name"]})
                needs = ctx["needs"]
                if len(ctx["picks"]) >= len(needs):
                    await finalize_deal(sender, session, lang)
                else:
                    next_kind = needs[len(ctx["picks"])]
                    await prompt_deal_pick(sender, session, next_kind, lang)
            return
        needs = ctx["needs"]
        if len(ctx["picks"]) < len(needs):
            await prompt_deal_pick(sender, session, needs[len(ctx["picks"])], lang)
        return

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

    if text.startswith("ADD_"):
        item_id = text.replace("ADD_", "").upper()
        cat, found_item = find_item(item_id, MENU)
        if not found_item:
            return

        if stage in {"upsell_combo", "upsell_check"}:
            session.pop("_pending_upsell_type", None)
            session["stage"] = "items"
            stage = "items"

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
            if "DL6" in session["order"]:
                session["order"]["DL6"]["qty"] += 1
            else:
                session["order"]["DL6"] = {"item": found_item, "qty": 1, "components": ["Fish & Chips", "Soda"]}
            session["last_added"] = "DL6"
            session["stage"] = "qty_control"
            await send_text_message(sender, t(lang, "deal_added"))
            await send_qty_control(sender, "DL6", found_item, session["order"], lang)
            return

        if item_id in BBQ_NEEDS_SIDES:
            if item_id in session["order"]:
                session["order"][item_id]["qty"] += 1
                session["last_added"] = item_id
                session["stage"] = "qty_control"
                await send_qty_control(sender, item_id, found_item, session["order"], lang)
                return
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

        if item_id in session["order"]:
            session["order"][item_id]["qty"] += 1
        else:
            session["order"][item_id] = {"item": found_item, "qty": 1}
        session["last_added"] = item_id
        session["stage"] = "qty_control"

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

        declined = session.get("upsell_declined_types", set())
        shown = session.get("upsell_shown_for", set())

        if (is_burger(item_id)
                and "burger_combo" not in declined
                and item_id not in shown
                and not has_any_side(session["order"])
                and not has_any_drink(session["order"])
                and "DL1" not in session["order"]):
            burgers_count = sum(1 for k in session["order"] if k.startswith("FF"))
            if burgers_count == 1:
                session["upsell_shown_for"].add(item_id)
                await send_quick_combo_upsell(sender, lang)
                return

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

    if text in ["QTY_PLUS", "QTY_MINUS"]:
        item_id = session.get("last_added")
        if item_id and item_id in session["order"]:
            if text == "QTY_PLUS":
                session["order"][item_id]["qty"] += 1
            else:
                if session["order"][item_id]["qty"] > 1:
                    session["order"][item_id]["qty"] -= 1
                else:
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

    if text == "SKIP_UPSELL":
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

    if text == "CHECKOUT":
        if session["order"]:
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

    if text in ["YES_UPSELL", "NO_UPSELL"]:
        if text == "YES_UPSELL":
            session["stage"] = "items"
            session["current_cat"] = "desserts"
            await send_category_items(sender, "desserts", session["order"], lang)
        else:
            session["upsell_declined_types"].add("dessert")
            session["stage"] = "confirm"
            await send_order_summary(sender, session["order"], lang)
        return

    if text == "CONFIRM_ORDER":
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

    if text == "DINE_IN":
        session["delivery_type"] = "dine_in"
        table_num = session.get("table_number", "?")
        session["stage"] = "payment"
        await send_text_message(sender, f"🍽️ Perfect! Table {table_num} noted.\n\nNow choose payment method 👇")
        await send_payment_buttons(sender, session.get("name", ""), lang)
        return

    if text in ["DELIVERY", "PICKUP"]:
        total = get_order_total(session["order"])
        if text == "DELIVERY":
            if total < MIN_DELIVERY_ORDER:
                await send_min_order_warning(sender, "delivery", lang)
                return
            session["delivery_type"] = "delivery"
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

    # ── PAYMENT BLOCK ──
    if text in ["CASH", "CARD_STRIPE", "APPLE_PAY"]:
        payment_map = {"CASH": t(lang, "cash"), "CARD_STRIPE": t(lang, "card"), "APPLE_PAY": t(lang, "apple_pay")}
        session["payment"] = payment_map[text]

        if text == "CARD_STRIPE":
            total = get_order_total(session["order"])
            tax = total * 0.08
            delivery_charge = get_delivery_fee(total, session.get("delivery_type"))
            grand_total = total + tax + delivery_charge

            order_id = str(int(time.time()))
            saved_orders[order_id] = {
                "order": session["order"],
                "sender": sender,
                "customer_name": session.get("name", ""),
                "delivery_type": session.get("delivery_type", ""),
                "address": session.get("address", ""),
                "timestamp": time.time()
            }

            payment_url = await create_stripe_checkout_session(order_id, grand_total)
            if payment_url:
                await send_text_message(sender, f"💳 Pay here:\n{payment_url}")
            else:
                await send_text_message(sender, "❌ Payment link creation failed. Please try again or choose another payment method.")
            return

        order_id = await send_order_confirmed(sender, session, lang)
        session["order_id"] = order_id
        save_profile(sender, session)
        add_to_order_history(sender, order_id, session["order"])
        await notify_manager(sender, session, order_id)
        await save_to_sheet(sender, session, order_id)
        session["stage"] = "post_order"
        session["post_order_at"] = time.time()
        return

    if stage == "get_name":
        if not is_valid_name(text):
            await send_text_message(sender, t(lang, "invalid_name"))
            return
        session["name"] = text.strip().title()[:30]
        session["stage"] = "delivery"
        await send_delivery_buttons(sender, session["name"], lang)
        return

    if stage == "address":
        if not is_valid_address(text):
            await send_text_message(sender, t(lang, "invalid_address"))
            return
        session["address"] = text.strip()
        session["stage"] = "payment"
        await send_text_message(sender, t(lang, "address_saved"))
        await send_payment_buttons(sender, session.get("name", ""), lang)
        return

    if text_lower in ["hi", "hello", "hey", "start", "salam", "hola"]:
        if stage == "lang_select":
            await send_language_selection(sender)
        else:
            session["stage"] = "menu"
            await send_text_message(sender, t(lang, "greeting_welcome"))
            await send_main_menu(sender, session["order"], lang)
        return

    if is_menu_request(text_lower):
        session["stage"] = "menu"
        await send_main_menu(sender, session["order"], lang)
        return

    cat_guess = guess_category(text_lower)
    protected_stages = {"get_name", "address", "payment", "delivery", "confirm",
                         "upsell_check", "upsell_combo", "bbq_sides", "deal_build"}
    if cat_guess and stage not in protected_stages:
        session["stage"] = "items"
        session["current_cat"] = cat_guess
        await send_category_items(sender, cat_guess, session["order"], lang)
        return

    session["conversation"].append({"role": "user", "content": text})
    reply = await get_ai_response(sender, text, lang, session)
    session["conversation"].append({"role": "assistant", "content": reply})
    session["conversation"] = session["conversation"][-8:]
    await send_text_message(sender, reply)

# ========== Order status helper ==========
async def handle_order_status(sender, session, lang, text):
    order_id = extract_order_number(text)
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
    if elapsed_min < expected_min:
        remaining = expected_min - elapsed_int
        msg = (
            f"{greet}Your order #{order_id} is being prepared! 🍳\n\n"
            f"⏱️ *Expected in about {remaining}-{expected_max - elapsed_int} more minutes*\n\n"
            f"Our kitchen is working on it right now. Thanks for your patience! 😊"
        )
        await send_text_message(sender, msg)
        return
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

# ========== Manager notification helpers ==========
async def notify_manager(customer_number, session, order_id):
    order = session.get("order", {})
    total = get_order_total(order)
    tax = total * 0.08
    delivery_charge = get_delivery_fee(total, session.get("delivery_type"))
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

# ========== Save to sheet ==========
async def save_to_sheet(customer_number, session, order_id):
    import aiohttp
    from config import GOOGLE_SHEET_WEBHOOK
    order = session.get("order", {})
    total = get_order_total(order)
    tax = total * 0.08
    delivery_charge = get_delivery_fee(total, session.get("delivery_type"))
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

# ========== Public entry point ==========
async def handle_flow(sender, text, is_button=False):
    try:
        await _handle_flow_inner(sender, text, is_button)
    except Exception as e:
        print(f"❌ handle_flow CRASHED for {sender} text={text!r}: {e}\n{traceback.format_exc()}")
        try:
            session = get_session(sender)
            lang = session.get("lang", "en")
            if session.get("order"):
                await send_cart_view(sender, session["order"], lang)
            else:
                await send_text_message(sender, "Sorry, something glitched on our end. Type *menu* to continue. 🙏")
        except Exception as inner:
            print(f"❌ Recovery also failed: {inner}")