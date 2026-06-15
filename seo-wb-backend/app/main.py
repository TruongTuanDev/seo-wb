from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import admin, auth, cards, finance, public, stores, wb
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.rate_limit import FixedWindowRateLimiter, client_ip
from app.db.session import get_db, init_db
from app.services.billing_foundation import ensure_subscription_plan_seeds
from app.services.wb_client import close_wb_clients


settings = get_settings()
settings.validate_runtime_security()
STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
global_limiter = FixedWindowRateLimiter(
    max_requests=settings.global_rate_limit_requests,
    window_seconds=settings.global_rate_limit_window_seconds,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_dependency = app.dependency_overrides.get(get_db, get_db)
    if db_dependency is get_db:
        init_db()
    # Respect the test database override during startup seeding.
    with contextmanager(db_dependency)() as db:
        ensure_subscription_plan_seeds(db)
        from app.services.admin_runtime import ensure_builtin_model_seeds
        ensure_builtin_model_seeds(db)
    try:
        yield
    finally:
        await close_wb_clients()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/storage", StaticFiles(directory=STORAGE_DIR), name="storage")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    global_limiter.check(client_ip(request))
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.should_secure_cookies:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(public.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(stores.router, prefix="/api/v1")
app.include_router(cards.router, prefix="/api/v1")
app.include_router(finance.router, prefix="/api/v1")
app.include_router(wb.router, prefix="/api/v1")
