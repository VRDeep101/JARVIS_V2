# ═════════════════════════════════════════════════════════════
#  Backend/Core/BackgroundTaskManager.py  —  Async Task System
#
#  Kya karta:
#    - Long tasks (>10s) background me bhejata
#    - Status track karta (running/complete/failed)
#    - User ko notify karta complete hone pe
#    - Max 3 simultaneous tasks
#    - Named tasks ("task 1", "image task") support
#
#  Usage:
#    from Backend.Core.BackgroundTaskManager import bg
#
#    task_id = bg.submit(
#        name="image_gen",
#        func=generate_images,
#        args=("sunset",),
#        on_success=lambda r: speak("Images ready, Sir"),
#        on_error=lambda e: speak("Image gen failed"),
#    )
#
#    bg.status(task_id)  → "running" / "done" / "failed"
#    bg.list_active()    → [task1, task2]
#    bg.cancel(task_id)  → terminates
# ═════════════════════════════════════════════════════════════

import threading
import uuid
import time
from enum import Enum
from typing import Callable, Any, Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, Future

from Backend.Utils.Logger import get_logger
from Backend.Core.ErrorHandler import handle_error

log = get_logger("BackgroundTask")

# ── Task Status ───────────────────────────────────────────────
class TaskStatus(Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    DONE      = "done"
    FAILED    = "failed"
    CANCELLED = "cancelled"

# ── Task Object ───────────────────────────────────────────────
class BackgroundTask:
    def __init__(
        self,
        task_id: str,
        name: str,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        on_success: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_progress: Optional[Callable] = None,
    ):
        self.id = task_id
        self.name = name
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}
        self.on_success = on_success
        self.on_error = on_error
        self.on_progress = on_progress
        
        self.status = TaskStatus.PENDING
        self.result: Any = None
        self.error: Optional[Exception] = None
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.future: Optional[Future] = None
    
    @property
    def duration(self) -> float:
        """Seconds elapsed (or 0 if not started)."""
        if self.start_time == 0:
            return 0.0
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time
    
    def is_active(self) -> bool:
        return self.status in (TaskStatus.PENDING, TaskStatus.RUNNING)

