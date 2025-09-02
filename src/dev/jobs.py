"""
Job Runner System
Manages background jobs with state tracking and output capture
"""

import asyncio
import logging
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class JobState(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAIL = "FAIL"


@dataclass
class Job:
    id: str
    cmd: List[str]
    state: JobState = JobState.PENDING
    pid: Optional[int] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    rc: Optional[int] = None
    stdout_tail: List[str] = field(default_factory=list)
    stderr_tail: List[str] = field(default_factory=list)
    family: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "cmd": " ".join(self.cmd),
            "state": self.state.value,
            "pid": self.pid,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "rc": self.rc,
            "stdout_tail": self.stdout_tail[-50:],  # Last 50 lines
            "stderr_tail": self.stderr_tail[-50:],
            "family": self.family,
        }


class JobRunner:
    """Manages job execution and state"""

    def __init__(self):
        self.job_store: Dict[str, Job] = {}
        self.lock = asyncio.Lock()
        self.family_locks: Dict[str, str] = {}  # family -> current job_id
        self.processes: Dict[str, subprocess.Popen] = {}
        self.tail_size = 200  # Keep last 200 lines

    async def spawn_job(self, cmd: List[str], family: Optional[str] = None) -> str:
        """Spawn a new job"""
        async with self.lock:
            # Check family rate limit
            if family and family in self.family_locks:
                current_job_id = self.family_locks[family]
                current_job = self.job_store.get(current_job_id)
                if current_job and current_job.state == JobState.RUNNING:
                    raise ValueError(
                        f"Job family '{family}' already has a running job: {current_job_id}"
                    )

            # Create job
            job_id = str(uuid.uuid4())[:8]
            job = Job(id=job_id, cmd=cmd, family=family, state=JobState.PENDING)

            self.job_store[job_id] = job

            if family:
                self.family_locks[family] = job_id

        # Start the job asynchronously
        asyncio.create_task(self._run_job(job_id))

        return job_id

    async def _run_job(self, job_id: str):
        """Execute job and track output"""
        job = self.job_store[job_id]

        try:
            # Update state to RUNNING
            async with self.lock:
                job.state = JobState.RUNNING
                job.started_at = datetime.now()

            # Start process
            process = subprocess.Popen(
                job.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=Path(__file__).parent.parent.parent,  # Run from project root
            )

            job.pid = process.pid
            self.processes[job_id] = process

            # Read output in real-time
            stdout_lines = []
            stderr_lines = []

            # Poll process
            while process.poll() is None:
                # Read stdout
                if process.stdout:
                    line = process.stdout.readline()
                    if line:
                        stdout_lines.append(line.rstrip())
                        if len(stdout_lines) > self.tail_size:
                            stdout_lines = stdout_lines[-self.tail_size :]
                        job.stdout_tail = stdout_lines[-self.tail_size :]

                # Read stderr
                if process.stderr:
                    line = process.stderr.readline()
                    if line:
                        stderr_lines.append(line.rstrip())
                        if len(stderr_lines) > self.tail_size:
                            stderr_lines = stderr_lines[-self.tail_size :]
                        job.stderr_tail = stderr_lines[-self.tail_size :]

                await asyncio.sleep(0.1)

            # Get return code
            job.rc = process.returncode

            # Final read of any remaining output
            if process.stdout:
                remaining = process.stdout.read()
                if remaining:
                    stdout_lines.extend(remaining.rstrip().split("\n"))
                    job.stdout_tail = stdout_lines[-self.tail_size :]

            if process.stderr:
                remaining = process.stderr.read()
                if remaining:
                    stderr_lines.extend(remaining.rstrip().split("\n"))
                    job.stderr_tail = stderr_lines[-self.tail_size :]

            # Update state
            async with self.lock:
                job.state = JobState.DONE if job.rc == 0 else JobState.FAIL
                job.ended_at = datetime.now()

                # Release family lock
                if job.family and self.family_locks.get(job.family) == job_id:
                    del self.family_locks[job.family]

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            async with self.lock:
                job.state = JobState.FAIL
                job.ended_at = datetime.now()
                job.stderr_tail.append(f"Error: {e!s}")

                # Release family lock
                if job.family and self.family_locks.get(job.family) == job_id:
                    del self.family_locks[job.family]

        finally:
            # Clean up process reference
            if job_id in self.processes:
                del self.processes[job_id]

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        async with self.lock:
            return self.job_store.get(job_id)

    async def list_jobs(self) -> List[Job]:
        """List all jobs"""
        async with self.lock:
            return list(self.job_store.values())

    async def kill_job(self, job_id: str) -> bool:
        """Kill a running job"""
        async with self.lock:
            job = self.job_store.get(job_id)
            if not job:
                return False

            if job.state != JobState.RUNNING:
                return False

            process = self.processes.get(job_id)
            if process:
                try:
                    process.terminate()
                    # Give it time to terminate gracefully
                    await asyncio.sleep(2)
                    if process.poll() is None:
                        process.kill()

                    job.state = JobState.FAIL
                    job.ended_at = datetime.now()
                    job.rc = -1
                    job.stderr_tail.append("Job terminated by user")

                    # Release family lock
                    if job.family and self.family_locks.get(job.family) == job_id:
                        del self.family_locks[job.family]

                    return True
                except Exception as e:
                    logger.error(f"Failed to kill job {job_id}: {e}")
                    return False

        return False

    async def get_job_output_stream(self, job_id: str):
        """Stream job output for SSE"""
        job = await self.get_job(job_id)
        if not job:
            yield f"data: Job {job_id} not found\n\n"
            return

        last_stdout_len = 0
        last_stderr_len = 0

        while job.state == JobState.RUNNING:
            # Send new stdout lines
            if len(job.stdout_tail) > last_stdout_len:
                for line in job.stdout_tail[last_stdout_len:]:
                    yield f"data: [STDOUT] {line}\n\n"
                last_stdout_len = len(job.stdout_tail)

            # Send new stderr lines
            if len(job.stderr_tail) > last_stderr_len:
                for line in job.stderr_tail[last_stderr_len:]:
                    yield f"data: [STDERR] {line}\n\n"
                last_stderr_len = len(job.stderr_tail)

            await asyncio.sleep(0.5)

            # Refresh job state
            job = await self.get_job(job_id)
            if not job:
                break

        # Send final status
        if job:
            yield f"data: [STATUS] Job completed with state: {job.state.value}, rc: {job.rc}\n\n"


# Global job runner instance
job_runner = JobRunner()
