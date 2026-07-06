import re
import requests
from bs4 import BeautifulSoup

def fetch_tg_channel_posts(channel_url: str, limit: int = 10) -> list[dict]:
    """
    Парсит публичные Telegram-каналы через их веб-превью.
    """
    match = re.search(r"(?:t\.me/(?:s/)?|@)([a-zA-Z0-9_]+)", channel_url)
    if not match:
        raise ValueError("Не удалось распознать ссылку на Telegram-канал.")
    
    channel_name = match.group(1)
    url = f"https://t.me/s/{channel_name}"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    response = requests.get(url, headers=headers, timeout=15)
    
    if not response.ok:
        raise Exception(f"Ошибка доступа к каналу. Код: {response.status_code}")

    soup = BeautifulSoup(response.text, "html.parser")
    message_divs = soup.find_all("div", class_="tgme_widget_message_text")
    
    results = []
    for div in reversed(message_divs[-limit:]):
        for br in div.find_all("br"):
            br.replace_with("\n")
            
        text = div.get_text(strip=True)
        if len(text) > 100:
            results.append({
                "channel": channel_name,
                "text": text
            })
            
    return results