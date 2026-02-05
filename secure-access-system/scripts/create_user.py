#!/usr/bin/env python3
"""
Terminal script for creating users (internal use only)
Run: python scripts/create_user.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, User
from routes.users import generate_password, generate_username

app = create_app()

with app.app_context():
    print("\n" + "="*50)
    print("INTERNAL USER CREATION TOOL")
    print("="*50)
    
    print("\nSelect creator role:")
    print("1. Management (can create concierge/resident)")
    print("2. Concierge (can create resident only)")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        creator_role = "management"
    elif choice == "2":
        creator_role = "concierge"
    else:
        print("Invalid choice")
        sys.exit(1)
    
    print(f"\nCreating user as {creator_role}...")
    print("-"*30)
    
    first_name = input("First Name: ").strip()
    last_name = input("Last Name: ").strip()
    email = input("Email: ").strip()
    
    if creator_role == "management":
        print("\nSelect role for new user:")
        print("1. Concierge")
        print("2. Resident")
        role_choice = input("Enter choice (1 or 2): ").strip()
        role = "concierge" if role_choice == "1" else "resident"
    else:
        # Concierge can only create residents
        role = "resident"
    
    # Check if user exists
    if User.query.filter_by(email=email).first():
        print(f"\n❌ User with email {email} already exists!")
        sys.exit(1)
    
    # Generate credentials
    temp_password = generate_password()
    username = generate_username(first_name, last_name)
    
    # Create user
    user = User(
        first_name=first_name,
        last_name=last_name,
        username=username,
        email=email,
        role=role
    )
    user.set_password(temp_password)
    
    db.session.add(user)
    db.session.commit()
    
    print(f"\n✅ User created successfully!")
    print(f"   Username: {username}")
    print(f"   Email: {email}")
    print(f"   Role: {role}")
    print(f"   Temporary Password: {temp_password}")
    print("\n⚠️  Note: This user cannot log in until Phase 2")
    print("="*50)