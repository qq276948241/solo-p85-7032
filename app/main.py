import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import Base, engine
from app.routers import store, owner, pet, booking, care, employee


def create_app() -> FastAPI:
    app = FastAPI(
        title="宠物寄养管理系统 API",
        description="三家宠物寄养店后端服务，含宠物档案、寄养预约、日常照护、员工管理模块",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        status_code = getattr(exc, "status_code", 500)
        detail = getattr(exc, "detail", str(exc))
        return JSONResponse(
            status_code=status_code,
            content={"code": status_code, "message": detail, "data": None},
        )

    @app.get("/api/health", tags=["系统"])
    async def health_check():
        return {"code": 0, "message": "ok", "data": {"status": "running"}}

    app.include_router(store.router)
    app.include_router(owner.router)
    app.include_router(pet.router)
    app.include_router(booking.router)
    app.include_router(care.router)
    app.include_router(employee.router)

    return app


app = create_app()


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "care"), exist_ok=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
    )
