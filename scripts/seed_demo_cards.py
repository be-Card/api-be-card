"""
Script para asignar tarjetas de prueba a los usuarios de demostración
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.tenant import Tenant
from app.models.user_extended import Usuario
from app.services.cards import CardService
from app.services.tenants import TenantService

UID_DEMO="0402bb821a6481"
UID_GUEST="176bb74d"

def _assign_to_tenant(session: Session, user: Usuario, tenant: Tenant) -> None:
    # Update the user's native tenant_id if null
    if user.tenant_id is None:
        user.tenant_id = tenant.id
        session.add(user)
        session.commit()
    
    # Also ensure membership in tenant_users
    TenantService.add_user_to_tenant(session, tenant_id=tenant.id, user_id=user.id, rol="member")


def main():
    with Session(engine) as session:
        print("\n💳 Configurando tarjetas NFC de prueba...")
        
        # 1. Encontrar el tenant de prueba
        tenant = session.exec(select(Tenant).order_by(Tenant.id).limit(1)).first()
        if not tenant:
            print("❌ No se encontró ningún tenant. Ejecutá seed_tenant.py primero.")
            return

        print(f"   Usando Tenant: {tenant.nombre} (ID: {tenant.id})")

        # 2. Configurar Cliente Demo (UID_DEMO)
        demo_user = session.exec(select(Usuario).where(Usuario.email == "cliente@demo.com")).first()
        if demo_user:
            _assign_to_tenant(session, demo_user, tenant)
            try:
                CardService.bind_to_user(
                    session=session,
                    tenant_id=tenant.id,
                    uid=UID_DEMO,
                    user_id_ext=None,
                    codigo_cliente=demo_user.codigo_cliente,
                    assigned_by=demo_user.id  # a sys user or themself
                )
                print(f"   ✅ Tarjeta {UID_DEMO} asignada a Cliente Demo ({demo_user.email})")
            except Exception as e:
                # If already assigned, ignore
                if "UID_ALREADY_ASSIGNED" in str(e):
                    print(f"   ✅ Tarjeta {UID_DEMO} ya asignada al Cliente Demo.")
                else:
                    print(f"   ⚠️ Error asignando tarjeta a Demo: {e}")
        else:
            print("   ⚠️ Cliente Demo no encontrado")

        # 3. Configurar Guest Demo (UID_GUEST)
        guest_user = session.exec(select(Usuario).where(Usuario.codigo_cliente == "GUEST-001")).first()
        if guest_user:
            _assign_to_tenant(session, guest_user, tenant)
            try:
                CardService.bind_to_user(
                    session=session,
                    tenant_id=tenant.id,
                    uid=UID_GUEST,
                    user_id_ext=None,
                    codigo_cliente=guest_user.codigo_cliente,
                    assigned_by=guest_user.id
                )
                print(f"   ✅ Tarjeta {UID_GUEST} asignada al Guest (GUEST-001)")
            except Exception as e:
                if "UID_ALREADY_ASSIGNED" in str(e):
                    print(f"   ✅ Tarjeta {UID_GUEST} ya asignada al Guest.")
                else:
                    print(f"   ⚠️ Error asignando tarjeta al Guest: {e}")
        else:
            print("   ⚠️ Cliente Guest no encontrado")

        print("\n🎉 Tarjetas de prueba listas!\n")

if __name__ == "__main__":
    main()
