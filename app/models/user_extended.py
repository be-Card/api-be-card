"""
Modelos extendidos de usuario para la API BeCard
Incluye roles, niveles, métodos de pago y referidos
"""
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, date
from decimal import Decimal
from .base import BaseModel, TimestampMixin, TipoSexo

# Importaciones para evitar referencias circulares
if TYPE_CHECKING:
    from .beer import Cerveza
    from .sales_point import PuntoVenta
    from .sales import Venta


class TipoRolUsuario(BaseModel, table=True):
    """Tipos de rol de usuario (sin asignar, cliente, socio, admin)"""
    __tablename__ = "tipos_rol_usuario"
    
    tipo: str = Field(max_length=50, unique=True)
    descripcion: Optional[str] = Field(default=None, description="Descripción del rol")
    creado_el: datetime = Field(default_factory=datetime.utcnow)
    
    # Relaciones
    usuarios_roles: List["UsuarioRol"] = Relationship(back_populates="rol")


class TipoNivelUsuario(BaseModel, table=True):
    """Niveles de usuario (bronce, plata, oro)"""
    __tablename__ = "tipo_nivel_usuario"
    
    nivel: str = Field(max_length=50, unique=True)
    puntaje_min: int = Field(ge=0, description="Puntaje mínimo requerido para este nivel")
    puntaje_max: Optional[int] = Field(default=None, description="Puntaje máximo del nivel")
    beneficios: Optional[str] = Field(default=None, description="Descripción de beneficios del nivel")
    
    # Relaciones
    usuarios_niveles: List["UsuarioNivel"] = Relationship(back_populates="nivel")


# NOTA: RolPermiso no está en el schema SQL proporcionado
# Comentado para mantener compatibilidad pero no se usará
# class RolPermiso(SQLModel, table=True):
#     """Permisos asociados a roles"""
#     __tablename__ = "roles_permisos"
#     
#     id_rol: int = Field(foreign_key="tipos_rol_usuario.id", primary_key=True)
#     permiso: str = Field(max_length=50, primary_key=True)
#     
#     # Relaciones
#     rol: TipoRolUsuario = Relationship(back_populates="permisos")


class TipoMetodoPago(BaseModel, table=True):
    """Tipos de método de pago (efectivo, QR, NFC, tarjeta RFID)"""
    __tablename__ = "tipos_metodo_pago"
    
    metodo_pago: str = Field(max_length=50, unique=True)
    requiere_autorizacion: bool = Field(default=False, description="Si requiere validación externa")
    activo: bool = Field(default=True, description="Si el método está disponible")
    
    # Relaciones
    usuarios_metodos: List["UsuarioMetodoPago"] = Relationship(back_populates="metodo_pago")


