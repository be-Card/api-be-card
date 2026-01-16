"""
Servicios de negocio para equipos
"""
from sqlmodel import Session, select, SQLModel
from typing import List, Optional
from decimal import Decimal
from datetime import datetime

from ..models.sales_point import (
    Equipo, EquipoCreate, EquipoRead, EquipoUpdate,
    TipoEstadoEquipo, TipoBarril, PuntoVenta,
    TipoEstadoEquipoRead, TipoBarrilRead, PuntoVentaRead
)
from ..models.beer import Cerveza, CervezaRead

class EquipoDetailRead(EquipoRead):
    """Esquema extendido para leer equipo con detalles completos"""
    estado: TipoEstadoEquipoRead
    barril: TipoBarrilRead
    punto_venta: Optional[PuntoVentaRead]
    cerveza_actual: Optional[CervezaRead]
    nivel_barril_porcentaje: int
    volumen_actual: float


class CambiarCervezaRequest(SQLModel):
    """Esquema para cambiar cerveza de un equipo"""
    id_cerveza: int
    capacidad_nueva: int
    id_barril: Optional[int] = None
    motivo: Optional[str] = None


class EquipoService:
    """Servicio de negocio para equipos"""
    
    @staticmethod
    def get_equipos_with_details(session: Session, tenant_id: Optional[int] = None) -> List[EquipoDetailRead]:
        """Obtener equipos con detalles completos"""

        stmt = select(Equipo).where(Equipo.activo == True).order_by(Equipo.nombre_equipo, Equipo.id)
        if tenant_id is not None:
            stmt = (
                stmt.join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
                .where(PuntoVenta.tenant_id == tenant_id)
            )

        equipos = session.exec(stmt).all()
        
        equipos_detail = []
        for equipo in equipos:
            equipo_detail = EquipoService._equipo_to_detail_read(session, equipo)
            equipos_detail.append(equipo_detail)
        
        return equipos_detail
    
    @staticmethod
    def get_equipo_by_id(session: Session, equipo_id: int) -> Optional[EquipoDetailRead]:
        """Obtener equipo por ID con detalles completos"""
        equipo = session.get(Equipo, equipo_id)
        if not equipo:
            return None
        
        return EquipoService._equipo_to_detail_read(session, equipo)
    
    @staticmethod
    def create_equipo(
        session: Session,
        equipo_data: EquipoCreate,
        user_id: int
    ) -> EquipoDetailRead:
        """Crear nuevo equipo"""
        
        equipo_dict = equipo_data.model_dump()
        equipo = Equipo(**equipo_dict)
        
        session.add(equipo)
        session.commit()
        session.refresh(equipo)
        
        return EquipoService._equipo_to_detail_read(session, equipo)
    
    @staticmethod
    def update_equipo(
        session: Session,
        equipo_id: int,
        equipo_data: EquipoUpdate,
        user_id: int
    ) -> Optional[EquipoDetailRead]:
        """Actualizar equipo"""
        
        equipo = session.get(Equipo, equipo_id)
        if not equipo:
            return None
        
        update_data = equipo_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(equipo, field, value)
        
        session.commit()
        session.refresh(equipo)
        
        return EquipoService._equipo_to_detail_read(session, equipo)
    
    @staticmethod
    def cambiar_cerveza_equipo(
        session: Session,
        equipo_id: int,
        nueva_cerveza_id: int,
        capacidad_nueva: int,
        id_barril: Optional[int],
        user_id: int,
        motivo: Optional[str] = None
    ) -> Optional[EquipoDetailRead]:
        """Cambiar cerveza de un equipo y actualizar capacidad"""
        
        equipo = session.get(Equipo, equipo_id)
        if not equipo:
            return None
        
        # Verificar que la cerveza existe
        cerveza = session.get(Cerveza, nueva_cerveza_id)
        if not cerveza:
            raise ValueError(f"Cerveza con ID {nueva_cerveza_id} no encontrada")
        
        if id_barril is not None and id_barril != equipo.id_barril:
            nuevo_barril = session.get(TipoBarril, id_barril)
            if not nuevo_barril:
                raise ValueError(f"Tipo de barril con ID {id_barril} no encontrado")
            equipo.id_barril = id_barril

        # Verificar que la capacidad no exceda la del barril
        barril = session.get(TipoBarril, equipo.id_barril)
        if capacidad_nueva > barril.capacidad:
            raise ValueError(f"Capacidad {capacidad_nueva}L excede la capacidad del barril ({barril.capacidad}L)")
        
        # Actualizar equipo
        equipo.id_cerveza = nueva_cerveza_id
        equipo.capacidad_actual = capacidad_nueva
        
        # TODO: Registrar el cambio en un log de cambios de cerveza
        # Esto podría ser útil para auditoría y seguimiento
        
        session.commit()
        session.refresh(equipo)
        return EquipoService._equipo_to_detail_read(session, equipo)
    
    @staticmethod
    def toggle_estado_equipo(
        session: Session,
        equipo_id: int,
        nuevo_estado_id: int,
        user_id: int,
        motivo: Optional[str] = None
    ) -> Optional[EquipoDetailRead]:
        """Cambiar estado de un equipo"""
        
        equipo = session.get(Equipo, equipo_id)
        if not equipo:
            return None
        
        # Verificar que el estado existe
        estado = session.get(TipoEstadoEquipo, nuevo_estado_id)
        if not estado:
            raise ValueError(f"Estado con ID {nuevo_estado_id} no encontrado")
        
        equipo.id_estado_equipo = nuevo_estado_id
        
        # TODO: Registrar el cambio de estado en un log
        
        session.commit()
        session.refresh(equipo)
        
        return EquipoService._equipo_to_detail_read(session, equipo)
    
    @staticmethod
    def toggle_estado_simple(
        session: Session,
        equipo_id: int,
        user_id: int
    ) -> Optional[EquipoDetailRead]:
        """Alternar estado del equipo entre Activo e Inactivo automáticamente"""
        
        equipo = session.get(Equipo, equipo_id)
        if not equipo:
            return None
        
        # Obtener el estado actual
        estado_actual = session.get(TipoEstadoEquipo, equipo.id_estado_equipo)
        if not estado_actual:
            raise ValueError("Estado actual del equipo no encontrado")
        
        # Buscar estados Activo e Inactivo
        estado_activo = session.exec(
            select(TipoEstadoEquipo).where(TipoEstadoEquipo.estado == "Activo")
        ).first()
        
        estado_inactivo = session.exec(
            select(TipoEstadoEquipo).where(
                TipoEstadoEquipo.estado.in_(["Inactivo", "Fuera de Servicio"])
            )
        ).first()
        
        if not estado_activo or not estado_inactivo:
            raise ValueError("Estados Activo/Inactivo no encontrados en la base de datos")
        
        # Alternar estado
        if estado_actual.estado == "Activo":
            equipo.id_estado_equipo = estado_inactivo.id
        else:
            equipo.id_estado_equipo = estado_activo.id
        
        # TODO: Registrar el cambio de estado en un log
        
        session.commit()
        session.refresh(equipo)
        
        return EquipoService._equipo_to_detail_read(session, equipo)
    
    @staticmethod
    def update_temperatura(
        session: Session,
        equipo_id: int,
        temperatura: float
    ) -> Optional[EquipoDetailRead]:
        """Actualizar temperatura del equipo"""
        
        equipo = session.get(Equipo, equipo_id)
        if not equipo:
            return None
        
        equipo.temperatura_actual = Decimal(str(temperatura))
        
        session.commit()
        session.refresh(equipo)
        
        return EquipoService._equipo_to_detail_read(session, equipo)
    
    @staticmethod
    def get_nivel_barril_porcentaje(
        capacidad_barril: int,
        capacidad_actual: int
    ) -> int:
        """Calcular porcentaje de nivel del barril"""
        if capacidad_barril <= 0:
            return 0
        
        porcentaje = (capacidad_actual / capacidad_barril) * 100
        return min(100, max(0, int(porcentaje)))
    
    @staticmethod
    def get_tipos_barril(session: Session) -> List[TipoBarrilRead]:
        """Obtener todos los tipos de barril"""
        tipos = session.exec(select(TipoBarril).order_by(TipoBarril.capacidad)).all()
        return [
            TipoBarrilRead(
                id=tipo.id,
                id_ext=str(tipo.id_ext),
                capacidad=tipo.capacidad,
                nombre=tipo.nombre
            )
            for tipo in tipos
        ]
    
    @staticmethod
    def get_estados_equipo(session: Session) -> List[TipoEstadoEquipoRead]:
        """Obtener todos los estados de equipo"""
        estados = session.exec(select(TipoEstadoEquipo).order_by(TipoEstadoEquipo.estado)).all()
        return [
            TipoEstadoEquipoRead(
                id=estado.id,
                id_ext=str(estado.id_ext),
                estado=estado.estado,
                permite_ventas=estado.permite_ventas
            )
            for estado in estados
        ]
    
    @staticmethod
    def get_equipos_con_stock_bajo(session: Session, umbral_porcentaje: int = 20) -> List[EquipoDetailRead]:
        """Obtener equipos con stock bajo"""
        equipos = session.exec(select(Equipo)).all()
        equipos_stock_bajo = []
        
        for equipo in equipos:
            barril = session.get(TipoBarril, equipo.id_barril)
            porcentaje = EquipoService.get_nivel_barril_porcentaje(
                barril.capacidad, 
                equipo.capacidad_actual
            )
            
            if porcentaje <= umbral_porcentaje:
                equipo_detail = EquipoService._equipo_to_detail_read(session, equipo)
                equipos_stock_bajo.append(equipo_detail)
        
        return equipos_stock_bajo
    
    @staticmethod
    def _equipo_to_detail_read(session: Session, equipo: Equipo) -> EquipoDetailRead:
        """Convertir modelo Equipo a EquipoDetailRead con datos adicionales"""
        
        # Obtener estado
        estado = session.get(TipoEstadoEquipo, equipo.id_estado_equipo)
        estado_read = TipoEstadoEquipoRead(
            id=estado.id,
            id_ext=str(estado.id_ext),
            estado=estado.estado,
            permite_ventas=estado.permite_ventas
        )
        
        # Obtener barril
        barril = session.get(TipoBarril, equipo.id_barril)
        barril_read = TipoBarrilRead(
            id=barril.id,
            id_ext=str(barril.id_ext),
            capacidad=barril.capacidad,
            nombre=barril.nombre
        )
        
        # Obtener punto de venta (opcional)
        punto_venta_read = None
        if equipo.id_punto_de_venta:
            punto_venta = session.get(PuntoVenta, equipo.id_punto_de_venta)
            if punto_venta:
                punto_venta_read = PuntoVentaRead(
                    id=punto_venta.id,
                    id_ext=str(punto_venta.id_ext),
                    nombre=punto_venta.nombre,
                    calle=punto_venta.calle,
                    altura=punto_venta.altura,
                    localidad=punto_venta.localidad,
                    provincia=punto_venta.provincia,
                    codigo_postal=punto_venta.codigo_postal,
                    telefono=punto_venta.telefono,
                    email=punto_venta.email,
                    horario_apertura=punto_venta.horario_apertura,
                    horario_cierre=punto_venta.horario_cierre,
                    activo=punto_venta.activo,
                    creado_el=punto_venta.creado_el,
                    creado_por=punto_venta.creado_por,
                    id_usuario_socio=punto_venta.id_usuario_socio
                )
        
        # Obtener cerveza actual (opcional)
        cerveza_read = None
        if equipo.id_cerveza:
            cerveza = session.get(Cerveza, equipo.id_cerveza)
            if cerveza:
                cerveza_read = CervezaRead(
                    id=cerveza.id,
                    id_ext=str(cerveza.id_ext),
                    nombre=cerveza.nombre,
                    tipo=cerveza.tipo,
                    abv=cerveza.abv,
                    ibu=cerveza.ibu,
                    descripcion=cerveza.descripcion,
                    imagen=cerveza.imagen,
                    proveedor=cerveza.proveedor,
                    activo=cerveza.activo,
                    destacado=cerveza.destacado,
                    creado_el=cerveza.creado_el,
                    creado_por=cerveza.creado_por,
                    estilos=[]  # Los estilos se pueden cargar por separado si es necesario
                )
        
        # Calcular nivel de barril
        nivel_porcentaje = EquipoService.get_nivel_barril_porcentaje(
            barril.capacidad,
            equipo.capacidad_actual
        )
        
        return EquipoDetailRead(
            id=equipo.id,
            id_ext=str(equipo.id_ext),
            nombre_equipo=equipo.nombre_equipo,
            id_barril=equipo.id_barril,
            capacidad_actual=equipo.capacidad_actual,
            temperatura_actual=equipo.temperatura_actual,
            ultima_limpieza=equipo.ultima_limpieza,
            proxima_limpieza=equipo.proxima_limpieza,
            id_estado_equipo=equipo.id_estado_equipo,
            id_punto_de_venta=equipo.id_punto_de_venta,
            id_cerveza=equipo.id_cerveza,
            creado_el=equipo.creado_el,
            estado=estado_read,
            barril=barril_read,
            punto_venta=punto_venta_read,
            cerveza_actual=cerveza_read,
            nivel_barril_porcentaje=nivel_porcentaje,
            volumen_actual=float(equipo.capacidad_actual)
        )
