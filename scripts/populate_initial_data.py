"""
Script para poblar datos iniciales de la base de datos
"""
import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from sqlmodel import Session, select
from decimal import Decimal

from app.core.database import engine
from app.models.beer import Cerveza, TipoEstiloCerveza
from app.models.sales_point import TipoBarril, TipoEstadoEquipo, PuntoVenta, Equipo
from app.models.user_extended import Usuario


def create_estilos_cerveza(session: Session):
    """Crear estilos de cerveza iniciales"""
    
    estilos_data = [
        {
            "estilo": "IPA",
            "descripcion": "India Pale Ale - Cerveza con alto contenido de lúpulo, sabor amargo y aromático",
            "origen": "Reino Unido"
        },
        {
            "estilo": "Lager",
            "descripcion": "Cerveza de fermentación baja, suave y refrescante",
            "origen": "Alemania"
        },
        {
            "estilo": "Stout",
            "descripcion": "Cerveza oscura con sabores tostados y cremosa",
            "origen": "Irlanda"
        },
        {
            "estilo": "Wheat Beer",
            "descripcion": "Cerveza de trigo, ligera y refrescante",
            "origen": "Alemania"
        },
        {
            "estilo": "Porter",
            "descripcion": "Cerveza oscura con sabores a chocolate y café",
            "origen": "Reino Unido"
        }
    ]
    
    print("Creando estilos de cerveza...")
    
    for estilo_data in estilos_data:
        # Verificar si ya existe
        existing = session.exec(
            select(TipoEstiloCerveza).where(TipoEstiloCerveza.estilo == estilo_data["estilo"])
        ).first()
        
        if not existing:
            estilo = TipoEstiloCerveza(**estilo_data)
            session.add(estilo)
            print(f"  ✓ Creado estilo: {estilo_data['estilo']}")
        else:
            print(f"  - Ya existe estilo: {estilo_data['estilo']}")
    
    session.commit()


def create_tipos_barril(session: Session):
    """Crear tipos de barril iniciales"""
    
    tipos_data = [
        {
            "nombre": "Barril 20L",
            "capacidad": 20,
            "descripcion": "Barril estándar de 20 litros"
        },
        {
            "nombre": "Barril 30L", 
            "capacidad": 30,
            "descripcion": "Barril mediano de 30 litros"
        },
        {
            "nombre": "Barril 50L",
            "capacidad": 50,
            "descripcion": "Barril grande de 50 litros"
        },
        {
            "nombre": "Barril 100L",
            "capacidad": 100,
            "descripcion": "Barril extra grande de 100 litros"
        }
    ]
    
    print("Creando tipos de barril...")
    
    for tipo_data in tipos_data:
        # Verificar si ya existe
        existing = session.exec(
            select(TipoBarril).where(TipoBarril.nombre == tipo_data["nombre"])
        ).first()
        
        if not existing:
            tipo = TipoBarril(**tipo_data)
            session.add(tipo)
            print(f"  ✓ Creado tipo de barril: {tipo_data['nombre']}")
        else:
            print(f"  - Ya existe tipo de barril: {tipo_data['nombre']}")
    
    session.commit()


def create_estados_equipo(session: Session):
    """Crear estados de equipo iniciales"""
    
    estados_data = [
        {
            "estado": "Activo",
            "permite_ventas": True
        },
        {
            "estado": "Mantenimiento",
            "permite_ventas": False
        },
        {
            "estado": "Fuera de Servicio",
            "permite_ventas": False
        },
        {
            "estado": "Sin Cerveza",
            "permite_ventas": False
        },
        {
            "estado": "Limpieza",
            "permite_ventas": False
        }
    ]
    
    print("Creando estados de equipo...")
    
    for estado_data in estados_data:
        # Verificar si ya existe
        existing = session.exec(
            select(TipoEstadoEquipo).where(TipoEstadoEquipo.estado == estado_data["estado"])
        ).first()
        
        if not existing:
            estado = TipoEstadoEquipo(**estado_data)
            session.add(estado)
            print(f"  ✓ Creado estado: {estado_data['estado']}")
        else:
            print(f"  - Ya existe estado: {estado_data['estado']}")
    
    session.commit()


def create_sample_cervezas(session: Session):
    """Crear cervezas de ejemplo"""
    
    # Obtener o crear usuario administrador
    admin_user = session.exec(select(Usuario)).first()
    if not admin_user:
        print("No hay usuarios en la base de datos. Creando usuario administrador...")
        admin_user = Usuario(
            nombre="Admin",
            email="admin@becard.com",
            telefono="123456789",
            activo=True
        )
        session.add(admin_user)
        session.commit()
        session.refresh(admin_user)
    
    # Obtener estilos
    estilos = session.exec(select(TipoEstiloCerveza)).all()
    estilo_map = {estilo.estilo: estilo.id for estilo in estilos}
    
    cervezas_data = [
        {
            "nombre": "Golden IPA",
            "tipo": "IPA",
            "descripcion": "IPA dorada con notas cítricas",
            "abv": Decimal("6.2"),
            "ibu": 55,
            "proveedor": "Cervecería Artesanal",
            "creado_por": admin_user.id
        },
        {
            "nombre": "Classic Lager",
            "tipo": "Lager",
            "descripcion": "Lager clásica y refrescante",
            "abv": Decimal("4.8"),
            "ibu": 18,
            "proveedor": "Cervecería Nacional",
            "creado_por": admin_user.id
        },
        {
            "nombre": "Dark Stout",
            "tipo": "Stout",
            "descripcion": "Stout cremosa con sabor a café",
            "abv": Decimal("5.5"),
            "ibu": 35,
            "proveedor": "Cervecería Premium",
            "creado_por": admin_user.id
        }
    ]
    
    print("Creando cervezas de ejemplo...")
    
    for cerveza_data in cervezas_data:
        # Verificar si ya existe
        existing = session.exec(
            select(Cerveza).where(Cerveza.nombre == cerveza_data["nombre"])
        ).first()
        
        if not existing:
            cerveza = Cerveza(**cerveza_data)
            session.add(cerveza)
            print(f"  ✓ Creada cerveza: {cerveza_data['nombre']}")
        else:
            print(f"  - Ya existe cerveza: {cerveza_data['nombre']}")
    
    session.commit()


