from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.auth import router as auth_router
from backend.api.invoices import router as invoice_router
from backend.api.dictionary import router as dictionary_router
from backend.api.health import router as health_router


# ==========================================================
# APPLICATION
# ==========================================================

app = FastAPI(
    title="Invoice AI",
    version="2.0.0",
)


# ==========================================================
# CORS
# ==========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================
# ROUTERS
# ==========================================================

app.include_router(
    auth_router,
    prefix="/api",
)

app.include_router(
    invoice_router,
    prefix="/api",
)

app.include_router(
    dictionary_router,
)

app.include_router(
    health_router,
)


# ==========================================================
# ROOT
# ==========================================================

@app.get("/")
def root():
    return {
        "service": "invoice-ai",
        "status": "running",
    }