"""
Servicio para clientes guest (sin cuenta)
"""
from typing import Optional
from sqlmodel import Session, select, func
from datetime import datetime, date

from app.models.user_extended import Usuario, UsuarioRol, UsuarioNivel
from app.services.users import UserService
from app.core.security import get_password_hash


class GuestService:
    """Servicio para operaciones con clientes guest"""
    
    @staticmethod
    def create_guest_customer(
        session: Session,
        *,
        nombres: str,
        apellidos: str,
        telefono: Optional[str] = None,
        sexo: Optional[str] = None,
        fecha_nac: Optional[date] = None,
        registrado_por: Optional[int] = None
    ) -> Usuario:
        """
        Crear cliente guest (sin cuenta)
        
        Args:
            session: Sesión de base de datos
            nombres: Nombres del cliente
            apellidos: Apellidos del cliente
            telefono: Teléfono opcional
            sexo: Sexo opcional (MASCULINO/FEMENINO)
            fecha_nac: Fecha de nacimiento opcional
            registrado_por: ID del socio que registra
        
        Returns:
            Cliente guest creado con código QR
        """
        # Generar código único
        codigo_cliente = UserService.generate_codigo_cliente()
        while GuestService.get_by_codigo(session, codigo_cliente):
            codigo_cliente = UserService.generate_codigo_cliente()
        
        # Crear usuario guest (sin email/password)
        guest = Usuario(
            codigo_cliente=codigo_cliente,
            nombres=nombres,
            apellidos=apellidos,
            telefono=telefono,
            sexo=sexo,
            fecha_nac=fecha_nac,
            tipo_registro='punto_venta',
            activo=True,
            verificado=False,
            registrado_por=registrado_por
        )
        
        session.add(guest)
        session.commit()
        session.refresh(guest)
        
        # Asignar nivel inicial (Bronce)
        usuario_nivel = UsuarioNivel(
            id_usuario=guest.id,
            id_nivel=1,  # Bronce
            puntaje_actual=0
        )
        session.add(usuario_nivel)
        
        # Asignar rol de usuario/cliente
        usuario_rol = UsuarioRol(
            id_usuario=guest.id,
            id_rol=1  # Cliente
        )
        session.add(usuario_rol)
        
        session.commit()
        session.refresh(guest)
        
        return guest
    
    @staticmethod
    def get_by_codigo(session: Session, codigo_cliente: str) -> Optional[Usuario]:
        """Buscar cliente por código"""
        statement = select(Usuario).where(Usuario.codigo_cliente == codigo_cliente)
        return session.exec(statement).first()
    
    @staticmethod
    def upgrade_to_full_account(
        session: Session,
        *,
        codigo_cliente: str,
        nombre_usuario: str,
        email: str,
        password: str,
        sexo: Optional[str] = None,
        fecha_nac: Optional[date] = None
    ) -> Optional[Usuario]:
        """
        Migrar cliente guest a cuenta completa
        
        Args:
            session: Sesión de base de datos
            codigo_cliente: Código QR del guest
            nombre_usuario: Nombre de usuario deseado
            email: Email para la cuenta
            password: Contraseña
            sexo: Sexo (si no lo tenía antes)
            fecha_nac: Fecha de nacimiento (si no la tenía)
        
        Returns:
            Usuario actualizado o None si no existe
        """
        # Buscar guest
        guest = GuestService.get_by_codigo(session, codigo_cliente)
        if not guest:
            return None
        
        # Verificar que sea realmente guest
        if not guest.is_guest():
            return None  # Ya tiene cuenta
        
        # Verificar que email no esté usado
        existing_email = UserService.get_user_by_email(session, email)
        if existing_email:
            return None
        
        # Verificar que username no esté usado
        existing_username = UserService.get_user_by_username(session, nombre_usuario)
        if existing_username:
            return None
        
        # Actualizar a cuenta completa
        guest.nombre_usuario = nombre_usuario
        guest.email = email
        guest.password_hash = get_password_hash(password)
        guest.tipo_registro = 'app'  # Ahora es cuenta app
        guest.verificado = False  # Deberá verificar email
        
        # Actualizar datos opcionales si se proporcionan
        if sexo and not guest.sexo:
            guest.sexo = sexo
        if fecha_nac and not guest.fecha_nac:
            guest.fecha_nac = fecha_nac
        
        session.add(guest)
        session.commit()
        session.refresh(guest)
        
        return guest
    
    @staticmethod
    def get_guest_stats(session: Session, codigo_cliente: str) -> Optional[dict]:
        """
        Obtener estadísticas de cliente guest
        
        Args:
            session: Sesión de base de datos
            codigo_cliente: Código del cliente
        
        Returns:
            Diccionario con estadísticas o None
        """
        guest = GuestService.get_by_codigo(session, codigo_cliente)
        if not guest:
            return None
        
        # Obtener puntos totales
        from app.models.transactions import TransaccionPuntos
        statement = select(func.sum(TransaccionPuntos.puntos_ganados)).where(
            TransaccionPuntos.id_usuario == guest.id
        )
        puntos_totales = session.exec(statement).one() or 0
        
        # Obtener nivel
        nivel = UserService.get_user_level(session, guest.id)
        
        # Obtener total de compras
        from app.models.sales import Venta
        statement = select(func.count()).select_from(Venta).where(
            Venta.id_usuario == guest.id
        )
        total_compras = session.exec(statement).one() or 0
        
        # Obtener monto total gastado
        statement = select(func.sum(Venta.monto_total)).where(
            Venta.id_usuario == guest.id
        )
        monto_total = session.exec(statement).one() or 0
        
        return {
            "codigo_cliente": guest.codigo_cliente,
            "nombres": guest.nombres,
            "apellidos": guest.apellidos,
            "puntos_totales": puntos_totales,
            "nivel_actual": nivel.nivel if nivel else "Sin nivel",
            "total_compras": total_compras,
            "monto_total_gastado": float(monto_total),
            "fecha_registro": guest.fecha_creacion,
            "puede_actualizar_cuenta": guest.is_guest()
        }
    
    @staticmethod
    def get_all_guests(
        session: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        registrado_por: Optional[int] = None
    ) -> list[Usuario]:
        """
        Listar clientes guest
        
        Args:
            session: Sesión de base de datos
            skip: Registros a omitir
            limit: Máximo de registros
            registrado_por: Filtrar por socio que registró
        
        Returns:
            Lista de clientes guest
        """
        statement = select(Usuario).where(
            Usuario.tipo_registro == 'punto_venta',
            Usuario.email == None
        )
        
        if registrado_por:
            statement = statement.where(Usuario.registrado_por == registrado_por)
        
        statement = statement.offset(skip).limit(limit)
        return list(session.exec(statement).all())
