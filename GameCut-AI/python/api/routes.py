import os
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Path, status

from utils.db import dependency_status, fetch_job_status
from utils.logging import log_extra

import logging


router = APIRouter()
logger = logging.getLogger("gamecut.api")


def _configured_token():
    return os.getenv("GAMECUT_AI_API_TOKEN", "")


def require_internal_token(
    authorization: str | None = Header(default=None),
    x_gamecut_token: str | None = Header(default=None, alias="X-GameCut-Token"),
):
    expected = _configured_token()
    supplied = x_gamecut_token

    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()

    if not expected or not supplied or supplied != expected:
        logger.warning("Unauthorized internal API request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": "Unauthorized"},
        )


JobId = Path(..., ge=1, description="Positive ai_jobs ID")


@router.get("/health")
def health():
    deps = dependency_status()
    return {
        "status": "ok",
        "service": "GameCut AI AI Service",
        "dependencies": deps,
        "internal_token_configured": bool(_configured_token()),
    }


@router.post("/jobs/{job_id}", dependencies=[Depends(require_internal_token)])
def receive_job(job_id: int = JobId):
    logger.info("Job received", **log_extra(job_id=job_id))
    return {"success": True, "job_id": job_id, "status": "received"}


@router.get("/jobs/{job_id}/status", dependencies=[Depends(require_internal_token)])
def job_status(job_id: int = JobId):
    job = fetch_job_status(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"success": False, "error": "Job not found"},
        )

    updated_at = job.get("updated_at")
    if isinstance(updated_at, datetime):
        updated_at = updated_at.isoformat()

    return {
        "job_id": int(job["id"]),
        "status": job["status"],
        "progress": int(job.get("progress") or 0),
        "current_step": job.get("current_step"),
        "error_message": job.get("error_message"),
        "updated_at": updated_at,
    }
