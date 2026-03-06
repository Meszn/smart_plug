"""
Priz Servisi — CRUD ve polling işlemleri.
"""
import math

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.registry import PlugAdapterRegistry
from app.core.polling import PlugOfflineError, PlugResponseError
from app.models.plug import Plug
from app.schemas.plug import ActionResponse, ActionType, PlugCreate, PlugUpdate


class PlugService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── CRUD ──────────────────────────────────────────────

    def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        plug_type: str | None = None,
    ) -> tuple[list[Plug], int]:
        query = select(Plug)
        if plug_type:
            query = query.where(Plug.plug_type == plug_type)

        total = self.db.execute(
            select(func.count()).select_from(query.subquery())
        ).scalar_one()

        offset = (page - 1) * page_size
        plugs = list(
            self.db.execute(
                query.offset(offset).limit(page_size).order_by(Plug.id)
            ).scalars().all()
        )
        return plugs, total

    def get_by_id(self, plug_id: int) -> Plug:
        plug = self.db.get(Plug, plug_id)
        if not plug:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ID={plug_id} olan priz bulunamadı.",
            )
        return plug

    def create(self, data: PlugCreate) -> Plug:
        if not PlugAdapterRegistry.is_supported(data.plug_type.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Desteklenmeyen tip: '{data.plug_type.value}'",
            )
        if data.mac_address:
            existing = self.db.execute(
                select(Plug).where(Plug.mac_address == data.mac_address)
            ).scalar_one_or_none()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"'{data.mac_address}' MAC adresi zaten kayıtlı",
                )

        plug = Plug(
            plug_type=data.plug_type.value,
            name=data.name,
            ip_address=data.ip_address,
            location=data.location,
            mac_address=data.mac_address,
            firmware_version=data.firmware_version,
            notes=data.notes,
        )
        self.db.add(plug)
        self.db.flush()
        self.db.refresh(plug)
        return plug

    def update(self, plug_id: int, data: PlugUpdate) -> Plug:
        plug = self.get_by_id(plug_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(plug, field, value)
        self.db.flush()
        self.db.refresh(plug)
        return plug

    def delete(self, plug_id: int) -> None:
        plug = self.get_by_id(plug_id)
        self.db.delete(plug)
        self.db.flush()

    # ── Polling ───────────────────────────────────────────

    async def get_status(self, plug_id: int) -> dict:
        plug = self.get_by_id(plug_id)
        adapter = PlugAdapterRegistry.get_adapter(plug)
        try:
            return await adapter.get_status()
        except PlugOfflineError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cihaza ulaşılamıyor: {e.reason}",
            )
        except PlugResponseError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Geçersiz cihaz yanıtı: {e.detail}",
            )
        except TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cihaz zaman aşımı: {plug.ip_address}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cihaza ulaşılamıyor: {str(e)}",
            )

    async def execute_action(self, plug_id: int, action: ActionType) -> ActionResponse:
        """Cihaza komut gönderir (aç/kapat/yeniden başlat)."""
        plug = self.get_by_id(plug_id)
        adapter = PlugAdapterRegistry.get_adapter(plug)

        if action == ActionType.TURN_ON:
            return await adapter.turn_on()
        elif action == ActionType.TURN_OFF:
            return await adapter.turn_off()
        elif action == ActionType.RESTART:
            return await adapter.restart()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Geçersiz eylem: '{action}'",
            )

    async def get_all_statuses(self, plug_ids: list[int]) -> list[dict]:
        import asyncio

        plugs = [self.get_by_id(pid) for pid in plug_ids]

        async def safe_status(plug):
            adapter = PlugAdapterRegistry.get_adapter(plug)
            try:
                return await adapter.get_status()
            except Exception:
                return {
                    "plug_id": plug.id,
                    "plug_type": plug.plug_type,
                    "name": plug.name,
                    "ip_address": plug.ip_address,
                    "is_on": False,
                    "is_online": False,
                    "error": "Cihaza ulaşılamıyor",
                }

        return list(await asyncio.gather(*[safe_status(p) for p in plugs]))
