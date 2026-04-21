import aiohttp
from config import GROQ_API_KEY, LANG_NAMES, MENU_SUMMARY
from strings import t
from session import SharedSession

async def get_ai_response(sender, user_message, lang="en", session=None, extra_instruction=""):
    lang_name = LANG_NAMES.get(lang, "English")
    system_prompt = f"""You are Alex, a friendly customer service rep at Wild Bites Restaurant.
IMPORTANT: Always reply in {lang_name} only. Never mention you are AI.
Be warm, casual, helpful. Max 3 sentences. Use emojis naturally.
Hours: 10am-11pm. Delivery min $30 + $4.99 fee (free over $50). Pickup min $10.
{MENU_SUMMARY}
{extra_instruction}
If customer seems confused or stuck, guide them to next step clearly."""
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
        shared_session = await SharedSession.get_session()
        async with shared_session.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers) as r:
            result = await r.json()
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"AI Error: {e}")
        return t(lang, "greeting_welcome")