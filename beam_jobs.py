"""Bounded, process-local background jobs for the optional nine-year optimizer.

No engine simulation runs inside an HTTP request thread. Jobs do not survive a
restart: the frontend must handle a 404 and explicitly start again.
"""
from __future__ import annotations

import copy
import threading
import time
import uuid

from fieldwise.beam_optimizer import run_beam_search_9y
from future_alternatives import _parameters_for_model_point

_LOCK = threading.Lock()
_JOBS: dict[str, dict] = {}
_ACTIVE: str | None = None
_RECENT_LIMIT = 10


def _run(job_id: str, settings: dict) -> None:
    global _ACTIVE
    with _LOCK:
        _JOBS[job_id]["stage"] = "Simulating nine-year crop rotation trajectories..."
    try:
        point = settings.pop("model_point")
        parameters = _parameters_for_model_point(lat=point[1], lon=point[0])
        result = run_beam_search_9y(
            lon=point[0], lat=point[1], model_params=parameters, **settings
        )
        with _LOCK:
            _JOBS[job_id].update(status="ready", stage="Complete", result=result)
    except Exception as exc:
        # Do not expose internal stack traces or local paths to the public API.
        with _LOCK:
            _JOBS[job_id].update(
                status="failed", stage="Optimization failed",
                error=str(exc)[:320] if isinstance(exc, (ValueError, RuntimeError))
                else "The optimization could not be completed. Check the backend logs.",
            )
    finally:
        with _LOCK:
            if _ACTIVE == job_id:
                _ACTIVE = None


def start(settings: dict) -> dict:
    global _ACTIVE
    with _LOCK:
        if _ACTIVE and _JOBS.get(_ACTIVE, {}).get("status") == "running":
            # The demo backend is single-worker and simulation-heavy: avoid
            # silently queueing unlimited jobs or returning a hanging request.
            return {"status": "busy", "stage": "Another nine-year optimization is already running."}
        job_id = uuid.uuid4().hex
        # Bounded memory for completed results. In-progress job is kept.
        finished = [key for key, val in _JOBS.items() if val["status"] != "running"]
        for key in finished[:-_RECENT_LIMIT]:
            del _JOBS[key]
        _JOBS[job_id] = {"status": "running", "stage": "Starting optimizer...", "createdAt": time.time()}
        _ACTIVE = job_id
    threading.Thread(target=_run, args=(job_id, copy.deepcopy(settings)), daemon=True).start()
    return {"jobId": job_id, "status": "running", "stage": "Starting optimizer..."}


def status(job_id: str) -> dict | None:
    with _LOCK:
        item = _JOBS.get(job_id)
        return copy.deepcopy(item) if item is not None else None
