import re
import hashlib
import urllib.parse
from datetime import datetime

try:
    import tls_client
    HAS_TLS = True
except ImportError:
    HAS_TLS = False
    print("  ⚠️ tls_client niedostępny, używam requests")

import requests
from bs4 import BeautifulSoup


def _make_id(link: str) -> str:
    return hashlib.md5(link.encode()).hexdigest()


def _get_session():
    if HAS_TLS:
        return tls_client.Session(
            client_identifier="chrome_120",
            random_tls_extension_order=True,
        )
    return requests.Session()


def _get(session, url: str, headers: dict, timeout=15):
    if HAS_TLS:
        return session.get(url, headers=headers, timeout_seconds=timeout)
    return session.get(url, headers=headers, timeout=timeout)


def _status_code(response):
    return response.status_code


def _text(response):
    if HAS_TLS:
        return response.text
    return response.text


# ─── OLX ─────────────────────────────────────────────────────────────────────
def scrape_olx(fraza: str, min_cena: float, max_cena: float) -> list[dict]:
    fraza_url = fraza.replace(" ", "-")
    url = (
        f"https://www.olx.pl/oferty/q-{fraza_url}/"
        f"?search%5Bfilter_float_price%3Afrom%5D={int(min_cena)}"
        f"&search%5Bfilter_float_price%3Ato%5D={int(max_cena)}"
    )
    offers = []
    try:
        session = _get_session()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
        r = _get(session, url, headers)
        if _status_code(r) != 200:
            print(f"  ⚠️ OLX status: {_status_code(r)}")
            return offers

        soup = BeautifulSoup(_text(r), "html.parser")
        cards = soup.select("div[data-cy='l-card']")
        print(f"  OLX: znaleziono {len(cards)} kart")

        for card in cards:
            link_tag = card.select_one("a[href]")
            title_tag = card.select_one("h4, h6, [data-testid='ad-title']")
            price_tag = card.select_one("[data-testid='ad-price']")
            loc_tag = card.select_one("[data-testid='location-date']")
            img_tag = card.select_one("img")

            if not (link_tag and title_tag and price_tag):
                continue

            price_text = price_tag.get_text(strip=True)
            raw = re.sub(r"[^0-9]", "", price_text)
            if not raw:
                continue
            try:
                price_val = int(raw)
            except ValueError:
                continue
            if price_val < min_cena or price_val > max_cena:
                continue

            href = link_tag["href"]
            if not href.startswith("http"):
                href = "https://www.olx.pl" + href

            # Wyciągnij datę z location-date (format: "Miasto, dzisiaj o 14:30")
            loc_text = loc_tag.get_text(strip=True) if loc_tag else ""
            data_dodania = "—"
            if loc_text:
                for sep in [",", "•", "-"]:
                    if sep in loc_text:
                        data_dodania = loc_text.split(sep, 1)[1].strip()
                        break

            offers.append({
                "id": _make_id(href),
                "tytul": title_tag.get_text(strip=True),
                "cena": price_text,
                "lokalizacja": loc_tag.get_text(strip=True) if loc_tag else "—",
                "data": data_dodania,
                "link": href,
                "zdjecie": img_tag.get("src") if img_tag else None,
                "serwis": "OLX",
            })
        print(f"  OLX: {len(offers)} ofert po filtrowaniu")
    except Exception as e:
        print(f"  ⚠️ OLX błąd: {e}")
    return offers


