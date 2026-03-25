"""
Task scheduler for managing and executing Agent tasks.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import uuid

from .models import Task, TaskStatus, IntentType

logger = logging.getLogger(__name__)


# Type alias for task handlers
TaskHandler = Callable[[Task], Awaitable[Dict[str, Any]]]


class TaskScheduler:
    """
    Schedule and execute Agent tasks.
    
    Features:
    - Task queue management
    - Priority-based scheduling
    - Retry mechanism
    - Task status tracking
    - Concurrent execution
    """
    
    def __init__(self, max_concurrent: int = 5):
        """
        Initialize the task scheduler.
        
        Args:
            max_concurrent: Maximum number of concurrent tasks
        """
        self.max_concurrent = max_concurrent
        
        # Task storage
        self.tasks: Dict[str, Task] = {}
        self.pending_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        
        # Task handlers
        self.handlers: Dict[IntentType, TaskHandler] = {}
        
        # Running tasks
        self.running_tasks: Dict[str, asyncio.Task] = {}
        
        # Worker state
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
    
    def register_handler(self, intent_type: IntentType, handler: TaskHandler):
        """
        Register a handler for an intent type.
        
        Args:
            intent_type: Intent type to handle
            handler: Async function to handle the task
        """
        self.handlers[intent_type] = handler
        logger.info(f"Registered handler for intent: {intent_type.value}")
    
    async def submit(self, task: Task) -> str:
        """
        Submit a task for execution.
        
        Args:
            task: Task to submit
            
        Returns:
            Task ID
        """
        # Store task
        self.tasks[task.task_id] = task
        
        # Add to queue with priority
        await self.pending_queue.put((-task.priority, task.created_at, task.task_id))
        
        logger.info(f"Submitted task {task.task_id} with priority {task.priority}")
        
        return task.task_id
    
    async def submit_batch(self, tasks: List[Task]) -> List[str]:
        """
        Submit multiple tasks for execution.
        
        Args:
            tasks: List of tasks to submit
            
        Returns:
            List of task IDs
        """
        task_ids = []
        for task in tasks:
            task_id = await self.submit(task)
            task_ids.append(task_id)
        return task_ids
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get a task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task if found, None otherwise
        """
        return self.tasks.get(task_id)
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """
        Get all tasks with a specific status.
        
        Args:
            status: Task status to filter
            
        Returns:
            List of matching tasks
        """
        return [t for t in self.tasks.values() if t.status == status]
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if cancelled, False if not found or already completed
        """
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False
        
        # Cancel running asyncio task if exists
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        
        logger.info(f"Cancelled task {task_id}")
        return True
    
    async def start(self):
        """Start the task scheduler worker."""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        
        logger.info("Task scheduler started")
    
    async def stop(self):
        """Stop the task scheduler."""
        self._running = False
        
        # Cancel all running tasks
        for task_id, atask in self.running_tasks.items():
            atask.cancel()
        
        # Wait for worker to finish
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Task scheduler stopped")
    
    async def _worker_loop(self):
        """Worker loop for processing tasks."""
        while self._running:
            try:
                # Check concurrent limit
                while len(self.running_tasks) >= self.max_concurrent:
                    await asyncio.sleep(0.1)
                
                # Get next task from queue
                try:
                    priority, created_at, task_id = await asyncio.wait_for(
                        self.pending_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                task = self.tasks.get(task_id)
                if not task or task.status == TaskStatus.CANCELLED:
                    continue
                
                # Execute task
                atask = asyncio.create_task(self._execute_task(task))
                self.running_tasks[task_id] = atask
                
                # Clean up when done
                def cleanup(t_id=task_id):
                    self.running_tasks.pop(t_id, None)
                
                atask.add_done_callback(lambda _: cleanup())
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    async def _execute_task(self, task: Task):
        """
        Execute a single task.
        
        Args:
            task: Task to execute
        """
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        logger.info(f"Executing task {task.task_id}")
        
        try:
            # Get handler
            handler = self.handlers.get(task.intent_type)
            
            if not handler:
                raise ValueError(f"No handler registered for intent: {task.intent_type.value}")
            
            # Execute handler
            result = await handler(task)
            
            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now()
            
            logger.info(f"Task {task.task_id} completed successfully")
            
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            logger.info(f"Task {task.task_id} cancelled")
            
        except Exception as e:
            logger.error(f"Task {task.task_id} failed: {e}")
            
            # Check if should retry
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.PENDING
                logger.info(f"Retrying task {task.task_id} (attempt {task.retry_count})")
                await self.submit(task)
            else:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.now()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        status_counts = {}
        for status in TaskStatus:
            status_counts[status.value] = len(self.get_tasks_by_status(status))
        
        return {
            "total_tasks": len(self.tasks),
            "running_tasks": len(self.running_tasks),
            "pending_tasks": self.pending_queue.qsize(),
            "status_counts": status_counts,
            "max_concurrent": self.max_concurrent,
            "is_running": self._running,
        }
    
    async def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> Optional[Task]:
        """
        Wait for a task to complete.
        
        Args:
            task_id: Task ID to wait for
            timeout: Optional timeout in seconds
            
        Returns:
            Completed task, or None if timeout
        """
        start_time = datetime.now()
        
        while True:
            task = self.tasks.get(task_id)
            
            if not task:
                return None
            
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return task
            
            if timeout:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= timeout:
                    return None
            
            await asyncio.sleep(0.1)
    
    async def wait_for_all(self, timeout: Optional[float] = None) -> List[Task]:
        """
        Wait for all pending tasks to complete.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            List of completed tasks
        """
        start_time = datetime.now()
        
        while True:
            # Check if all tasks are done
            pending = self.get_tasks_by_status(TaskStatus.PENDING)
            running = self.get_tasks_by_status(TaskStatus.RUNNING)
            
            if not pending and not running:
                return list(self.tasks.values())
            
            if timeout:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= timeout:
                    return list(self.tasks.values())
            
            await asyncio.sleep(0.5)