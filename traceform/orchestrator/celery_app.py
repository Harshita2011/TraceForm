"""
# §4 Orchestrator — Celery application instance.

Isolated in its own module to prevent circular imports:
  orchestrator.jobs imports celery_app (this module)
  celery_app does NOT import jobs or any app code.

Broker + result backend: Redis (docker-compose redis service) or in-memory for eager dev mode.
"""

import os

from celery import Celery

is_eager = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

broker_url = "memory://" if is_eager else REDIS_URL
backend_url = "cache+memory://" if is_eager else REDIS_URL

celery_app = Celery(
    "traceform",
    broker=broker_url,
    backend=backend_url,
    include=["orchestrator.jobs"],
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Reliability — §4
    task_acks_late=True,             # ACK only after the task completes (prevents lost tasks on worker crash)
    task_reject_on_worker_lost=True, # Re-queue if the worker dies mid-task
    worker_prefetch_multiplier=1,    # One task at a time per worker slot — fair fan-out
    # Dead-letter: exhausted tasks route to a dedicated dead-letter queue
    task_routes={
        "orchestrator.jobs.run_analyst_stage": {"queue": "analyst"},
        "orchestrator.jobs.run_generator_task": {"queue": "generators"},
        "orchestrator.jobs.run_generation_pipeline": {"queue": "pipeline"},
    },
    task_queues_max_priority=10,
    # Retry defaults (overridden per-task where needed)
    task_default_retry_delay=5,   # seconds
    # Result expiry — keep results for 24 h
    result_expires=86400,
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Test / Dev mode — when CELERY_TASK_ALWAYS_EAGER=true, tasks run in-process.
    task_always_eager=is_eager,
    task_eager_propagates=True,
)
