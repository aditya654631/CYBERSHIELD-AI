import os
import json
from datetime import datetime, timezone
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
from backend.app.api.system_routes import router as system_router
from backend.app.api.evidence_routes import router as evidence_router
from backend.app.api.report_routes import router as report_router
from backend.app.api.handoff_routes import router as handoff_router
from backend.app.api.outcome_routes import router as outcome_router
from backend.app.api.geography_routes import router as geography_router
from backend.app.api.intervention_routes import router as intervention_router
from backend.app.api.atm_context_routes import router as atm_context_router
from backend.app.api.golden_hour_routes import router as golden_hour_router
from backend.app.websocket.manager import ws_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    engine_type = get_database_engine_type()
    # Startup: Database schema managed authoritatively by Alembic migrations; Base.metadata.create_all retained for test/bootstrap fallback
    print(f"[Startup] Verifying database connectivity and schema readiness for {engine_type}...")
    try:
        ensure_prototype_schema(engine)

        # Seed demo dataset only if explicitly configured in non-production, non-test environments
        is_prod = str(settings.ENVIRONMENT).lower() in ("production", "prod")
        if settings.AUTO_SEED_DEMO_DATA and not is_prod and settings.ENVIRONMENT != "test":
            db = SessionLocal()
            try:
                seed_database(db)
            finally:
                db.close()
        app.state.bootstrap_ready = True
    except Exception as exc:
        app.state.bootstrap_ready = False
        print(f"[Startup] Warning: Database bootstrap initialization failed ({exc.__class__.__name__}). Database may be unreachable.")

    yield
    # Shutdown
    await ws_manager.close_all()
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
        "X-Transaction-Count",
        "Content-Disposition"
    ],
)

from fastapi.responses import JSONResponse

# Root Health Check (Reports real database connectivity without leaking credentials)
@app.get("/health", tags=["Health"])
def health_check():
    from backend.app.services.prediction_service import prediction_service
    db_health = check_database_connection()
    provider = prediction_service.ml_provider
    model_ready = provider.is_available()
    schema_ready = db_health.get("status") == "connected"
    db_status = db_health.get("status", "disconnected")
    db_engine = db_health.get("engine", "PostgreSQL")
    is_healthy = db_health.get("status") == "connected" and model_ready
    return {
        "status": "healthy" if is_healthy else "degraded",
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "engine": "Online" if model_ready else "Unavailable",
        "database": db_health,
        "database_status": db_status,
        "database_info": db_health,
        "database_engine": db_engine,
        "ml_engine": "ready" if model_ready else "standby",
        "model_version": provider.model_version,
        "schema_ready": schema_ready,
        "predictive_pipeline": "Active (Delhi synthetic prototype)" if model_ready and schema_ready else "Unavailable",
        "models": {"available": model_ready, "location": provider.model_version, "time": provider.time_model_version},
        "bank_gateway_status": "SIMULATED_LOCAL_PROTOTYPE (No external API connected)"
    }


@app.get("/health/live", tags=["Health"])
def liveness_check():
    """Liveness probe: verifies process is alive and receiving HTTP traffic."""
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/health/ready", tags=["Health"])
def readiness_check():
    """Readiness probe: verifies database connectivity, schema readiness, and ML model availability."""
    from backend.app.services.prediction_service import prediction_service
    from backend.app.services.model_verification_service import model_verification_service
    db_health = check_database_connection()
    provider = prediction_service.ml_provider
    model_ready = provider.is_available()
    db_connected = db_health.get("status") == "connected"
    
    # Verify active model integrity based on configured environment target
    active_target = os.environ.get("ACTIVE_LOCATION_MODEL_VERSION", "v8_debiased")
    meta_file = "model_metadata_v8_debiased.json" if active_target == "v8_debiased" else "model_metadata_v7_compat.json"
    verification = model_verification_service.verify_model_artifacts(meta_file)
    model_verified = verification.get("is_ready", False)

    is_ready = db_connected and model_ready and model_verified

    payload = {
        "status": "ready" if is_ready else "not_ready",
        "database_connected": db_connected,
        "model_available": model_ready,
        "model_verified": model_verified,
        "active_model_version": provider.model_version if model_ready else "MODEL_UNAVAILABLE",
        "artifact_verification_status": verification.get("status", "UNKNOWN"),
        "load_error": provider.load_error,
        "verification_details": verification,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if not is_ready:
        return JSONResponse(status_code=503, content=payload)
    return payload

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
app.include_router(system_router, prefix=api_prefix)
app.include_router(evidence_router, prefix=api_prefix)
app.include_router(report_router, prefix=api_prefix)
app.include_router(handoff_router, prefix=api_prefix)
app.include_router(outcome_router, prefix=api_prefix)
app.include_router(geography_router, prefix=api_prefix)
app.include_router(intervention_router, prefix=api_prefix)
app.include_router(atm_context_router, prefix=api_prefix)
app.include_router(golden_hour_router, prefix=api_prefix)

# Authenticated WebSocket for real-time alerts
@app.websocket("/ws/alerts")
async def websocket_alerts_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    try:
        # Validate query param token before accept
        user = verify_ws_token(token, db)
    except Exception:
        # Reject unauthenticated connection immediately with policy violation code 1008
        await websocket.close(code=1008, reason="Unauthorized: Missing or invalid token")
        return

    await ws_manager.connect(websocket, user=user)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle heartbeat ping or general messages
            try:
                msg = json.loads(data)
                if isinstance(msg, dict) and msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }))
                    continue
            except Exception:
                pass
            await websocket.send_text(f'{{"type":"pong","received":{data}}}')
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
