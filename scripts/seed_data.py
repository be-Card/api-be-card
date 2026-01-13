"""
Script para insertar datos iniciales en la base de datos
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session
from app.core.database import engine
from app.models.beer import TipoEstiloCerveza
from app.models.sales_point import TipoEstadoEquipo, TipoBarril

def seed_estilos_cerveza():
    """Insertar estilos de cerveza iniciales"""
    estilos = [
        {
            "estilo": "IPA",
            "descripcion": "India Pale Ale - Cerveza con alto contenido de lúpulo",
            "origen": "Reino Unido"
        },
        {
            "estilo": "Lager",
            "descripcion": "Cerveza de fermentación baja, suave y refrescante",
            "origen": "Alemania"
        },
        {
            "estilo": "Stout",
            "descripcion": "Cerveza oscura con sabores tostados",
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
    
    with Session(engine) as session:
        for estilo_data in estilos:
            # Verificar si ya existe
            existing = session.query(TipoEstiloCerveza).filter(
                TipoEstiloCerveza.estilo == estilo_data["estilo"]
            ).first()
            
            if not existing:
                estilo = TipoEstiloCerveza(**estilo_data)
                session.add(estilo)
        
        session.commit()
        print("Estilos de cerveza insertados correctamente")

def seed_estados_equipo():
    """Insertar estados de equipo iniciales"""
    estados = [
        {"estado": "Activo", "permite_ventas": True},
        {"estado": "Inactivo", "permite_ventas": False},
        {"estado": "En Mantenimiento", "permite_ventas": False},
        {"estado": "Fuera de Servicio", "permite_ventas": False}
    ]
    
    with Session(engine) as session:
        for estado_data in estados:
            # Verificar si ya existe
            existing = session.query(TipoEstadoEquipo).filter(
                TipoEstadoEquipo.estado == estado_data["estado"]
            ).first()
            
            if not existing:
                estado = TipoEstadoEquipo(**estado_data)
                session.add(estado)
        
        session.commit()
        print("Estados de equipo insertados correctamente")

def seed_tipos_barril():
    """Insertar tipos de barril iniciales"""
    tipos = [
        {"capacidad": 20, "nombre": "Barril 20L"},
        {"capacidad": 30, "nombre": "Barril 30L"},
        {"capacidad": 50, "nombre": "Barril 50L"}
    ]
    
    with Session(engine) as session:
        for tipo_data in tipos:
            # Verificar si ya existe
            existing = session.query(TipoBarril).filter(
                TipoBarril.capacidad == tipo_data["capacidad"]
            ).first()
            
            if not existing:
                tipo = TipoBarril(**tipo_data)
                session.add(tipo)
        
        session.commit()
        print("Tipos de barril insertados correctamente")

if __name__ == "__main__":
    print("Insertando datos iniciales...")
    seed_estilos_cerveza()
    seed_estados_equipo()
    seed_tipos_barril()
    print("Datos iniciales insertados correctamente")