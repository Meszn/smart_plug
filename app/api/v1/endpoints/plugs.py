"""
Priz endpoint'leri.
"""
import asyncio
import json
import math

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.plug import (
    ActionResponse, PaginatedPlugResponse,
    PlugCreate, PlugDetail, PlugResponse, PlugUpdate,
)
from app.services.plug_service import PlugService

router = APIRouter(prefix="/plugs", tags=["Priz Yönetimi"])


def get_service(db: Session = Depends(get_db)) -> PlugService:
    return PlugService(db)


@router.get("", response_model=PaginatedPlugResponse, summary="Prizleri listele")
def list_plugs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    plug_type: str | None = Query(default=None),
    service: PlugService = Depends(get_service),
) -> PaginatedPlugResponse:
    plugs, total = service.get_all(page, page_size, plug_type)
    return PaginatedPlugResponse(
        items=[PlugResponse.model_validate(p) for p in plugs],
        total=total, page=page, page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.post("", response_model=PlugDetail,
             status_code=status.HTTP_201_CREATED, summary="Priz ekle")
def create_plug(data: PlugCreate, service: PlugService = Depends(get_service)) -> PlugDetail:
    return PlugDetail.model_validate(service.create(data))


@router.get("/{plug_id}", response_model=PlugDetail, summary="Priz detayı")
def get_plug(plug_id: int, service: PlugService = Depends(get_service)) -> PlugDetail:
    return PlugDetail.model_validate(service.get_by_id(plug_id))


@router.put("/{plug_id}", response_model=PlugDetail, summary="Priz güncelle")
def update_plug(plug_id: int, data: PlugUpdate, service: PlugService = Depends(get_service)) -> PlugDetail:
    return PlugDetail.model_validate(service.update(plug_id, data))


@router.delete("/{plug_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Priz sil")
def delete_plug(plug_id: int, service: PlugService = Depends(get_service)) -> None:
    service.delete(plug_id)


@router.get("/{plug_id}/status", summary="Anlık durum — cihazdan polling")
async def get_plug_status(
    plug_id: int, service: PlugService = Depends(get_service)
) -> dict:
    return await service.get_status(plug_id)


@router.get(
    "/{plug_id}/status/stream",
    summary="Canlı durum akışı — SSE",
    description="""
Server-Sent Events ile periyodik durum güncellemesi.

Frontend kullanımı:
```javascript
const es = new EventSource('/api/v1/plugs/1/status/stream?interval=3');
es.onmessage = e => updateUI(JSON.parse(e.data));
es.addEventListener('error', e => console.log('Hata:', JSON.parse(e.data)));
```
    """,
)
async def stream_plug_status(
    plug_id: int,
    interval: float = Query(default=3.0, ge=1.0, le=60.0),
    service: PlugService = Depends(get_service),
) -> StreamingResponse:
    service.get_by_id(plug_id)  # 404 kontrolü

    async def event_generator():
        while True:
            try:
                data = await service.get_status(plug_id)
                yield f"data: {json.dumps(data, default=str)}\n\n"
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            await asyncio.sleep(interval)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/statuses", summary="Paralel çoklu durum sorgusu")
async def get_multiple_statuses(
    plug_ids: list[int], service: PlugService = Depends(get_service)
) -> list[dict]:
    return await service.get_all_statuses(plug_ids)


@router.post("/{plug_id}/actions/turn-on", response_model=ActionResponse)
async def turn_on(plug_id: int, service: PlugService = Depends(get_service)) -> ActionResponse:
    from app.schemas.plug import ActionType
    return await service.execute_action(plug_id, ActionType.TURN_ON)


@router.post("/{plug_id}/actions/turn-off", response_model=ActionResponse)
async def turn_off(plug_id: int, service: PlugService = Depends(get_service)) -> ActionResponse:
    from app.schemas.plug import ActionType
    return await service.execute_action(plug_id, ActionType.TURN_OFF)


@router.post("/{plug_id}/actions/restart", response_model=ActionResponse)
async def restart(plug_id: int, service: PlugService = Depends(get_service)) -> ActionResponse:
    from app.schemas.plug import ActionType
    return await service.execute_action(plug_id, ActionType.RESTART)