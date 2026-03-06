"""
Smart Plug API — Ana uygulama.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core import get_settings
from app.db.database import Base, check_database_connection, engine
from app.schemas.plug import HealthResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("smart_plug_api")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🔌 Smart Plug API başlatılıyor...")

    # Tüm adapter'ları yükle
    import app.adapters.basic_plug
    import app.adapters.energy_monitor
    import app.adapters.surge_protector
    import app.adapters.hs110          # ← YENİ
    import app.adapters.hs100          # ← YENİ

    from app.adapters.registry import PlugAdapterRegistry
    logger.info(f"✅ Kayıtlı adapter'lar: {PlugAdapterRegistry.supported_types()}")

    Base.metadata.create_all(bind=engine)
    logger.info("✅ Veritabanı tabloları hazır.")
    yield
    logger.info("🛑 Uygulama kapatılıyor...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
## 🔌 Smart Plug Management API


    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.router.default_response_class = JSONResponse

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc), "error_code": "VALIDATION_ERROR"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Beklenmedik hata: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Sunucu hatası.", "error_code": "INTERNAL_SERVER_ERROR"},
    )


app.include_router(api_router)


@app.get("/", include_in_schema=False)
def root():
    return {"message": f"{settings.app_name} v{settings.app_version}", "docs": "/docs"}


@app.get("/health", response_model=HealthResponse, tags=["Sistem"])
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        database="ok" if check_database_connection() else "error",
    )