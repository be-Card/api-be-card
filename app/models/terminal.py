"""
Modelos para terminales MQTT, telemetría y eventos
"""
from sqlmodel import SQLModel, Field, Index
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid

from .base import BaseModel, BaseModelWithTimestamp


# ─── Enums ────────────────────────────────────────────────────────────────────


class TipoTelemetria(str, Enum):
    TEMPERATURE = "temperature"
    BARREL_LEVEL = "barrel_level"
    FLOW_RATE = "flow_rate"


class UnidadTelemetria(str, Enum):
    CELSIUS = "celsius"
    LITERS = "liters"
    ML_PER_SEC = "ml_per_sec"


class TipoEventoTerminal(str, Enum):
    HEARTBEAT = "heartbeat"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    ERROR = "error"
    COMMAND_ACK = "command_ack"


# ─── Modelos de tabla ─────────────────────────────────────────────────────────


class TerminalRegistro(BaseModelWithTimestamp, table=True):
    """Registro de terminales físicas con credenciales MQTT"""
    __tablename__ = "terminales_registro"
    __table_args__ = (
        Index("ux_terminales_tenant_codigo", "tenant_id", "codigo_terminal", unique=True),
    )

    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    equipo_id: Optional[int] = Field(default=None, foreign_key="equipos.id")
    punto_venta_id: Optional[int] = Field(default=None, foreign_key="puntos_de_venta.id")

    codigo_terminal: str = Field(max_length=20, index=True)
    nombre: str = Field(max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)

    # Credenciales MQTT
    mqtt_username: str = Field(max_length=100, unique=True, index=True)
    mqtt_password_hash: str = Field(max_length=255)
    mqtt_client_id: str = Field(max_length=100, unique=True, index=True)

    # Estado
    activo: bool = Field(default=True, index=True)
    ultimo_heartbeat: Optional[datetime] = Field(default=None)
    online: bool = Field(default=False)

    # Hardware
    hardware_id: Optional[str] = Field(default=None, max_length=100)
    firmware_version: Optional[str] = Field(default=None, max_length=50)
    ip_address: Optional[str] = Field(default=None, max_length=45)


class EquipoTelemetria(BaseModel, table=True):
    """Histórico de lecturas de telemetría de equipos"""
    __tablename__ = "equipo_telemetria"

    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    terminal_id: int = Field(foreign_key="terminales_registro.id", index=True)
    equipo_id: int = Field(foreign_key="equipos.id", index=True)

    tipo: str = Field(max_length=30)
    valor: float
    unidad: str = Field(max_length=20)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)


class TerminalEvento(BaseModel, table=True):
    """Log de eventos de terminales (heartbeats, conexiones, errores)"""
    __tablename__ = "terminal_eventos"

    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    terminal_id: int = Field(foreign_key="terminales_registro.id", index=True)

    tipo_evento: str = Field(max_length=30, index=True)
    payload: Optional[str] = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)


# ─── Schemas Pydantic ─────────────────────────────────────────────────────────


class TerminalRegistroCreate(SQLModel):
    """Schema para registrar una nueva terminal"""
    nombre: str = Field(max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)
    equipo_id: Optional[int] = None
    punto_venta_id: Optional[int] = None
    hardware_id: Optional[str] = Field(default=None, max_length=100)
    firmware_version: Optional[str] = Field(default=None, max_length=50)


class TerminalRegistroRead(SQLModel):
    """Schema de lectura de terminal (sin credenciales)"""
    id: int
    id_ext: str
    tenant_id: int
    equipo_id: Optional[int]
    punto_venta_id: Optional[int]
    codigo_terminal: str
    nombre: str
    descripcion: Optional[str]
    mqtt_username: str
    mqtt_client_id: str
    activo: bool
    ultimo_heartbeat: Optional[datetime]
    online: bool
    hardware_id: Optional[str]
    firmware_version: Optional[str]
    ip_address: Optional[str]
    creado_el: datetime


class TerminalCredencialesRead(SQLModel):
    """Schema con credenciales MQTT (solo visible al crear/rotar)"""
    id: int
    id_ext: str
    codigo_terminal: str
    mqtt_username: str
    mqtt_password: str  # password en texto plano, solo al crear/rotar
    mqtt_client_id: str
    mqtt_broker_host: str
    mqtt_broker_port: int
    topics: dict


class EquipoTelemetriaRead(SQLModel):
    """Schema de lectura de telemetría"""
    id: int
    id_ext: str
    terminal_id: int
    equipo_id: int
    tipo: str
    valor: float
    unidad: str
    timestamp: datetime


class TerminalEventoRead(SQLModel):
    """Schema de lectura de evento de terminal"""
    id: int
    id_ext: str
    terminal_id: int
    tipo_evento: str
    payload: Optional[str]
    timestamp: datetime
