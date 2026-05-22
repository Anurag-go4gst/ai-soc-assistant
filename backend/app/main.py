from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_chat import router as chat_router
from app.api.routes_health import router as health_router
from app.api.routes_investigations import router as investigations_router
from app.api.routes_scenarios import router as scenarios_router
from app.api.routes_settings import router as settings_router
from app.auth.routes_auth import router as auth_router


app = FastAPI(title="AI SOC Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3010",
        "http://127.0.0.1:3010",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(health_router, prefix="/api")
app.include_router(auth_router)
app.include_router(auth_router, prefix="/api")
app.include_router(chat_router)
app.include_router(chat_router, prefix="/api")
app.include_router(investigations_router)
app.include_router(investigations_router, prefix="/api")
app.include_router(scenarios_router)
app.include_router(scenarios_router, prefix="/api")
app.include_router(settings_router)
app.include_router(settings_router, prefix="/api")
