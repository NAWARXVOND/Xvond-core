import logging
import signal
import threading
import time
import uuid

from redis.exceptions import RedisError

from backend.app.api.whatsapp_webhook import (
    process_webhook_payload,
)
from backend.app.modules.channels.whatsapp_queue import (
    whatsapp_job_queue,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("xvond.whatsapp.worker")
running = True
WORKER_LEASE_SECONDS = 30
WORKER_HEARTBEAT_SECONDS = 10


def stop_worker(_signum, _frame):
    global running
    running = False


def _lease_heartbeat(owner: str, stop_event: threading.Event, lost_event: threading.Event):
    while not stop_event.wait(WORKER_HEARTBEAT_SECONDS):
        try:
            if not whatsapp_job_queue.refresh_worker_lock(owner, WORKER_LEASE_SECONDS):
                logger.error("WhatsApp worker lease was lost")
                lost_event.set()
                return
        except RedisError:
            logger.exception("WhatsApp worker lease heartbeat failed")
            lost_event.set()
            return


def main():
    global running
    if not whatsapp_job_queue.enabled:
        raise RuntimeError(
            "REDIS_URL is required for the WhatsApp worker"
        )

    signal.signal(signal.SIGTERM, stop_worker)
    signal.signal(signal.SIGINT, stop_worker)

    owner = str(uuid.uuid4())
    try:
        acquired = whatsapp_job_queue.acquire_worker_lock(
            owner,
            WORKER_LEASE_SECONDS,
        )
    except RedisError as exc:
        raise RuntimeError("Could not acquire WhatsApp worker lease") from exc
    if not acquired:
        raise RuntimeError(
            "Another WhatsApp worker is already active; refusing unsafe concurrent recovery"
        )

    stop_heartbeat = threading.Event()
    lost_lease = threading.Event()
    heartbeat = threading.Thread(
        target=_lease_heartbeat,
        args=(owner, stop_heartbeat, lost_lease),
        name="whatsapp-worker-lease",
        daemon=True,
    )
    heartbeat.start()

    try:
        # Recovery is safe only while this process owns the singleton lease.
        recovered = whatsapp_job_queue.recover_interrupted()
        logger.info(
            "WhatsApp worker started; recovered=%s",
            recovered,
        )

        while running and not lost_lease.is_set():
            try:
                reserved = whatsapp_job_queue.reserve(timeout=5)
            except RedisError:
                logger.exception("Redis unavailable")
                time.sleep(2)
                continue

            if reserved is None:
                continue

            raw, job = reserved

            try:
                process_webhook_payload(
                    raw_body=job["body"].encode("utf-8"),
                    signature=job["signature"],
                )
            except Exception as exc:
                try:
                    status = whatsapp_job_queue.retry_or_dead_letter(
                        raw=raw,
                        job=job,
                        error=exc,
                    )
                except RedisError:
                    logger.exception(
                        "WhatsApp job failed and retry transition could not be persisted; id=%s",
                        job.get("id"),
                    )
                    lost_lease.set()
                    break
                logger.exception(
                    "WhatsApp job failed; id=%s status=%s",
                    job.get("id"),
                    status,
                )
            else:
                try:
                    whatsapp_job_queue.acknowledge(raw)
                except RedisError:
                    # The database/webhook path already committed. Leave the job
                    # recoverable; inbound event deduplication makes the replay safe.
                    logger.exception(
                        "WhatsApp job completed but acknowledgement failed; id=%s",
                        job.get("id"),
                    )
                    lost_lease.set()
                    break
                logger.info(
                    "WhatsApp job completed; id=%s",
                    job.get("id"),
                )
    finally:
        stop_heartbeat.set()
        heartbeat.join(timeout=2)
        try:
            whatsapp_job_queue.release_worker_lock(owner)
        except RedisError:
            logger.exception("Could not release WhatsApp worker lease")
        logger.info("WhatsApp worker stopped")


if __name__ == "__main__":
    main()
