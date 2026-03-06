"""
Ağ Keşif Endpoint'leri.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.discovery import RegisterDeviceRequest, ScanRequest, ScanResult
from app.services.discovery_service import DiscoveryService

router = APIRouter(prefix="/discovery", tags=["Ağ Keşfi"])


def get_service(db: Session = Depends(get_db)) -> DiscoveryService:
    return DiscoveryService(db)


@router.post(
    "/scan",
    response_model=ScanResult,
    summary="Ağı tara — Kasa/HS cihazlarını keşfet",
)
async def scan_network(
    request: ScanRequest,
    service: DiscoveryService = Depends(get_service),
) -> ScanResult:
    return await service.scan_network(
        subnet=request.subnet,
        timeout=request.timeout,
    )


@router.post(
    "/register",
    summary="Keşfedilen cihazı sisteme kaydet",
)
async def register_device(
    request: RegisterDeviceRequest,
    service: DiscoveryService = Depends(get_service),
) -> dict:
    plug = await service.register_device(
        ip_address=request.ip_address,
        name=request.name,
        location=request.location,
        notes=request.notes,
    )
    return {
        "id": plug.id,
        "plug_type": plug.plug_type,
        "name": plug.name,
        "location": plug.location,
        "ip_address": plug.ip_address,
        "mac_address": plug.mac_address,
        "firmware_version": plug.firmware_version,
        "notes": plug.notes,

        "created_at": plug.created_at.isoformat(),
        "updated_at": plug.updated_at.isoformat(),
    }