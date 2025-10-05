"""
Script para crear datos iniciales (seed data) en la base de datos

Ejecutar con:
    python scripts/seed_data.py
"""
import sys
from pathlib import Path

# Añadir el directorio raíz del proyecto al sys.path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.user_extended import (
    TipoRolUsuario,
    TipoNivelUsuario,
    TipoMetodoPago,
    Usuario
)
from app.core.security import get_password_hash
from datetime import datetime, date


def seed_roles():
    """Crear roles iniciales"""
    with Session(engine) as session:
        # Verificar si ya existen
        existing = session.exec(select(TipoRolUsuario)).first()
        if existing:
            print("✓ Roles ya existen, saltando...")
            return
        
        roles = [
            TipoRolUsuario(
                rol="usuario",
                descripcion="Cliente regular del sistema de fidelización",
                creado_el=datetime.utcnow()
            ),
            TipoRolUsuario(
                rol="socio",
                descripcion="Propietario de punto de venta",
                creado_el=datetime.utcnow()
            ),
            TipoRolUsuario(
                rol="administrador",
                descripcion="Administrador del sistema",
                creado_el=datetime.utcnow()
            )
        ]
        
        for role in roles:
            session.add(role)
        
        session.commit()
        print("✓ Roles creados exitosamente")


def seed_niveles():
    """Crear niveles iniciales"""
    with Session(engine) as session:
        # Verificar si ya existen
        existing = session.exec(select(TipoNivelUsuario)).first()
        if existing:
            print("✓ Niveles ya existen, saltando...")
            return
        
        niveles = [
            TipoNivelUsuario(
                nivel="Bronce",
                puntaje_minimo=0,
                puntaje_max=100,
                beneficios="Acceso básico al sistema de fidelización"
            ),
            TipoNivelUsuario(
                nivel="Plata",
                puntaje_minimo=101,
                puntaje_max=500,
                beneficios="10% de descuento en premios, acceso a promociones especiales"
            ),
            TipoNivelUsuario(
                nivel="Oro",
                puntaje_minimo=501,
                puntaje_max=1000,
                beneficios="20% de descuento en premios, acceso prioritario a eventos"
            ),
            TipoNivelUsuario(
                nivel="Platino",
                puntaje_minimo=1001,
                puntaje_max=None,  # Sin límite
                beneficios="30% de descuento en premios, beneficios VIP, invitaciones exclusivas"
            )
        ]
        
        for nivel in niveles:
            session.add(nivel)
        
        session.commit()
        print("✓ Niveles creados exitosamente")


def seed_metodos_pago():
    """Crear métodos de pago iniciales"""
    with Session(engine) as session:
        # Verificar si ya existen
        existing = session.exec(select(TipoMetodoPago)).first()
        if existing:
            print("✓ Métodos de pago ya existen, saltando...")
            return
        
        metodos = [
            TipoMetodoPago(
                metodo_pago="efectivo",
                requiere_autorizacion=False,
                activo=True
            ),
            TipoMetodoPago(
                metodo_pago="tarjeta_debito",
                requiere_autorizacion=True,
                activo=True
            ),
            TipoMetodoPago(
                metodo_pago="tarjeta_credito",
                requiere_autorizacion=True,
                activo=True
            ),
            TipoMetodoPago(
                metodo_pago="mercadopago",
                requiere_autorizacion=True,
                activo=True
            ),
            TipoMetodoPago(
                metodo_pago="transferencia",
                requiere_autorizacion=False,
                activo=True
            )
        ]
        
        for metodo in metodos:
            session.add(metodo)
        
        session.commit()
        print("✓ Métodos de pago creados exitosamente")


def seed_admin_user():
    """Crear usuario administrador por defecto"""
    with Session(engine) as session:
        # Verificar si ya existe admin
        existing = UserService.get_user_by_email(session, "admin@becard.com")
        if existing:
            print("✓ Usuario admin ya existe, saltando...")
            return
        
        # Crear admin
        admin = UserService.create_user(
            session,
            nombre_usuario="admin",
            email="admin@becard.com",
            password="Admin123!",  # ⚠️ CAMBIAR EN PRODUCCIÓN
            nombre="Administrador",
            apellido="BeCard",
            sexo="MASCULINO",
            fecha_nacimiento=datetime(1990, 1, 1),
            telefono="+5491112345678"
        )
        
        # Asignar rol de administrador (id=3)
        UserService.add_role_to_user(session, admin.id, 3)
        
        print(f"✓ Usuario admin creado exitosamente (ID: {admin.id})")
        print(f"  Email: admin@becard.com")
        print(f"  Password: Admin123!")
        print(f"  ⚠️  IMPORTANTE: Cambiar password en producción")


def seed_demo_users():
    """Crear usuarios de demostración"""
    with Session(engine) as session:
        # Cliente demo
        cliente = UserService.get_user_by_email(session, "cliente@demo.com")
        if not cliente:
            cliente = UserService.create_user(
                session,
                nombre_usuario="cliente_demo",
                email="cliente@demo.com",
                password="Demo123!",
                nombre="Juan",
                apellido="Cliente",
                sexo="MASCULINO",
                fecha_nacimiento=datetime(1995, 5, 15),
                telefono="+5491123456789"
            )
            print(f"✓ Cliente demo creado (ID: {cliente.id})")
        
        # Socio demo
        socio = UserService.get_user_by_email(session, "socio@demo.com")
        if not socio:
            socio = UserService.create_user(
                session,
                nombre_usuario="socio_demo",
                email="socio@demo.com",
                password="Demo123!",
                nombre="María",
                apellido="Socia",
                sexo="FEMENINO",
                fecha_nacimiento=datetime(1988, 8, 20),
                telefono="+5491198765432"
            )
            # Asignar rol de socio (id=2)
            UserService.add_role_to_user(session, socio.id, 2)
            print(f"✓ Socio demo creado (ID: {socio.id})")


def main():
    """Ejecutar todos los seeds"""
    print("\n🌱 Iniciando seed de datos...\n")
    
    try:
        seed_roles()
        seed_niveles()
        seed_metodos_pago()
        seed_admin_user()
        seed_demo_users()
        
        print("\n✅ Seed completado exitosamente!\n")
        print("Usuarios creados:")
        print("  - Admin: admin@becard.com / Admin123!")
        print("  - Cliente: cliente@demo.com / Demo123!")
        print("  - Socio: socio@demo.com / Demo123!")
        print("\n⚠️  RECORDAR: Cambiar contraseñas en producción\n")
        
    except Exception as e:
        print(f"\n❌ Error durante el seed: {e}\n")
        raise


if __name__ == "__main__":
    main()
