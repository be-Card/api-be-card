#!/usr/bin/env python3
"""
Check users in database
"""
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[0]
sys.path.append(str(project_root))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.user_extended import Usuario
from app.core.security import verify_password

def check_users():
    """Check users in database"""
    with Session(engine) as session:
        # Get all users
        users = session.exec(select(Usuario)).all()
        
        print(f"Found {len(users)} users:")
        for user in users:
            print(f"- ID: {user.id}")
            print(f"  Email: {user.email}")
            print(f"  Username: {user.nombre_usuario}")
            print(f"  Password Hash: {user.password_hash}")
            print(f"  Active: {user.activo}")
            print(f"  Verified: {user.verificado}")
            
            # Test password verification for known users
            if user.email == "admin@becard.com":
                result = verify_password("admin", user.password_hash)
                print(f"  Password 'admin' verification: {result}")
            elif user.email == "cliente@demo.com":
                result = verify_password("demo", user.password_hash)
                print(f"  Password 'demo' verification: {result}")
            print()

if __name__ == "__main__":
    check_users()