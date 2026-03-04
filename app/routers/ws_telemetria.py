"""
WebSocket para telemetría en tiempo real.
El frontend se conecta aquí para recibir actualizaciones push
sin necesidad de polling.

Uso desde el frontend:
    const ws = new WebSocket("ws://localhost:8000/api/v1/ws/telemetria?token=JWT&tenant_id=1");
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        // data = { type: "telemetry"|"heartbeat"|"terminal_status", ... }
    };
"""
import json
import logging
from typing import Dict, Set, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.security import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ws-telemetria"])


# ─── Connection Manager ──────────────────────────────────────────────────────


class TelemetriaConnectionManager:
    """Gestiona conexiones WebSocket agrupadas por tenant"""

    def __init__(self):
        # tenant_id → set of websockets
        self._connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, tenant_id: int):
        await websocket.accept()
        if tenant_id not in self._connections:
            self._connections[tenant_id] = set()
        self._connections[tenant_id].add(websocket)
        logger.info("WS connected: tenant=%s (total=%d)", tenant_id, len(self._connections[tenant_id]))

    def disconnect(self, websocket: WebSocket, tenant_id: int):
        conns = self._connections.get(tenant_id)
        if conns:
            conns.discard(websocket)
            if not conns:
                del self._connections[tenant_id]

    async def broadcast_to_tenant(self, tenant_id: int, data: dict):
        """Envía mensaje a todos los clientes conectados de un tenant"""
        conns = self._connections.get(tenant_id)
        if not conns:
            return

        message = json.dumps(data, default=str)
        dead = []
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            conns.discard(ws)


# Instancia global del manager
manager = TelemetriaConnectionManager()


# ─── WebSocket Endpoint ──────────────────────────────────────────────────────


@router.websocket("/ws/telemetria")
async def websocket_telemetria(
    websocket: WebSocket,
    token: str = Query(...),
    tenant_id: Optional[int] = Query(None),
):
    """
    WebSocket para recibir telemetría en tiempo real.
    Requiere JWT token como query parameter.
    Opcionalmente acepta tenant_id para usuarios multi-tenant.
    """
    # Validar JWT
    payload = verify_token(token, expected_type="access")
    if payload is None:
        await websocket.close(code=4001, reason="Token inválido")
        return

    user_id = payload.get("sub")
    if user_id is None:
        await websocket.close(code=4001, reason="Token inválido")
        return

    # Resolver tenants del usuario
    from sqlmodel import Session, select
    from app.core.database import engine
    from app.models.tenant import TenantUser

    with Session(engine) as session:
        tenant_users = session.exec(
            select(TenantUser).where(TenantUser.user_id == int(user_id))
        ).all()

    if not tenant_users:
        await websocket.close(code=4003, reason="Sin tenant asignado")
        return

    user_tenant_ids = {tu.tenant_id for tu in tenant_users}

    # Si se especifica tenant_id, validar que el usuario pertenece
    if tenant_id is not None:
        if tenant_id not in user_tenant_ids:
            await websocket.close(code=4003, reason="Sin acceso a este tenant")
            return
        resolved_tenant_id = tenant_id
    else:
        # Si el usuario tiene un solo tenant, usar ese
        if len(user_tenant_ids) == 1:
            resolved_tenant_id = next(iter(user_tenant_ids))
        else:
            # Multi-tenant sin especificar: requerir tenant_id
            await websocket.close(code=4003, reason="Especifique tenant_id (usuario multi-tenant)")
            return

    await manager.connect(websocket, resolved_tenant_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, resolved_tenant_id)
        logger.info("WS disconnected: tenant=%s, user=%s", resolved_tenant_id, user_id)


# ─── Función para que los servicios notifiquen al WS ─────────────────────────


async def notify_telemetry(tenant_id: int, data: dict):
    """Llamada desde los servicios para pushear datos al frontend"""
    await manager.broadcast_to_tenant(tenant_id, data)
