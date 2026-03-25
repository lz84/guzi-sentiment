"""
Data models for Agent interface module.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional
import uuid


class IntentType(Enum):
    """Intent types for Agent commands."""
    COLLECT = "collect"       # 数据采集
    ANALYZE = "analyze"       # 数据分析
    QUERY = "query"           # 数据查询
    REPORT = "report"         # 报告生成
    SUBSCRIBE = "subscribe"   # 订阅预警
    CONFIG = "config"         # 配置管理
    UNKNOWN = "unknown"       # 未知意图


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SessionStatus(Enum):
    """Session status."""
    ACTIVE = "active"
    IDLE = "idle"
    CLOSED = "closed"


@dataclass
class ParsedCommand:
    """Parsed command from Agent input."""
    raw_text: str
    intent_type: IntentType
    params: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "intent_type": self.intent_type.value,
            "params": self.params,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class Intent:
    """Recognized intent from natural language."""
    intent_type: IntentType
    params: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    raw_text: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Intent":
        return cls(
            intent_type=IntentType(data.get("type", "unknown")),
            params=data.get("params", {}),
            confidence=data.get("confidence", 0.0),
            raw_text=data.get("raw_text", ""),
        )


@dataclass
class Task:
    """Task for execution."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    intent_type: IntentType = IntentType.UNKNOWN
    params: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "intent_type": self.intent_type.value,
            "params": self.params,
            "status": self.status.value,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
        }


@dataclass
class SessionState:
    """Session state for Agent interaction."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    status: SessionStatus = SessionStatus.ACTIVE
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_active_at: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "context": self.context,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
            "message_count": self.message_count,
        }


@dataclass
class TaskState:
    """State for a specific task."""
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    message: str = ""
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }