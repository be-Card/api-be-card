#!/usr/bin/env python3
"""
Script to add an admin user with admin@gmail.com email
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.user_extended import Usuario
from app.core.security import get_password_hash
import uuid
from datetime import datetime

def add_gmail_admin():
    """Add admin user with admin@gmail.com email"""
    with Session(engine) as session:
        # Check if admin@gmail.com already exists
        existing_user = session.exec(
            select(Usuario).where(Usuario.email == "admin@gmail.com")
        ).first()
        
        if existing_user:
            print("User admin@gmail.com already exists!")
            print(f"- ID: {existing_user.id}")
            print(f"- Active: {existing_user.activo}")
            print(f"- Username: {existing_user.nombre_usuario}")
            return
        
        # Create new admin user
        new_admin = Usuario(
            id_ext=str(uuid.uuid4()),
            nombre_usuario="admin_gmail",
            codigo_cliente=f"ADM{datetime.now().strftime('%Y%m%d%H%M%S')}",
            nombres="Admin",
            apellidos="Gmail",
            email="admin@gmail.com",
            password_hash=get_password_hash("admin"),  # Same password as other admin
            activo=True,
            verificado=True,
            tipo_registro="app",
            intentos_login_fallidos=0
        )
        
        session.add(new_admin)
        session.commit()
        session.refresh(new_admin)
        
        print(f"Successfully created admin@gmail.com user!")
        print(f"- ID: {new_admin.id}")
        print(f"- Username: {new_admin.nombre_usuario}")
        print(f"- Email: {new_admin.email}")
        print(f"- Password: admin")
        print(f"- Active: {new_admin.activo}")

if __name__ == "__main__":
    add_gmail_admin()