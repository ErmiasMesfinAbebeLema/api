from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.config import settings
from api.routers import auth, students, documents, courses, enrollments, certificates, payment_methods, payments, invoices, reports
from api.database import engine
from api.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - runs on startup and shutdown"""
    # Startup: Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # Shutdown: Close engine
    await engine.dispose()


app = FastAPI(
    title="Mulat Beauty Training Institute API",
    description="Backend API for Institute Management System",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(students.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(courses.router, prefix="/api/v1")
app.include_router(enrollments.router, prefix="/api/v1")
app.include_router(certificates.templates_router, prefix="/api/v1")
app.include_router(certificates.admin_certificates_router, prefix="/api/v1")
app.include_router(certificates.public_certificates_router, prefix="/api/v1")
app.include_router(payment_methods.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(invoices.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")

# Serve uploaded files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/")
def read_root():
    return {"message": "Welcome to Mulat Beauty Training Institute API"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