# ─── VINTED ──────────────────────────────────────────────────────────────────
def scrape_vinted(fraza: str, min_cena: float, max_cena: float) -> list[dict]:
    session = _get_session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if HAS_TLS:
        session.headers.update(headers)

    offers = []
    try:
        _get(session, "https://www.vinted.pl", headers)
        encoded_query = urllib.parse.quote(fraza)
        api_url = (
            f"https://www.vinted.pl/api/v2/catalog/items?search_text={encoded_query}"
            f"&price_from={int(min_cena)}&price_to={int(max_cena)}&order=newest_first"
        )
        response = _get(session, api_url, headers)
        if _status_code(response) != 200:
            print(f"  ⚠️ Vinted API status: {_status_code(response)}")
            return offers

        data = response.json() if hasattr(response, "json") else json.loads(_text(response))
        items = data.get("items", [])
        print(f"  Vinted: znaleziono {len(items)} items")

        for item in items:
            price_data = item.get("price", {}) or {}
            price_amount = price_data.get("amount")
            price_currency = price_data.get("currency", "")
            if price_amount is None:
                continue
            try:
                price_val = float(price_amount)
            except (ValueError, TypeError):
                continue
            if price_val < min_cena or price_val > max_cena:
                continue

            url = item.get("url", "")
            photo_data = item.get("photo", {}) or {}

            # Data dodania z API Vinted
            created_ts = item.get("created_at_ts") or item.get("created_at")
            data_dodania = "—"
            if created_ts:
                try:
                    if isinstance(created_ts, (int, float)):
                        data_dodania = datetime.fromtimestamp(created_ts).strftime("%d.%m.%Y %H:%M")
                    else:
                        dt = datetime.fromisoformat(str(created_ts).replace("Z", "+00:00"))
                        data_dodania = dt.strftime("%d.%m.%Y %H:%M")
                except Exception:
                    data_dodania = str(created_ts)

            offers.append({
                "id": str(item.get("id", _make_id(url))),
                "tytul": item.get("title", "Brak tytułu"),
                "cena": f"{price_amount} {price_currency}",
                "lokalizacja": "Vinted",
                "data": data_dodania,
                "link": url,
                "zdjecie": photo_data.get("url") if photo_data else None,
                "serwis": "Vinted",
            })
        print(f"  Vinted: {len(offers)} ofert po filtrowaniu")
    except Exception as e:
        print(f"  ⚠️ Vinted błąd połączenia: {e}")
    return offers


# ─── ALLEGRO ─────────────────────────────────────────────────────────────────
def scrape_allegro(fraza: str, min_cena: float, max_cena: float) -> list[dict]:
    fraza_url = fraza.replace(" ", "%20")
    url = (
        f"https://allegro.pl/listing?string={fraza_url}"
        f"&price_from={int(min_cena)}&price_to={int(max_cena)}"
        f"&stan=używane&order=qd"
    )
    offers = []
    try:
        session = _get_session()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        r = _get(session, url, headers)
        if _status_code(r) != 200:
            print(f"  ⚠️ Allegro status: {_status_code(r)}")
            return offers

        soup = BeautifulSoup(_text(r), "html.parser")
        articles = soup.select("article")
        print(f"  Allegro: znaleziono {len(articles)} artykułów")

        for article in articles:
            link_tag = article.select_one("a[href*='/oferta/']")
            title_tag = article.select_one("h2, [data-role='offer-title']")
            price_tag = article.select_one("span._1svub, [data-role='price']")
            img_tag = article.select_one("img")
            date_tag = article.select_one("time, [datetime], .mgn2_14, [data-testid='offer-date']")

            if not (link_tag and title_tag):
                continue

            price_text = price_tag.get_text(strip=True) if price_tag else ""
            raw = re.sub(r"[^0-9]", "", price_text)
            if raw:
                try:
                    price_val = int(raw)
                except ValueError:
                    continue
                if price_val > max_cena * 100:
                    price_val = price_val // 100
                if price_val < min_cena or price_val > max_cena:
                    continue

            href = link_tag["href"]
            if not href.startswith("http"):
                href = "https://allegro.pl" + href
            if "allegro.pl/oferta/" not in href:
                continue

            # Data dodania
            data_dodania = "—"
            if date_tag:
                dt_attr = date_tag.get("datetime", "")
                if dt_attr:
                    try:
                        dt = datetime.fromisoformat(dt_attr.replace("Z", "+00:00"))
                        data_dodania = dt.strftime("%d.%m.%Y %H:%M")
                    except Exception:
                        data_dodania = date_tag.get_text(strip=True)
                else:
                    data_dodania = date_tag.get_text(strip=True)

            offers.append({
                "id": _make_id(href),
                "tytul": title_tag.get_text(strip=True),
                "cena": price_text if price_text else "—",
                "lokalizacja": "Allegro",
                "data": data_dodania,
                "link": href,
                "zdjecie": img_tag.get("src") if img_tag else None,
                "serwis": "Allegro",
            })
        print(f"  Allegro: {len(offers)} ofert po filtrowaniu")
    except Exception as e:
        print(f"  ⚠️ Allegro błąd: {e}")
    return offers
