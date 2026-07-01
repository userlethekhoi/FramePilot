from collections.abc import Callable
from typing import Any

from loguru import logger
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from app.core.exceptions import JobError


class WorkerSignals(QObject):
    """Defines the signals available from a running job worker.

    Supported signals are:
    - started: job_id (str)
    - progress: job_id (str), step_type (str), percentage (float)
    - completed: job_id (str), results (dict)
    - failed: job_id (str), error_msg (str)
    """

    started = Signal(str)
    progress = Signal(str, str, float)
    completed = Signal(str, dict)
    failed = Signal(str, str)


class JobWorker(QRunnable):
    """Background task runner that executes a workload in a worker thread and emits progress signals."""

    def __init__(
        self,
        job_id: str,
        workload_fn: Callable[[Callable[[str, float], None]], dict[str, Any]],
    ) -> None:
        super().__init__()
        self.job_id = job_id
        self.workload_fn = workload_fn
        self.signals = WorkerSignals()
        self.is_cancelled = False

    def cancel(self) -> None:
        """Flags the worker to cancel execution if supported by the workload."""
        self.is_cancelled = True

    @Slot()
    def run(self) -> None:
        """Executes the task and routes signals back to the main thread."""
        logger.info("Starting background execution for job: {}", self.job_id)
        self.signals.started.emit(self.job_id)

        def report_progress(step_type: str, percent: float) -> None:
            if self.is_cancelled:
                raise JobError("Job execution cancelled by user request.")
            self.signals.progress.emit(self.job_id, step_type, percent)

        try:
            # Execute workload passing progress callback
            results = self.workload_fn(report_progress)

            if self.is_cancelled:
                logger.info("Job {} was cancelled during execution.", self.job_id)
                self.signals.failed.emit(self.job_id, "Job cancelled by user.")
            else:
                logger.info("Job {} completed successfully.", self.job_id)
                self.signals.completed.emit(self.job_id, results)

        except Exception as e:
            error_msg = str(e)
            logger.error("Job {} failed with error: {}", self.job_id, error_msg)
            self.signals.failed.emit(self.job_id, error_msg)


class JobQueueManager:
    """Manages scheduling and running media tasks in a thread-safe QThreadPool queue."""

    def __init__(self, max_threads: int = 4) -> None:
        self._thread_pool = QThreadPool.globalInstance()
        self._thread_pool.setMaxThreadCount(max_threads)
        self._active_workers: dict[str, JobWorker] = {}
        logger.info("JobQueueManager initialized with pool size limit: {}", max_threads)

    def submit(
        self,
        job_id: str,
        workload_fn: Callable[[Callable[[str, float], None]], dict[str, Any]],
        on_started: Callable[[str], None] | None = None,
        on_progress: Callable[[str, str, float], None] | None = None,
        on_completed: Callable[[str, dict[str, Any]], None] | None = None,
        on_failed: Callable[[str, str], None] | None = None,
    ) -> None:
        """Enqueues a new background task for execution."""
        worker = JobWorker(job_id, workload_fn)

        # Wire up listeners to QSignals
        if on_started:
            worker.signals.started.connect(on_started)
        if on_progress:
            worker.signals.progress.connect(on_progress)
        if on_completed:
            worker.signals.completed.connect(on_completed)
        if on_failed:
            worker.signals.failed.connect(on_failed)

        # Always clean up active worker reference upon termination
        def cleanup_worker(*args: Any) -> None:
            self._active_workers.pop(job_id, None)

        worker.signals.completed.connect(cleanup_worker)
        worker.signals.failed.connect(cleanup_worker)

        # Register and start
        self._active_workers[job_id] = worker
        self._thread_pool.start(worker)
        logger.debug("Job {} submitted and thread pools started.", job_id)

    def cancel(self, job_id: str) -> bool:
        """Cancels a currently active running job."""
        worker = self._active_workers.get(job_id)
        if worker:
            worker.cancel()
            logger.info("Sent cancellation request to job: {}", job_id)
            return True
        logger.warning("Attempted to cancel job {} but it was not running.", job_id)
        return False

    def is_running(self, job_id: str) -> bool:
        """Returns True if the job is actively running in the thread pool."""
        return job_id in self._active_workers

    @property
    def max_thread_count(self) -> int:
        return self._thread_pool.maxThreadCount()

    @max_thread_count.setter
    def max_thread_count(self, count: int) -> None:
        self._thread_pool.setMaxThreadCount(count)
