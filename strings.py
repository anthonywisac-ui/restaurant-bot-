import json
import os

STRINGS = {}

def load_strings():
    global STRINGS
    langs = ["en", "ar", "hi", "fr", "de", "ru", "zh", "ml"]
    for lang in langs:
        try:
            with open(f"locales/{lang}.json", "r", encoding="utf-8") as f:
                STRINGS[lang] = json.load(f)
        except FileNotFoundError:
            print(f"Warning: locales/{lang}.json not found, using English fallback")
            if lang != "en":
                STRINGS[lang] = STRINGS.get("en", {})
    if "en" not in STRINGS:
        raise Exception("locales/en.json is required")

def t(lang, key):
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, key))

def reload_strings():
    load_strings()

# Initial load
load_strings()
