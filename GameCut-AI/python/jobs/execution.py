"""Execution ownership primitives for the database-backed job queue.

The queue schema predates explicit lease columns.  Until a migration introduces
those fields, this module stores an opaque execution token in the job JSON
payload.  Every worker mutation is then conditional on that token, so a stale,
cancelled, or regenerated execution cannot publish results for a newer one.
"""

from __future__ import annotations

import json
import re
import secrets
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


RUNTIME_KEY = "_gamecut_runtime"
EXECUTION_TOKEN_KEY = "execution_token"
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


class JobOwnershipLostError(RuntimeError):
    """Raised when an execution no longer owns its job row."""


def payload_as_dict(payload: Any) -> dict[str, Any]:
    """Return a defensive object payload, matching the worker's legacy fallback."""
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8", errors="replace")

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {}

    if not isinstance(payload, Mapping):
        return {}

    return deepcopy(dict(payload))


def new_execution_token() -> str:
    """Create a filesystem-safe, high-entropy execution identifier."""
    return secrets.token_urlsafe(24)


def attach_execution_token(payload: Any, token: str | None = None) -> dict[str, Any]:
    """Attach a worker-owned token without trusting a client-supplied runtime key."""
    token = token or new_execution_token()
    if not _TOKEN_PATTERN.fullmatch(token):
        raise ValueError("Execution token has an invalid format")

    data = payload_as_dict(payload)
    runtime = data.get(RUNTIME_KEY)
    runtime = dict(runtime) if isinstance(runtime, Mapping) else {}
    runtime[EXECUTION_TOKEN_KEY] = token
    data[RUNTIME_KEY] = runtime
    return data


def execution_token_for(job: Mapping[str, Any]) -> str:
    """Read and validate the token assigned at queue claim time."""
    token = job.get("execution_token")
    if not isinstance(token, str):
        runtime = payload_as_dict(job.get("payload")).get(RUNTIME_KEY, {})
        token = runtime.get(EXECUTION_TOKEN_KEY) if isinstance(runtime, Mapping) else None

    if not isinstance(token, str) or not _TOKEN_PATTERN.fullmatch(token):
        raise JobOwnershipLostError("Job has no valid execution token")
    return token


def execution_work_directory(root: str | Path, job_id: int, token: str) -> Path:
    """Build an isolated workspace for one execution attempt."""
    if int(job_id) <= 0:
        raise ValueError("Job ID must be positive")
    if not _TOKEN_PATTERN.fullmatch(token):
        raise ValueError("Execution token has an invalid format")

    root_path = Path(root).resolve()
    workspace = (root_path / str(int(job_id)) / token).resolve()
    if root_path not in workspace.parents:
        raise ValueError("Execution workspace is outside the analysis root")
    return workspace
