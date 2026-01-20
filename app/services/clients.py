"""
Servicio optimizado para operaciones de clientes
Refactorizado para usar ORM SQLModel en lugar de consultas SQL directas
"""
from typing import Optional, List, Dict, Any
from sqlmodel import Session, select, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import case
from datetime import datetime, date
from decimal import Decimal
import re
import secrets

from app.schemas.clients import (
    ClientSummary, ClientDetail, ClientStats, ClientLoyalty,
    Order, PaymentMethod, PointTransaction, PaginationInfo, FilterOptions, ClientRewardItem
)

# Importar modelos SQLModel necesarios
from app.models import (
    Usuario, UsuarioNivel, TipoNivelUsuario, Venta, Canje, 
    UsuarioMetodoPago, TipoMetodoPago, TransaccionPuntos, CatalogoPremio, Pago
)
from app.models.beer import Cerveza
from app.services.users import UserService
from app.core.config import settings


class ClientService:
    """Servicio optimizado para operaciones de clientes usando ORM SQLModel"""
    
    @staticmethod
    def get_clients_paginated(
        session: Session,
        tenant_id: int,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        status: Optional[str] = None,
        loyalty_level: Optional[str] = None,
        sort_by: str = 'name',
        sort_order: str = 'asc'
    ) -> Dict[str, Any]:
        """
        Obtener lista paginada de clientes usando ORM SQLModel
        """
        
        # Subconsulta para estadísticas de ventas
        stats_subquery = (
            select(
                Venta.id_usuario,
                func.count(Venta.id).label('total_ordenes'),
                func.sum(Venta.monto_total).label('monto_total_gastado'),
                func.max(Venta.fecha_hora).label('fecha_ultima_orden')
            )
            .group_by(Venta.id_usuario)
            .subquery()
        )
        
        # Query principal con joins
        query = (
            select(
                Usuario.id_ext.label('id'),
                (Usuario.nombres + ' ' + Usuario.apellidos).label('name'),
                Usuario.email,
                Usuario.telefono.label('phone'),
                Usuario.activo.label('activo'),
                func.coalesce(TipoNivelUsuario.nivel, 'Sin Nivel').label('loyaltyLevel'),
                func.coalesce(UsuarioNivel.puntaje_actual, 0).label('loyaltyPoints'),
                func.coalesce(stats_subquery.c.monto_total_gastado, 0).label('totalSpent'),
                func.coalesce(stats_subquery.c.total_ordenes, 0).label('totalOrders'),
                Usuario.fecha_creacion.label('joinDate'),
                stats_subquery.c.fecha_ultima_orden.label('lastOrder')
            )
            .select_from(Usuario)
            .outerjoin(UsuarioNivel, Usuario.id == UsuarioNivel.id_usuario)
            .outerjoin(TipoNivelUsuario, UsuarioNivel.id_nivel == TipoNivelUsuario.id)
            .outerjoin(stats_subquery, Usuario.id == stats_subquery.c.id_usuario)
            .where(Usuario.tenant_id == tenant_id)
        )
        
        # Aplicar filtros
        if search:
            search_filter = or_(
                (Usuario.nombres + ' ' + Usuario.apellidos).ilike(f"%{search}%"),
                Usuario.email.ilike(f"%{search}%")
            )
            query = query.where(search_filter)
        
        if status:
            active_status = status == 'Activo'
            query = query.where(Usuario.activo == active_status)
        
        if loyalty_level:
            query = query.where(TipoNivelUsuario.nivel == loyalty_level)
        
        # Aplicar ordenamiento
        sort_mapping = {
            'name': (Usuario.nombres + ' ' + Usuario.apellidos),
            'joinDate': Usuario.fecha_creacion,
            'totalSpent': func.coalesce(stats_subquery.c.monto_total_gastado, 0),
            'loyaltyPoints': func.coalesce(UsuarioNivel.puntaje_actual, 0)
        }
        
        sort_field = sort_mapping.get(sort_by, sort_mapping['name'])
        if sort_order.lower() == 'desc':
            query = query.order_by(desc(sort_field))
        else:
            query = query.order_by(asc(sort_field))
        
        # Contar total de registros (antes de aplicar paginación)
        count_query = select(func.count()).select_from(query.subquery())
        total = session.exec(count_query).one()
        
        # Aplicar paginación
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        
        # Ejecutar query principal
        result = session.exec(query)
        clients_data = result.all()
        
        # Convertir resultados a objetos ClientSummary
        clients = []
        for row in clients_data:
            total_spent_decimal = Decimal(str(row.totalSpent or 0))
            balance_decimal = (total_spent_decimal * Decimal(str(settings.client_balance_rate))).quantize(Decimal("0.01"))
            client = ClientSummary(
                id=str(row.id),
                name=row.name or "",
                email=row.email,
                phone=row.phone,
                status='Activo' if row.activo else 'Inactivo',
                loyaltyLevel=row.loyaltyLevel or "Sin Nivel",
                loyaltyPoints=int(row.loyaltyPoints or 0),
                totalSpent=total_spent_decimal,
                totalOrders=int(row.totalOrders or 0),
                balance=balance_decimal,
                joinDate=row.joinDate,
                lastOrder=row.lastOrder
            )
            clients.append(client)
        
        # Obtener opciones de filtrado
        filters = ClientService._get_filter_options(session)
        
        return {
            'clients': clients,
            'pagination': PaginationInfo(
                page=page,
                limit=limit,
                total=total,
                totalPages=(total + limit - 1) // limit
            ),
            'filters': filters
        }
    
    @staticmethod
    def get_client_detail(session: Session, client_id: str, *, tenant_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtener detalle completo de un cliente por su id_ext usando ORM
        """
        
        # Buscar usuario con relaciones cargadas
        query = (
            select(Usuario)
            .options(
                selectinload(Usuario.nivel).selectinload(UsuarioNivel.nivel),
                selectinload(Usuario.ventas),
                selectinload(Usuario.canjes),
                selectinload(Usuario.metodos_pago).selectinload(UsuarioMetodoPago.metodo_pago)
            )
            .where(Usuario.id_ext == client_id, Usuario.tenant_id == tenant_id)
        )
        
        result = session.exec(query)
        user = result.first()
        
        if not user:
            return None
        
        # Obtener estadísticas del cliente
        stats = ClientService._get_client_stats(session, user.id)
        
        # Obtener información de lealtad
        loyalty = ClientService._get_client_loyalty(session, user.id)
        
        # Obtener órdenes recientes
        recent_orders = ClientService._get_recent_orders(session, user.id, limit=10)
        
        # Obtener métodos de pago
        payment_methods = ClientService._get_payment_methods(session, user.id)
        
        # Calcular edad si hay fecha de nacimiento
        age = None
        if user.fecha_nac:
            today = date.today()
            age = today.year - user.fecha_nac.year - ((today.month, today.day) < (user.fecha_nac.month, user.fecha_nac.day))
        
        sexo_value = user.sexo.value if getattr(user.sexo, "value", None) else user.sexo
        if sexo_value == "M":
            gender = "Masculino"
        elif sexo_value == "F":
            gender = "Femenino"
        else:
            gender = "Otro"
        
        # Crear objeto de respuesta
        client_detail = ClientDetail(
            id=str(user.id_ext),
            name=f"{user.nombres} {user.apellidos}",
            email=user.email,
            phone=user.telefono,
            address=getattr(user, 'direccion', None),  # Usar getattr por si no existe el campo
            gender=gender,
            birthDate=user.fecha_nac,
            age=age,
            status='Activo' if user.activo else 'Inactivo',
            joinDate=user.fecha_creacion,
            lastLogin=user.ultimo_login,
            verified=user.verificado
        )
        
        return {
            'client': client_detail,
            'stats': stats,
            'loyalty': loyalty,
            'recent_orders': recent_orders,
            'payment_methods': payment_methods
        }
    
    @staticmethod
    def _get_client_stats(session: Session, user_id: int) -> ClientStats:
        """Obtener estadísticas del cliente usando ORM"""
        
        # Estadísticas de ventas
        ventas_stats = session.exec(
            select(
                func.coalesce(func.sum(Venta.monto_total), 0).label('total_spent'),
                func.count(Venta.id).label('total_orders'),
                func.coalesce(func.avg(Venta.monto_total), 0).label('average_order_value'),
                func.max(Venta.fecha_hora).label('last_order_at'),
            )
            .where(Venta.id_usuario == user_id)
        ).first()
        
        # Estilo favorito (cerveza más comprada)
        favorite_style_result = session.exec(
            select(Cerveza.tipo)
            .select_from(Venta)
            .join(Cerveza, Venta.id_cerveza == Cerveza.id)
            .where(Venta.id_usuario == user_id)
            .group_by(Cerveza.tipo)
            .order_by(desc(func.count(Venta.id)))
            .limit(1)
        ).first()
        
        # Estadísticas de canjes
        canjes_stats = session.exec(
            select(
                func.count(Canje.id).label('total_redemptions'),
                func.coalesce(func.sum(Canje.puntos_utilizados), 0).label('points_redeemed')
            )
            .where(and_(Canje.id_usuario == user_id, Canje.estado != 'cancelado'))
        ).first()
        
        total_spent = Decimal(str(ventas_stats.total_spent)) if ventas_stats else Decimal('0')
        available_balance = (total_spent * Decimal(str(settings.client_balance_rate))).quantize(Decimal("0.01"))

        return ClientStats(
            totalSpent=total_spent,
            totalOrders=int(ventas_stats.total_orders) if ventas_stats else 0,
            averageOrderValue=Decimal(str(ventas_stats.average_order_value)) if ventas_stats else Decimal('0'),
            favoriteStyle=favorite_style_result,
            totalRedemptions=int(canjes_stats.total_redemptions) if canjes_stats else 0,
            pointsRedeemed=int(canjes_stats.points_redeemed) if canjes_stats else 0,
            availableBalance=available_balance,
            balanceUpdatedAt=ventas_stats.last_order_at if ventas_stats else None,
        )
    
    @staticmethod
    def _get_client_loyalty(session: Session, user_id: int) -> ClientLoyalty:
        """Obtener información de lealtad del cliente usando ORM"""
        
        # Buscar nivel del usuario
        query = (
            select(UsuarioNivel, TipoNivelUsuario)
            .join(TipoNivelUsuario, UsuarioNivel.id_nivel == TipoNivelUsuario.id)
            .where(UsuarioNivel.id_usuario == user_id)
        )
        
        result = session.exec(query).first()
        
        if result:
            usuario_nivel, tipo_nivel = result
            current_points = usuario_nivel.puntaje_actual
            level = tipo_nivel.nivel
            level_benefits = tipo_nivel.beneficios
            max_points = tipo_nivel.puntaje_max
            min_points = tipo_nivel.puntaje_min
        else:
            current_points = 0
            level = 'Sin Nivel'
            level_benefits = None
            max_points = None
            min_points = 0
        
        # Calcular progreso al siguiente nivel
        progress_to_next = 0
        points_to_next_level = None
        
        if max_points and max_points > min_points:
            progress_to_next = min(100, int(((current_points - min_points) / (max_points - min_points)) * 100))
            points_to_next_level = max(0, max_points - current_points)
        
        return ClientLoyalty(
            currentPoints=current_points,
            level=level,
            levelBenefits=level_benefits,
            progressToNext=progress_to_next,
            pointsToNextLevel=points_to_next_level
        )
    
    @staticmethod
    def _get_recent_orders(session: Session, user_id: int, limit: int = 10) -> List[Order]:
        """Obtener órdenes recientes del cliente usando ORM"""
        
        query = (
            select(Venta, Cerveza)
            .outerjoin(Cerveza, Venta.id_cerveza == Cerveza.id)
            .where(Venta.id_usuario == user_id)
            .order_by(desc(Venta.fecha_hora))
            .limit(limit)
        )
        
        result = session.exec(query)
        orders_data = result.all()
        
        orders = []
        for venta, cerveza in orders_data:
            payment_method = session.exec(
                select(TipoMetodoPago.metodo_pago)
                .select_from(Pago)
                .join(TipoMetodoPago, TipoMetodoPago.id == Pago.id_metodo_pago)
                .where(
                    Pago.id_venta == venta.id,
                    Pago.fecha_venta == venta.fecha_hora,
                )
                .order_by(desc(Pago.fecha_pago))
                .limit(1)
            ).first()
            order = Order(
                id=str(venta.id_ext),
                date=venta.fecha_hora,
                amount=venta.monto_total,
                quantity=venta.cantidad_ml,
                beerName=cerveza.nombre if cerveza else 'N/A',
                beerType=cerveza.tipo if cerveza else 'N/A',
                paymentMethod=payment_method,
            )
            orders.append(order)
        
        return orders
    
    @staticmethod
    def _get_payment_methods(session: Session, user_id: int) -> List[PaymentMethod]:
        """Obtener métodos de pago del cliente usando ORM"""
        
        query = (
            select(UsuarioMetodoPago, TipoMetodoPago)
            .join(TipoMetodoPago, UsuarioMetodoPago.id_metodo_pago == TipoMetodoPago.id)
            .where(and_(UsuarioMetodoPago.id_usuario == user_id, UsuarioMetodoPago.activo == True))
            .order_by(desc(UsuarioMetodoPago.fecha_creacion))
        )
        
        result = session.exec(query)
        payment_data = result.all()
        
        payment_methods = []
        for usuario_metodo, tipo_metodo in payment_data:
            last_used = session.exec(
                select(func.max(Pago.fecha_pago))
                .select_from(Pago)
                .join(
                    Venta,
                    and_(Venta.id == Pago.id_venta, Venta.fecha_hora == Pago.fecha_venta),
                )
                .where(
                    Venta.id_usuario == user_id,
                    Pago.id_metodo_pago == tipo_metodo.id,
                )
            ).first()
            payment_method = PaymentMethod(
                id=usuario_metodo.id_metodo_pago,
                method=tipo_metodo.metodo_pago,
                provider=usuario_metodo.proveedor_metodo_pago,
                active=usuario_metodo.activo,
                createdAt=usuario_metodo.fecha_creacion,
                lastUsed=last_used,
            )
            payment_methods.append(payment_method)
        
        return payment_methods

    @staticmethod
    def get_loyalty_history(session: Session, user_id: int, limit: int = 50) -> List[PointTransaction]:
        rows = session.exec(
            select(TransaccionPuntos)
            .where(TransaccionPuntos.id_usuario == user_id)
            .order_by(desc(TransaccionPuntos.fecha))
            .limit(limit)
        ).all()

        txs: List[PointTransaction] = []
        for t in rows:
            delta = int(t.puntos_ganados or 0) - int(t.puntos_canjeados or 0)
            if int(t.puntos_canjeados or 0) > 0:
                tx_type = "redeemed"
                points = -int(t.puntos_canjeados)
            elif int(t.puntos_ganados or 0) > 0:
                tx_type = "earned"
                points = int(t.puntos_ganados)
            else:
                tx_type = "adjustment"
                points = delta

            txs.append(
                PointTransaction(
                    id=str(t.id),
                    type=tx_type,
                    points=points,
                    description=t.descripcion or t.tipo_transaccion,
                    date=t.fecha,
                    relatedOrderId=str(t.id_venta) if t.id_venta else None,
                    relatedRedemptionId=str(t.id_canje) if t.id_canje else None,
                )
            )
        return txs

    @staticmethod
    def get_rewards(session: Session, user_id: int) -> dict:
        loyalty = ClientService._get_client_loyalty(session, user_id)
        now = datetime.utcnow()

        available_rows = session.exec(
            select(CatalogoPremio)
            .where(
                CatalogoPremio.activo == True,
                or_(CatalogoPremio.fecha_vencimiento == None, CatalogoPremio.fecha_vencimiento > now),
                or_(CatalogoPremio.stock_disponible == None, CatalogoPremio.stock_disponible > 0),
            )
            .order_by(asc(CatalogoPremio.puntos_requeridos), asc(CatalogoPremio.nombre))
        ).all()

        redeemed_rows = session.exec(
            select(Canje, CatalogoPremio)
            .join(CatalogoPremio, CatalogoPremio.id == Canje.id_premio)
            .where(Canje.id_usuario == user_id)
            .order_by(desc(Canje.fecha_canje))
            .limit(20)
        ).all()

        available: List[ClientRewardItem] = []
        for p in available_rows:
            available.append(
                ClientRewardItem(
                    id=p.id,
                    name=p.nombre,
                    pointsCost=int(p.puntos_requeridos),
                    status="Disponible",
                    redeemedDate=None,
                    category=p.categoria,
                )
            )

        history: List[ClientRewardItem] = []
        for canje, premio in redeemed_rows:
            status = "Canjeado"
            if getattr(canje, "estado", None) == "cancelado":
                status = "Expirado"
            history.append(
                ClientRewardItem(
                    id=premio.id,
                    name=premio.nombre,
                    pointsCost=int(canje.puntos_utilizados),
                    status=status,
                    redeemedDate=canje.fecha_canje,
                    category=premio.categoria,
                )
            )

        return {
            "currentPoints": loyalty.currentPoints,
            "level": loyalty.level,
            "available": available,
            "history": history,
        }

    @staticmethod
    def redeem_reward(session: Session, client_id_ext: str, premio_id: int, *, tenant_id: int) -> dict:
        user = session.exec(select(Usuario).where(Usuario.id_ext == client_id_ext, Usuario.tenant_id == tenant_id)).first()
        if not user:
            raise ValueError("Cliente no encontrado")

        premio = session.get(CatalogoPremio, premio_id)
        if not premio or not premio.activo:
            raise ValueError("Premio no disponible")

        loyalty = ClientService._get_client_loyalty(session, user.id)
        if loyalty.currentPoints < int(premio.puntos_requeridos):
            raise ValueError("Puntos insuficientes")

        canje = Canje(
            id_usuario=user.id,
            id_premio=premio.id,
            puntos_utilizados=int(premio.puntos_requeridos),
            estado="canjeado",
            notas=None,
        )
        session.add(canje)
        session.commit()
        session.refresh(canje)

        usuario_nivel = session.exec(select(UsuarioNivel).where(UsuarioNivel.id_usuario == user.id)).first()
        if usuario_nivel:
            usuario_nivel.puntaje_actual = max(0, int(usuario_nivel.puntaje_actual or 0) - int(premio.puntos_requeridos))
            session.add(usuario_nivel)

        tx = TransaccionPuntos(
            id_usuario=user.id,
            puntos_ganados=0,
            puntos_canjeados=int(premio.puntos_requeridos),
            saldo_anterior=max(0, int(loyalty.currentPoints)),
            saldo_posterior=max(0, int(loyalty.currentPoints) - int(premio.puntos_requeridos)),
            id_canje=canje.id,
            descripcion=f"Canje: {premio.nombre}",
            tipo_transaccion="canje",
        )
        session.add(tx)

        if premio.stock_disponible is not None and premio.stock_disponible > 0:
            premio.stock_disponible -= 1
            session.add(premio)

        session.commit()

        updated = ClientService._get_client_loyalty(session, user.id)
        return {"currentPoints": updated.currentPoints, "level": updated.level}
    
    @staticmethod
    def _get_filter_options(session: Session) -> FilterOptions:
        """Obtener opciones de filtrado disponibles usando ORM"""
        
        # Obtener niveles de lealtad disponibles
        loyalty_levels_query = select(TipoNivelUsuario.nivel).distinct().order_by(TipoNivelUsuario.nivel)
        loyalty_levels_result = session.exec(loyalty_levels_query)
        loyalty_levels = list(loyalty_levels_result.all())
        
        # Opciones de estado
        status_options = ['Activo', 'Inactivo']
        
        return FilterOptions(
            loyaltyLevels=loyalty_levels,
            statusOptions=status_options
        )
    
    @staticmethod
    def update_client(
        session: Session,
        client_id: str,
        update_data: Dict[str, Any],
        tenant_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Actualizar información del cliente usando ORM"""
        
        # Buscar usuario
        query = select(Usuario).where(Usuario.id_ext == client_id, Usuario.tenant_id == tenant_id)
        result = session.exec(query)
        user = result.first()
        
        if not user:
            return None
        
        # Procesar datos de actualización
        for key, value in update_data.items():
            if key == 'name' and value:
                # Separar nombre completo
                name_parts = value.split(' ', 1)
                user.nombres = name_parts[0]
                if len(name_parts) > 1:
                    user.apellidos = name_parts[1]
            elif key == 'email' and value is not None:
                user.email = value
            elif key == 'phone' and value is not None:
                user.telefono = value
            elif key == 'address' and value is not None:
                # Usar setattr por si el campo no existe
                setattr(user, 'direccion', value)
            elif key == 'gender' and value:
                gender_normalized = str(value).strip().lower()
                if gender_normalized in {"masculino", "m", "male"}:
                    user.sexo = "M"
                elif gender_normalized in {"femenino", "f", "female"}:
                    user.sexo = "F"
                else:
                    user.sexo = None
            elif key == 'birthDate' and value is not None:
                user.fecha_nac = value
        
        # Guardar cambios
        session.add(user)
        session.commit()
        session.refresh(user)
        
        # Retornar cliente actualizado
        return ClientService.get_client_detail(session, client_id, tenant_id=tenant_id)
    
    @staticmethod
    def toggle_client_status(
        session: Session,
        client_id: str,
        tenant_id: int,
        reason: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Alternar estado activo/inactivo del cliente usando ORM"""
        
        # Buscar usuario
        query = select(Usuario).where(Usuario.id_ext == client_id, Usuario.tenant_id == tenant_id)
        result = session.exec(query)
        user = result.first()
        
        if not user:
            return None
        
        # Guardar estado anterior
        previous_status = 'Activo' if user.activo else 'Inactivo'
        
        # Alternar estado
        user.activo = not user.activo
        new_status = 'Activo' if user.activo else 'Inactivo'
        
        # Guardar cambios
        session.add(user)
        session.commit()
        
        # Obtener datos completos del cliente actualizado
        client_detail = ClientService.get_client_detail(session, client_id, tenant_id=tenant_id)
        
        return {
            'client': client_detail['client'] if client_detail else None,
            'previous_status': previous_status,
            'new_status': new_status,
            'reason': reason
        }

    @staticmethod
    def create_client(
        session: Session,
        *,
        tenant_id: int,
        creado_por: int,
        name: str,
        email: str,
        phone: Optional[str],
        address: Optional[str],
        gender: str,
        birth_date: date,
    ) -> Dict[str, Any]:
        email_normalized = (email or "").lower().strip()
        existing = UserService.get_user_by_email(session, email_normalized)
        if existing:
            if existing.tenant_id is not None and existing.tenant_id != tenant_id:
                raise ValueError("EMAIL_ALREADY_EXISTS_OTHER_TENANT")

            name_parts = (name or "").strip().split()
            first_name = name_parts[0] if name_parts else ""
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

            gender_normalized = (gender or "").strip().lower()
            sexo = "M" if gender_normalized.startswith("m") else "F" if gender_normalized.startswith("f") else "M"

            if existing.tenant_id is None:
                existing.tenant_id = tenant_id
            if getattr(existing, "registrado_por", None) is None:
                existing.registrado_por = creado_por

            if first_name:
                existing.nombres = first_name
            if last_name:
                existing.apellidos = last_name
            if sexo:
                existing.sexo = sexo
            if birth_date and getattr(existing, "fecha_nac", None) is None:
                existing.fecha_nac = birth_date
            if phone and not getattr(existing, "telefono", None):
                existing.telefono = phone
            if address is not None and not getattr(existing, "direccion", None):
                existing.direccion = address

            session.add(existing)
            session.commit()
            session.refresh(existing)

            result = ClientService.get_client_detail(session, str(existing.id_ext), tenant_id=tenant_id)
            if not result:
                raise ValueError("No se pudo vincular el cliente")
            return result

        name_parts = name.strip().split()
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        local_part = email.split("@", 1)[0].lower().strip()
        username_base = re.sub(r"[^a-z0-9_]+", "_", local_part).strip("_") or "user"
        username = username_base
        suffix = 1
        while UserService.get_user_by_username(session, username):
            suffix += 1
            username = f"{username_base}_{suffix}"

        gender_normalized = gender.strip().lower()
        sexo = "M" if gender_normalized.startswith("m") else "F" if gender_normalized.startswith("f") else "M"
        temp_password = secrets.token_urlsafe(12)

        user = UserService.create_user(
            session=session,
            nombre_usuario=username,
            email=email,
            password=temp_password,
            nombre=first_name,
            apellido=last_name,
            sexo=sexo,
            fecha_nacimiento=birth_date,
            telefono=phone,
            tenant_id=tenant_id,
            registrado_por=creado_por,
        )

        if address is not None:
            user.direccion = address
            session.add(user)
            session.commit()
            session.refresh(user)

        result = ClientService.get_client_detail(session, str(user.id_ext), tenant_id=tenant_id)
        if not result:
            raise ValueError("No se pudo crear el cliente")
        return result
