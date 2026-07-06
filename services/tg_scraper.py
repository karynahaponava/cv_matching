import re
import requests
from bs4 import BeautifulSoup

def fetch_tg_channel_posts(channel_url: str, limit: int = 10) -> list[dict]:
    """
    Парсит публичные Telegram-каналы через их веб-превью, вытаскивая текст и ID поста.
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
    
    messages = soup.find_all("div", class_="tgme_widget_message")
    
    results = []
    for msg in reversed(messages[-limit:]):
        text_div = msg.find("div", class_="tgme_widget_message_text")
        if not text_div:
            continue
            
        data_post = msg.get("data-post", "")
        post_id = 0
        if "/" in data_post:
            try:
                post_id = int(data_post.split("/")[-1])
            except ValueError:
                pass

        for br in text_div.find_all("br"):
            br.replace_with("\n")
            
        text = text_div.get_text(strip=True)
        
        if len(text) > 100:
            results.append({
                "channel": channel_name,
                "text": text,
                "post_id": post_id
            })
            
    return results