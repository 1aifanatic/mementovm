import logging
import time

from sqlalchemy import select

from backend.app.config import get_settings
from backend.app.db import SessionLocal
from backend.app.models import MonitoringJob


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mementovm.worker")


def tick() -> None:
    with SessionLocal() as db:
        pending = db.scalars(
            select(MonitoringJob).where(MonitoringJob.status == "PENDING").limit(10)
        ).all()
        logger.info("worker heartbeat: pending_jobs=%s", len(pending))


if __name__ == "__main__":
    logger.info("MementoVM worker started in %s", get_settings().app_env)
    while True:
        tick()
        time.sleep(15)

