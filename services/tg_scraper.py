import re
import requests
from bs4 import BeautifulSoup

def fetch_tg_channel_posts(channel_url: str, limit: int = 10) -> list[dict]:
    """Парсит публичные ТГ-каналы. Листает историю назад, пока не соберет limit постов."""
    match = re.search(r"(?:t\.me/(?:s/)?|@)([a-zA-Z0-9_]+)", channel_url)
    if not match:
        raise ValueError("Не удалось распознать ссылку на Telegram-канал.")
    
    channel_name = match.group(1)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    results = []
    next_before = None
    
    while len(results) < limit:
        url = f"https://t.me/s/{channel_name}?before={next_before}" if next_before else f"https://t.me/s/{channel_name}"
            
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if not response.ok:
                break
        except Exception:
            break
            
        soup = BeautifulSoup(response.text, "html.parser")
        messages = soup.find_all("div", class_="tgme_widget_message")
        
        if not messages:
            break
            
        page_posts = []
        min_post_id = float('inf')
        
        for msg in messages:
            text_div = msg.find("div", class_="tgme_widget_message_text")
            data_post = msg.get("data-post", "")
            
            if "/" in data_post:
                try:
                    pid = int(data_post.split("/")[-1])
                    if 0 < pid < min_post_id:
                        min_post_id = pid
                except ValueError:
                    pass
                    
            if not text_div:
                continue

            for br in text_div.find_all("br"):
                br.replace_with("\n")
                
            text = text_div.get_text(strip=True)
            if len(text) > 100:
                page_posts.append({
                    "channel": channel_name,
                    "text": text,
                    "post_id": int(data_post.split("/")[-1]) if "/" in data_post else 0
                })
        
        if not page_posts:
            break
            
        results = page_posts + results
        
        if min_post_id == float('inf') or min_post_id <= 1 or next_before == min_post_id:
            break
            
        next_before = min_post_id

    return results[-limit:]