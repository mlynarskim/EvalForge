from __future__ import annotations

import asyncio
import uuid

from app.services.experiment_service import experiment_service


def run_experiment(experiment_id: str) -> None:
    asyncio.run(experiment_service.execute(uuid.UUID(experiment_id)))