class Usuario(BaseModel, table=True):
    """Modelo principal de usuario extendido"""
    __tablename__ = "usuarios"
    
    # Identificación
    nombre_usuario: Optional[str] = Field(max_length=50, unique=True, index=True, default=None)
    codigo_cliente: str = Field(
        max_length=20, 
        unique=True, 
        index=True,
        description="Código único para QR (usado por guests y app users)"
    )
    
    # Datos personales
    nombres: str = Field(max_length=100)
    apellidos: str = Field(max_length=100)
    telefono: Optional[str] = Field(max_length=20, default=None)
    sexo: Optional[TipoSexo] = Field(default=None)
    fecha_nac: Optional[date] = Field(default=None)
    
    # Credenciales (opcionales para guests)
    email: Optional[str] = Field(
        max_length=100, 
        unique=True, 
        index=True,
        default=None,
        regex=r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
    )
    password_hash: Optional[str] = Field(default=None)
    password_salt: Optional[str] = Field(default=None)
    
    # Tipo de registro
    tipo_registro: str = Field(
        max_length=20,
        default='app',
        index=True,
        description="app, punto_venta, importado"
    )
    
    # Estado y seguridad
    fecha_creacion: datetime = Field(default_factory=datetime.utcnow, index=True)
    ultimo_login: Optional[datetime] = Field(default=None)
    activo: bool = Field(default=True, index=True)
    verificado: bool = Field(default=False, description="Si el email está verificado")
    intentos_login_fallidos: int = Field(default=0, ge=0, description="Contador para bloqueo de seguridad")
    bloqueado_hasta: Optional[datetime] = Field(default=None, description="Fecha hasta la cual está bloqueado")
    
    # Metadata para guests
    registrado_por: Optional[int] = Field(
        foreign_key="usuarios.id",
        default=None,
        description="ID del socio que registró este guest"
    )
    
    # Relaciones
    roles: List["UsuarioRol"] = Relationship(
        back_populates="usuario",
        sa_relationship_kwargs={"foreign_keys": "UsuarioRol.id_usuario"}
    )
    canjes: List["Canje"] = Relationship(back_populates="usuario")
    transacciones_puntos: List["TransaccionPuntos"] = Relationship(back_populates="usuario")
    nivel: Optional["UsuarioNivel"] = Relationship(back_populates="usuario")
    metodos_pago: List["UsuarioMetodoPago"] = Relationship(back_populates="usuario")
    ventas: List["Venta"] = Relationship(back_populates="usuario")
    cervezas_creadas: List["Cerveza"] = Relationship(back_populates="creador")
    puntos_venta: List["PuntoVenta"] = Relationship(
        back_populates="socio",
        sa_relationship_kwargs={"foreign_keys": "PuntoVenta.id_usuario_socio"}
    )
    referidos_generados: List["Referido"] = Relationship(
        back_populates="usuario_generador",
        sa_relationship_kwargs={"foreign_keys": "Referido.id_usuario_generador"}
    )
    referidos_recibidos: List["Referido"] = Relationship(
        back_populates="usuario_referido", 
        sa_relationship_kwargs={"foreign_keys": "Referido.id_usuario_referido"}
    )
    
    def is_guest(self) -> bool:
        """Verifica si el usuario es guest (sin cuenta)"""
        return self.tipo_registro == 'punto_venta' and self.email is None
    
    def can_login(self) -> bool:
        """Verifica si el usuario puede hacer login"""
        return self.email is not None and self.password_hash is not None


class UsuarioRol(SQLModel, table=True):
    """Relación usuario-rol (un usuario puede tener múltiples roles)"""
    __tablename__ = "usuarios_roles"
    
    id_usuario: int = Field(foreign_key="usuarios.id", primary_key=True)
    id_rol: int = Field(foreign_key="tipos_rol_usuario.id", primary_key=True)
    fecha_asignacion: datetime = Field(default_factory=datetime.utcnow)
    asignado_por: Optional[int] = Field(default=None, foreign_key="usuarios.id", description="Quién asignó el rol")
    fecha_revocacion: Optional[datetime] = Field(default=None, description="Fecha de revocación del rol")
    
    # Relaciones
    usuario: Usuario = Relationship(
        back_populates="roles",
        sa_relationship_kwargs={"foreign_keys": "UsuarioRol.id_usuario"}
    )
    rol: TipoRolUsuario = Relationship(back_populates="usuarios_roles")


class UsuarioNivel(SQLModel, table=True):
    """Relación usuario-nivel"""
    __tablename__ = "usuarios_niveles"
    
    id_usuario: int = Field(foreign_key="usuarios.id", primary_key=True)
    id_nivel: int = Field(foreign_key="tipo_nivel_usuario.id")
    fecha_asignacion: datetime = Field(default_factory=datetime.utcnow)
    puntaje_actual: int = Field(default=0, ge=0, description="Cache del puntaje actual")
    
    # Relaciones
    usuario: Usuario = Relationship(back_populates="nivel")
    nivel: TipoNivelUsuario = Relationship(back_populates="usuarios_niveles")


