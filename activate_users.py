#!/usr/bin/env python3
"""
Activate test users
"""
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[0]
sys.path.append(str(project_root))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.user_extended import Usuario

def activate_test_users():
    """Activate test users"""
    with Session(engine) as session:
        # Activate admin user
        admin = session.exec(select(Usuario).where(Usuario.email == "admin@becard.com")).first()
        if admin:
            admin.activo = True
            session.add(admin)
            print(f"✅ Activated admin user: {admin.email}")
        
        # Activate demo user
        demo = session.exec(select(Usuario).where(Usuario.email == "cliente@demo.com")).first()
        if demo:
            demo.activo = True
            session.add(demo)
            print(f"✅ Activated demo user: {demo.email}")
        
        session.commit()
        print("🎉 Test users activated successfully!")

if __name__ == "__main__":
    activate_test_users()