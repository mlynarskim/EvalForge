from __future__ import annotations

import uuid

from redis import Redis
from rq import Queue

from app.config import settings


class QueueUnavailableError(RuntimeError):
    pass


def enqueue_experiment(experiment_id: uuid.UUID) -> str:
    try:
        connection = Redis.from_url(settings.redis_url)
        connection.ping()
        job = Queue("experiments", connection=connection).enqueue(
            "app.workers.tasks.run_experiment",
            str(experiment_id),
            job_timeout="24h",
            result_ttl=86400,
        )
        return job.id
    except Exception as exc:
        raise QueueUnavailableError("The experiment queue is unavailable") from exc
