import os
import sys
import json
import threading
import hashlib
from datetime import datetime
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

# ─── HEALTH CHECK SERVER (Railway wymaga otwartego portu) ────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()


def start_health_server(port: int):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"  🌐 Health check server na porcie {port}")


# ─── CONFIG ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"


def load_config():
    config = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(f"  ⚠️ Błąd wczytywania config.json: {e}")

    config["discord_token"] = os.environ.get("DISCORD_TOKEN", config.get("discord_token", ""))
    config["discord_channel_id"] = os.environ.get("DISCORD_CHANNEL_ID", config.get("discord_channel_id", "0"))
    config["szukana_fraza"] = os.environ.get("SZUKANA_FRAZA", config.get("szukana_fraza", ""))
    config["min_cena_pln"] = os.environ.get("MIN_CENA_PLN", config.get("min_cena_pln", "0"))
    config["maks_cena_pln"] = os.environ.get("MAKS_CENA_PLN", config.get("maks_cena_pln", "999999"))
    config["interwal_sprawdzania_sek"] = os.environ.get("INTERWAL_SEK", config.get("interwal_sprawdzania_sek", "300"))
    return config


CONFIG = load_config()
DISCORD_TOKEN = CONFIG.get("discord_token", "")
DISCORD_CHANNEL_ID = int(CONFIG.get("discord_channel_id", 0))
DEFAULT_MIN = float(CONFIG.get("min_cena_pln", 0))
DEFAULT_MAX = float(CONFIG.get("maks_cena_pln", 999999))
DEFAULT_FRAZA = CONFIG.get("szukana_fraza", "")
INTERWAL_SEK = int(CONFIG.get("interwal_sprawdzania_sek", 300))

# ─── IMPORTS ─────────────────────────────────────────────────────────────────
try:
    import discord
    from discord.ext import commands, tasks
except ImportError as e:
    print(f"❌ Błąd importu discord.py: {e}")
    print("   Upewnij się, że w requirements.txt jest: discord.py>=2.3.0")
    sys.exit(1)

from database import Database
from scrapers import scrape_olx, scrape_vinted, scrape_allegro

