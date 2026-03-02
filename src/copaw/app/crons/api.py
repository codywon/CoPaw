# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request

from ...config import load_config
from .manager import CronManager
from .models import CronJobSpec, CronJobView
from .targeting import enrich_dispatch_meta, resolve_target_for_persist

router = APIRouter(prefix="/cron", tags=["cron"])


def get_cron_manager(request: Request) -> CronManager:
    mgr = getattr(request.app.state, "cron_manager", None)
    if mgr is None:
        raise HTTPException(
            status_code=503,
            detail="cron manager not initialized",
        )
    return mgr


def _normalize_spec_for_save(spec: CronJobSpec) -> CronJobSpec:
    cfg = load_config()
    dispatch = spec.dispatch
    target = dispatch.target
    try:
        resolved_user_id, resolved_session_id = resolve_target_for_persist(
            channel=dispatch.channel,
            user_id=target.user_id,
            session_id=target.session_id,
            target_policy=dispatch.target_policy,
            last_dispatch=cfg.last_dispatch,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    payload = spec.model_dump(mode="json")
    payload["dispatch"]["target"]["user_id"] = resolved_user_id
    payload["dispatch"]["target"]["session_id"] = resolved_session_id
    payload["dispatch"]["meta"] = enrich_dispatch_meta(
        channel=dispatch.channel,
        user_id=resolved_user_id,
        meta=payload["dispatch"].get("meta"),
    )
    return CronJobSpec.model_validate(payload)


@router.get("/jobs", response_model=list[CronJobSpec])
async def list_jobs(mgr: CronManager = Depends(get_cron_manager)):
    return await mgr.list_jobs()


@router.get("/jobs/{job_id}", response_model=CronJobView)
async def get_job(job_id: str, mgr: CronManager = Depends(get_cron_manager)):
    job = await mgr.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return CronJobView(spec=job, state=mgr.get_state(job_id))


@router.post("/jobs", response_model=CronJobSpec)
async def create_job(
    spec: CronJobSpec,
    mgr: CronManager = Depends(get_cron_manager),
):
    # server generates id; ignore client-provided spec.id
    job_id = str(uuid.uuid4())
    normalized = _normalize_spec_for_save(spec)
    payload = normalized.model_dump(mode="json")
    payload["id"] = job_id
    created = CronJobSpec.model_validate(payload)
    await mgr.create_or_replace_job(created)
    return created


@router.put("/jobs/{job_id}", response_model=CronJobSpec)
async def replace_job(
    job_id: str,
    spec: CronJobSpec,
    mgr: CronManager = Depends(get_cron_manager),
):
    if spec.id != job_id:
        raise HTTPException(status_code=400, detail="job_id mismatch")
    normalized = _normalize_spec_for_save(spec)
    await mgr.create_or_replace_job(normalized)
    return normalized


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    ok = await mgr.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="job not found")
    return {"deleted": True}


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str, mgr: CronManager = Depends(get_cron_manager)):
    try:
        await mgr.pause_job(job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"paused": True}


@router.post("/jobs/{job_id}/resume")
async def resume_job(
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    try:
        await mgr.resume_job(job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"resumed": True}


@router.post("/jobs/{job_id}/run")
async def run_job(job_id: str, mgr: CronManager = Depends(get_cron_manager)):
    try:
        await mgr.run_job(job_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="job not found") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"started": True}


@router.get("/jobs/{job_id}/state")
async def get_job_state(
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    job = await mgr.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return mgr.get_state(job_id).model_dump(mode="json")
