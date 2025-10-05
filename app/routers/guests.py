"""
Router para clientes guest (sin cuenta)
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session

from app.core.database import get_session
from app.services.guests import GuestService
from app.services.users import UserService
from app.models.user_extended import Usuario
from app.schemas.guests import (
    GuestCustomerCreate,
    GuestCustomerRead,
    GuestLookup,
    GuestUpgradeRequest,
    GuestStats
)
from app.schemas.users import UserRead, MessageResponse
from app.schemas.auth import Token
from app.routers.auth import get_current_active_user, require_role
from app.core.security import create_access_token
from app.core.config import settings
from datetime import timedelta

router = APIRouter(prefix="/guests", tags=["guests"])


@router.post("/register", response_model=GuestCustomerRead, status_code=status.HTTP_201_CREATED)
def register_guest_customer(
    guest: GuestCustomerCreate,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(require_role("socio"))
):
    """
    Registrar cliente guest en punto de venta (solo socios)
    
    El socio registra un cliente que no tiene cuenta en la app.
    Se genera un código QR único que el cliente puede usar para:
    - Acumular puntos en cada compra
    - Canjear premios en punto de venta
    - Migrar a cuenta completa más tarde
    
    - **nombres**: Nombres del cliente
    - **apellidos**: Apellidos del cliente
    - **telefono**: Teléfono opcional
    - **sexo**: MASCULINO/FEMENINO (opcional)
    - **fecha_nac**: Fecha de nacimiento (opcional)
    """
    # Crear guest
    db_guest = GuestService.create_guest_customer(
        session,
        nombres=guest.nombres,
        apellidos=guest.apellidos,
        telefono=guest.telefono,
        sexo=guest.sexo,
        fecha_nac=guest.fecha_nac,
        registrado_por=current_user.id
    )
    
    return GuestCustomerRead(
        id=db_guest.id,
        codigo_cliente=db_guest.codigo_cliente,
        nombres=db_guest.nombres,
        apellidos=db_guest.apellidos,
        telefono=db_guest.telefono,
        fecha_creacion=db_guest.fecha_creacion,
        tipo_registro=db_guest.tipo_registro,
        mensaje=f"Cliente registrado. Código QR: {db_guest.codigo_cliente}"
    )


@router.post("/lookup", response_model=UserRead)
def lookup_guest(
    lookup: GuestLookup,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(get_current_active_user)
):
    """
    Buscar cliente por código QR
    
    Permite a un socio o al propio cliente (si ya tiene cuenta)
    buscar información de un cliente por su código.
    
    - **codigo_cliente**: Código QR del cliente
    """
    guest = GuestService.get_by_codigo(session, lookup.codigo_cliente)
    if not guest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado"
        )
    
    return guest


@router.get("/stats/{codigo_cliente}", response_model=GuestStats)
def get_guest_stats(
    codigo_cliente: str,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(get_current_active_user)
):
    """
    Obtener estadísticas de cliente guest
    
    Muestra puntos, nivel, compras totales, etc.
    Útil para que el socio le muestre al cliente su progreso.
    
    - **codigo_cliente**: Código QR del cliente
    """
    stats = GuestService.get_guest_stats(session, codigo_cliente)
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado"
        )
    
    return GuestStats(**stats)


@router.post("/upgrade", response_model=dict, status_code=status.HTTP_200_OK)
def upgrade_guest_to_account(
    upgrade_request: GuestUpgradeRequest,
    session: Session = Depends(get_session)
):
    """
    Migrar cliente guest a cuenta completa
    
    El cliente ya tiene un código QR y ha acumulado puntos.
    Ahora quiere crear una cuenta para:
    - Ver su historial en la app
    - Recibir notificaciones
    - Canjear premios desde la app
    
    **IMPORTANTE:** No necesita autenticación porque el guest aún no tiene cuenta.
    La verificación se hace con el código QR.
    
    - **codigo_cliente**: Código QR actual del cliente
    - **nombre_usuario**: Nombre de usuario deseado
    - **email**: Email para la cuenta
    - **password**: Contraseña (mínimo 8 caracteres)
    - **sexo**: MASCULINO/FEMENINO (si no lo tenía)
    - **fecha_nac**: Fecha de nacimiento (si no la tenía)
    """
    # Verificar que el código existe
    existing = GuestService.get_by_codigo(session, upgrade_request.codigo_cliente)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Código de cliente no encontrado"
        )
    
    # Verificar que sea realmente guest
    if not existing.is_guest():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este código ya tiene una cuenta asociada"
        )
    
    # Verificar que email no esté usado
    if UserService.get_user_by_email(session, upgrade_request.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )
    
    # Verificar que username no esté usado
    if UserService.get_user_by_username(session, upgrade_request.nombre_usuario):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre de usuario ya está registrado"
        )
    
    # Upgrade
    upgraded_user = GuestService.upgrade_to_full_account(
        session,
        codigo_cliente=upgrade_request.codigo_cliente,
        nombre_usuario=upgrade_request.nombre_usuario,
        email=upgrade_request.email,
        password=upgrade_request.password,
        sexo=upgrade_request.sexo,
        fecha_nac=upgrade_request.fecha_nac
    )
    
    if not upgraded_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar cuenta"
        )
    
    # Crear token automáticamente (login automático)
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(upgraded_user.id), "email": upgraded_user.email},
        expires_delta=access_token_expires
    )
    
    return {
        "message": "Cuenta actualizada exitosamente",
        "user": UserRead(
            id=upgraded_user.id,
            id_ext=upgraded_user.id_ext,
            nombre_usuario=upgraded_user.nombre_usuario,
            email=upgraded_user.email,
            nombre=upgraded_user.nombres,
            apellido=upgraded_user.apellidos,
            sexo=upgraded_user.sexo,
            fecha_nacimiento=upgraded_user.fecha_nac,
            telefono=upgraded_user.telefono,
            activo=upgraded_user.activo,
            verificado=upgraded_user.verificado,
            fecha_creacion=upgraded_user.fecha_creacion,
            ultimo_login=upgraded_user.ultimo_login,
            intentos_login_fallidos=upgraded_user.intentos_login_fallidos
        ),
        "token": Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60
        ),
        "puntos_conservados": "Todos tus puntos y compras anteriores se mantienen"
    }


@router.get("/list", response_model=List[UserRead])
def list_my_guests(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(require_role("socio"))
):
    """
    Listar clientes guest registrados por este socio
    
    Permite al socio ver todos los clientes que ha registrado.
    
    - **skip**: Registros a omitir (paginación)
    - **limit**: Máximo de registros
    """
    guests = GuestService.get_all_guests(
        session,
        skip=skip,
        limit=limit,
        registrado_por=current_user.id
    )
    
    return guests
