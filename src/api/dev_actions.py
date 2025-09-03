"""
Developer Actions API
Job execution and management endpoints
"""

import sys
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel

from src.adapters.web.fastapi_adapter import APIRouter, HTTPException, StreamingResponse

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.dev.jobs import job_runner

router = APIRouter(prefix="/api/dev", tags=["dev"])


class ActionRequest(BaseModel):
    action: str
    args: Optional[Dict] = {}


ACTION_MAP = {
    "demo": ["python", "run_paper_session.py", "5"],
    "qa": ["python", "tools/qa_proof.py"],
    "readiness": ["python", "tools/live_readiness.py"],
    "arbitrage": ["python", "tools/run_tr_arbitrage_session.py", "30"],
    "campaign": ["python", "tools/run_paper_campaign.py", "--days", "3"],
    "fault": ["python", "tools/fault_injector.py"],
    "consistency": ["python", "tools/consistency_check.py"],
    "shadow": ["python", "tools/shadow_report.py"],
    "grid-sweep": ["python", "tools/grid_sweeper.py"],
    "pilot-plan": ["python", "tools/pilot_plan.py"],
    "adapt": ["python", "tools/apply_adaptive_params.py"],
    "orchestrate": [
        "python",
        "tools/session_orchestrator.py",
        "--grid-mins",
        "60",
        "--arb-mins",
        "30",
    ],
}
ACTION_FAMILIES = {
    "demo": "trading",
    "arbitrage": "trading",
    "campaign": "trading",
    "qa": "testing",
    "readiness": "testing",
    "fault": "testing",
    "consistency": "analysis",
    "shadow": "analysis",
    "grid-sweep": "optimization",
    "adapt": "optimization",
}


@router.post("/actions")
async def execute_action(request: ActionRequest):
    """Execute a predefined action"""
    if request.action not in ACTION_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")
    cmd = ACTION_MAP[request.action].copy()
    if request.args:
        for key, value in request.args.items():
            cmd.extend([f"--{key}", str(value)])
    family = ACTION_FAMILIES.get(request.action)
    try:
        job_id = await job_runner.spawn_job(cmd, family=family)
        return {"job_id": job_id, "action": request.action, "family": family, "status": "started"}
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start job: {e}")


@router.get("/jobs")
async def list_jobs():
    """List all jobs"""
    jobs = await job_runner.list_jobs()
    return {"items": [job.to_dict() for job in jobs], "total": len(jobs)}


@router.get("/jobs/{job_id}")
async def get_job_details(job_id: str):
    """Get job details"""
    job = await job_runner.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job.to_dict()


@router.get("/logs/stream")
async def stream_job_logs(job_id: str):
    """Stream job logs via SSE"""

    async def generate():
        async for line in job_runner.get_job_output_stream(job_id):
            yield line

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/jobs/{job_id}/kill")
async def kill_job(job_id: str):
    """Kill a running job"""
    success = await job_runner.kill_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found or not running")
    return {"status": "killed", "job_id": job_id}
