import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# Railway Volume = trwały dysk, montowany w /data
# Lokalnie = w katalogu aplikacji
if os.path.isdir("/data"):
    DB_PATH = Path("/data") / "bot.db"
else:
    DB_PATH = Path(__file__).parent / "bot.db"


class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seen_offers (
                    id TEXT PRIMARY KEY,
                    serwis TEXT NOT NULL,
                    fraza TEXT NOT NULL,
                    tytul TEXT,
                    cena TEXT,
                    link TEXT,
                    zdjecie TEXT,
                    data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # migracja: dodaj kolumnę data jeśli nie istnieje
            try:
                conn.execute("ALTER TABLE seen_offers ADD COLUMN data TEXT")
            except sqlite3.OperationalError:
                pass
            conn.execute("""
                CREATE TABLE IF NOT EXISTS searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fraza TEXT NOT NULL,
                    min_cena REAL DEFAULT 0,
                    max_cena REAL DEFAULT 999999,
                    channel_id INTEGER DEFAULT 0,
                    active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # migracja: dodaj kolumnę channel_id jeśli nie istnieje
            try:
                conn.execute("ALTER TABLE searches ADD COLUMN channel_id INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            conn.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def is_seen(self, offer_id: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT 1 FROM seen_offers WHERE id = ?", (offer_id,)
                ).fetchone()
                return row is not None
        except Exception as e:
            print(f"  ⚠️ DB is_seen error: {e}")
            return False

    def add_seen(self, offer: dict, fraza: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT OR IGNORE INTO seen_offers
                    (id, serwis, fraza, tytul, cena, link, zdjecie, data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        offer["id"],
                        offer.get("serwis", ""),
                        fraza,
                        offer.get("tytul", ""),
                        offer.get("cena", ""),
                        offer.get("link", ""),
                        offer.get("zdjecie", ""),
                        offer.get("data", ""),
                    ),
                )
                conn.commit()
        except Exception as e:
            print(f"  ⚠️ DB add_seen error: {e}")

    def cleanup_old(self, days: int = 7):
        try:
            cutoff = datetime.now() - timedelta(days=days)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM seen_offers WHERE created_at < ?",
                    (cutoff.isoformat(),),
                )
                conn.commit()
        except Exception as e:
            print(f"  ⚠️ DB cleanup error: {e}")

    def get_stats(self) -> dict:
        try:
            with sqlite3.connect(self.db_path) as conn:
                total = conn.execute(
                    "SELECT COUNT(*) FROM seen_offers"
                ).fetchone()[0]
                by_service = conn.execute(
                    "SELECT serwis, COUNT(*) FROM seen_offers GROUP BY serwis"
                ).fetchall()
                return {
                    "total": total,
                    "by_service": dict(by_service),
                }
        except Exception as e:
            print(f"  ⚠️ DB get_stats error: {e}")
            return {"total": 0, "by_service": {}}

    def add_search(self, fraza: str, min_cena: float, max_cena: float, channel_id: int = 0) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO searches (fraza, min_cena, max_cena, channel_id) VALUES (?, ?, ?, ?)",
                (fraza, min_cena, max_cena, channel_id),
            )
            conn.commit()
            return cur.lastrowid

    def get_searches(self, active_only=True):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                if active_only:
                    rows = conn.execute(
                        "SELECT * FROM searches WHERE active = 1 ORDER BY created_at DESC"
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM searches ORDER BY created_at DESC"
                    ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"  ⚠️ DB get_searches error: {e}")
            return []

    def remove_search(self, search_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM searches WHERE id = ?", (search_id,))
            conn.commit()

    def toggle_search(self, search_id: int, active: bool):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE searches SET active = ? WHERE id = ?",
                (1 if active else 0, search_id),
            )
            conn.commit()

    def log(self, level: str, message: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO logs (level, message) VALUES (?, ?)",
                    (level, message),
                )
                conn.commit()
        except Exception as e:
            print(f"  ⚠️ DB log error: {e}")

    def get_logs(self, limit=50):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM logs ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"  ⚠️ DB get_logs error: {e}")
            return []
