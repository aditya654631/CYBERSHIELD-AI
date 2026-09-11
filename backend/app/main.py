import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config.settings import settings
from backend.app.models.db import engine, Base, SessionLocal, check_database_connection, get_database_engine_type
from backend.app.models import models
from database.seed.seed_data import seed_database

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
from backend.app.websocket.manager import ws_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    engine_type = get_database_engine_type()
    # Startup: Database schema managed authoritatively by Alembic migrations; Base.metadata.create_all retained for test/bootstrap fallback
    print(f"[Startup] Verifying database connectivity and schema readiness for {engine_type}...")
    try:
        Base.metadata.create_all(bind=engine)

        db = SessionLocal()
        try:
            seed_database(db)
        finally:
            db.close()
    except Exception as exc:
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

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root Health Check (Reports real database connectivity without leaking credentials)
@app.get("/health", tags=["Health"])
def health_check():
    db_health = check_database_connection()
    is_healthy = db_health.get("status") == "connected"
    return {
        "status": "healthy" if is_healthy else "degraded",
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "engine": "Online",
        "database": db_health,
        "predictive_pipeline": "Active (Hybrid Ensemble + NetworkX Centrality)"
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

# WebSocket for real-time alerts
@app.websocket("/ws/alerts")
async def websocket_alerts_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo or handle ping
            await websocket.send_text(f'{{"type":"pong","received":{data}}}')
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
