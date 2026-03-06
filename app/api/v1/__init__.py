from fastapi import APIRouter

from app.api.v1.endpoints.discovery import router as discovery_router
from app.api.v1.endpoints.plugs import router as plugs_router
from app.api.v1.endpoints.provision import router as provision_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(plugs_router)
api_router.include_router(discovery_router)
api_router.include_router(provision_router)
