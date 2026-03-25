"""
State manager for managing Agent session and task states.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
import asyncio
from dataclasses import asdict

from .models import SessionState, TaskState, SessionStatus, TaskStatus

logger = logging.getLogger(__name__)


class StateManager:
    """
    Manage Agent session and task states.
    
    Features:
    - Session lifecycle management
    - Task state tracking
    - Context persistence
    - State expiration
    """
    
    def __init__(
        self,
        persist_dir: Optional[str] = None,
        session_timeout: int = 3600,  # 1 hour
        task_timeout: int = 86400,    # 24 hours
    ):
        """
        Initialize the state manager.
        
        Args:
            persist_dir: Directory for state persistence
            session_timeout: Session timeout in seconds
            task_timeout: Task state timeout in seconds
        """
        self.persist_dir = Path(persist_dir) if persist_dir else None
        self.session_timeout = session_timeout
        self.task_timeout = task_timeout
        
        # In-memory storage
        self.sessions: Dict[str, SessionState] = {}
        self.task_states: Dict[str, TaskState] = {}
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    async def create_session(
        self, agent_id: str, context: Optional[Dict[str, Any]] = None
    ) -> SessionState:
        """
        Create a new session for an Agent.
        
        Args:
            agent_id: Agent ID
            context: Initial context
            
        Returns:
            Created SessionState
        """
        async with self._lock:
            session = SessionState(
                agent_id=agent_id,
                status=SessionStatus.ACTIVE,
                context=context or {},
            )
            
            self.sessions[session.session_id] = session
            
            logger.info(f"Created session {session.session_id} for agent {agent_id}")
            
            return session
    
    async def get_session(self, session_id: str) -> Optional[SessionState]:
        """
        Get a session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            SessionState if found, None otherwise
        """
        return self.sessions.get(session_id)
    
    async def get_or_create_session(
        self, agent_id: str, session_id: Optional[str] = None
    ) -> SessionState:
        """
        Get an existing session or create a new one.
        
        Args:
            agent_id: Agent ID
            session_id: Optional existing session ID
            
        Returns:
            SessionState
        """
        if session_id:
            session = self.sessions.get(session_id)
            if session and session.agent_id == agent_id:
                await self.update_session_activity(session_id)
                return session
        
        return await self.create_session(agent_id)
    
    async def update_session_context(
        self, session_id: str, context: Dict[str, Any]
    ) -> bool:
        """
        Update session context.
        
        Args:
            session_id: Session ID
            context: Context updates to merge
            
        Returns:
            True if updated, False if session not found
        """
        async with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return False
            
            session.context.update(context)
            session.last_active_at = datetime.now()
            
            return True
    
    async def update_session_activity(self, session_id: str) -> bool:
        """
        Update session last activity time.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if updated, False if session not found
        """
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        session.last_active_at = datetime.now()
        session.message_count += 1
        
        return True
    
    async def close_session(self, session_id: str) -> bool:
        """
        Close a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if closed, False if session not found
        """
        async with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return False
            
            session.status = SessionStatus.CLOSED
            session.last_active_at = datetime.now()
            
            logger.info(f"Closed session {session_id}")
            
            return True
    
    async def get_agent_sessions(self, agent_id: str) -> List[SessionState]:
        """
        Get all active sessions for an agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of SessionState
        """
        return [
            s for s in self.sessions.values()
            if s.agent_id == agent_id and s.status == SessionStatus.ACTIVE
        ]
    
    async def create_task_state(
        self, task_id: str, status: TaskStatus = TaskStatus.PENDING, message: str = ""
    ) -> TaskState:
        """
        Create a new task state.
        
        Args:
            task_id: Task ID
            status: Initial status
            message: Status message
            
        Returns:
            Created TaskState
        """
        async with self._lock:
            state = TaskState(
                task_id=task_id,
                status=status,
                message=message,
            )
            
            self.task_states[task_id] = state
            
            return state
    
    async def get_task_state(self, task_id: str) -> Optional[TaskState]:
        """
        Get task state by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            TaskState if found, None otherwise
        """
        return self.task_states.get(task_id)
    
    async def update_task_state(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
    ) -> bool:
        """
        Update task state.
        
        Args:
            task_id: Task ID
            status: Optional new status
            progress: Optional progress (0-1)
            message: Optional status message
            
        Returns:
            True if updated, False if task not found
        """
        async with self._lock:
            state = self.task_states.get(task_id)
            if not state:
                return False
            
            if status is not None:
                state.status = status
            if progress is not None:
                state.progress = min(max(progress, 0.0), 1.0)
            if message is not None:
                state.message = message
            
            state.updated_at = datetime.now()
            
            return True
    
    async def set_task_progress(self, task_id: str, progress: float, message: str = "") -> bool:
        """
        Set task progress.
        
        Args:
            task_id: Task ID
            progress: Progress value (0-1)
            message: Progress message
            
        Returns:
            True if updated, False if task not found
        """
        return await self.update_task_state(task_id, progress=progress, message=message)
    
    async def complete_task(self, task_id: str, message: str = "Completed") -> bool:
        """
        Mark task as completed.
        
        Args:
            task_id: Task ID
            message: Completion message
            
        Returns:
            True if updated, False if task not found
        """
        return await self.update_task_state(
            task_id, status=TaskStatus.COMPLETED, progress=1.0, message=message
        )
    
    async def fail_task(self, task_id: str, error: str) -> bool:
        """
        Mark task as failed.
        
        Args:
            task_id: Task ID
            error: Error message
            
        Returns:
            True if updated, False if task not found
        """
        return await self.update_task_state(
            task_id, status=TaskStatus.FAILED, message=error
        )
    
    async def cleanup_expired(self) -> int:
        """
        Clean up expired sessions and task states.
        
        Returns:
            Number of items cleaned up
        """
        async with self._lock:
            now = datetime.now()
            cleaned = 0
            
            # Clean expired sessions
            expired_sessions = []
            for session_id, session in self.sessions.items():
                age = (now - session.last_active_at).total_seconds()
                if age > self.session_timeout:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self.sessions[session_id]
                cleaned += 1
            
            # Clean expired task states
            expired_tasks = []
            for task_id, state in self.task_states.items():
                age = (now - state.updated_at).total_seconds()
                if age > self.task_timeout:
                    expired_tasks.append(task_id)
            
            for task_id in expired_tasks:
                del self.task_states[task_id]
                cleaned += 1
            
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} expired items")
            
            return cleaned
    
    async def save_state(self):
        """Save current state to disk."""
        if not self.persist_dir:
            return
        
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Save sessions
        sessions_file = self.persist_dir / "sessions.json"
        sessions_data = {
            sid: asdict(s) for sid, s in self.sessions.items()
        }
        with open(sessions_file, "w", encoding="utf-8") as f:
            json.dump(sessions_data, f, ensure_ascii=False, default=str)
        
        # Save task states
        tasks_file = self.persist_dir / "task_states.json"
        tasks_data = {
            tid: asdict(t) for tid, t in self.task_states.items()
        }
        with open(tasks_file, "w", encoding="utf-8") as f:
            json.dump(tasks_data, f, ensure_ascii=False, default=str)
        
        logger.info("State saved to disk")
    
    async def load_state(self):
        """Load state from disk."""
        if not self.persist_dir:
            return
        
        # Load sessions
        sessions_file = self.persist_dir / "sessions.json"
        if sessions_file.exists():
            with open(sessions_file, "r", encoding="utf-8") as f:
                sessions_data = json.load(f)
            for sid, data in sessions_data.items():
                self.sessions[sid] = SessionState(
                    session_id=data["session_id"],
                    agent_id=data["agent_id"],
                    status=SessionStatus(data["status"]),
                    context=data.get("context", {}),
                    created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
                    last_active_at=datetime.fromisoformat(data["last_active_at"]) if data.get("last_active_at") else None,
                    message_count=data.get("message_count", 0),
                )
        
        # Load task states
        tasks_file = self.persist_dir / "task_states.json"
        if tasks_file.exists():
            with open(tasks_file, "r", encoding="utf-8") as f:
                tasks_data = json.load(f)
            for tid, data in tasks_data.items():
                self.task_states[tid] = TaskState(
                    task_id=data["task_id"],
                    status=TaskStatus(data["status"]),
                    progress=data.get("progress", 0.0),
                    message=data.get("message", ""),
                    updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
                )
        
        logger.info("State loaded from disk")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get state manager statistics."""
        active_sessions = sum(
            1 for s in self.sessions.values() if s.status == SessionStatus.ACTIVE
        )
        
        task_status_counts = {}
        for status in TaskStatus:
            task_status_counts[status.value] = sum(
                1 for t in self.task_states.values() if t.status == status
            )
        
        return {
            "total_sessions": len(self.sessions),
            "active_sessions": active_sessions,
            "total_task_states": len(self.task_states),
            "task_status_counts": task_status_counts,
            "session_timeout": self.session_timeout,
            "task_timeout": self.task_timeout,
        }