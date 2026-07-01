import time
from typing import Any

from PySide6.QtCore import QCoreApplication

from app.application.services.job_queue import JobQueueManager


def test_job_queue_success(qtbot: Any) -> None:
    """Verifies that submitting a valid workload executes successfully in the thread pool."""
    # Ensure QCoreApplication exists (pytest-qt handles this but let's be safe)
    QCoreApplication.instance() or QCoreApplication([])

    manager = JobQueueManager(max_threads=2)
    assert manager.max_thread_count == 2

    job_id = "job_test_123"
    events = []

    def workload(progress_fn: Any) -> dict[str, Any]:
        progress_fn("step_1", 25.0)
        progress_fn("step_2", 75.0)
        return {"output_file": "video.mp4"}

    def on_started(jid: str) -> None:
        events.append(("started", jid))

    def on_progress(jid: str, step: str, progress: float) -> None:
        events.append(("progress", jid, step, progress))

    def on_completed(jid: str, results: dict[str, Any]) -> None:
        events.append(("completed", jid, results))

    def on_failed(jid: str, err: str) -> None:
        events.append(("failed", jid, err))

    # Submit job to thread pool
    manager.submit(
        job_id,
        workload,
        on_started=on_started,
        on_progress=on_progress,
        on_completed=on_completed,
        on_failed=on_failed,
    )

    # Wait for signals using qtbot or simple spin loop routing Qt event processing
    # Timeout after 3 seconds
    qtbot.waitUntil(
        lambda: any(e[0] == "completed" for e in events) or any(e[0] == "failed" for e in events),
        timeout=3000,
    )

    assert ("started", job_id) in events
    assert ("progress", job_id, "step_1", 25.0) in events
    assert ("progress", job_id, "step_2", 75.0) in events
    assert ("completed", job_id, {"output_file": "video.mp4"}) in events
    assert not any(e[0] == "failed" for e in events)


def test_job_queue_failure(qtbot: Any) -> None:
    """Verifies that exceptions thrown inside workloads trigger the failed signal callback."""
    manager = JobQueueManager(max_threads=1)
    job_id = "job_test_fail"
    events = []

    def faulty_workload(progress_fn: Any) -> dict[str, Any]:
        raise ValueError("Something went wrong during rendering.")

    def on_failed(jid: str, err: str) -> None:
        events.append(("failed", jid, err))

    manager.submit(
        job_id,
        faulty_workload,
        on_failed=on_failed,
    )

    qtbot.waitUntil(lambda: len(events) > 0, timeout=3000)

    assert len(events) == 1
    assert events[0][0] == "failed"
    assert events[0][1] == job_id
    assert "Something went wrong" in events[0][2]


def test_job_queue_cancel(qtbot: Any) -> None:
    """Verifies that running jobs can be cancelled mid-execution."""
    manager = JobQueueManager(max_threads=1)
    job_id = "job_test_cancel"
    events = []

    def slow_workload(progress_fn: Any) -> dict[str, Any]:
        # Perform steps checking loop
        for i in range(10):
            time.sleep(0.1)
            progress_fn(f"loop_{i}", float(i * 10))
        return {}

    def on_failed(jid: str, err: str) -> None:
        events.append(("failed", jid, err))

    manager.submit(job_id, slow_workload, on_failed=on_failed)

    # Cancel immediately
    assert manager.is_running(job_id) is True
    cancelled = manager.cancel(job_id)
    assert cancelled is True

    qtbot.waitUntil(lambda: len(events) > 0, timeout=3000)

    assert len(events) == 1
    assert events[0][0] == "failed"
    assert "cancelled" in events[0][2]
    assert manager.is_running(job_id) is False
