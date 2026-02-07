# check_database.py
import os
import sys
from app import create_app
from models import db, User

app = create_app()
with app.app_context():
    print("🔍 Database Check")
    print("=" * 50)
    
    # Check database file
    db_path = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    print(f"Database URI: {db_path}")
    
    # Check if using file or memory
    if ':memory:' in db_path:
        print("❌ ERROR: Using in-memory database (data lost on restart)")
    elif 'sqlite:///' in db_path:
        # Extract filename
        filename = db_path.replace('sqlite:///', '')
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            print(f"✅ Database file exists: {filename}")
            print(f"📏 File size: {size} bytes")
        else:
            print(f"❌ Database file NOT found: {filename}")
    
    # Count users
    user_count = User.query.count()
    print(f"👥 Total users in database: {user_count}")
    
    # List all users
    print("\n📋 User List:")
    print("-" * 50)
    for user in User.query.all():
        print(f"ID: {user.id}, Username: {user.username}, Role: {user.role}, Email: {user.email}")
    
    print("\n✅ Database check complete!")