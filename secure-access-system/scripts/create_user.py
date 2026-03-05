#!/usr/bin/env python3
"""
Terminal script for creating users (internal use only)
Run: python scripts/create_user.py
"""
import sys
import os
import re
import secrets
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
    
    # Resident-specific fields
    unit_number = None
    floor = None
    door_code = None
    if role == "resident":
        unit_number = input("Unit Number (e.g., 12A): ").strip()
        if not unit_number:
            print("❌ Unit number is required for residents")
            sys.exit(1)
        # Extract floor from unit_number (leading digits)
        match = re.match(r"^(\d+)", unit_number)
        floor = int(match.group(1)) if match else 1
        door_code = secrets.token_hex(8).upper()  # Unique door code like IMEI
    
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
        role=role,
        unit_number=unit_number,
        floor=floor,
        door_code=door_code
    )
    user.set_password(temp_password)
    
    db.session.add(user)
    db.session.commit()
    
    print(f"\n✅ User created successfully!")
    print(f"   Username: {username}")
    print(f"   Email: {email}")
    print(f"   Role: {role}")
    print(f"   Temporary Password: {temp_password}")
    if role == "resident":
        print(f"   Unit Number: {unit_number}")
        print(f"   Floor: {floor}")
        print(f"   Door Code (IMEI): {door_code}")
    print("\n⚠️  Note: User can now log in and access the simulation if resident.")
    print("="*50)