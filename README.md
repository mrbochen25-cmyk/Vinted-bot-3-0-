# VintedBot — Monitor Ogłoszeń

Bot monitoruje **OLX**, **Vinted** i **Allegro** pod kątem nowych ofert i wysyła je na Discord.

## Co nowego

- ✅ Naprawione scrapery (OLX, Vinted, Allegro)
- ✅ SQLite zamiast JSON — niezawodna deduplikacja z TTL 7 dni
- ✅ Komendy Discord: `!check`, `!status`, `!add`, `!remove`, `!toggle`, `!clear`, `!logs`
- ✅ Wiele jednoczesnych wyszukiwań
- ✅ Panel webowy do zarządzania
- ✅ **Kompatybilny z Railway.com**

## Struktura (WAŻNE — wszystko w root!)

```
├── bot.py            # Główny bot Discord
├── scrapers.py       # Scrapery OLX / Vinted / Allegro
├── database.py       # SQLite + deduplikacja
├── config.json       # Konfiguracja (lub env vars)
├── requirements.txt  # Zależności Python
├── Procfile          # Jak uruchomić na Railway
└── src/App.tsx       # Panel webowy (React)
```

> ⚠️ **WAŻNE:** Wszystkie pliki `.py` muszą być w **głównym katalogu** repo, NIE w podfolderach! Railway szuka `bot.py` w `/app/`, a nie w `/app/bot/`.

## Instalacja lokalna

```bash
pip install -r requirements.txt
python bot.py
```

## Deploy na Railway.com

### 1. Ustaw zmienne środowiskowe (Variables)

W Railway → Variables dodaj:

| Zmienna | Wartość | Opis |
|---------|---------|------|
| `DISCORD_TOKEN` | `MTA0...` | Token bota z Discord Developer Portal |
| `DISCORD_CHANNEL_ID` | `123456789` | ID kanału (PPM → Kopiuj ID kanału) |
| `SZUKANA_FRAZA` | `gogle` | Domyślna fraza |
| `MIN_CENA_PLN` | `300` | Min cena |
| `MAKS_CENA_PLN` | `2000` | Max cena |
| `INTERWAL_SEK` | `300` | Co ile sekund sprawdzać |

> **Nie commituj tokena do repo!** Użyj Variables.

### 2. Uprawnienia bota

W [Discord Developer Portal](https://discord.com/developers/applications):
1. Bot → Privileged Gateway Intents → włącz **Message Content Intent**
2. OAuth2 → URL Generator:
   - Scopes: `bot`
   - Bot Permissions: `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`
3. Skopiuj link i dodaj bota na serwer

### 3. Deploy

Railway automatycznie:
1. Zainstaluje zależności z `requirements.txt`
2. Uruchomi bota przez `Procfile` (`web: python bot.py`)
3. Otworzy port dla health check

## Jak dodać pliki na GitHub (dla początkujących)

### Opcja A: Przez GitHub Desktop (najprostsza)

1. Pobierz [GitHub Desktop](https://desktop.github.com/)
2. Zaloguj się i sklonuj repo
3. Skopiuj pliki (`bot.py`, `scrapers.py`, `database.py`, `requirements.txt`, `Procfile`, `config.json`) do folderu repo
4. W GitHub Desktop zobaczysz zmiany → wpisz opis commita → "Commit to main"
5. Kliknij "Push origin"

### Opcja B: Przez terminal

```bash
# Wejdź w folder projektu
cd twój-projekt

# Dodaj wszystkie pliki
git add bot.py scrapers.py database.py requirements.txt Procfile config.json

# Commit
git commit -m "Dodano bota Vinted"

# Push
git push origin main
```

### ⚠️ Ważne: Foldery w Git

Git **nie trackuje pustych folderów**. Jeśli chcesz dodać folder, musisz dodać do niego plik (nawet pusty). Najlepiej po prostu trzymaj wszystkie pliki `.py` w **głównym katalogu** repo — tak jak teraz.

## Komendy Discord

| Komenda | Opis |
|---------|------|
| `!check [fraza] [min] [max]` | Ręczne sprawdzenie ofert |
| `!status` | Statystyki i status |
| `!searches` | Lista wyszukiwań |
| `!add <fraza> <min> <max>` | Dodaj wyszukiwanie |
| `!remove <id>` | Usuń wyszukiwanie |
| `!toggle <id>` | Włącz / wyłącz |
| `!clear` | Reset bazy seen_offers |
| `!logs [limit]` | Ostatnie logi |
| `!helpbot` | Pomoc |

## Naprawione błędy

- **OLX** — `[^d]` → `[^0-9]` (regex zostawiał literę `d` zamiast cyfr)
- **Vinted** — `item['price']` to dict, teraz pobieramy `.get('amount')`
- **Allegro** — ten sam błąd regex + lepsze headery
- **Deduplikacja** — SQLite zamiast JSON, auto-czyszczenie po 7 dniach
- **Railway** — health check server, env vars, fallback `requests`
- **Foldery** — wszystko w root, nie w podfolderach
