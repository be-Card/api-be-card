"""
Servicio de negocio para reglas de precios y cálculo
"""
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from sqlmodel import Session, select
from decimal import Decimal

from ..models.pricing import (
    ReglaDePrecio,
    ReglaDePrecioCreate,
    ReglaDePrecioRead,
    ReglaDePrecioUpdate,
    ReglaDePrecioAlcance,
    ReglaDePrecioAlcanceRead,
    ConsultaPrecio,
    CalculoPrecio,
    CalculadoraPrecios,
)
from ..models.base import TipoAlcanceRegla, TipoPrioridadRegla
from .cervezas import CervezaService
from ..models.beer import Cerveza
from ..models.sales_point import PuntoVenta, Equipo


class PricingService:
    """Servicio de negocio para pricing"""

    @staticmethod
    def list_reglas(
        session: Session,
        skip: int = 0,
        limit: int = 10,
        search: Optional[str] = None,
        activo: Optional[bool] = None,
        estado: Optional[str] = None,
        order_dir: str = "asc",
    ) -> Tuple[List[ReglaDePrecioRead], int]:
        """Listar reglas de precio con filtros básicos y paginación"""
        query = select(ReglaDePrecio)

        if search:
            search_term = f"%{search}%"
            query = query.where(ReglaDePrecio.nombre.ilike(search_term))

        if activo is not None:
            query = query.where(ReglaDePrecio.esta_activo == activo)

        now = datetime.utcnow()
        if estado:
            estado_lower = estado.lower()
            if estado_lower == "programada":
                query = query.where(ReglaDePrecio.esta_activo == True, ReglaDePrecio.fecha_hora_inicio > now)
            elif estado_lower == "activa":
                query = query.where(
                    ReglaDePrecio.esta_activo == True,
                    ReglaDePrecio.fecha_hora_inicio <= now,
                    ReglaDePrecio.fecha_hora_fin != None,
                    ReglaDePrecio.fecha_hora_fin >= now,
                )
            elif estado_lower == "inactiva":
                query = query.where(
                    (ReglaDePrecio.esta_activo == False)
                    | ((ReglaDePrecio.esta_activo == True) & (ReglaDePrecio.fecha_hora_fin != None) & (ReglaDePrecio.fecha_hora_fin < now))
                )
            else:
                raise ValueError("Estado inválido. Use: Activa, Programada o Inactiva")

        total = len(session.exec(query).all())
        if order_dir.lower() == "desc":
            query = query.order_by(ReglaDePrecio.nombre.desc(), ReglaDePrecio.id.desc())
        else:
            query = query.order_by(ReglaDePrecio.nombre.asc(), ReglaDePrecio.id.asc())
        reglas = session.exec(query.offset(skip).limit(limit)).all()

        return [PricingService._to_read(session, regla) for regla in reglas], total

    @staticmethod
    def get_regla(session: Session, regla_id: int) -> Optional[ReglaDePrecioRead]:
        """Obtener una regla por ID"""
        regla = session.get(ReglaDePrecio, regla_id)
        return PricingService._to_read(session, regla) if regla else None

    @staticmethod
    def create_regla(
        session: Session,
        data: ReglaDePrecioCreate,
        user_id: int,
    ) -> ReglaDePrecioRead:
        """Crear una nueva regla de precio y sus alcances"""

        # Asegurar fecha fin para evitar errores en esta_vigente
        fecha_inicio = data.fecha_hora_inicio
        fecha_fin = data.fecha_hora_fin or (fecha_inicio + timedelta(days=3650))

        regla = ReglaDePrecio(
            nombre=data.nombre,
            descripcion=data.descripcion,
            precio=data.precio,
            esta_activo=data.esta_activo,
            prioridad=data.prioridad or TipoPrioridadRegla.MEDIA,
            multiplicador=data.multiplicador,
            fecha_hora_inicio=fecha_inicio,
            fecha_hora_fin=fecha_fin,
            dias_semana=data.dias_semana,
            creado_por=user_id,
            creado_el=datetime.utcnow(),
        )
        session.add(regla)
        session.flush()

        # Crear alcances
        if data.cervezas_ids:
            for cid in data.cervezas_ids:
                session.add(ReglaDePrecioAlcance(
                    id_regla_de_precio=regla.id,
                    tipo_alcance=TipoAlcanceRegla.CERVEZA,
                    id_entidad=cid,
                ))

        if data.puntos_venta_ids:
            for pid in data.puntos_venta_ids:
                session.add(ReglaDePrecioAlcance(
                    id_regla_de_precio=regla.id,
                    tipo_alcance=TipoAlcanceRegla.PUNTO_DE_VENTA,
                    id_entidad=pid,
                ))

        if data.equipos_ids:
            for eid in data.equipos_ids:
                session.add(ReglaDePrecioAlcance(
                    id_regla_de_precio=regla.id,
                    tipo_alcance=TipoAlcanceRegla.EQUIPO,
                    id_entidad=eid,
                ))

        session.commit()
        session.refresh(regla)
        return PricingService._to_read(session, regla)

    @staticmethod
    def update_regla(
        session: Session,
        regla_id: int,
        data: ReglaDePrecioUpdate,
    ) -> Optional[ReglaDePrecioRead]:
        """Actualizar una regla y opcionalmente sus alcances"""
        regla = session.get(ReglaDePrecio, regla_id)
        if not regla:
            return None

        update_data = data.model_dump(exclude_unset=True)
        # Campos simples
        for field in [
            "nombre", "descripcion", "precio", "esta_activo",
            "prioridad", "multiplicador", "fecha_hora_inicio",
            "fecha_hora_fin", "dias_semana",
        ]:
            if field in update_data and update_data[field] is not None:
                setattr(regla, field, update_data[field])

        # Asegurar fecha fin
        if regla.fecha_hora_fin is None:
            regla.fecha_hora_fin = regla.fecha_hora_inicio + timedelta(days=3650)

        # Actualizar alcances si vienen en el update
        alcances_actualizados = False
        for coll_name in ["cervezas_ids", "puntos_venta_ids", "equipos_ids"]:
            if coll_name in update_data:
                alcances_actualizados = True
        if alcances_actualizados:
            # Eliminar alcances existentes
            existentes = session.exec(
                select(ReglaDePrecioAlcance).where(ReglaDePrecioAlcance.id_regla_de_precio == regla.id)
            ).all()
            for a in existentes:
                session.delete(a)
            # Crear nuevos
            if data.cervezas_ids:
                for cid in data.cervezas_ids:
                    session.add(ReglaDePrecioAlcance(
                        id_regla_de_precio=regla.id,
                        tipo_alcance=TipoAlcanceRegla.CERVEZA,
                        id_entidad=cid,
                    ))
            if data.puntos_venta_ids:
                for pid in data.puntos_venta_ids:
                    session.add(ReglaDePrecioAlcance(
                        id_regla_de_precio=regla.id,
                        tipo_alcance=TipoAlcanceRegla.PUNTO_DE_VENTA,
                        id_entidad=pid,
                    ))
            if data.equipos_ids:
                for eid in data.equipos_ids:
                    session.add(ReglaDePrecioAlcance(
                        id_regla_de_precio=regla.id,
                        tipo_alcance=TipoAlcanceRegla.EQUIPO,
                        id_entidad=eid,
                    ))

        session.commit()
        session.refresh(regla)
        return PricingService._to_read(session, regla)

    @staticmethod
    def delete_regla(session: Session, regla_id: int) -> bool:
        """Inactivar (soft delete) una regla"""
        regla = session.get(ReglaDePrecio, regla_id)
        if not regla:
            return False
        regla.esta_activo = False
        session.commit()
        return True

    @staticmethod
    def calcular_precio(
        session: Session,
        consulta: ConsultaPrecio,
    ) -> CalculoPrecio:
        """Calcular precio final para una consulta"""
        # Obtener precio base de la cerveza
        precio_base: Optional[Decimal] = CervezaService.get_precio_actual(session, consulta.id_cerveza)
        if precio_base is None:
            raise ValueError("Precio base no encontrado para la cerveza")

        # Obtener reglas aplicables
        reglas = PricingService._obtener_reglas_aplicables(
            session,
            id_cerveza=consulta.id_cerveza,
            id_equipo=consulta.id_equipo,
            id_punto_venta=consulta.id_punto_venta,
        )

        # Aplicar reglas y multiplicadores
        calculo = CalculadoraPrecios.aplicar_reglas(precio_base, reglas, consulta.fecha_consulta)
        return calculo

    @staticmethod
    def _obtener_reglas_aplicables(
        session: Session,
        id_cerveza: Optional[int] = None,
        id_equipo: Optional[int] = None,
        id_punto_venta: Optional[int] = None,
    ) -> List[ReglaDePrecio]:
        """Obtiene las reglas activas que aplican al contexto. Si no hay alcances, se considera regla global."""
        now = datetime.utcnow()
        reglas_activas = session.exec(
            select(ReglaDePrecio).where(ReglaDePrecio.esta_activo == True)
        ).all()

        aplicables: List[ReglaDePrecio] = []
        for r in reglas_activas:
            # Asegurar fecha fin
            if r.fecha_hora_fin is None:
                continue  # no considerar reglas con fecha fin nula (para evitar errores)

            # Vigencia
            if not (r.fecha_hora_inicio <= now <= r.fecha_hora_fin):
                continue

            if not r.alcances or len(r.alcances) == 0:
                aplicables.append(r)
                continue

            for a in r.alcances:
                if a.tipo_alcance == TipoAlcanceRegla.CERVEZA and id_cerveza and a.id_entidad == id_cerveza:
                    aplicables.append(r)
                    break
                if a.tipo_alcance == TipoAlcanceRegla.EQUIPO and id_equipo and a.id_entidad == id_equipo:
                    aplicables.append(r)
                    break
                if a.tipo_alcance == TipoAlcanceRegla.PUNTO_DE_VENTA and id_punto_venta and a.id_entidad == id_punto_venta:
                    aplicables.append(r)
                    break

        return aplicables

    @staticmethod
    def _to_read(session: Session, regla: Optional[ReglaDePrecio]) -> Optional[ReglaDePrecioRead]:
        if not regla:
            return None
        now = datetime.utcnow()
        vigente = False
        if regla.fecha_hora_fin is not None:
            vigente = regla.esta_activo and regla.fecha_hora_inicio <= now <= regla.fecha_hora_fin

        if regla.esta_activo:
            if regla.fecha_hora_inicio > now:
                estado = "Programada"
            elif regla.fecha_hora_fin is None or now <= regla.fecha_hora_fin:
                estado = "Activa"
            else:
                estado = "Inactiva"
        else:
            estado = "Inactiva"

        alcances_read: List[ReglaDePrecioAlcanceRead] = []
        alcance_label = "Todas las cervezas"
        if regla.alcances and len(regla.alcances) > 0:
            tipos = {a.tipo_alcance for a in regla.alcances}
            if tipos == {TipoAlcanceRegla.CERVEZA}:
                tipos_cerveza = []
                for a in regla.alcances:
                    cerveza = session.get(Cerveza, a.id_entidad)
                    nombre = cerveza.tipo if cerveza else None
                    if nombre:
                        tipos_cerveza.append(nombre)
                    alcances_read.append(
                        ReglaDePrecioAlcanceRead(tipo_alcance=a.tipo_alcance, id_entidad=a.id_entidad, nombre=nombre)
                    )
                tipos_unicos = sorted(set(tipos_cerveza))
                alcance_label = tipos_unicos[0] if len(tipos_unicos) == 1 else "Varias cervezas"
            elif tipos == {TipoAlcanceRegla.PUNTO_DE_VENTA}:
                nombres = []
                for a in regla.alcances:
                    pv = session.get(PuntoVenta, a.id_entidad)
                    nombre = pv.nombre if pv else None
                    if nombre:
                        nombres.append(nombre)
                    alcances_read.append(
                        ReglaDePrecioAlcanceRead(tipo_alcance=a.tipo_alcance, id_entidad=a.id_entidad, nombre=nombre)
                    )
                alcance_label = nombres[0] if len(set(nombres)) == 1 and len(nombres) == 1 else "Varios puntos de venta"
            elif tipos == {TipoAlcanceRegla.EQUIPO}:
                nombres = []
                for a in regla.alcances:
                    eq = session.get(Equipo, a.id_entidad)
                    nombre = eq.nombre_equipo if eq else None
                    if nombre:
                        nombres.append(nombre)
                    alcances_read.append(
                        ReglaDePrecioAlcanceRead(tipo_alcance=a.tipo_alcance, id_entidad=a.id_entidad, nombre=nombre)
                    )
                alcance_label = nombres[0] if len(set(nombres)) == 1 and len(nombres) == 1 else "Varios equipos"
            else:
                for a in regla.alcances:
                    alcances_read.append(
                        ReglaDePrecioAlcanceRead(tipo_alcance=a.tipo_alcance, id_entidad=a.id_entidad, nombre=None)
                    )
                alcance_label = "Alcance múltiple"

        return ReglaDePrecioRead(
            id=regla.id,
            id_ext=str(regla.id_ext),
            nombre=regla.nombre,
            descripcion=regla.descripcion,
            precio=regla.precio,
            esta_activo=regla.esta_activo,
            prioridad=regla.prioridad,
            multiplicador=regla.multiplicador,
            fecha_hora_inicio=regla.fecha_hora_inicio,
            fecha_hora_fin=regla.fecha_hora_fin,
            dias_semana=regla.dias_semana,
            creado_por=regla.creado_por,
            creado_el=regla.creado_el,
            vigente=vigente,
            estado=estado,
            alcance=alcance_label,
            alcances=alcances_read,
        )
