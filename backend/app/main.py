import os
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from backend.app.config.settings import settings
from backend.app.models.db import engine, Base, SessionLocal, get_db, check_database_connection, get_database_engine_type
from backend.app.models import models
from backend.app.models.bootstrap import ensure_prototype_schema
from database.seed.seed_data import seed_database
from backend.app.auth.security import verify_ws_token

# Routers
from backend.app.api.auth_routes import router as auth_router
from backend.app.api.complaint_routes import router as complaint_router
from backend.app.api.transaction_routes import router as transaction_router
from backend.app.api.prediction_routes import router as prediction_router
from backend.app.api.gis_routes import router as gis_router
from backend.app.api.alert_routes import router as alert_router
from backend.app.api.analytics_routes import router as analytics_router
from backend.app.api.dashboard_routes import router as dashboard_router
from backend.app.api.model_routes import router as model_router
from backend.app.api.audit_routes import router as audit_router
from backend.app.api.bank_action_routes import router as bank_action_router
from backend.app.websocket.manager import ws_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    engine_type = get_database_engine_type()
    # Startup: Database schema managed authoritatively by Alembic migrations; Base.metadata.create_all retained for test/bootstrap fallback
    print(f"[Startup] Verifying database connectivity and schema readiness for {engine_type}...")
    try:
        ensure_prototype_schema(engine)

        db = SessionLocal()
        try:
            seed_database(db)
            app.state.bootstrap_ready = True
        finally:
            db.close()
    except Exception as exc:
        app.state.bootstrap_ready = False
        print(f"[Startup] Warning: Database bootstrap initialization failed ({exc.__class__.__name__}). Database may be unreachable.")

    yield
    # Shutdown
    print("[Shutdown] CyberShield AI engine stopped.")

app = FastAPI(
    title=settings.APP_NAME,
    description="National Cybercrime Predictive Intelligence Platform — SIH26184",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Hardened CORS Configuration:
# - No wildcard domain regexes for railway.app or vercel.app
# - Strictly explicitly configured origins
# - Localhost development support only in non-production environments
# - Exposed pagination and metadata headers for frontend consumption
is_production = str(settings.ENVIRONMENT).lower() in ("production", "prod")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=None if is_production else r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Total-Count",
        "X-Page",
        "X-Total-Pages",
        "X-Limit",
        "X-Context-Type",
        "X-Source-Scenario",
        "X-Transaction-Count"
    ],
)

# Root Health Check (Reports real database connectivity without leaking credentials)
@app.get("/health", tags=["Health"])
def health_check():
    from backend.app.services.prediction_service import prediction_service
    db_health = check_database_connection()
    provider = prediction_service.ml_provider
    model_ready = provider.is_available()
    bootstrap_state = getattr(app.state, "bootstrap_ready", None)
    schema_ready = db_health.get("status") == "connected" if bootstrap_state is None else bool(bootstrap_state)
    db_status = db_health.get("status", "disconnected")
    db_engine = db_health.get("engine", "PostgreSQL")
    is_healthy = db_health.get("status") == "connected" and model_ready and schema_ready
    return {
        "status": "healthy" if is_healthy else "degraded",
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "engine": "Online" if model_ready else "Unavailable",
        "database": db_status,
        "database_info": db_health,
        "database_engine": db_engine,
        "ml_engine": "ready" if model_ready else "standby",
        "model_version": provider.model_version,
        "schema_ready": schema_ready,
        "predictive_pipeline": "Active (Delhi synthetic prototype)" if model_ready and schema_ready else "Unavailable",
        "models": {"available": model_ready, "location": provider.model_version, "time": provider.time_model_version},
        "bank_gateway_status": "SIMULATED_LOCAL_PROTOTYPE (No external API connected)"
    }

# Include API Routers under /api/v1
api_prefix = "/api/v1"
app.include_router(auth_router, prefix=api_prefix)
app.include_router(complaint_router, prefix=api_prefix)
app.include_router(transaction_router, prefix=api_prefix)
app.include_router(prediction_router, prefix=api_prefix)
app.include_router(gis_router, prefix=api_prefix)
app.include_router(alert_router, prefix=api_prefix)
app.include_router(analytics_router, prefix=api_prefix)
app.include_router(dashboard_router, prefix=api_prefix)
app.include_router(model_router, prefix=api_prefix)
app.include_router(audit_router, prefix=api_prefix)
app.include_router(bank_action_router, prefix=api_prefix)

# Authenticated WebSocket for real-time alerts
@app.websocket("/ws/alerts")
async def websocket_alerts_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    try:
        # Validate query param token before accept
        verify_ws_token(token, db)
    except Exception:
        # Reject unauthenticated connection immediately with policy violation code 1008
        await websocket.close(code=1008, reason="Unauthorized: Missing or invalid token")
        return

    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo or handle ping
            await websocket.send_text(f'{{"type":"pong","received":{data}}}')
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
