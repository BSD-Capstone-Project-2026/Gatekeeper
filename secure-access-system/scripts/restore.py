#!/usr/bin/env python3
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def restore_database(backup_file, dst):
    with sqlite3.connect(backup_file) as source:
        if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError(f"Backup failed integrity check: {backup_file}")
        with sqlite3.connect(dst) as target:
            source.backup(target)
        target.close()
    source.close()
    print(f"Restored {dst} from {backup_file}")


if __name__ == '__main__':
    from app import create_app
    from models import db
    app = create_app()
    backup_dir = app.config["BACKUP_DIR"]
    if len(sys.argv) != 2:
        print("Usage: python scripts/restore.py <backup file>\nStop the app before restoring.\nAvailable backups:")
        for name in sorted(os.listdir(backup_dir)) if os.path.isdir(backup_dir) else []:
            print(f"  {os.path.join(backup_dir, name)}")
        sys.exit(1)
    with app.app_context():
        path = db.engine.url.database
        db.engine.dispose()
    restore_database(sys.argv[1], path)
