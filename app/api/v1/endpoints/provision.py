# -*- coding: utf-8 -*-
"""
Provision endpoint'leri — priz ilk kurulum.
"""
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.provision import (
    ProvisionRequest,
    ProvisionResponse,
    ProvisionStep,
)
from app.services.provision_service import ProvisionService

router = APIRouter(prefix="/provision", tags=["Priz Kurulum"])


@router.get(
    "/scan-ap",
    summary="Çevredeki fabrika modundaki prizleri listele",
    description="TP-Link ile başlayan WiFi ağlarını listeler. Bunlar kurulum bekleyen prizler olabilir.",
)
def scan_plug_aps():
    try:
        service = ProvisionService()
        networks = service.get_tp_link_networks()
        current = service.get_current_wifi()
        result = {
            "current_wifi": current,
            "tp_link_networks": networks,
            "all_networks": service.scan_nearby_wifi(),
        }
        return JSONResponse(
            content=json.loads(json.dumps(result, ensure_ascii=False)),
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        import traceback
        return {"error": str(e), "detail": traceback.format_exc()}


@router.post(
    "/setup",
    summary="Prizi WiFi'a bagla",
    description="""
Fabrika modundaki prizi hedef WiFi agina baglar.

**Adimlar:**
1. PC prizin AP'ine baglanir (TP-Link_XXXX)
2. Prize hedef WiFi bilgileri gonderilir
3. PC asil aga geri doner
4. Priz yeni agda otomatik aranir

**Sure:** ~30-60 saniye
    """,
)
async def setup_plug(request: ProvisionRequest):
    service = ProvisionService()
    result = await service.provision_plug(
        plug_ap_ssid=request.plug_ap_ssid,
        target_ssid=request.target_ssid,
        target_password=request.target_password,
        original_ssid=request.original_ssid,
    )
    return JSONResponse(
        content=json.loads(json.dumps(result, ensure_ascii=False)),
        media_type="application/json; charset=utf-8"
    )


@router.get(
    "/wifi-profiles",
    summary="Kayitli WiFi profillerini listele",
)
def list_wifi_profiles():
    service = ProvisionService()
    result = {
        "current": service.get_current_wifi(),
        "profiles": service.get_available_wifi_profiles(),
    }
    return JSONResponse(
        content=json.loads(json.dumps(result, ensure_ascii=False)),
        media_type="application/json; charset=utf-8"
    )