import json
import os

MENU = {}

def load_menu():
    global MENU
    try:
        with open("menu.json", "r", encoding="utf-8") as f:
            MENU = json.load(f)
        print("Menu loaded from menu.json")
    except Exception as e:
        print(f"Error loading menu.json: {e}")
        # fallback hardcoded minimal menu
        MENU = {
            "fastfood": {"name": "🍔 Burgers", "items": {}},
            "deals": {"name": "🔥 Deals", "items": {}}
        }

def reload_menu():
    load_menu()

# Initial load
load_menu()
