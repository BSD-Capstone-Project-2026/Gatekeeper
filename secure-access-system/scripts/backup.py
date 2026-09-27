#!/usr/bin/env python3
import shutil
import os
from datetime import datetime

def backup_database():
    src = 'secure_access.db'
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(backup_dir, f'secure_access_{timestamp}.db')
    shutil.copy2(src, dst)
    print(f"Backup created: {dst}")
    # Optionally, remove old backups (keep last 10)
    backups = sorted(os.listdir(backup_dir))
    if len(backups) > 10:
        os.remove(os.path.join(backup_dir, backups[0]))

if __name__ == '__main__':
    backup_database()