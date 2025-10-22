import os, requests
def send_telegram_text(token_env: str, chat_env: str, text: str):
    token = os.getenv(token_env) if token_env else None
    chat_id = os.getenv(chat_env) if chat_env else None
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=15)
    except Exception as e:
        print("Telegram text alert error:", e)
def send_telegram_photo(token_env: str, chat_env: str, photo_url: str, caption: str = None):
    token = os.getenv(token_env) if token_env else None
    chat_id = os.getenv(chat_env) if chat_env else None
    if not token or not chat_id or not photo_url:
        return
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    data = {"chat_id": chat_id, "photo": photo_url}
    if caption:
        data["caption"] = caption
        data["parse_mode"] = "HTML"
    try:
        requests.post(url, data=data, timeout=20)
    except Exception as e:
        print("Telegram photo alert error:", e)