# ─── KONSTANTY ───────────────────────────────────────────────────────────────
COLORS = {
    "OLX": 0x00C896,
    "Vinted": 0x007782,
    "Allegro": 0xFF6600,
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
db = Database()


# ─── EMBED ───────────────────────────────────────────────────────────────────
def make_embed(offer: dict):
    color = COLORS.get(offer["serwis"], 0x00C896)
    embed = discord.Embed(
        title=offer["tytul"][:256],
        url=offer["link"],
        color=color,
        timestamp=datetime.now(),
    )
    embed.add_field(name="💰 Cena", value=offer["cena"], inline=True)
    embed.add_field(name="📍 Lokalizacja", value=offer.get("lokalizacja", "—"), inline=True)
    embed.add_field(name="🛒 Serwis", value=offer["serwis"], inline=True)
    embed.set_footer(text="Monitor Ogłoszeń")
    if offer.get("zdjecie"):
        embed.set_image(url=offer["zdjecie"])
    return embed


async def send_offer(channel, offer: dict):
    try:
        embed = make_embed(offer)
        await channel.send(embed=embed)
        db.log("INFO", f"Wysłano {offer['serwis']}: {offer['tytul'][:60]}")
    except Exception as e:
        db.log("ERROR", f"Błąd wysyłki Discord: {e}")


# ─── CHECK ONCE ──────────────────────────────────────────────────────────────
async def check_once(channel, fraza: str, min_cena: float, max_cena: float, silent=False):
    db.log("INFO", f"Sprawdzam: '{fraza}' | {min_cena:.0f}-{max_cena:.0f} PLN")
    if not silent:
        try:
            await channel.send(f"🔍 Sprawdzam oferty dla: **{fraza}** ({min_cena:.0f} - {max_cena:.0f} PLN)")
        except Exception:
            pass

    all_offers = []
    all_offers.extend(scrape_olx(fraza, min_cena, max_cena))
    all_offers.extend(scrape_vinted(fraza, min_cena, max_cena))
    all_offers.extend(scrape_allegro(fraza, min_cena, max_cena))

    new_offers = []
    for offer in all_offers:
        if not db.is_seen(offer["id"]):
            new_offers.append(offer)
            db.add_seen(offer, fraza)

    for offer in new_offers:
        await send_offer(channel, offer)

    db.cleanup_old(days=7)

    msg = f"📊 Znaleziono {len(all_offers)} ofert, **{len(new_offers)}** nowych."
    db.log("INFO", msg)
    if not silent:
        try:
            await channel.send(msg)
        except Exception:
            pass
    return len(new_offers)


# ─── MONITOR LOOP ────────────────────────────────────────────────────────────
@tasks.loop(seconds=INTERWAL_SEK)
async def monitor_loop():
    searches = db.get_searches(active_only=True)
    if not searches:
        searches = [{
            "fraza": DEFAULT_FRAZA,
            "min_cena": DEFAULT_MIN,
            "max_cena": DEFAULT_MAX,
            "channel_id": DISCORD_CHANNEL_ID,
        }]

    for s in searches:
        ch_id = s.get("channel_id", 0) or DISCORD_CHANNEL_ID
        channel = bot.get_channel(int(ch_id))
        if not channel:
            db.log("ERROR", f"Nie znaleziono kanału ID {ch_id} dla wyszukiwania '{s['fraza']}'")
            continue
        await check_once(channel, s["fraza"], s["min_cena"], s["max_cena"], silent=True)


@bot.event
async def on_ready():
    print(f"✅ Zalogowano jako {bot.user}")
    db.log("INFO", f"Bot wystartował: {bot.user}")
    if not monitor_loop.is_running():
        monitor_loop.start()


# ─── KOMENDY ─────────────────────────────────────────────────────────────────

@bot.command(name="check")
async def cmd_check(ctx, fraza: str = None, min_cena: float = None, max_cena: float = None):
    fraza = fraza or DEFAULT_FRAZA
    min_cena = min_cena if min_cena is not None else DEFAULT_MIN
    max_cena = max_cena if max_cena is not None else DEFAULT_MAX
    await check_once(ctx.channel, fraza, min_cena, max_cena)


@bot.command(name="status")
async def cmd_status(ctx):
    stats = db.get_stats()
    searches = db.get_searches(active_only=False)
    embed = discord.Embed(title="📊 Status Monitora", color=0x3498DB)
    embed.add_field(name="Ofert w bazie", value=str(stats["total"]), inline=True)
    embed.add_field(name="Aktywnych wyszukiwań", value=str(len([s for s in searches if s["active"]])), inline=True)
    embed.add_field(name="Interwał", value=f"{INTERWAL_SEK}s", inline=True)
    services = "\n".join([f"{k}: {v}" for k, v in stats.get("by_service", {}).items()]) or "Brak"
    embed.add_field(name="Ofert per serwis", value=services, inline=False)
    embed.set_footer(text=f"Uptime: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    await ctx.send(embed=embed)


@bot.command(name="searches")
async def cmd_searches(ctx):
    searches = db.get_searches(active_only=False)
    if not searches:
        await ctx.send("📭 Brak zapisanych wyszukiwań.")
        return
    embed = discord.Embed(title="🔍 Lista Wyszukiwań", color=0x9B59B6)
    for s in searches:
        status = "🟢" if s["active"] else "🔴"
        ch_id = s.get("channel_id", 0)
        channel_mention = f"<#{ch_id}>" if ch_id else "domyślny"
        embed.add_field(
            name=f"{status} ID {s['id']}: {s['fraza']}",
            value=f"Cena: {s['min_cena']:.0f} - {s['max_cena']:.0f} PLN | Kanał: {channel_mention}",
            inline=False,
        )
    await ctx.send(embed=embed)


@bot.command(name="add")
async def cmd_add(ctx, fraza: str, min_cena: float, max_cena: float):
    sid = db.add_search(fraza, min_cena, max_cena, channel_id=ctx.channel.id)
    await ctx.send(
        f"✅ Dodano wyszukiwanie **ID {sid}**: {fraza} ({min_cena:.0f} - {max_cena:.0f} PLN)\n"
        f"📡 Wyniki będą wysyłane na <#{ctx.channel.id}>"
    )


@bot.command(name="remove")
async def cmd_remove(ctx, search_id: int):
    db.remove_search(search_id)
    await ctx.send(f"🗑️ Usunięto wyszukiwanie ID {search_id}")


@bot.command(name="toggle")
async def cmd_toggle(ctx, search_id: int):
    searches = db.get_searches(active_only=False)
    target = next((s for s in searches if s["id"] == search_id), None)
    if not target:
        await ctx.send(f"❌ Nie znaleziono wyszukiwania ID {search_id}")
        return
    new_state = not target["active"]
    db.toggle_search(search_id, new_state)
    status = "włączone" if new_state else "wyłączone"
    await ctx.send(f"🔘 Wyszukiwanie ID {search_id} jest teraz **{status}**.")


@bot.command(name="clear")
async def cmd_clear(ctx):
    db.cleanup_old(days=0)
    await ctx.send("🧹 Wyczyszczono bazę seen_offers. Od teraz wszystkie oferty będą traktowane jako nowe.")


@bot.command(name="logs")
async def cmd_logs(ctx, limit: int = 10):
    logs = db.get_logs(limit=limit)
    if not logs:
        await ctx.send("📭 Brak logów.")
        return
    lines = []
    for log in logs:
        ts = log["created_at"]
        lines.append(f"`[{ts}]` **{log['level']}**: {log['message']}")
    embed = discord.Embed(title="📜 Ostatnie Logi", description="\n".join(lines[:10]), color=0xE67E22)
    await ctx.send(embed=embed)


@bot.command(name="helpbot")
async def cmd_helpbot(ctx):
    embed = discord.Embed(title="📖 Komendy Monitora", color=0x2ECC71)
    cmds = [
        ("!check [fraza] [min] [max]", "Ręczne sprawdzenie ofert"),
        ("!status", "Status monitora i statystyki"),
        ("!searches", "Lista wszystkich wyszukiwań"),
        ("!add <fraza> <min> <max>", "Dodaj nowe wyszukiwanie"),
        ("!remove <id>", "Usuń wyszukiwanie"),
        ("!toggle <id>", "Włącz/wyłącz wyszukiwanie"),
        ("!clear", "Wyczyść bazę seen_offers (reset)"),
        ("!logs [limit]", "Pokaż ostatnie logi"),
        ("!helpbot", "Ta pomoc"),
    ]
    for name, desc in cmds:
        embed.add_field(name=name, value=desc, inline=False)
    await ctx.send(embed=embed)


# ─── START ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    start_health_server(port)

    if not DISCORD_TOKEN:
        print("❌ Brak DISCORD_TOKEN!")
        print("   Ustaw zmienną środowiskową DISCORD_TOKEN lub dodaj do config.json")
        sys.exit(1)
    if not DISCORD_CHANNEL_ID:
        print("❌ Brak DISCORD_CHANNEL_ID!")
        print("   Ustaw zmienną środowiskową DISCORD_CHANNEL_ID lub dodaj do config.json")
        sys.exit(1)

    print(f"🔍 Bot startuje...")
    print(f"   Kanał: {DISCORD_CHANNEL_ID}")
    print(f"   Interwał: {INTERWAL_SEK}s")
    print(f"   Domyślna fraza: {DEFAULT_FRAZA}")
    print(f"   Cena: {DEFAULT_MIN:.0f} - {DEFAULT_MAX:.0f} PLN")

    bot.run(DISCORD_TOKEN)
