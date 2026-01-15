"""
Servicios de negocio para cervezas
"""
from sqlmodel import Session, select, and_, or_
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError

from ..models.beer import (
    Cerveza, CervezaCreate, CervezaRead, CervezaUpdate,
    TipoEstiloCerveza, CervezaEstilo, PrecioCerveza,
    TipoEstiloCervezaRead, PrecioCervezaCreate
)
from ..models.sales_point import Equipo, PuntoVenta


class CervezaService:
    """Servicio de negocio para cervezas"""
    
    @staticmethod
    def _validate_estilos_for_tenant(session: Session, *, tenant_id: int, estilos_ids: List[int]) -> None:
        if not estilos_ids:
            return
        estilos_ids_int = [int(e) for e in estilos_ids]
        estilos_existentes = session.exec(
            select(TipoEstiloCerveza.id)
            .where(TipoEstiloCerveza.id.in_(estilos_ids_int))
            .where((TipoEstiloCerveza.tenant_id.is_(None)) | (TipoEstiloCerveza.tenant_id == tenant_id))
        ).all()
        if len(set(estilos_existentes)) != len(set(estilos_ids_int)):
            raise ValueError("Uno o más estilos seleccionados no existen o no están habilitados")

    @staticmethod
    def get_cervezas_with_filters(
        session: Session,
        tenant_id: int,
        skip: int = 0,
        limit: int = 10,
        search: Optional[str] = None,
        estilo_id: Optional[int] = None,
        activo: Optional[bool] = None,
        destacado: Optional[bool] = None,
        order_dir: str = "asc",
    ) -> tuple[List[CervezaRead], int]:
        """Obtener cervezas con filtros y paginación"""
        
        # Query base
        query = select(Cerveza)
        
        # Aplicar filtros
        conditions = []
        conditions.append(Cerveza.tenant_id == tenant_id)
        
        if search:
            search_term = f"%{search}%"
            conditions.append(
                or_(
                    Cerveza.nombre.ilike(search_term),
                    Cerveza.tipo.ilike(search_term),
                    Cerveza.proveedor.ilike(search_term)
                )
            )
        
        if estilo_id:
            # Join con CervezaEstilo para filtrar por estilo
            query = query.join(CervezaEstilo).where(CervezaEstilo.id_estilo == estilo_id)
        
        if activo is not None:
            conditions.append(Cerveza.activo == activo)
        
        if destacado is not None:
            conditions.append(Cerveza.destacado == destacado)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Contar total
        count_query = select(Cerveza.id)
        if conditions:
            count_query = count_query.where(and_(*conditions))
        if estilo_id:
            count_query = count_query.join(CervezaEstilo).where(CervezaEstilo.id_estilo == estilo_id)
        
        total = len(session.exec(count_query).all())
        
        # Aplicar paginación y ordenamiento
        if order_dir.lower() == "desc":
            query = query.order_by(desc(Cerveza.nombre))
        else:
            query = query.order_by(Cerveza.nombre)

        query = query.offset(skip).limit(limit)
        
        cervezas = session.exec(query).all()
        
        # Convertir a CervezaRead con datos adicionales
        cervezas_read = []
        for cerveza in cervezas:
            cerveza_read = CervezaService._cerveza_to_read(session, cerveza)
            cervezas_read.append(cerveza_read)
        
        return cervezas_read, total
    
    @staticmethod
    def get_cerveza_by_id(session: Session, cerveza_id: int, *, tenant_id: int) -> Optional[CervezaRead]:
        """Obtener cerveza por ID con precio actual"""
        cerveza = session.exec(select(Cerveza).where(Cerveza.id == cerveza_id, Cerveza.tenant_id == tenant_id)).first()
        if not cerveza:
            return None
        
        return CervezaService._cerveza_to_read(session, cerveza)
    
    @staticmethod
    def create_cerveza(
        session: Session,
        cerveza_data: CervezaCreate,
        tenant_id: int,
        user_id: int,
        precio_inicial: Optional[Decimal] = None
    ) -> CervezaRead:
        """Crear nueva cerveza con precio inicial"""
        
        # Crear cerveza
        cerveza_dict = cerveza_data.model_dump(exclude={'estilos_ids'})
        cerveza_dict['creado_por'] = user_id
        cerveza_dict['tenant_id'] = tenant_id
        
        cerveza = Cerveza(**cerveza_dict)
        session.add(cerveza)
        session.flush()  # Para obtener el ID
        
        # Asociar estilos
        if cerveza_data.estilos_ids:
            CervezaService._validate_estilos_for_tenant(
                session,
                tenant_id=tenant_id,
                estilos_ids=[int(e) for e in cerveza_data.estilos_ids],
            )
            for estilo_id in cerveza_data.estilos_ids:
                cerveza_estilo = CervezaEstilo(
                    id_cerveza=cerveza.id,
                    id_estilo=estilo_id
                )
                session.add(cerveza_estilo)
        
        # Crear precio inicial si se proporciona
        if precio_inicial:
            precio = PrecioCerveza(
                id_cerveza=cerveza.id,
                precio=precio_inicial,
                creado_por=user_id,
                motivo="Precio inicial"
            )
            session.add(precio)
        
        session.commit()
        session.refresh(cerveza)
        
        return CervezaService._cerveza_to_read(session, cerveza)
    
    @staticmethod
    def update_cerveza(
        session: Session,
        cerveza_id: int,
        cerveza_data: CervezaUpdate,
        tenant_id: int,
        user_id: int,
        precio_nuevo: Optional[Decimal] = None,
        motivo_precio: Optional[str] = None
    ) -> Optional[CervezaRead]:
        """Actualizar cerveza y crear nuevo precio si es necesario"""
        
        cerveza = session.exec(select(Cerveza).where(Cerveza.id == cerveza_id, Cerveza.tenant_id == tenant_id)).first()
        if not cerveza:
            return None
        
        # Actualizar campos de la cerveza
        update_data = cerveza_data.model_dump(exclude_unset=True, exclude={'estilos_ids'})
        for field, value in update_data.items():
            setattr(cerveza, field, value)
        
        # Actualizar estilos si se proporcionan
        if cerveza_data.estilos_ids is not None:
            estilos_ids = [int(estilo_id) for estilo_id in cerveza_data.estilos_ids]
            CervezaService._validate_estilos_for_tenant(session, tenant_id=tenant_id, estilos_ids=estilos_ids)

            # Eliminar estilos existentes
            existing_estilos = session.exec(
                select(CervezaEstilo).where(CervezaEstilo.id_cerveza == cerveza_id)
            ).all()
            for estilo in existing_estilos:
                session.delete(estilo)
            
            # Agregar nuevos estilos
            for estilo_id in estilos_ids:
                cerveza_estilo = CervezaEstilo(
                    id_cerveza=cerveza_id,
                    id_estilo=estilo_id
                )
                session.add(cerveza_estilo)
        
        # Crear nuevo precio si se proporciona
        if precio_nuevo:
            # Cerrar precio actual
            precio_actual = session.exec(
                select(PrecioCerveza)
                .where(PrecioCerveza.id_cerveza == cerveza_id)
                .where(PrecioCerveza.fecha_fin.is_(None))
            ).first()
            
            if precio_actual:
                precio_actual.fecha_fin = datetime.utcnow()
            
            # Crear nuevo precio
            nuevo_precio = PrecioCerveza(
                id_cerveza=cerveza_id,
                precio=precio_nuevo,
                creado_por=user_id,
                motivo=motivo_precio or "Actualización de precio"
            )
            session.add(nuevo_precio)
        
        try:
            session.commit()
        except IntegrityError as e:
            session.rollback()
            message = str(getattr(e, "orig", e))
            if "cervezas.nombre" in message or "UNIQUE constraint failed" in message:
                raise ValueError("Ya existe una cerveza con ese nombre")
            raise ValueError("No se pudo actualizar la cerveza por un error de integridad")

        session.refresh(cerveza)
        
        return CervezaService._cerveza_to_read(session, cerveza)
    
    @staticmethod
    def delete_cerveza(session: Session, cerveza_id: int, *, tenant_id: int) -> bool:
        """Soft delete de cerveza (activo = False)"""
        cerveza = session.exec(select(Cerveza).where(Cerveza.id == cerveza_id, Cerveza.tenant_id == tenant_id)).first()
        if not cerveza:
            return False
        
        cerveza.activo = False
        session.commit()
        return True
    
    @staticmethod
    def get_precio_actual(session: Session, cerveza_id: int) -> Optional[Decimal]:
        """Obtener precio actual de una cerveza"""
        precio = session.exec(
            select(PrecioCerveza)
            .where(PrecioCerveza.id_cerveza == cerveza_id)
            .where(PrecioCerveza.fecha_fin.is_(None))
            .order_by(PrecioCerveza.fecha_inicio.desc())
        ).first()
        
        return precio.precio if precio else None
    
    @staticmethod
    def calculate_stock_total(session: Session, cerveza_id: int, *, tenant_id: int) -> int:
        """Calcular stock total basado en equipos activos"""
        equipos = session.exec(
            select(Equipo)
            .where(Equipo.id_cerveza == cerveza_id)
            .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
            .where(PuntoVenta.tenant_id == tenant_id)
            .join(Equipo.estado_equipo)
            .where(Equipo.estado_equipo.has(permite_ventas=True))
        ).all()
        
        return sum(equipo.capacidad_actual for equipo in equipos)
    
    @staticmethod
    def get_estilos_cerveza(session: Session) -> List[TipoEstiloCervezaRead]:
        estilos = session.exec(select(TipoEstiloCerveza).order_by(TipoEstiloCerveza.estilo, TipoEstiloCerveza.id)).all()
        return [
            TipoEstiloCervezaRead(
                id=estilo.id,
                id_ext=str(estilo.id_ext),
                estilo=estilo.estilo,
                descripcion=estilo.descripcion,
                origen=estilo.origen,
            )
            for estilo in estilos
        ]

    @staticmethod
    def get_estilos_cerveza_for_tenant(session: Session, *, tenant_id: int) -> List[TipoEstiloCervezaRead]:
        estilos = session.exec(
            select(TipoEstiloCerveza)
            .where((TipoEstiloCerveza.tenant_id.is_(None)) | (TipoEstiloCerveza.tenant_id == tenant_id))
            .order_by(TipoEstiloCerveza.estilo, TipoEstiloCerveza.id)
        ).all()
        return [
            TipoEstiloCervezaRead(
                id=estilo.id,
                id_ext=str(estilo.id_ext),
                estilo=estilo.estilo,
                descripcion=estilo.descripcion,
                origen=estilo.origen,
            )
            for estilo in estilos
        ]

    @staticmethod
    def create_estilo_cerveza_for_tenant(
        session: Session,
        *,
        tenant_id: int,
        estilo: str,
        descripcion: Optional[str],
        origen: Optional[str],
    ) -> TipoEstiloCervezaRead:
        estilo_norm = (estilo or "").strip()
        if not estilo_norm:
            raise ValueError("Estilo inválido")

        row = TipoEstiloCerveza(
            tenant_id=tenant_id,
            estilo=estilo_norm,
            descripcion=descripcion,
            origen=origen,
        )
        session.add(row)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise ValueError("Ya existe un estilo con ese nombre")
        session.refresh(row)
        return TipoEstiloCervezaRead(
            id=row.id,
            id_ext=str(row.id_ext),
            estilo=row.estilo,
            descripcion=row.descripcion,
            origen=row.origen,
        )

    @staticmethod
    def delete_estilo_cerveza_for_tenant(session: Session, *, tenant_id: int, estilo_id: int) -> None:
        from sqlmodel import func

        estilo = session.get(TipoEstiloCerveza, estilo_id)
        if estilo is None:
            raise ValueError("Estilo no encontrado")
        if estilo.tenant_id != tenant_id:
            raise ValueError("No se puede eliminar un estilo global")

        in_use = session.exec(
            select(func.count())
            .select_from(CervezaEstilo)
            .join(Cerveza, Cerveza.id == CervezaEstilo.id_cerveza)
            .where(CervezaEstilo.id_estilo == estilo_id)
            .where(Cerveza.tenant_id == tenant_id)
        ).one()
        if int(in_use) > 0:
            raise ValueError("No se puede eliminar: el estilo está en uso")

        session.delete(estilo)
        session.commit()
    
    @staticmethod
    def _cerveza_to_read(session: Session, cerveza: Cerveza) -> CervezaRead:
        """Convertir modelo Cerveza a CervezaRead con datos adicionales"""
        
        # Obtener estilos
        estilos_query = (
            select(TipoEstiloCerveza)
            .join(CervezaEstilo)
            .where(CervezaEstilo.id_cerveza == cerveza.id)
        )
        estilos = session.exec(estilos_query).all()
        estilos_read = [
            TipoEstiloCervezaRead(
                id=estilo.id,
                id_ext=str(estilo.id_ext),
                estilo=estilo.estilo,
                descripcion=estilo.descripcion,
                origen=estilo.origen
            )
            for estilo in estilos
        ]
        
        # Obtener precio actual
        precio_actual = CervezaService.get_precio_actual(session, cerveza.id)
        
        # Calcular stock total
        stock_total = CervezaService.calculate_stock_total(session, cerveza.id, tenant_id=int(cerveza.tenant_id or 0))
        
        return CervezaRead(
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
            estilos=estilos_read,
            precio_actual=precio_actual,
            stock_total=stock_total
        )