def create_sample_punto_venta(session: Session):
    """Crear punto de venta de ejemplo"""
    
    # Verificar si ya existe un punto de venta
    existing = session.exec(select(PuntoVenta)).first()
    
    if not existing:
        punto_venta = PuntoVenta(
            nombre="Bar Principal",
            calle="Av. Cervecera",
            altura=123,
            localidad="Buenos Aires",
            provincia="Buenos Aires",
            codigo_postal="1000",
            telefono="+54 11 1234-5678",
            email="bar@becard.com",
            creado_por=1  # Asumimos que existe un usuario con ID 1
        )
        session.add(punto_venta)
        session.commit()
        print("✓ Creado punto de venta: Bar Principal")
        return punto_venta.id
    else:
        print("- Ya existe punto de venta")
        return existing.id


def create_sample_equipos(session: Session):
    """Crear equipos de ejemplo"""
    
    # Obtener datos necesarios
    punto_venta_id = create_sample_punto_venta(session)
    
    tipos_barril = session.exec(select(TipoBarril)).all()
    estados = session.exec(select(TipoEstadoEquipo)).all()
    cervezas = session.exec(select(Cerveza)).all()
    
    if not tipos_barril or not estados:
        print("Error: No hay tipos de barril o estados disponibles")
        return
    
    # Mapear por nombre
    barril_map = {barril.nombre: barril.id for barril in tipos_barril}
    estado_map = {estado.estado: estado.id for estado in estados}
    
    equipos_data = [
        {
            "nombre_equipo": "Grifo 1 - Barra Principal",
            "id_barril": barril_map.get("Barril 30L"),
            "capacidad_actual": 25,  # 85% lleno (25 de 30L)
            "temperatura_actual": Decimal("4.5"),
            "id_punto_de_venta": punto_venta_id,
            "id_estado_equipo": estado_map.get("Activo"),
            "id_cerveza": cervezas[0].id if cervezas else None
        },
        {
            "nombre_equipo": "Grifo 2 - Barra Principal", 
            "id_barril": barril_map.get("Barril 20L"),
            "capacidad_actual": 3,   # 15% lleno - stock bajo (3 de 20L)
            "temperatura_actual": Decimal("4.0"),
            "id_punto_de_venta": punto_venta_id,
            "id_estado_equipo": estado_map.get("Activo"),
            "id_cerveza": cervezas[1].id if len(cervezas) > 1 else None
        },
        {
            "nombre_equipo": "Grifo 3 - Terraza",
            "id_barril": barril_map.get("Barril 50L"),
            "capacidad_actual": 45,  # 90% lleno (45 de 50L)
            "temperatura_actual": Decimal("5.0"),
            "id_punto_de_venta": punto_venta_id,
            "id_estado_equipo": estado_map.get("Activo"),
            "id_cerveza": cervezas[2].id if len(cervezas) > 2 else None
        },
        {
            "nombre_equipo": "Grifo 4 - Mantenimiento",
            "id_barril": barril_map.get("Barril 20L"),
            "capacidad_actual": 0,   # Vacío
            "temperatura_actual": Decimal("6.0"),
            "id_punto_de_venta": punto_venta_id,
            "id_estado_equipo": estado_map.get("Mantenimiento"),
            "id_cerveza": None
        }
    ]
    
    print("Creando equipos de ejemplo...")
    
    for equipo_data in equipos_data:
        if equipo_data["id_barril"] and equipo_data["id_estado_equipo"]:
            # Verificar si ya existe
            existing = session.exec(
                select(Equipo).where(Equipo.nombre_equipo == equipo_data["nombre_equipo"])
            ).first()
            
            if not existing:
                equipo = Equipo(**equipo_data)
                session.add(equipo)
                print(f"  ✓ Creado equipo: {equipo_data['nombre_equipo']}")
            else:
                print(f"  - Ya existe equipo: {equipo_data['nombre_equipo']}")
    
    session.commit()


def main():
    """Función principal para poblar datos iniciales"""
    
    print("🍺 Iniciando población de datos iniciales para BeCard...")
    print("=" * 60)
    
    with Session(engine) as session:
        try:
            # Crear datos en orden de dependencias
            create_estilos_cerveza(session)
            print()
            
            create_tipos_barril(session)
            print()
            
            create_estados_equipo(session)
            print()
            
            create_sample_cervezas(session)
            print()
            
            create_sample_equipos(session)
            print()
            
            print("=" * 60)
            print("✅ Población de datos completada exitosamente!")
            print("\nDatos creados:")
            print("- Estilos de cerveza: IPA, Lager, Stout, Wheat Beer, Porter")
            print("- Tipos de barril: 20L, 30L, 50L, 100L")
            print("- Estados de equipo: Activo, Mantenimiento, Fuera de Servicio, Sin Cerveza, Limpieza")
            print("- Cervezas de ejemplo: Golden IPA, Classic Lager, Dark Stout")
            print("- Equipos de ejemplo: 4 grifos con diferentes niveles de stock")
            print("\n🎯 El sistema está listo para probar las alertas de stock!")
            
        except Exception as e:
            print(f"❌ Error durante la población de datos: {e}")
            session.rollback()
            raise


if __name__ == "__main__":
    main()