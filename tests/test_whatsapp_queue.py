import json

from backend.app.modules.channels.whatsapp_queue import (
    WhatsAppJobQueue,
)


class FakeRedis:
    def __init__(self):
        self.data = {}
        self.sorted = {}

    def lpush(self, key, value):
        self.data.setdefault(key, []).insert(0, value)

    def rpush(self, key, value):
        self.data.setdefault(key, []).append(value)

    def rpop(self, key):
        items = self.data.setdefault(key, [])
        return items.pop() if items else None

    def llen(self, key):
        return len(self.data.setdefault(key, []))

    def lrange(self, key, start, end):
        items = self.data.setdefault(key, [])
        return items[start:end + 1]

    def brpoplpush(self, source, destination, timeout=0):
        items = self.data.setdefault(source, [])
        if not items:
            return None
        value = items.pop()
        self.data.setdefault(destination, []).insert(0, value)
        return value

    def rpoplpush(self, source, destination):
        return self.brpoplpush(source, destination)

    def zadd(self, key, mapping):
        self.sorted.setdefault(key, {}).update(mapping)

    def zcard(self, key):
        return len(self.sorted.setdefault(key, {}))

    def eval(self, _script, _numkeys, retry_key, queue_key, now, limit):
        due = [
            (raw, score)
            for raw, score
            in self.sorted.setdefault(retry_key, {}).items()
            if score <= float(now)
        ]
        due.sort(key=lambda item: item[1])
        selected = due[:int(limit)]
        for raw, _score in selected:
            del self.sorted[retry_key][raw]
            self.lpush(queue_key, raw)
        return len(selected)

    def lrem(self, key, count, value):
        items = self.data.setdefault(key, [])
        removed = 0
        while value in items and removed < count:
            items.remove(value)
            removed += 1
        return removed


def make_queue():
    queue = WhatsAppJobQueue(redis_url="")
    queue.client = FakeRedis()
    return queue


def test_job_is_reserved_and_acknowledged():
    queue = make_queue()
    job_id = queue.enqueue(
        body='{"object":"whatsapp_business_account"}',
        signature="sha256=test",
    )

    raw, job = queue.reserve(timeout=1)

    assert job["id"] == job_id
    assert job["attempts"] == 0
    assert len(queue.client.data[queue.processing_key]) == 1

    queue.acknowledge(raw)

    assert queue.client.data[queue.processing_key] == []


def test_failed_job_retries_then_moves_to_dead_letter():
    queue = make_queue()
    queue.enqueue(body="{}", signature="sha256=test")
    raw, job = queue.reserve(timeout=1)

    status = queue.retry_or_dead_letter(
        raw=raw,
        job=job,
        error=RuntimeError("temporary"),
        max_attempts=2,
    )

    assert status == "retry"
    assert queue.client.zcard(queue.retry_key) == 1
    assert queue.reserve(timeout=1) is None

    assert queue.promote_due(now=10**12) == 1
    raw, job = queue.reserve(timeout=1)
    status = queue.retry_or_dead_letter(
        raw=raw,
        job=job,
        error=RuntimeError("permanent"),
        max_attempts=2,
    )

    assert status == "dead"
    dead = json.loads(
        queue.client.data[queue.dead_key][0]
    )
    assert dead["attempts"] == 2
    assert dead["last_error"] == "permanent"


def test_interrupted_jobs_are_recovered_on_worker_start():
    queue = make_queue()
    queue.enqueue(body="{}", signature="sha256=test")
    queue.reserve(timeout=1)

    assert queue.recover_interrupted() == 1
    assert queue.client.data[queue.processing_key] == []
    assert len(queue.client.data[queue.queue_key]) == 1



def test_stats_report_queue_depths():
    queue = make_queue()
    queue.enqueue(body="{}", signature="secret")
    queue.client.lpush(
        queue.dead_key,
        json.dumps({
            "id": "dead-1",
            "body": "private customer message",
            "signature": "private signature",
            "attempts": 5,
            "last_error": "delivery failed",
        }),
    )

    assert queue.stats() == {
        "configured": True,
        "queued": 1,
        "processing": 0,
        "retrying": 0,
        "dead": 1,
    }


def test_dead_job_view_never_exposes_body_or_signature():
    queue = make_queue()
    queue.client.lpush(
        queue.dead_key,
        json.dumps({
            "id": "dead-1",
            "body": "private customer message",
            "signature": "private signature",
            "attempts": 5,
            "last_error": "delivery failed",
        }),
    )

    item = queue.dead_jobs()[0]

    assert item["id"] == "dead-1"
    assert item["last_error"] == "delivery failed"
    assert "body" not in item
    assert "signature" not in item


def test_admin_retry_resets_attempts_and_requeues():
    queue = make_queue()
    queue.client.lpush(
        queue.dead_key,
        json.dumps({
            "id": "dead-1",
            "body": "{}",
            "signature": "sha256=test",
            "attempts": 5,
            "last_error": "delivery failed",
            "last_failed_at": "2026-08-24T12:00:00+00:00",
        }),
    )

    assert queue.requeue_dead(limit=1) == 1

    queued = json.loads(
        queue.client.data[queue.queue_key][0]
    )
    assert queued["attempts"] == 0
    assert "last_error" not in queued
    assert queue.client.data[queue.dead_key] == []


def test_retry_delay_increases_with_attempts():
    queue = make_queue()
    queue.enqueue(body="{}", signature="sha256=test")
    raw, job = queue.reserve(timeout=1)

    queue.retry_or_dead_letter(
        raw=raw,
        job=job,
        error=RuntimeError("temporary"),
    )
    scheduled = next(iter(queue.client.sorted[queue.retry_key]))
    first = json.loads(scheduled)
    assert first["attempts"] == 1
    assert first["retry_after_seconds"] == 5

    queue.promote_due(now=10**12)
    raw, job = queue.reserve(timeout=1)
    queue.retry_or_dead_letter(
        raw=raw,
        job=job,
        error=RuntimeError("temporary again"),
    )
    scheduled = next(iter(queue.client.sorted[queue.retry_key]))
    second = json.loads(scheduled)
    assert second["attempts"] == 2
    assert second["retry_after_seconds"] == 30


def test_blocking_reserve_timeout_has_socket_margin():
    source = (
        __import__(
            "pathlib"
        ).Path(
            "backend/app/modules/channels/whatsapp_queue.py"
        ).read_text(encoding="utf-8")
    )
    assert "socket_timeout=15" in source
    assert "def reserve(self, timeout: int = 5)" in source
