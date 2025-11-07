import os
import sqlite3

# Base directory for resolving paths
BASE_DIR = os.path.dirname(__file__)

# Shared database path (moved into sql folder)
DB_NAME = os.path.join(BASE_DIR, "sql", "hotel.db")


def connect():
    """Create a SQLite connection with foreign keys enabled."""
    # Ensure the sql directory exists before connecting
    os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    # Enable foreign keys, WAL mode and a reasonable busy timeout to reduce 'database is locked'
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")  # wait up to 5s when DB is busy
    except Exception:
        # Some PRAGMA may fail on certain environments; ignore silently
        pass
    return conn


# Authentication constants (keep consistent with existing modules)
SECRET_KEY = 'homes_rental_secret_key'
JWT_EXPIRATION_DELTA = 30 * 60  # 30 minutes, sliding expiration window