class UsuarioMetodoPago(SQLModel, table=True):
    """Métodos de pago de usuarios"""
    __tablename__ = "usuarios_metodos_de_pago"
    
    id_usuario: int = Field(foreign_key="usuarios.id", primary_key=True)
    id_metodo_pago: int = Field(foreign_key="tipos_metodo_pago.id", primary_key=True)
    proveedor_metodo_pago: str = Field(max_length=50)
    token_proveedor: str
    fecha_creacion: datetime = Field(default_factory=datetime.utcnow)
    activo: bool = Field(default=True, description="Si el método está activo")
    fecha_expiracion: Optional[date] = Field(default=None, description="Fecha de expiración (ej: tarjetas)")
    
    # Relaciones
    usuario: Usuario = Relationship(back_populates="metodos_pago")
    metodo_pago: TipoMetodoPago = Relationship(back_populates="usuarios_metodos")


class Referido(BaseModel, table=True):
    """Sistema de referidos"""
    __tablename__ = "referidos"
    
    id_usuario_generador: Optional[int] = Field(foreign_key="usuarios.id", default=None)
    id_usuario_referido: Optional[int] = Field(foreign_key="usuarios.id", default=None)
    codigo: str = Field(max_length=20, unique=True, index=True)
    fecha_registro: datetime = Field(default_factory=datetime.utcnow)
    puntos_otorgados: int = Field(ge=0)
    estado: str = Field(default="pendiente", max_length=20, description="pendiente, activo, completado")
    fecha_activacion: Optional[datetime] = Field(default=None, description="Cuando el referido se activó")
    
    # Relaciones
    usuario_generador: Optional[Usuario] = Relationship(
        back_populates="referidos_generados",
        sa_relationship_kwargs={"foreign_keys": "Referido.id_usuario_generador"}
    )
    usuario_referido: Optional[Usuario] = Relationship(
        back_populates="referidos_recibidos",
        sa_relationship_kwargs={"foreign_keys": "Referido.id_usuario_referido"}
    )


# ReglaConversionPuntos se define en app.models.points


# Esquemas Pydantic para API

class UsuarioBase(SQLModel):
    """Esquema base para usuario"""
    nombre_usuario: str = Field(max_length=50)
    nombres: str = Field(max_length=100)
    apellidos: str = Field(max_length=100)
    telefono: Optional[str] = Field(max_length=20, default=None)
    sexo: TipoSexo
    email: str = Field(max_length=100)
    fecha_nac: Optional[date] = None
    activo: bool = Field(default=False)


class UsuarioCreate(UsuarioBase):
    """Esquema para crear usuario"""
    password: str = Field(min_length=8, max_length=100)


class UsuarioRead(UsuarioBase):
    """Esquema para leer usuario"""
    id: int
    id_ext: str
    fecha_creacion: datetime
    ultimo_login: Optional[datetime] = None
    verificado: bool = False
    intentos_login_fallidos: int = 0
    bloqueado_hasta: Optional[datetime] = None


class UsuarioUpdate(SQLModel):
    """Esquema para actualizar usuario"""
    nombres: Optional[str] = Field(default=None, max_length=100)
    apellidos: Optional[str] = Field(default=None, max_length=100)
    telefono: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=100)
    fecha_nac: Optional[date] = None
    activo: Optional[bool] = None
    verificado: Optional[bool] = None
    intentos_login_fallidos: Optional[int] = None
    bloqueado_hasta: Optional[datetime] = None


class RolUsuarioCreate(SQLModel):
    """Esquema para asignar rol a usuario"""
    id_usuario: int
    id_rol: int


class MetodoPagoCreate(SQLModel):
    """Esquema para crear método de pago"""
    id_usuario: int
    id_metodo_pago: int
    proveedor_metodo_pago: str = Field(max_length=50)
    token_proveedor: str


class ReferidoCreate(SQLModel):
    """Esquema para crear referido"""
    codigo: str = Field(max_length=20)
    id_usuario_generador: Optional[int] = None
    puntos_otorgados: int = Field(default=100)