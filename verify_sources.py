from sqlalchemy import create_engine, inspect, text
import sys

DB_URL = "sqlite:///library.db"
engine = create_engine(DB_URL)

with engine.connect() as conn:
    result = conn.execute(text("SELECT name, key FROM sources"))
    sources = result.fetchall()

    found_qq_all = False
    for name, key in sources:
        print(f"Source: {name} ({key})")
        if key == 'questionablequesting_all':
            found_qq_all = True

    if found_qq_all:
        print("PASS: questionablequesting_all source found.")
    else:
        # Since I just created the migration, I haven't run it yet.
        # But wait, I can't run alembic directly.
        # I rely on `init_db` or manually running the migration code via python if needed.
        # However, `test_story_manager.py` uses `init_db` which runs migrations.
        print("FAIL: questionablequesting_all source MISSING.")
