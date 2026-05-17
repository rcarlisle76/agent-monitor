import os
import aiosqlite

DB_PATH = os.getenv("DB_PATH", "./agent_monitor.db")


ACCURACY_FLAG_THRESHOLD = float(os.getenv("ACCURACY_FLAG_THRESHOLD", "70.0"))


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                parent_id TEXT,
                replaces TEXT,
                status TEXT NOT NULL,
                current_task TEXT,
                current_accuracy REAL,
                flagged INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                status TEXT NOT NULL,
                task TEXT,
                accuracy REAL,
                metadata TEXT DEFAULT '{}',
                recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migrate existing DBs that lack the new columns
        for col, definition in [
            ("current_accuracy", "REAL"),
            ("flagged", "INTEGER DEFAULT 0"),
            ("replaces", "TEXT"),
        ]:
            try:
                await db.execute(f"ALTER TABLE agents ADD COLUMN {col} {definition}")
            except Exception:
                pass
        try:
            await db.execute("ALTER TABLE tasks ADD COLUMN accuracy REAL")
        except Exception:
            pass
        await db.commit()


def get_db():
    return aiosqlite.connect(DB_PATH)
