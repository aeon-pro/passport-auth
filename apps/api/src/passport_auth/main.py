from fastapi import FastAPI

from passport_auth.api.v1 import router as api_v1_router


def create_app() -> FastAPI:
    app = FastAPI(title="Passport Auth API")
    app.include_router(api_v1_router)
    return app


app = create_app()
