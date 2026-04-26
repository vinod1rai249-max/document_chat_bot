from __future__ import annotations

from dataclasses import asdict, dataclass, field
from threading import Lock
from uuid import uuid4


@dataclass
class IndexJob:
    id: str
    status: str = "queued"
    stage: str = "queued"
    progress: float = 0.0
    message: str = "Queued"
    documents_indexed: int = 0
    total_files: int = 0
    error: str | None = None
    filenames: list[str] = field(default_factory=list)


class IndexJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, IndexJob] = {}
        self._lock = Lock()

    def create_job(self, filenames: list[str]) -> IndexJob:
        job = IndexJob(
            id=uuid4().hex,
            total_files=len(filenames),
            filenames=filenames,
            message="Upload received",
        )
        with self._lock:
            self._jobs[job.id] = job
        return job

    def update_job(self, job_id: str, **fields) -> IndexJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            for key, value in fields.items():
                setattr(job, key, value)
            return job

    def get_job(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return asdict(job)


job_store = IndexJobStore()
