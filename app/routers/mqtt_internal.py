"""
Router para endpoints internos del bridge MQTT y autenticación de Mosquitto.

Dos grupos de endpoints:
1. /internal/mqtt/mosquitto/* → llamados por mosquitto-go-auth plugin (sin token)
2. /internal/mqtt/*           → llamados por el bridge (con X-Internal-Token)
"""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Header, Form, Response
from sqlmodel import SQLModel, Session, select
from typing import Optional
from uuid import UUID
from datetime import datetime
import logging

from ..core.database import get_session
from ..core.config import settings
from ..services.terminales import TerminalService
from ..services.telemetria import TelemetriaService
from ..services.cards import CardService
from ..services.wallets import WalletService
from ..services.device_sessions import DeviceSessionService
from ..models.terminal import (
    TerminalRegistro, EquipoTelemetriaRead, TerminalEventoRead,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/mqtt", tags=["mqtt-internal"])


# ─── Helpers ──────────────────────────────────────────────────────────────────


def verify_internal_token(
    x_internal_token: str = Header(..., alias="X-Internal-Token"),
) -> None:
    """Verifica el token interno compartido con el bridge"""
    if x_internal_token != settings.mqtt_internal_token:
        raise HTTPException(status_code=403, detail="Token interno inválido")


def _resolve_terminal(session: Session, terminal_id_ext: str) -> TerminalRegistro:
    """Resuelve terminal por id_ext (UUID string). Raise 404 si no existe."""
    try:
        id_ext_uuid = UUID(terminal_id_ext)
    except ValueError:
        raise HTTPException(status_code=400, detail="terminal_id_ext inválido")

    terminal = session.exec(
        select(TerminalRegistro).where(
            TerminalRegistro.id_ext == id_ext_uuid,
            TerminalRegistro.activo == True,
        )
    ).first()

    if terminal is None:
        raise HTTPException(status_code=404, detail="Terminal no encontrada")
    return terminal


# ══════════════════════════════════════════════════════════════════════════════
#  GRUPO 1: Endpoints para mosquitto-go-auth plugin (form-encoded, sin token)
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/mosquitto/auth")
def mosquitto_auth_user(
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    """
    Mosquitto llama aquí para validar usuario/password.
    Debe retornar HTTP 200 si OK, 403 si rechazado.
    """
    # Permitir siempre al bridge (usa su propio password)
    if username == settings.mqtt_bridge_username:
        if password == settings.mqtt_bridge_password:
            return Response(status_code=200)
        return Response(status_code=403)

    # Autenticar terminal
    terminal = TerminalService.autenticar_terminal(
        session, mqtt_username=username, mqtt_password=password,
    )
    if terminal is None:
        return Response(status_code=403)

    return Response(status_code=200)


@router.post("/mosquitto/acl")
def mosquitto_check_acl(
    username: str = Form(...),
    topic: str = Form(...),
    acc: int = Form(...),  # mosquitto-go-auth: 1=sub, 2=pub, 4=unsub
    session: Session = Depends(get_session),
):
    """
    Mosquitto llama aquí para validar si el usuario puede acceder al topic.
    HTTP 200 = permitido, 403 = denegado.
    """
    # Bridge tiene acceso total
    if username == settings.mqtt_bridge_username:
        return Response(status_code=200)

    # Buscar terminal
    terminal = session.exec(
        select(TerminalRegistro).where(
            TerminalRegistro.mqtt_username == username,
            TerminalRegistro.activo == True,
        )
    ).first()

    if terminal is None:
        return Response(status_code=403)

    # Validar que el topic pertenece a esta terminal
    prefix = settings.mqtt_topic_prefix
    terminal_ext = str(terminal.id_ext)
    tenant_id = str(terminal.tenant_id)

    # Topics permitidos empiezan con: becard/{tenant_id}/{terminal_id_ext}/
    allowed_prefix = f"{prefix}/{tenant_id}/{terminal_ext}/"
    if not topic.startswith(allowed_prefix):
        logger.warning(
            "ACL denied: user=%s tried topic=%s (expected prefix=%s)",
            username, topic, allowed_prefix,
        )
        return Response(status_code=403)

    # Terminales no pueden publicar en command/* ni response/* (solo el bridge)
    rest = topic[len(allowed_prefix):]
    if acc == 2 and (rest.startswith("command/") or rest.startswith("response/")):
        return Response(status_code=403)

    return Response(status_code=200)


@router.post("/mosquitto/superuser")
def mosquitto_check_superuser(
    username: str = Form(...),
):
    """
    Mosquitto pregunta si es superusuario (acceso total sin ACL check).
    Solo el bridge es superusuario.
    """
    if username == settings.mqtt_bridge_username:
        return Response(status_code=200)
    return Response(status_code=403)


# ══════════════════════════════════════════════════════════════════════════════
#  GRUPO 2: Endpoints para el Bridge (JSON, con X-Internal-Token)
# ══════════════════════════════════════════════════════════════════════════════


class MqttAuthRequest(SQLModel):
    mqtt_username: str
    mqtt_password: str


class MqttAuthResponse(SQLModel):
    ok: bool
    terminal_id: Optional[int] = None
    terminal_id_ext: Optional[str] = None
    tenant_id: Optional[int] = None
    equipo_id: Optional[int] = None
    mqtt_client_id: Optional[str] = None


class TelemetryIngestRequest(SQLModel):
    terminal_id_ext: str
    equipo_id: int
    tipo: str
    valor: float
    unidad: str
    timestamp: Optional[datetime] = None


class HeartbeatIngestRequest(SQLModel):
    terminal_id_ext: str
    ip_address: Optional[str] = None


class EventIngestRequest(SQLModel):
    terminal_id_ext: str
    tipo_evento: str
    payload: Optional[str] = None
    timestamp: Optional[datetime] = None

class EquipoInfoRequest(SQLModel):
    terminal_id_ext: str

class EquipoInfoResponse(SQLModel):
    ok: bool
    cerveza_id: Optional[str] = None
    cerveza_nombre: Optional[str] = None
    cerveza_tipo: Optional[str] = None
    cerveza_descripcion: Optional[str] = None
    cerveza_imagen: Optional[str] = None
    cerveza_abv: Optional[float] = None
    cerveza_ibu: Optional[float] = None
    precio_por_litro: Optional[float] = None
    error: Optional[str] = None

@router.post("/auth", response_model=MqttAuthResponse)
def mqtt_auth(
    data: MqttAuthRequest,
    session: Session = Depends(get_session),
    _: None = Depends(verify_internal_token),
):
    """Validar credenciales de terminal (llamado por el bridge)"""
    terminal = TerminalService.autenticar_terminal(
        session,
        mqtt_username=data.mqtt_username,
        mqtt_password=data.mqtt_password,
    )
    if terminal is None:
        return MqttAuthResponse(ok=False)

    return MqttAuthResponse(
        ok=True,
        terminal_id=terminal.id,
        terminal_id_ext=str(terminal.id_ext),
        tenant_id=terminal.tenant_id,
        equipo_id=terminal.equipo_id,
        mqtt_client_id=terminal.mqtt_client_id,
    )


@router.post("/telemetry", response_model=EquipoTelemetriaRead)
def mqtt_telemetry(
    data: TelemetryIngestRequest,
    session: Session = Depends(get_session),
    _: None = Depends(verify_internal_token),
):
    """Ingest de telemetría desde el bridge"""
    from app.models.sales_point import Equipo

    terminal = _resolve_terminal(session, data.terminal_id_ext)

    # Validar que el equipo existe y pertenece al mismo tenant
    equipo = session.get(Equipo, data.equipo_id)
    if not equipo or not equipo.activo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    if equipo.tenant_id != terminal.tenant_id:
        raise HTTPException(status_code=403, detail="Equipo no pertenece a este tenant")

    # Si la terminal está vinculada a un equipo específico, verificar match
    if terminal.equipo_id is not None and terminal.equipo_id != data.equipo_id:
        raise HTTPException(
            status_code=403,
            detail="Terminal configurada para otro equipo",
        )

    try:
        return TelemetriaService.registrar_lectura(
            session,
            tenant_id=terminal.tenant_id,
            terminal_id=terminal.id,
            equipo_id=data.equipo_id,
            tipo=data.tipo,
            valor=data.valor,
            unidad=data.unidad,
            timestamp=data.timestamp,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/heartbeat")
def mqtt_heartbeat(
    data: HeartbeatIngestRequest,
    session: Session = Depends(get_session),
    _: None = Depends(verify_internal_token),
):
    """Ingest de heartbeat desde el bridge"""
    terminal = _resolve_terminal(session, data.terminal_id_ext)

    TerminalService.registrar_heartbeat(
        session, terminal_id=terminal.id, ip_address=data.ip_address,
    )

    TelemetriaService.registrar_evento(
        session,
        tenant_id=terminal.tenant_id,
        terminal_id=terminal.id,
        tipo_evento="heartbeat",
    )

    return {"ok": True}


@router.post("/event", response_model=TerminalEventoRead)
def mqtt_event(
    data: EventIngestRequest,
    session: Session = Depends(get_session),
    _: None = Depends(verify_internal_token),
):
    """Ingest de evento desde el bridge"""
    terminal = _resolve_terminal(session, data.terminal_id_ext)

    return TelemetriaService.registrar_evento(
        session,
        tenant_id=terminal.tenant_id,
        terminal_id=terminal.id,
        tipo_evento=data.tipo_evento,
        payload=data.payload,
        timestamp=data.timestamp,
    )

@router.post("/terminal-beer", response_model=EquipoInfoResponse)
def mqtt_equipo_info(
    data: EquipoInfoRequest,
    session: Session = Depends(get_session),
    _: None = Depends(verify_internal_token),
):
    """Info del equipo/cerveza para mostrar en el terminal al arrancar."""
    from app.models.sales_point import Equipo
    from app.models.beer import Cerveza
    from app.models.pricing import ConsultaPrecio
    from app.services.pricing import PricingService

    terminal = _resolve_terminal(session, data.terminal_id_ext)

    if not terminal.equipo_id:
        return EquipoInfoResponse(ok=False, error="EQUIPO_NOT_CONFIGURED")

    equipo = session.get(Equipo, terminal.equipo_id)
    if not equipo or not equipo.activo:
        return EquipoInfoResponse(ok=False, error="EQUIPO_NOT_FOUND")

    if not equipo.id_cerveza:
        return EquipoInfoResponse(ok=False, error="CERVEZA_NOT_CONFIGURED")

    cerveza = session.get(Cerveza, equipo.id_cerveza)
    if not cerveza:
        return EquipoInfoResponse(ok=False, error="CERVEZA_NOT_FOUND")

    precio_por_litro = None
    try:
        consulta = ConsultaPrecio(
            id_cerveza=cerveza.id,
            id_equipo=equipo.id,
            id_punto_venta=equipo.id_punto_de_venta,
        )
        calculo = PricingService.calcular_precio(
            session, consulta=consulta, tenant_id=terminal.tenant_id
        )
        precio_por_litro = float(calculo.precio_final)
    except ValueError:
        from app.services.cervezas import CervezaService
        precio_base = CervezaService.get_precio_actual(session, cerveza.id)
        if precio_base is not None:
            precio_por_litro = float(precio_base)
        else:
            return EquipoInfoResponse(ok=False, error="CERVEZA_PRICE_NOT_CONFIGURED")

    return EquipoInfoResponse(
        ok=True,
        cerveza_id=str(cerveza.id_ext),
        cerveza_nombre=cerveza.nombre,
        cerveza_tipo=cerveza.tipo,
        cerveza_descripcion=cerveza.descripcion,
        cerveza_imagen=cerveza.imagen,
        cerveza_abv=float(cerveza.abv) if cerveza.abv else None,
        cerveza_ibu=float(cerveza.ibu) if cerveza.ibu else None,
        precio_por_litro=precio_por_litro,
    )

# ══════════════════════════════════════════════════════════════════════════════
#  GRUPO 3: Endpoints de sesión de dispensado (JSON, con X-Internal-Token)
# ══════════════════════════════════════════════════════════════════════════════


class CardLookupRequest(SQLModel):
    terminal_id_ext: str
    uid: str


class CardLookupResponse(SQLModel):
    ok: bool
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    wallet_balance: Optional[float] = None
    card_type: Optional[str] = None
    error: Optional[str] = None


class SessionStartRequest(SQLModel):
    terminal_id_ext: str
    uid: Optional[str] = None
    equipo_id: Optional[int] = None
    requested_ml: int
    payment_mode: str = "wallet"
    idempotency_key: Optional[str] = None


class SessionStartResponse(SQLModel):
    ok: bool
    session_id: Optional[str] = None
    cerveza_id: Optional[int] = None
    price_per_liter: Optional[float] = None
    max_ml: Optional[int] = None
    estimated_amount: Optional[float] = None
    error: Optional[str] = None


class SessionCompleteRequest(SQLModel):
    terminal_id_ext: str
    session_id: str
    poured_ml: int
    payment_method_name: Optional[str] = None
    provider_transaction_id: Optional[str] = None


class SessionCompleteResponse(SQLModel):
    ok: bool
    status: Optional[str] = None
    poured_ml: Optional[int] = None
    final_amount: Optional[float] = None
    error: Optional[str] = None


class CreateQRPaymentRequest(SQLModel):
    terminal_id_ext: str
    session_id: str
    amount: float
    description: str = "Cerveza BeCard"


class CreateQRPaymentResponse(SQLModel):
    ok: bool
    qr_data: Optional[str] = None
    provider_payment_id: Optional[str] = None
    error: Optional[str] = None


class SendCommandRequest(SQLModel):
    terminal_id_ext: str
    command_type: str
    payload: Optional[str] = None


@router.post("/card-lookup", response_model=CardLookupResponse)
def mqtt_card_lookup(
    data: CardLookupRequest,
    session: Session = Depends(get_session),
    _: None = Depends(verify_internal_token),
):
    """Consulta de tarjeta NFC: busca usuario, wallet y tipo de asignación"""
    terminal = _resolve_terminal(session, data.terminal_id_ext)

    card, assignment, user = CardService.lookup(
        session, tenant_id=terminal.tenant_id, uid=data.uid,
    )

    if not card:
        return CardLookupResponse(ok=False, error="CARD_NOT_FOUND")

    if not assignment:
        return CardLookupResponse(ok=False, error="CARD_NOT_ASSIGNED")

    wallet_balance = 0.0
    card_type = assignment.assignment_type

    if user:
        wallet = WalletService.get_or_create_user_wallet(
            session, tenant_id=terminal.tenant_id, user_id=user.id,
        )
        wallet_balance = float(wallet.balance)
        return CardLookupResponse(
            ok=True,
            user_id=user.id,
            user_name=user.nombre if hasattr(user, "nombre") else str(user.id),
            wallet_balance=wallet_balance,
            card_type=card_type,
        )

    if card_type == "anonymous_wallet":
        wallet = WalletService.get_or_create_card_wallet(
            session, tenant_id=terminal.tenant_id, card_id=card.id,
        )
        wallet_balance = float(wallet.balance)
        return CardLookupResponse(
            ok=True,
            wallet_balance=wallet_balance,
            card_type=card_type,
        )

    return CardLookupResponse(ok=False, error="CARD_NO_WALLET")


@router.post("/session-start", response_model=SessionStartResponse)
def mqtt_session_start(
    data: SessionStartRequest,
    session: Session = Depends(get_session),
    _: None = Depends(verify_internal_token),
):
    """Inicia sesión de dispensado. Reutiliza DeviceSessionService.create_session()"""
    terminal = _resolve_terminal(session, data.terminal_id_ext)

    equipo_id = data.equipo_id or terminal.equipo_id
    if not equipo_id:
        return SessionStartResponse(ok=False, error="EQUIPO_NOT_CONFIGURED")

    uid_hash = None
    user_id = None
    if data.uid:
        uid_hash = CardService.hash_uid(data.uid)
        _, assignment, user = CardService.lookup(
            session, tenant_id=terminal.tenant_id, uid=data.uid,
        )
        if assignment and assignment.user_id:
            user_id = int(assignment.user_id)

    try:
        device_session = DeviceSessionService.create_session(
            session,
            tenant_id=terminal.tenant_id,
            equipo_id=equipo_id,
            uid_hash=uid_hash,
            requested_ml=data.requested_ml,
            payment_mode=data.payment_mode,
            idempotency_key=data.idempotency_key,
            user_id=user_id,
        )
    except ValueError as e:
        return SessionStartResponse(ok=False, error=str(e))

    return SessionStartResponse(
        ok=True,
        session_id=str(device_session.id_ext),
        cerveza_id=device_session.cerveza_id,
        price_per_liter=float(device_session.price_per_liter),
        max_ml=device_session.max_ml,
        estimated_amount=float(device_session.estimated_amount),
    )


@router.post("/session-complete", response_model=SessionCompleteResponse)
def mqtt_session_complete(
    data: SessionCompleteRequest,
    session: Session = Depends(get_session),
    _: None = Depends(verify_internal_token),
):
    """Completa sesión de dispensado. Reutiliza DeviceSessionService."""
    terminal = _resolve_terminal(session, data.terminal_id_ext)

    try:
        device_session = DeviceSessionService.complete_wallet_session(
            session,
            tenant_id=terminal.tenant_id,
            session_id_ext=data.session_id,
            poured_ml=data.poured_ml,
            created_by=None,
        )
    except ValueError as e:
        code = str(e)
        if code == "INVALID_PAYMENT_MODE":
            try:
                device_session = DeviceSessionService.complete_external_session(
                    session,
                    tenant_id=terminal.tenant_id,
                    session_id_ext=data.session_id,
                    poured_ml=data.poured_ml,
                    payment_method_name=data.payment_method_name or "MercadoPago",
                    provider_transaction_id=data.provider_transaction_id,
                )
            except ValueError as e2:
                return SessionCompleteResponse(ok=False, error=str(e2))
        else:
            return SessionCompleteResponse(ok=False, error=code)

    return SessionCompleteResponse(
        ok=True,
        status=device_session.status,
        poured_ml=int(device_session.poured_ml or 0),
        final_amount=float(device_session.final_amount or 0),
    )


@router.post("/create-qr-payment", response_model=CreateQRPaymentResponse)
def mqtt_create_qr_payment(
    data: CreateQRPaymentRequest,
    session: Session = Depends(get_session),
    _: None = Depends(verify_internal_token),
):
    """Crea intención de pago QR en la pasarela configurada"""
    _resolve_terminal(session, data.terminal_id_ext)

    try:
        from app.services.payment_gateway import get_payment_gateway

        gateway = get_payment_gateway()
        result = gateway.create_qr_payment(
            amount=Decimal(str(data.amount)),
            description=data.description,
            external_reference=data.session_id,
        )
        return CreateQRPaymentResponse(
            ok=True,
            qr_data=result.qr_data,
            provider_payment_id=result.provider_payment_id,
        )
    except Exception as e:
        logger.exception("Error creando QR payment")
        return CreateQRPaymentResponse(ok=False, error=str(e))


@router.post("/send-command")
def mqtt_send_command(
    data: SendCommandRequest,
    session: Session = Depends(get_session),
    _: None = Depends(verify_internal_token),
):
    """Envía comando a terminal vía bridge HTTP"""
    import httpx

    terminal = _resolve_terminal(session, data.terminal_id_ext)

    try:
        resp = httpx.post(
            f"{settings.mqtt_bridge_base_url}/send-command",
            json={
                "tenant_id": terminal.tenant_id,
                "terminal_id_ext": data.terminal_id_ext,
                "command_type": data.command_type,
                "payload": data.payload,
            },
            timeout=5,
        )
        return {"ok": resp.status_code == 200}
    except httpx.HTTPError as e:
        logger.error("Error enviando comando al bridge: %s", e)
        return {"ok": False, "error": str(e)}