# ── Task Manager ──────────────────────────────────────────────
class BackgroundTaskManager:
    """
    Manages long-running tasks in background threads.
    Thread-safe, max 3 concurrent, named tasks supported.
    """
    
    MAX_CONCURRENT = 3
    BACKGROUND_THRESHOLD_SEC = 10  # tasks estimated > this → background
    
    def __init__(self):
        self._tasks: Dict[str, BackgroundTask] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=self.MAX_CONCURRENT,
            thread_name_prefix="JarvisBg"
        )
        self._lock = threading.Lock()
    
    def submit(
        self,
        name: str,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        on_success: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> str:
        """
        Submit a task to run in background.
        Returns task_id (also used as alias key if name is unique).
        """
        with self._lock:
            # Check if task with same name is already active
            for t in self._tasks.values():
                if t.name == name and t.is_active():
                    log.warn(f"Task '{name}' already running, skipping duplicate")
                    return t.id
            
            task_id = str(uuid.uuid4())[:8]
            task = BackgroundTask(
                task_id=task_id,
                name=name,
                func=func,
                args=args,
                kwargs=kwargs,
                on_success=on_success,
                on_error=on_error,
                on_progress=on_progress,
            )
            self._tasks[task_id] = task
        
        task.status = TaskStatus.RUNNING
        task.start_time = time.time()
        task.future = self._executor.submit(self._run_task, task)
        log.info(f"Submitted task '{name}' [{task_id}]")
        return task_id
    
    def _run_task(self, task: BackgroundTask):
        """Internal task runner."""
        try:
            log.action(f"Running: {task.name}")
            result = task.func(*task.args, **task.kwargs)
            task.result = result
            task.status = TaskStatus.DONE
            task.end_time = time.time()
            log.success(f"Task '{task.name}' done in {task.duration:.1f}s")
            
            if task.on_success:
                try:
                    task.on_success(result)
                except Exception as e:
                    log.error(f"on_success callback error: {e}")
        
        except Exception as e:
            task.error = e
            task.status = TaskStatus.FAILED
            task.end_time = time.time()
            log.error(f"Task '{task.name}' failed: {e}")
            
            if task.on_error:
                try:
                    task.on_error(e)
                except Exception as cb_err:
                    log.error(f"on_error callback error: {cb_err}")
    
    # ── Status queries ─────────────────────────────────────────
    def status(self, task_id_or_name: str) -> Optional[TaskStatus]:
        """Get status by ID or name."""
        task = self._resolve(task_id_or_name)
        return task.status if task else None
    
    def result(self, task_id_or_name: str) -> Any:
        """Get task result (None if not done)."""
        task = self._resolve(task_id_or_name)
        return task.result if task and task.status == TaskStatus.DONE else None
    
    def list_active(self) -> List[BackgroundTask]:
        """List tasks still running."""
        with self._lock:
            return [t for t in self._tasks.values() if t.is_active()]
    
    def list_all(self) -> List[BackgroundTask]:
        """List every task (including completed)."""
        with self._lock:
            return list(self._tasks.values())
    
    def list_active_summary(self) -> str:
        """Human-friendly summary of active tasks."""
        active = self.list_active()
        if not active:
            return "No tasks running in background."
        lines = []
        for t in active:
            lines.append(f"  • {t.name} ({t.duration:.0f}s elapsed)")
        return f"Currently running:\n" + "\n".join(lines)
    
    def cancel(self, task_id_or_name: str) -> bool:
        """Attempt to cancel a task."""
        task = self._resolve(task_id_or_name)
        if not task or not task.is_active():
            return False
        
        if task.future and task.future.cancel():
            task.status = TaskStatus.CANCELLED
            task.end_time = time.time()
            log.info(f"Cancelled task '{task.name}'")
            return True
        
        # Can't cancel already-running; just mark it
        log.warn(f"Task '{task.name}' can't be forcibly stopped (already running)")
        return False
    
    def clear_completed(self):
        """Remove done/failed/cancelled tasks from memory."""
        with self._lock:
            active = {
                tid: t for tid, t in self._tasks.items()
                if t.is_active()
            }
            cleared = len(self._tasks) - len(active)
            self._tasks = active
            if cleared:
                log.debug(f"Cleared {cleared} completed tasks")
    
    def _resolve(self, key: str) -> Optional[BackgroundTask]:
        """Find task by ID or name."""
        with self._lock:
            if key in self._tasks:
                return self._tasks[key]
            for t in self._tasks.values():
                if t.name == key:
                    return t
        return None
    
    def shutdown(self, wait: bool = True):
        """Shutdown the executor (called on Jarvis exit)."""
        log.info("Shutting down background task manager")
        self._executor.shutdown(wait=wait)

# ── Singleton ─────────────────────────────────────────────────
bg = BackgroundTaskManager()

# =============================================================
#  Singleton + Main.py compat methods
# =============================================================
task_mgr = BackgroundTaskManager()

def _start_task_compat(self, name: str, func, *args, **kwargs):
    """Main.py compat: start_task(name, func) -> submit."""
    return self.submit(func, *args, name=name, **kwargs)

def _stop_all_compat(self):
    """Main.py compat: stop all tasks."""
    return self.shutdown(wait=False)

# Bind compat methods
BackgroundTaskManager.start_task = _start_task_compat
BackgroundTaskManager.stop_all = _stop_all_compat

# ── Test block ────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n─── BackgroundTaskManager Test ───\n")
    
    def slow_task(duration: int, label: str):
        print(f"  [task {label}] starting, will take {duration}s")
        time.sleep(duration)
        return f"Result from {label}"
    
    def failing_task():
        time.sleep(1)
        raise RuntimeError("intentional failure")
    
    # Submit 3 tasks
    id1 = bg.submit(
        name="slow_1",
        func=slow_task,
        args=(2, "A"),
        on_success=lambda r: print(f"  ✓ Task A done → {r}"),
    )
    id2 = bg.submit(
        name="slow_2",
        func=slow_task,
        args=(3, "B"),
        on_success=lambda r: print(f"  ✓ Task B done → {r}"),
    )
    id3 = bg.submit(
        name="failing",
        func=failing_task,
        on_error=lambda e: print(f"  ✗ failing task errored: {e}"),
    )
    
    print(f"\nSubmitted 3 tasks. Active count: {len(bg.list_active())}")
    print(bg.list_active_summary())
    
    # Wait and check
    time.sleep(4)
    
    print(f"\nAfter 4 seconds:")
    for t in bg.list_all():
        print(f"  {t.name:10} status={t.status.value:10} duration={t.duration:.1f}s")
    
    bg.clear_completed()
    print(f"\nAfter cleanup, remaining: {len(bg.list_all())}")
    
    bg.shutdown()
    print("\n✓ BackgroundTaskManager test complete\n")