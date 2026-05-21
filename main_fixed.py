import requests
import json
import time
import re
import hashlib
import tls_client
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup

# ─── KONFIGURACJA ────────────────────────────────────────────────────────────
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

DISCORD_WEBHOOK = CONFIG["discord_webhook"]
SZUKANA_FRAZA   = CONFIG["szukana_fraza"]
MAKS_CENA       = float(CONFIG["maks_cena_pln"])
MIN_CENA        = float(CONFIG.get("min_cena_pln", 0))
INTERWAL_SEK    = CONFIG["interwal_sprawdzania_sek"]
SEEN_FILE       = "seen_offers.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9",
}

# ─── KOLORY SERWISÓW (Discord embed) ─────────────────────────────────────────
COLORS = {
    "OLX":     0x00C896,
    "Vinted":  0x007782,
    "Allegro": 0xFF6600,
}

# ─── STAN ────────────────────────────────────────────────────────────────────
def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

# ─── DISCORD ─────────────────────────────────────────────────────────────────
def send_discord(offer: dict):
    color = COLORS.get(offer["serwis"], 0x00C896)
    embed = {
        "title": offer["tytul"][:256],
        "url":   offer["link"],
        "color": color,
        "fields": [
            {"name": "💰 Cena",        "value": offer["cena"],               "inline": True},
            {"name": "📍 Lokalizacja", "value": offer.get("lokalizacja","—"), "inline": True},
            {"name": "🛒 Serwis",      "value": offer["serwis"],             "inline": True},
        ],
        "footer": {"text": f"Monitor • {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"},
    }
    if offer.get("zdjecie"):
        embed["image"] = {"url": offer["zdjecie"]}

    payload = {"username": "🔍 Monitor Ogłoszeń", "embeds": [embed]}
    try:
        r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        r.raise_for_status()
        print(f"  ✅ Discord → {offer['serwis']}: {offer['tytul'][:60]}")
    except Exception as e:
        print(f"  ❌ Discord błąd: {e}")

def send_discord_info(msg: str):
    try:
        requests.post(DISCORD_WEBHOOK, json={"username": "🔍 Monitor Ogłoszeń", "content": msg}, timeout=10)
    except Exception:
        pass

# ─── OLX ─────────────────────────────────────────────────────────────────────
def scrape_olx() -> list[dict]:
    fraza_url = SZUKANA_FRAZA.replace(" ", "-")
    url = (
        f"https://www.olx.pl/oferty/q-{fraza_url}/"
        f"?search%5Bfilter_float_price%3Afrom%5D={MIN_CENA}"
        f"&search%5Bfilter_float_price%3Ato%5D={MAKS_CENA}"
    )
    offers = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select("div[data-cy='l-card']"):
            link_tag  = card.select_one("a[href]")
            title_tag = card.select_one("h4, h6, [data-testid='ad-title']")
            price_tag = card.select_one("[data-testid='ad-price']")
            loc_tag   = card.select_one("[data-testid='location-date']")
            img_tag   = card.select_one("img")
            
            if not (link_tag and title_tag and price_tag):
                continue
            
            # POPRAWKA: [^d] → [^0-9] (zostawiamy tylko cyfry, nie literę 'd')
            raw = re.sub(r"[^0-9]", "", price_tag.get_text())
            if not raw or int(raw) < MIN_CENA or int(raw) > MAKS_CENA:
                continue
                
            href = link_tag["href"]
            if not href.startswith("http"):
                href = "https://www.olx.pl" + href
                
            offers.append({
                "id":          hashlib.md5(href.encode()).hexdigest(),
                "tytul":       title_tag.get_text(strip=True),
                "cena":        price_tag.get_text(strip=True),
                "lokalizacja": loc_tag.get_text(strip=True) if loc_tag else "—",
                "link":        href,
                "zdjecie":     img_tag.get("src") if img_tag else None,
                "serwis":      "OLX",
            })
        print(f"  OLX: {len(offers)} ofert")
    except Exception as e:
        print(f"  ⚠️  OLX błąd: {e}")
    return offers

