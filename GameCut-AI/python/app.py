import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.routes import router
from utils.logging import configure_logging, log_extra


configure_logging()
logger = logging.getLogger("gamecut.app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("API startup", **log_extra(service="GameCut AI AI Service"))
    yield


app = FastAPI(title="GameCut AI Processing Service", lifespan=lifespan)
app.include_router(router)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.exception(
            "Unexpected API error",
            **log_extra(
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            ),
        )
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error"},
        )

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "API request",
        **log_extra(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        ),
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    logger.warning(
        "API validation failure",
        **log_extra(method=request.method, path=request.url.path, errors=exc.errors()),
    )
    return JSONResponse(
        status_code=422,
        content={"success": False, "error": "Validation failed", "details": exc.errors()},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
