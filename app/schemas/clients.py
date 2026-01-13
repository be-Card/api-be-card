"""
Esquemas Pydantic para clientes (API)
Basado en el análisis del schema SQL optimizado
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal


# Esquemas base para clientes
class ClientSummary(BaseModel):
    """Resumen de cliente para listas"""
    id: str  # id_ext del usuario
    name: str  # nombres + apellidos concatenados
    email: Optional[str] = None
    phone: Optional[str] = None
    status: str  # 'Activo' | 'Inactivo'
    loyaltyLevel: str
    loyaltyPoints: int
    totalSpent: Decimal
    totalOrders: int
    balance: Decimal
    joinDate: datetime
    lastOrder: Optional[datetime] = None


class ClientDetail(BaseModel):
    """Detalle completo de cliente"""
    id: str  # id_ext del usuario
    name: str  # nombres + apellidos concatenados
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None  # nuevo campo direccion
    gender: Optional[str] = None  # sexo mapeado a string
    birthDate: Optional[date] = None
    age: Optional[int] = None  # calculado desde fecha_nac
    status: str  # 'Activo' | 'Inactivo'
    joinDate: datetime
    lastLogin: Optional[datetime] = None
    verified: bool


class ClientStats(BaseModel):
    """Estadísticas del cliente"""
    totalSpent: Decimal
    totalOrders: int
    averageOrderValue: Decimal
    favoriteStyle: Optional[str] = None
    totalRedemptions: int
    pointsRedeemed: int
    availableBalance: Decimal
    balanceUpdatedAt: Optional[datetime] = None


class ClientLoyalty(BaseModel):
    """Información de lealtad del cliente"""
    currentPoints: int
    level: str
    levelBenefits: Optional[str] = None
    progressToNext: int  # Porcentaje 0-100
    pointsToNextLevel: Optional[int] = None


class Order(BaseModel):
    """Orden/venta del cliente"""
    id: str  # id_ext de la venta
    date: datetime
    amount: Decimal
    quantity: int  # cantidad_ml
    beerName: str
    beerType: str
    paymentMethod: Optional[str] = None


class PaymentMethod(BaseModel):
    """Método de pago del cliente"""
    id: int
    method: str  # metodo_pago
    provider: Optional[str] = None  # proveedor_metodo_pago
    active: bool
    createdAt: datetime
    lastUsed: Optional[datetime] = None


class PaginationInfo(BaseModel):
    """Información de paginación"""
    page: int
    limit: int
    total: int
    totalPages: int


class FilterOptions(BaseModel):
    """Opciones de filtrado disponibles"""
    loyaltyLevels: List[str]
    statusOptions: List[str]


# Requests
class ClientListRequest(BaseModel):
    """Request para lista de clientes"""
    page: Optional[int] = Field(default=1, ge=1)
    limit: Optional[int] = Field(default=20, ge=1, le=100)
    search: Optional[str] = None
    status: Optional[str] = None  # 'Activo' | 'Inactivo'
    loyaltyLevel: Optional[str] = None
    sortBy: Optional[str] = Field(default='name')  # 'name' | 'joinDate' | 'totalSpent' | 'loyaltyPoints'
    sortOrder: Optional[str] = Field(default='asc')  # 'asc' | 'desc'


class ClientCreateRequest(BaseModel):
    """Request para crear cliente"""
    name: str = Field(min_length=1)
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    gender: str = Field(min_length=1)
    birthDate: date


class UpdateClientRequest(BaseModel):
    """Request para actualizar cliente"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    gender: Optional[str] = None
    birthDate: Optional[date] = None


class ToggleStatusRequest(BaseModel):
    """Request para cambiar estado del cliente"""
    reason: Optional[str] = None


# Aliases para compatibilidad con el router
ClientUpdateRequest = UpdateClientRequest
ClientStatusToggleRequest = ToggleStatusRequest


# Responses
class ClientListResponse(BaseModel):
    """Response para lista de clientes"""
    clients: List[ClientSummary]
    pagination: PaginationInfo
    filters: FilterOptions


class ClientDetailResponse(BaseModel):
    """Response para detalle de cliente"""
    client: ClientDetail
    stats: ClientStats
    loyalty: ClientLoyalty
    recentOrders: List[Order]
    paymentMethods: List[PaymentMethod]


class UpdateClientResponse(BaseModel):
    """Response para actualización de cliente"""
    client: ClientDetail
    message: str


class ToggleStatusResponse(BaseModel):
    """Response para cambio de estado"""
    client: ClientDetail
    previousStatus: str
    newStatus: str
    message: str


# Alias adicional para compatibilidad
ClientStatusToggleResponse = ToggleStatusResponse


class ClientOrdersResponse(BaseModel):
    """Response para órdenes del cliente"""
    orders: List[Order]
    pagination: PaginationInfo
    summary: ClientStats


class PointTransaction(BaseModel):
    """Transacción de puntos"""
    id: str
    type: str  # 'earned' | 'redeemed' | 'adjustment'
    points: int
    description: str
    date: datetime
    relatedOrderId: Optional[str] = None
    relatedRedemptionId: Optional[str] = None


class LoyaltyHistoryResponse(BaseModel):
    """Response para historial de lealtad"""
    transactions: List[PointTransaction]
    summary: ClientLoyalty


class ClientRewardItem(BaseModel):
    id: int
    name: str
    pointsCost: int
    status: str  # Disponible | Canjeado | Expirado
    redeemedDate: Optional[datetime] = None
    category: Optional[str] = None


class ClientRewardsResponse(BaseModel):
    currentPoints: int
    level: str
    available: List[ClientRewardItem]
    history: List[ClientRewardItem]


# Respuestas genéricas
class MessageResponse(BaseModel):
    """Respuesta genérica con mensaje"""
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Respuesta de error"""
    message: str
    error_code: Optional[str] = None
    success: bool = False