# ─── VINTED (oficjalne API) ───────────────────────────────────────────────────
def scrape_vinted() -> list[dict]:
    session = tls_client.Session(
        client_identifier="chrome_120",
        random_tls_extension_order=True
    )
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    session.headers.update(headers)
    
    offers = []
    try:
        # Pobranie ciasteczka sesyjnego
        session.get("https://www.vinted.pl", timeout_seconds=15)
        
        # Kodowanie znaków z configu (np. spacje)
        encoded_query = urllib.parse.quote(SZUKANA_FRAZA)
        api_url = (
            f"https://www.vinted.pl/api/v2/catalog/items?search_text={encoded_query}"
            f"&price_from={MIN_CENA}&price_to={MAKS_CENA}&order=newest_first"
        )
        
        response = session.get(api_url, timeout_seconds=15)
        
        if response.status_code == 200:
            items = response.json().get('items', [])
            
            for item in items:
                # POPRAWKA: item['price'] to dict, trzeba wziąć .get('amount')
                try:
                    price_amount = item.get('price', {}).get('amount')
                    if price_amount is None:
                        continue
                    price_val = float(price_amount)
                    if price_val < MIN_CENA or price_val > MAKS_CENA:
                        continue
                except (ValueError, TypeError):
                    pass
                
                # Dodawanie oferty w formacie wymaganym przez główną pętlę
                offers.append({
                    "id":          str(item.get('id', hashlib.md5(item.get('url', '').encode()).hexdigest())),
                    "tytul":       item.get('title', 'Brak tytułu'),
                    "cena":        f"{item.get('price', {}).get('amount')} {item.get('price', {}).get('currency', '')}",
                    "lokalizacja": "Vinted",
                    "link":        item.get('url'),
                    "zdjecie":     item.get('photo', {}).get('url') if item.get('photo') else None,
                    "serwis":      "Vinted",
                })
            print(f"  Vinted: {len(offers)} ofert")
        else:
            print(f"  ⚠️  Vinted błąd API: Kod {response.status_code}")
            
    except Exception as e:
        print(f"  ⚠️  Vinted błąd połączenia: {e}")
        
    return offers

# ─── ALLEGRO ─────────────────────────────────────────────────────────────────
def scrape_allegro() -> list[dict]:
    fraza_url = SZUKANA_FRAZA.replace(" ", "%20")
    url = (
        f"https://allegro.pl/listing?string={fraza_url}"
        f"&price_from={MIN_CENA}&price_to={MAKS_CENA}&stan=używane&order=qd"
    )
    offers = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        for article in soup.select("article"):
            link_tag  = article.select_one("a[href*='/oferta/']")
            title_tag = article.select_one("h2, [data-role='offer-title']")
            price_tag = article.select_one("span._1svub, [data-role='price']")
            img_tag   = article.select_one("img")

            if not (link_tag and title_tag):
                continue

            price_text = price_tag.get_text(strip=True) if price_tag else ""
            # POPRAWKA: [^d] → [^0-9] (także w Allegro)
            raw = re.sub(r"[^0-9]", "", price_text)
            if raw:
                if int(raw) > MAKS_CENA * 100:  
                    raw = str(int(raw) // 100)
                price_val = int(raw)
                if price_val < MIN_CENA or price_val > MAKS_CENA:
                    continue

            href = link_tag["href"]
            if not href.startswith("http"):
                href = "https://allegro.pl" + href

            if "allegro.pl/oferta/" not in href:
                continue

            offers.append({
                "id":          hashlib.md5(href.encode()).hexdigest(),
                "tytul":       title_tag.get_text(strip=True),
                "cena":        price_text if price_text else "—",
                "lokalizacja": "Allegro",
                "link":        href,
                "zdjecie":     img_tag.get("src") if img_tag else None,
                "serwis":      "Allegro",
            })
        print(f"  Allegro: {len(offers)} ofert")
    except Exception as e:
        print(f"  ⚠️  Allegro błąd: {e}")
    return offers

# ─── GŁÓWNA PĘTLA ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    seen = load_seen()
    print(f"🔍 Monitor: '{SZUKANA_FRAZA}' | Cena: {MIN_CENA:.0f} - {MAKS_CENA:.0f} PLN | Interwał: {INTERWAL_SEK}s")
    send_discord_info(f"🟢 Monitor wystartował! Szukam: **{SZUKANA_FRAZA}** w zakresie **{MIN_CENA:.0f} - {MAKS_CENA:.0f} PLN**")

    while True:
        print(f"\n⏳ {datetime.now().strftime('%H:%M:%S')} — Sprawdzam oferty...")
        all_offers = scrape_olx() + scrape_vinted() + scrape_allegro()

        new_offers = [o for o in all_offers if o["id"] not in seen]
        for offer in new_offers:
            send_discord(offer)
            seen.add(offer["id"])

        if new_offers:
            save_seen(seen)
            print(f"📢 Wysłano {len(new_offers)} nowych ofert na Discord.")
        else:
            print("😴 Brak nowych ofert.")

        time.sleep(INTERWAL_SEK)
