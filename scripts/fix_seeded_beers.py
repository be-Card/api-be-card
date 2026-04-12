import sys
import os
from pathlib import Path
from sqlmodel import Session, select
from decimal import Decimal

# Agregar el directorio raíz al path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from app.core.database import engine
from app.models.beer import Cerveza
from app.models.sales_point import Equipo

def fix_beers_for_tenant(tenant_id: int):
    print(f"🍺 Starting data fix for Tenant ID: {tenant_id}...")
    with Session(engine) as session:
        # Find all equipment for this tenant
        equipos = session.exec(select(Equipo).where(Equipo.tenant_id == tenant_id)).all()
        if not equipos:
            print(f"❌ No equipment found for Tenant {tenant_id}. Make sure to run seed scripts first.")
            return

        print(f"Found {len(equipos)} equipment(s) for Tenant {tenant_id}")
        
        fixed_count = 0
        for eq in equipos:
            if eq.id_cerveza:
                cerveza = session.get(Cerveza, eq.id_cerveza)
                if cerveza:
                    if cerveza.tenant_id is None:
                        print(f"  ✓ Linking global beer '{cerveza.nombre}' (ID: {cerveza.id}) to Tenant {tenant_id}")
                        cerveza.tenant_id = tenant_id
                        session.add(cerveza)
                        fixed_count += 1
                    elif cerveza.tenant_id == tenant_id:
                        print(f"  - Beer '{cerveza.nombre}' is already linked to Tenant {tenant_id}")
                    else:
                        print(f"  ⚠️  WARNING: Beer '{cerveza.nombre}' belongs to a DIFFERENT Tenant ({cerveza.tenant_id})")
                else:
                    print(f"  ❌ Assigned beer ID {eq.id_cerveza} not found in database for equipment '{eq.nombre_equipo}'")
            else:
                print(f"  - No beer assigned to equipment '{eq.nombre_equipo}'")
        
        if fixed_count > 0:
            session.commit()
            print(f"✅ Success: {fixed_count} beer(s) linked to Tenant {tenant_id}")
        else:
            print("ℹ️  No changes needed.")

if __name__ == "__main__":
    # We focus on Tenant ID 1 as requested by the user
    fix_beers_for_tenant(1)
