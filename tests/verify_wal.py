import os
import sys
from sqlalchemy import text

# Add repo root to path so we can import scrollarr
sys.path.append(os.getcwd())

from scrollarr.database import engine

def verify_wal():
    print("Connecting to database...")
    with engine.connect() as conn:
        print("Checking PRAGMA journal_mode...")
        result = conn.execute(text("PRAGMA journal_mode;")).scalar()
        print(f"journal_mode: {result}")
        if str(result).lower() != 'wal':
            print("FAIL: journal_mode is not WAL")
            sys.exit(1)

        print("Checking PRAGMA synchronous...")
        result = conn.execute(text("PRAGMA synchronous;")).scalar()
        print(f"synchronous: {result}")
        # 1 is NORMAL, 0 is OFF, 2 is FULL, 3 is EXTRA
        if int(result) != 1:
            print("FAIL: synchronous is not NORMAL (1)")
            sys.exit(1)

        print("Checking PRAGMA busy_timeout...")
        result = conn.execute(text("PRAGMA busy_timeout;")).scalar()
        print(f"busy_timeout: {result}")
        if int(result) != 30000:
            print("FAIL: busy_timeout is not 30000")
            sys.exit(1)

        print("Checking PRAGMA foreign_keys...")
        result = conn.execute(text("PRAGMA foreign_keys;")).scalar()
        print(f"foreign_keys: {result}")
        if int(result) != 1:
            print("FAIL: foreign_keys is not ON (1)")
            sys.exit(1)

    print("SUCCESS: All SQLite settings verified.")

if __name__ == "__main__":
    verify_wal()
