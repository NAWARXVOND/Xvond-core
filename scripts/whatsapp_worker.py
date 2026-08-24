import logging
import signal
import time

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


def stop_worker(_signum, _frame):
    global running
    running = False


def main():
    if not whatsapp_job_queue.enabled:
        raise RuntimeError(
            "REDIS_URL is required for the WhatsApp worker"
        )

    signal.signal(signal.SIGTERM, stop_worker)
    signal.signal(signal.SIGINT, stop_worker)

    recovered = whatsapp_job_queue.recover_interrupted()
    logger.info(
        "WhatsApp worker started; recovered=%s",
        recovered,
    )

    while running:
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
            status = whatsapp_job_queue.retry_or_dead_letter(
                raw=raw,
                job=job,
                error=exc,
            )
            logger.exception(
                "WhatsApp job failed; id=%s status=%s",
                job.get("id"),
                status,
            )
        else:
            whatsapp_job_queue.acknowledge(raw)
            logger.info(
                "WhatsApp job completed; id=%s",
                job.get("id"),
            )

    logger.info("WhatsApp worker stopped")


if __name__ == "__main__":
    main()
