import json
import uuid
from datetime import datetime

from redis import Redis
from redis.exceptions import RedisError

from backend.app.core.config.settings import settings


class WhatsAppJobQueue:
    queue_key = "xvond:whatsapp:jobs"
    processing_key = "xvond:whatsapp:processing"
    dead_key = "xvond:whatsapp:dead"

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self.client = (
            Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=5,
                health_check_interval=30,
            )
            if self.redis_url
            else None
        )

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def enqueue(
        self,
        body: str,
        signature: str,
    ) -> str:
        if self.client is None:
            raise RuntimeError("WhatsApp queue is not configured")

        job_id = str(uuid.uuid4())
        job = {
            "id": job_id,
            "body": body,
            "signature": signature,
            "attempts": 0,
            "enqueued_at": datetime.utcnow().isoformat(),
        }
        self.client.lpush(
            self.queue_key,
            json.dumps(job),
        )
        return job_id

    def recover_interrupted(self) -> int:
        if self.client is None:
            return 0

        recovered = 0
        while True:
            item = self.client.rpoplpush(
                self.processing_key,
                self.queue_key,
            )
            if item is None:
                return recovered
            recovered += 1

    def reserve(self, timeout: int = 5):
        if self.client is None:
            return None

        raw = self.client.brpoplpush(
            self.queue_key,
            self.processing_key,
            timeout=timeout,
        )
        if raw is None:
            return None

        return raw, json.loads(raw)

    def acknowledge(self, raw: str):
        if self.client is not None:
            self.client.lrem(
                self.processing_key,
                1,
                raw,
            )

    def retry_or_dead_letter(
        self,
        raw: str,
        job: dict,
        error: Exception,
        max_attempts: int = 5,
    ) -> str:
        if self.client is None:
            return "unavailable"

        self.client.lrem(
            self.processing_key,
            1,
            raw,
        )

        job["attempts"] = int(job.get("attempts", 0)) + 1
        job["last_error"] = str(error)[:1000]
        job["last_failed_at"] = datetime.utcnow().isoformat()
        encoded = json.dumps(job)

        if job["attempts"] >= max_attempts:
            self.client.lpush(
                self.dead_key,
                encoded,
            )
            return "dead"

        self.client.lpush(
            self.queue_key,
            encoded,
        )
        return "retry"


whatsapp_job_queue = WhatsAppJobQueue()
