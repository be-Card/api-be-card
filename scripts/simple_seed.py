"""
Script simple para crear datos iniciales básicos
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
import hashlib
from datetime import datetime, date


def create_basic_data():
    """Crear datos básicos sin relaciones complejas"""
    with Session(engine) as session:
        print("🌱 Creando datos básicos...")
        
        # 1. Crear roles
        print("📋 Creando roles...")
        roles = [
            TipoRolUsuario(tipo="cliente", descripcion="Cliente regular"),
            TipoRolUsuario(tipo="socio", descripcion="Propietario de punto de venta"),
            TipoRolUsuario(tipo="administrador", descripcion="Administrador del sistema")
        ]
        for role in roles:
            existing = session.exec(select(TipoRolUsuario).where(TipoRolUsuario.tipo == role.tipo)).first()
            if not existing:
                session.add(role)
        session.commit()
        print("✅ Roles creados")
        
        # 2. Crear niveles
        print("📊 Creando niveles...")
        niveles = [
            TipoNivelUsuario(nivel="Bronce", puntaje_min=0, puntaje_max=999, beneficios="Acceso básico"),
            TipoNivelUsuario(nivel="Plata", puntaje_min=1000, puntaje_max=4999, beneficios="Descuentos exclusivos"),
            TipoNivelUsuario(nivel="Oro", puntaje_min=5000, puntaje_max=None, beneficios="Beneficios VIP")
        ]
        for nivel in niveles:
            existing = session.exec(select(TipoNivelUsuario).where(TipoNivelUsuario.nivel == nivel.nivel)).first()
            if not existing:
                session.add(nivel)
        session.commit()
        print("✅ Niveles creados")
        
        # 3. Crear métodos de pago
        print("💳 Creando métodos de pago...")
        metodos = [
            TipoMetodoPago(metodo_pago="Efectivo", activo=True, requiere_autorizacion=False),
            TipoMetodoPago(metodo_pago="Tarjeta de Crédito", activo=True, requiere_autorizacion=True),
            TipoMetodoPago(metodo_pago="Mercado Pago", activo=True, requiere_autorizacion=True)
        ]
        for metodo in metodos:
            existing = session.exec(select(TipoMetodoPago).where(TipoMetodoPago.metodo_pago == metodo.metodo_pago)).first()
            if not existing:
                session.add(metodo)
        session.commit()
        print("✅ Métodos de pago creados")
        
        # 4. Crear usuario admin
        print("👤 Creando usuario administrador...")
        admin_email = "admin@becard.com"
        existing_admin = session.exec(select(Usuario).where(Usuario.email == admin_email)).first()
        if not existing_admin:
            admin = Usuario(
                nombre_usuario="admin",
                email=admin_email,
                password_hash=hashlib.sha256("admin".encode()).hexdigest(),
                nombres="Admin",
                apellidos="BeCard",
                codigo_cliente="ADMIN-001",
                tipo_registro="app",
                activo=True,
                verificado=True
            )
            session.add(admin)
            session.commit()
            print("✅ Usuario administrador creado")
        else:
            print("✅ Usuario administrador ya existe")
        
        # 5. Crear usuario cliente demo
        print("👤 Creando usuario cliente demo...")
        cliente_email = "cliente@demo.com"
        existing_cliente = session.exec(select(Usuario).where(Usuario.email == cliente_email)).first()
        if not existing_cliente:
            cliente = Usuario(
                nombre_usuario="cliente_demo",
                email=cliente_email,
                password_hash=hashlib.sha256("demo".encode()).hexdigest(),
                nombres="Cliente",
                apellidos="Demo",
                codigo_cliente="DEMO-001",
                tipo_registro="app",
                activo=True,
                verificado=True
            )
            session.add(cliente)
            session.commit()
            print("✅ Usuario cliente demo creado")
        else:
            print("✅ Usuario cliente demo ya existe")
        
        # 6. Crear cliente guest
        print("👤 Creando cliente guest...")
        guest_codigo = "GUEST-001"
        existing_guest = session.exec(select(Usuario).where(Usuario.codigo_cliente == guest_codigo)).first()
        if not existing_guest:
            guest = Usuario(
                nombres="Guest",
                apellidos="Visitante",
                codigo_cliente=guest_codigo,
                tipo_registro="punto_venta",
                activo=True,
                verificado=False
            )
            session.add(guest)
            session.commit()
            print("✅ Cliente guest creado")
        else:
            print("✅ Cliente guest ya existe")
        
        print("\n🎉 Datos básicos creados exitosamente!")
        print("\n📝 Credenciales de prueba:")
        print("   Admin: admin@becard.com / admin")
        print("   Cliente: cliente@demo.com / demo")
        print("   Guest: Código GUEST-001")


if __name__ == "__main__":
    create_basic_data()
