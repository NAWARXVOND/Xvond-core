import json
import time
import uuid
from datetime import datetime, timezone

from redis import Redis
from redis.exceptions import RedisError

from backend.app.core.config.settings import settings


class WhatsAppJobQueue:
    queue_key = "xvond:whatsapp:jobs"
    processing_key = "xvond:whatsapp:processing"
    dead_key = "xvond:whatsapp:dead"
    retry_key = "xvond:whatsapp:retry"
    retry_delays = (5, 30, 120, 600)

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
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
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

    def promote_due(self, now: float | None = None, limit: int = 100) -> int:
        if self.client is None:
            return 0

        script = """
        local items = redis.call(
            'ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1],
            'LIMIT', 0, ARGV[2]
        )
        for _, item in ipairs(items) do
            redis.call('ZREM', KEYS[1], item)
            redis.call('LPUSH', KEYS[2], item)
        end
        return #items
        """
        return int(
            self.client.eval(
                script,
                2,
                self.retry_key,
                self.queue_key,
                now if now is not None else time.time(),
                max(1, min(int(limit), 1000)),
            )
        )

    def reserve(self, timeout: int = 5):
        if self.client is None:
            return None

        self.promote_due()

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

    def stats(self) -> dict:
        if self.client is None:
            return {
                "configured": False,
                "queued": 0,
                "processing": 0,
                "retrying": 0,
                "dead": 0,
            }

        return {
            "configured": True,
            "queued": int(
                self.client.llen(self.queue_key)
            ),
            "processing": int(
                self.client.llen(self.processing_key)
            ),
            "retrying": int(
                self.client.zcard(self.retry_key)
            ),
            "dead": int(
                self.client.llen(self.dead_key)
            ),
        }

    def dead_jobs(self, limit: int = 50) -> list[dict]:
        if self.client is None:
            return []

        safe_limit = max(1, min(int(limit), 200))
        items = self.client.lrange(
            self.dead_key,
            0,
            safe_limit - 1,
        )
        result = []

        for raw in items:
            try:
                job = json.loads(raw)
            except (TypeError, ValueError):
                result.append({
                    "id": None,
                    "attempts": None,
                    "last_error": "Invalid dead-letter payload",
                })
                continue

            # Never expose message bodies or webhook signatures.
            result.append({
                "id": job.get("id"),
                "attempts": job.get("attempts"),
                "enqueued_at": job.get("enqueued_at"),
                "last_failed_at": job.get("last_failed_at"),
                "last_error": job.get("last_error"),
            })

        return result

    def requeue_dead(self, limit: int = 100) -> int:
        if self.client is None:
            return 0

        safe_limit = max(1, min(int(limit), 500))
        requeued = 0

        for _ in range(safe_limit):
            raw = self.client.rpop(self.dead_key)
            if raw is None:
                break

            try:
                job = json.loads(raw)
            except (TypeError, ValueError):
                self.client.rpush(self.dead_key, raw)
                break

            job["attempts"] = 0
            job.pop("last_error", None)
            job.pop("last_failed_at", None)
            self.client.lpush(
                self.queue_key,
                json.dumps(job),
            )
            requeued += 1

        return requeued

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
        job["last_failed_at"] = datetime.now(timezone.utc).isoformat()
        encoded = json.dumps(job)

        if job["attempts"] >= max_attempts:
            self.client.lpush(
                self.dead_key,
                encoded,
            )
            return "dead"

        delay_index = min(
            job["attempts"] - 1,
            len(self.retry_delays) - 1,
        )
        delay_seconds = self.retry_delays[delay_index]
        job["retry_after_seconds"] = delay_seconds
        encoded = json.dumps(job)

        self.client.zadd(
            self.retry_key,
            {
                encoded: time.time() + delay_seconds,
            },
        )
        return "retry"


whatsapp_job_queue = WhatsAppJobQueue()
