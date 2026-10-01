#!/usr/bin/env python3
import os
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def backup_database(src, backup_dir, keep=10):
    os.makedirs(backup_dir, exist_ok=True)
    dst = os.path.join(backup_dir, f"secure_access_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.db")
    with sqlite3.connect(src) as source, sqlite3.connect(dst) as target:
        source.backup(target)
    source.close()
    target.close()
    backups = sorted(f for f in os.listdir(backup_dir) if f.startswith("secure_access_") and f.endswith(".db"))
    for old in backups[:-keep]:
        os.remove(os.path.join(backup_dir, old))
    print(f"Backup created: {dst}")
    return dst


if __name__ == '__main__':
    from app import create_app
    from models import db
    app = create_app()
    with app.app_context():
        backup_database(db.engine.url.database, app.config["BACKUP_DIR"], app.config["BACKUP_KEEP"])
