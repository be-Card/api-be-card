"""
Servicio CRUD para usuarios
"""
from typing import Optional, List
from sqlmodel import Session, select
from datetime import datetime, date
import secrets

from app.models.user_extended import (
    Usuario, 
    UsuarioRol,
    UsuarioNivel,
    TipoRolUsuario,
    TipoNivelUsuario
)
from app.core.security import get_password_hash, verify_password


class UserService:
    """Servicio para operaciones CRUD de usuarios"""
    
    @staticmethod
    def generate_codigo_cliente() -> str:
        """Generar código único para cliente (QR)"""
        # Formato: BC-XXXXXX (BC = BeCard, 6 caracteres alfanuméricos)
        return f"BC-{secrets.token_hex(3).upper()}"
    
    @staticmethod
    def create_user(
        session: Session,
        *,
        nombre_usuario: str,
        email: str,
        password: str,
        nombre: str,
        apellido: str,
        sexo: str,
        fecha_nacimiento: Optional[date] = None,
        telefono: Optional[str] = None,
        tenant_id: Optional[int] = None,
        registrado_por: Optional[int] = None,
        activo: bool = True,
        role_tipo: str = "usuario",
        nivel_id: int = 1  # Nivel básico por defecto
    ) -> Usuario:
        """
        Crear un nuevo usuario
        
        Args:
            session: Sesión de base de datos
            nombre_usuario: Nombre de usuario único
            email: Email único
            password: Contraseña en texto plano (será hasheada)
            nombre: Nombre del usuario
            apellido: Apellido del usuario
            sexo: Sexo del usuario
            fecha_nacimiento: Fecha de nacimiento
            telefono: Teléfono opcional
            nivel_id: ID del nivel inicial (por defecto 1)
        
        Returns:
            Usuario creado
        """
        # Normalizar email a lowercase para evitar duplicados por case
        email_normalized = email.lower().strip()

        # Hash de la contraseña
        password_hash = get_password_hash(password)

        # Generar código de cliente único
        codigo_cliente = UserService.generate_codigo_cliente()
        while UserService.get_customer_by_codigo(session, codigo_cliente):
            codigo_cliente = UserService.generate_codigo_cliente()

        # Crear usuario
        db_user = Usuario(
            nombre_usuario=nombre_usuario.strip(),
            codigo_cliente=codigo_cliente,
            email=email_normalized,
            password_hash=password_hash,
            password_salt="",  # Ya incluido en el hash con bcrypt
            nombres=nombre,
            apellidos=apellido,
            sexo=sexo,
            fecha_nac=fecha_nacimiento,
            telefono=telefono,
            tipo_registro='app',
            activo=bool(activo),
            verificado=False,
            tenant_id=tenant_id,
            registrado_por=registrado_por,
        )
        
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        
        # Asignar nivel inicial
        usuario_nivel = UsuarioNivel(
            id_usuario=db_user.id,
            id_nivel=nivel_id,
            puntaje_actual=0
        )
        session.add(usuario_nivel)
        
        role_tipo_normalized = (role_tipo or "usuario").strip().lower()
        role_id = session.exec(
            select(TipoRolUsuario.id).where(TipoRolUsuario.tipo == role_tipo_normalized)
        ).first() or 1

        # Asignar rol de usuario
        usuario_rol = UsuarioRol(
            id_usuario=db_user.id,
            id_rol=role_id
        )
        session.add(usuario_rol)
        
        session.commit()
        session.refresh(db_user)
        
        return db_user
    
    @staticmethod
    def get_user_by_id(session: Session, user_id: int) -> Optional[Usuario]:
        """Obtener usuario por ID"""
        return session.get(Usuario, user_id)
    
    @staticmethod
    def get_user_by_email(session: Session, email: str) -> Optional[Usuario]:
        """Obtener usuario por email (case-insensitive)"""
        email_normalized = email.lower().strip()
        statement = select(Usuario).where(Usuario.email == email_normalized)
        return session.exec(statement).first()
    
    @staticmethod
    def get_user_by_username(session: Session, username: str) -> Optional[Usuario]:
        """Obtener usuario por nombre de usuario"""
        statement = select(Usuario).where(Usuario.nombre_usuario == username)
        return session.exec(statement).first()
    
    @staticmethod
    def get_customer_by_codigo(session: Session, codigo_cliente: str) -> Optional[Usuario]:
        """Obtener cliente por código QR"""
        statement = select(Usuario).where(Usuario.codigo_cliente == codigo_cliente)
        return session.exec(statement).first()
    
    @staticmethod
    def get_users(
        session: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        activo: Optional[bool] = None
    ) -> List[Usuario]:
        """
        Obtener lista de usuarios con paginación
        
        Args:
            session: Sesión de base de datos
            skip: Número de registros a omitir
            limit: Número máximo de registros
            activo: Filtrar por estado activo (opcional)
        
        Returns:
            Lista de usuarios
        """
        statement = select(Usuario)
        
        if activo is not None:
            statement = statement.where(Usuario.activo == activo)
        
        statement = statement.offset(skip).limit(limit)
        return list(session.exec(statement).all())
    
    @staticmethod
    def update_user(
        session: Session,
        *,
        user_id: int,
        nombres: Optional[str] = None,
        apellidos: Optional[str] = None,
        telefono: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None
    ) -> Optional[Usuario]:
        """
        Actualizar datos de un usuario
        
        Args:
            session: Sesión de base de datos
            user_id: ID del usuario
            nombres: Nuevos nombres (opcional)
            apellidos: Nuevos apellidos (opcional)
            telefono: Nuevo teléfono (opcional)
            email: Nuevo email (opcional)
            password: Nueva contraseña (opcional)
        
        Returns:
            Usuario actualizado o None si no existe
        """
        db_user = session.get(Usuario, user_id)
        if not db_user:
            return None
        
        if nombres is not None:
            db_user.nombres = nombres
        if apellidos is not None:
            db_user.apellidos = apellidos
        if telefono is not None:
            db_user.telefono = telefono
        if email is not None:
            db_user.email = email
        if password is not None:
            db_user.password_hash = get_password_hash(password)
        
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        
        return db_user
    
    @staticmethod
    def delete_user(session: Session, user_id: int) -> bool:
        """
        Eliminar (desactivar) un usuario
        
        Args:
            session: Sesión de base de datos
            user_id: ID del usuario
        
        Returns:
            True si se desactivó, False si no existe
        """
        db_user = session.get(Usuario, user_id)
        if not db_user:
            return False
        
        db_user.activo = False
        session.add(db_user)
        session.commit()
        
        return True
    
    @staticmethod
    def hard_delete_user(session: Session, user_id: int) -> bool:
        """
        Eliminación física de un usuario (usar con precaución)
        
        Args:
            session: Sesión de base de datos
            user_id: ID del usuario
        
        Returns:
            True si se eliminó, False si no existe
        """
        db_user = session.get(Usuario, user_id)
        if not db_user:
            return False
        
        session.delete(db_user)
        session.commit()
        
        return True
    
    @staticmethod
    def authenticate_user(
        session: Session,
        username_or_email: str,
        password: str
    ) -> Optional[Usuario]:
        """
        Autenticar un usuario
        
        Args:
            session: Sesión de base de datos
            username_or_email: Nombre de usuario o email
            password: Contraseña en texto plano
        
        Returns:
            Usuario si las credenciales son correctas, None si no
        """
        # Buscar por email o username
        if "@" in username_or_email:
            db_user = UserService.get_user_by_email(session, username_or_email)
        else:
            db_user = UserService.get_user_by_username(session, username_or_email)
        
        if not db_user:
            return None

        if not verify_password(password, db_user.password_hash):
            # Incrementar contador de intentos fallidos
            db_user.intentos_login_fallidos += 1
            session.add(db_user)
            session.commit()
            return None
        
        # Reset intentos fallidos y actualizar último login
        db_user.intentos_login_fallidos = 0
        if db_user.activo:
            db_user.ultimo_login = datetime.utcnow()
        session.add(db_user)
        session.commit()
        
        return db_user
    
    @staticmethod
    def verify_user_email(session: Session, user_id: int) -> bool:
        """
        Marcar el email de un usuario como verificado
        
        Args:
            session: Sesión de base de datos
            user_id: ID del usuario
        
        Returns:
            True si se verificó, False si no existe
        """
        db_user = session.get(Usuario, user_id)
        if not db_user:
            return False
        
        db_user.verificado = True
        session.add(db_user)
        session.commit()
        
        return True
    
    @staticmethod
    def add_role_to_user(
        session: Session,
        user_id: int,
        role_id: int,
        assigned_by: Optional[int] = None
    ) -> bool:
        """
        Asignar un rol a un usuario
        
        Args:
            session: Sesión de base de datos
            user_id: ID del usuario
            role_id: ID del rol
            assigned_by: ID del usuario que asigna (opcional)
        
        Returns:
            True si se asignó, False si no existe el usuario o rol
        """
        # Verificar que existan usuario y rol
        db_user = session.get(Usuario, user_id)
        db_role = session.get(TipoRolUsuario, role_id)
        
        if not db_user or not db_role:
            return False
        
        # Verificar que no tenga ya ese rol
        statement = select(UsuarioRol).where(
            UsuarioRol.id_usuario == user_id,
            UsuarioRol.id_rol == role_id,
            UsuarioRol.fecha_revocacion == None
        )
        existing_role = session.exec(statement).first()
        
        if existing_role:
            return True  # Ya tiene el rol
        
        # Crear la asignación
        usuario_rol = UsuarioRol(
            id_usuario=user_id,
            id_rol=role_id,
            asignado_por=assigned_by
        )
        session.add(usuario_rol)
        session.commit()
        
        return True
    
    @staticmethod
    def remove_role_from_user(
        session: Session,
        user_id: int,
        role_id: int
    ) -> bool:
        """
        Revocar un rol de un usuario
        
        Args:
            session: Sesión de base de datos
            user_id: ID del usuario
            role_id: ID del rol
        
        Returns:
            True si se revocó, False si no existe la asignación
        """
        statement = select(UsuarioRol).where(
            UsuarioRol.id_usuario == user_id,
            UsuarioRol.id_rol == role_id,
            UsuarioRol.fecha_revocacion == None
        )
        usuario_rol = session.exec(statement).first()
        
        if not usuario_rol:
            return False
        
        usuario_rol.fecha_revocacion = datetime.utcnow()
        session.add(usuario_rol)
        session.commit()
        
        return True
    
    @staticmethod
    def get_user_roles(session: Session, user_id: int) -> List[TipoRolUsuario]:
        """
        Obtener los roles activos de un usuario
        
        Args:
            session: Sesión de base de datos
            user_id: ID del usuario
        
        Returns:
            Lista de roles
        """
        statement = select(TipoRolUsuario).join(UsuarioRol).where(
            UsuarioRol.id_usuario == user_id,
            UsuarioRol.fecha_revocacion == None
        )
        return list(session.exec(statement).all())
    
    @staticmethod
    def get_user_role_assignments(session: Session, user_id: int) -> List[UsuarioRol]:
        """
        Obtener las asignaciones de roles activas de un usuario con información completa
        
        Args:
            session: Sesión de base de datos
            user_id: ID del usuario
        
        Returns:
            Lista de asignaciones de roles con información del rol
        """
        statement = select(UsuarioRol).where(
            UsuarioRol.id_usuario == user_id,
            UsuarioRol.fecha_revocacion == None
        ).options(
            # Eager load the related TipoRolUsuario
            # Note: SQLModel/SQLAlchemy will automatically load the relationship
        )
        return list(session.exec(statement).all())
    
    @staticmethod
    def get_user_level(session: Session, user_id: int) -> Optional[TipoNivelUsuario]:
        """
        Obtener el nivel actual de un usuario
        
        Args:
            session: Sesión de base de datos
            user_id: ID del usuario
        
        Returns:
            Nivel del usuario o None
        """
        statement = select(TipoNivelUsuario).join(UsuarioNivel).where(
            UsuarioNivel.id_usuario == user_id
        )
        return session.exec(statement).first()
