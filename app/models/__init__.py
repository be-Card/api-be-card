"""
Modelos SQLModel para la API BeCard
"""

# Modelos base y enums
from .base import (
    TipoPrioridadRegla,
    TipoSexo,
    TipoEstadoPago,
    TipoAlcanceRegla,
    BaseModel,
    TimestampMixin,
    BaseModelWithTimestamp
)

# Modelos de usuario extendidos
from .user_extended import (
    TipoRolUsuario,
    TipoNivelUsuario,
    TipoMetodoPago,
    Usuario,
    UsuarioRol,
    UsuarioNivel,
    UsuarioMetodoPago,
    Referido,

    UsuarioBase,
    UsuarioCreate,
    UsuarioRead,
    UsuarioUpdate,
    RolUsuarioCreate,
    MetodoPagoCreate,
    ReferidoCreate
)

# Modelos de cervezas
from .beer import (
    TipoEstiloCerveza,
    Cerveza,
    CervezaEstilo,
    PrecioCerveza,
    TipoEstiloCervezaBase,
    TipoEstiloCervezaCreate,
    TipoEstiloCervezaRead,
    CervezaBase,
    CervezaCreate,
    CervezaRead,
    CervezaUpdate,
    PrecioCervezaCreate,
    PrecioCervezaRead
)

# Modelos de puntos de venta
from .sales_point import (
    TipoEstadoEquipo,
    TipoBarril,
    PuntoVenta,
    Equipo,
    TipoEstadoEquipoBase,
    TipoEstadoEquipoCreate,
    TipoEstadoEquipoRead,
    TipoBarrilBase,
    TipoBarrilCreate,
    TipoBarrilRead,
    PuntoVentaBase,
    PuntoVentaCreate,
    PuntoVentaRead,
    PuntoVentaUpdate,
    EquipoBase,
    EquipoCreate,
    EquipoRead,
    EquipoUpdate
)

# Modelos de ventas
from .sales import (
    Venta,
    VentaBase,
    VentaCreate,
    VentaRead,
    VentaUpdate,
    VentaFilter,
    VentaStats,
    VentaResumen,
    ParticionVentas
)

# Modelos de precios
from .pricing import (
    TipoAlcanceReglaDePrecio,
    ReglaDePrecio,
    ReglaDePrecioAlcance,
    TipoAlcanceReglaDePrecioBase,
    TipoAlcanceReglaDePrecioCreate,
    TipoAlcanceReglaDePrecioRead,
    ReglaDePrecioBase,
    ReglaDePrecioCreate,
    ReglaDePrecioRead,
    ReglaDePrecioUpdate,
    CalculoPrecio,
    ConsultaPrecio,
    CalculadoraPrecios
)

# Modelos de puntos
from .points import (
    ReglaConversionPuntos,
    ReglaConversionPuntosBase,
    ReglaConversionPuntosCreate,
    ReglaConversionPuntosRead,
    ReglaConversionPuntosUpdate,
    CalculoPuntos,
    ConsultaPuntos,
    CalculadoraPuntos,
    ConfiguracionPuntos
)

# Modelos de recompensas (premios y canjes)
from .rewards import (
    CatalogoPremio,
    Canje,
    CatalogoPremioBase,
    CatalogoPremioCreate,
    CatalogoPremioRead,
    CatalogoPremioUpdate,
    CanjeBase,
    CanjeCreate,
    CanjeRead,
    CanjeResumen,
    ValidadorCanjes
)

# Modelos de transacciones (puntos y pagos)
from .transactions import (
    TipoEstadoPago as TipoEstadoPagoTransaccion,
    TransaccionPuntos,
    Pago,
    TransaccionPuntosBase,
    TransaccionPuntosCreate,
    TransaccionPuntosRead,
    TransaccionPuntosFilter,
    SaldoPuntos,
    PagoBase,
    PagoCreate,
    PagoRead,
    PagoUpdate,
    PagoResumen,
    GestorTransaccionesPuntos
)

