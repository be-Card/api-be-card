import sys
import os
from pathlib import Path
import uuid
from decimal import Decimal
from sqlmodel import Session, select

# Agregar el directorio raíz al path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from app.core.database import engine, create_db_and_tables
from app.models.terminal import TerminalRegistro
from app.models.sales_point import Equipo, PuntoVenta
from app.models.tenant import Tenant
from app.models.beer import Cerveza, PrecioCerveza
from app.models.user_extended import Usuario
from app.core.security import get_password_hash

def seed_terminal(kiosk_uuid_str: str):
    try:
        kiosk_uuid = uuid.UUID(kiosk_uuid_str)
    except ValueError:
        print(f"Error: {kiosk_uuid_str} no es un UUID válido.")
        return
    
    with Session(engine) as session:
        # 1. Asegurar que existe al menos un Tenant (usar el de bar-test de seed_tenant.py si existe)
        tenant = session.exec(select(Tenant).where(Tenant.slug == "bar-test")).first()
        if not tenant:
            tenant = session.exec(select(Tenant)).first()
            
        if not tenant:
            print("Creando tenant por defecto...")
            tenant = Tenant(
                nombre="Bar Test",
                slug="bar-test",
                plan_id=1,
                activo=True
            )
            session.add(tenant)
            session.commit()
            session.refresh(tenant)
        
        # 2. Asegurar que existe al menos un Equipo (usar Grifo 1 si existe)
        equipo = session.exec(select(Equipo).where(Equipo.nombre_equipo == "Grifo 1 - Barra Principal")).first()
        if not equipo:
            equipo = session.exec(select(Equipo)).first()
            
        if not equipo:
            print("Error: No se encontró ningún equipo. Por favor, corre populate_initial_data.py primero.")
            return

        # 3. Verificar si el terminal ya existe (por id_ext o por nombre)
        existing = session.exec(
            select(TerminalRegistro).where(TerminalRegistro.id_ext == kiosk_uuid)
        ).first()

        if existing:
            print(f"La terminal {kiosk_uuid_str} ya existe.")
            existing.activo = True
            existing.equipo_id = equipo.id
            existing.tenant_id = tenant.id
            session.add(existing)
            session.commit()
        else:
            # 4. Crear el registro de la terminal
            print(f"Registrando terminal {kiosk_uuid_str}...")
            terminal = TerminalRegistro(
                id_ext=kiosk_uuid,
                tenant_id=tenant.id,
                equipo_id=equipo.id,
                punto_venta_id=equipo.id_punto_de_venta,
                codigo_terminal="KIOSK-TEST",
                nombre="Kiosk Test Device",
                mqtt_username="kiosk-test",
                mqtt_password_hash=get_password_hash("kiosk-secret"),
                mqtt_client_id=f"becard-kiosk-test",
                activo=True
            )
            
            session.add(terminal)
            session.commit()
            print(f"Terminal registrada exitosamente vinculada al equipo {equipo.id} ({equipo.nombre_equipo})")

        # 5. Asegurar que todas las cervezas tienen un precio configurado
        print("Verificando precios de cervezas...")
        cervezas = session.exec(select(Cerveza)).all()
        admin_user = session.exec(select(Usuario)).first()
        if not admin_user:
             print("Error: No se encontró usuario para asignar como creador del precio.")
             return

        for cerveza in cervezas:
            precio_actual = session.exec(
                select(PrecioCerveza)
                .where(PrecioCerveza.id_cerveza == cerveza.id)
                .where(PrecioCerveza.fecha_fin.is_(None))
            ).first()

            if not precio_actual:
                print(f"  - Sembrando precio para {cerveza.nombre}...")
                nuevo_precio = PrecioCerveza(
                    id_cerveza=cerveza.id,
                    precio=Decimal("500.00"),
                    creado_por=admin_user.id,
                    motivo="Semilla inicial para tests"
                )
                session.add(nuevo_precio)
        
        session.commit()
        print("Precios de cervezas verificados.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("kiosk_id", help="UUID della terminal física")
    args = parser.parse_args()
    seed_terminal(args.kiosk_id)