# Exportar todos los modelos para facilitar las importaciones
__all__ = [
    # Base
    "TipoPrioridadRegla",
    "TipoSexo",
    "TipoEstadoPago",
    "TipoAlcanceRegla",
    "BaseModel",
    "TimestampMixin",
    "BaseModelWithTimestamp",
    
    # User Extended
    "TipoRolUsuario",
    "TipoNivelUsuario",
    "TipoMetodoPago",
    "Usuario",
    "UsuarioRol",
    "UsuarioNivel",
    "UsuarioMetodoPago",
    "Referido",

    "UsuarioBase",
    "UsuarioCreate",
    "UsuarioRead",
    "UsuarioUpdate",
    "RolUsuarioCreate",
    "MetodoPagoCreate",
    "ReferidoCreate",
    
    # Beer
    "TipoEstiloCerveza",
    "Cerveza",
    "CervezaEstilo",
    "PrecioCerveza",
    "TipoEstiloCervezaBase",
    "TipoEstiloCervezaCreate",
    "TipoEstiloCervezaRead",
    "CervezaBase",
    "CervezaCreate",
    "CervezaRead",
    "CervezaUpdate",
    "PrecioCervezaCreate",
    "PrecioCervezaRead",
    
    # Sales Point
    "TipoEstadoEquipo",
    "TipoBarril",
    "PuntoVenta",
    "Equipo",
    "TipoEstadoEquipoBase",
    "TipoEstadoEquipoCreate",
    "TipoEstadoEquipoRead",
    "TipoBarrilBase",
    "TipoBarrilCreate",
    "TipoBarrilRead",
    "PuntoVentaBase",
    "PuntoVentaCreate",
    "PuntoVentaRead",
    "PuntoVentaUpdate",
    "EquipoBase",
    "EquipoCreate",
    "EquipoRead",
    "EquipoUpdate",
    
    # Sales
    "Venta",
    "VentaBase",
    "VentaCreate",
    "VentaRead",
    "VentaUpdate",
    "VentaFilter",
    "VentaStats",
    "VentaResumen",
    "ParticionVentas",
    
    # Pricing
    "TipoAlcanceReglaDePrecio",
    "ReglaDePrecio",
    "ReglaDePrecioAlcance",
    "TipoAlcanceReglaDePrecioBase",
    "TipoAlcanceReglaDePrecioCreate",
    "TipoAlcanceReglaDePrecioRead",
    "ReglaDePrecioBase",
    "ReglaDePrecioCreate",
    "ReglaDePrecioRead",
    "ReglaDePrecioUpdate",
    "CalculoPrecio",
    "ConsultaPrecio",
    "CalculadoraPrecios",
    
    # Points
    "ReglaConversionPuntos",
    "ReglaConversionPuntosBase",
    "ReglaConversionPuntosCreate",
    "ReglaConversionPuntosRead",
    "ReglaConversionPuntosUpdate",
    "CalculoPuntos",
    "ConsultaPuntos",
    "CalculadoraPuntos",
    "ConfiguracionPuntos",
    
    # Rewards
    "CatalogoPremio",
    "Canje",
    "CatalogoPremioBase",
    "CatalogoPremioCreate",
    "CatalogoPremioRead",
    "CatalogoPremioUpdate",
    "CanjeBase",
    "CanjeCreate",
    "CanjeRead",
    "CanjeResumen",
    "ValidadorCanjes",
    
    # Transactions
    "TipoEstadoPagoTransaccion",
    "TransaccionPuntos",
    "Pago",
    "TransaccionPuntosBase",
    "TransaccionPuntosCreate",
    "TransaccionPuntosRead",
    "TransaccionPuntosFilter",
    "SaldoPuntos",
    "PagoBase",
    "PagoCreate",
    "PagoRead",
    "PagoUpdate",
    "PagoResumen",
    "GestorTransaccionesPuntos",
]