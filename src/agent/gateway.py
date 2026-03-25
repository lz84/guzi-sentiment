"""
Agent Gateway - Main entry point for Agent interactions.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .command_parser import CommandParser
from .intent_recognizer import IntentRecognizer
from .task_scheduler import TaskScheduler
from .state_manager import StateManager
from .models import ParsedCommand, Intent, Task, IntentType, TaskStatus

logger = logging.getLogger(__name__)


class AgentGateway:
    """
    Main gateway for Agent interactions.
    
    Orchestrates:
    - Command parsing
    - Intent recognition
    - Task scheduling
    - State management
    """
    
    def __init__(
        self,
        llm_client: Optional[Any] = None,
        persist_dir: Optional[str] = None,
        max_concurrent_tasks: int = 5,
    ):
        """
        Initialize the Agent Gateway.
        
        Args:
            llm_client: Optional LLM client for intent recognition
            persist_dir: Directory for state persistence
            max_concurrent_tasks: Maximum concurrent tasks
        """
        self.command_parser = CommandParser()
        self.intent_recognizer = IntentRecognizer(llm_client=llm_client)
        self.task_scheduler = TaskScheduler(max_concurrent=max_concurrent_tasks)
        self.state_manager = StateManager(persist_dir=persist_dir)
        
        self._initialized = False
    
    async def initialize(self):
        """Initialize the gateway."""
        if self._initialized:
            return
        
        # Load persisted state
        await self.state_manager.load_state()
        
        # Start task scheduler
        await self.task_scheduler.start()
        
        self._initialized = True
        logger.info("Agent Gateway initialized")
    
    async def shutdown(self):
        """Shutdown the gateway."""
        # Stop task scheduler
        await self.task_scheduler.stop()
        
        # Save state
        await self.state_manager.save_state()
        
        self._initialized = False
        logger.info("Agent Gateway shutdown")
    
    async def process_message(
        self,
        agent_id: str,
        message: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process an Agent message.
        
        Args:
            agent_id: Agent ID
            message: Message text
            session_id: Optional session ID for context
            
        Returns:
            Response dict with action result
        """
        # Ensure initialized
        if not self._initialized:
            await self.initialize()
        
        # Get or create session
        session = await self.state_manager.get_or_create_session(
            agent_id, session_id
        )
        
        # Parse command
        parsed = self.command_parser.parse(message, session.context)
        
        # Recognize intent (using LLM if available)
        intent = self.intent_recognizer.recognize(message, session.context)
        
        # Merge parsed params with recognized intent
        final_params = {**parsed.params, **intent.params}
        
        # Update session context
        await self.state_manager.update_session_context(
            session.session_id,
            {"last_intent": intent.intent_type.value, "last_params": final_params},
        )
        
        # Create and submit task
        task = Task(
            intent_type=intent.intent_type,
            params=final_params,
            priority=self._get_priority(intent.intent_type),
        )
        
        await self.task_scheduler.submit(task)
        
        # Create task state
        await self.state_manager.create_task_state(
            task.task_id,
            status=TaskStatus.PENDING,
            message="Task submitted",
        )
        
        return {
            "success": True,
            "message": self._generate_response(intent, task),
            "data": {
                "task_id": task.task_id,
                "intent": intent.intent_type.value,
                "params": final_params,
                "session_id": session.session_id,
            },
            "suggestions": self.command_parser.suggest_command(message),
        }
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task status.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task status dict or None
        """
        task = self.task_scheduler.get_task(task_id)
        state = await self.state_manager.get_task_state(task_id)
        
        if not task:
            return None
        
        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "intent": task.intent_type.value,
            "progress": state.progress if state else 0.0,
            "message": state.message if state else "",
            "result": task.result,
            "error": task.error,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.
        
        Args:
            task_id: Task ID
            
        Returns:
            True if cancelled
        """
        result = await self.task_scheduler.cancel_task(task_id)
        if result:
            await self.state_manager.update_task_state(
                task_id, status=TaskStatus.CANCELLED, message="Cancelled by user"
            )
        return result
    
    async def get_session_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session context.
        
        Args:
            session_id: Session ID
            
        Returns:
            Context dict or None
        """
        session = await self.state_manager.get_session(session_id)
        return session.context if session else None
    
    async def update_session_context(
        self, session_id: str, context: Dict[str, Any]
    ) -> bool:
        """
        Update session context.
        
        Args:
            session_id: Session ID
            context: Context updates
            
        Returns:
            True if updated
        """
        return await self.state_manager.update_session_context(session_id, context)
    
    def register_task_handler(self, intent_type: IntentType, handler):
        """
        Register a task handler.
        
        Args:
            intent_type: Intent type
            handler: Async handler function
        """
        self.task_scheduler.register_handler(intent_type, handler)
    
    def _get_priority(self, intent_type: IntentType) -> int:
        """Get priority for an intent type."""
        priorities = {
            IntentType.COLLECT: 10,
            IntentType.ANALYZE: 8,
            IntentType.QUERY: 5,
            IntentType.REPORT: 3,
            IntentType.SUBSCRIBE: 2,
            IntentType.CONFIG: 1,
            IntentType.UNKNOWN: 0,
        }
        return priorities.get(intent_type, 0)
    
    def _generate_response(self, intent: Intent, task: Task) -> str:
        """Generate response message."""
        responses = {
            IntentType.COLLECT: f"已启动数据采集任务，任务ID: {task.task_id[:8]}...",
            IntentType.ANALYZE: f"正在分析数据，任务ID: {task.task_id[:8]}...",
            IntentType.QUERY: f"正在查询数据，任务ID: {task.task_id[:8]}...",
            IntentType.REPORT: f"正在生成报告，任务ID: {task.task_id[:8]}...",
            IntentType.SUBSCRIBE: f"已配置订阅，任务ID: {task.task_id[:8]}...",
            IntentType.CONFIG: f"配置已更新，任务ID: {task.task_id[:8]}...",
            IntentType.UNKNOWN: "抱歉，无法理解您的指令。请尝试：采集、分析、查询、报告、订阅、配置",
        }
        return responses.get(intent.intent_type, "任务已提交")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get gateway statistics."""
        return {
            "scheduler": self.task_scheduler.get_stats(),
            "state_manager": self.state_manager.get_stats(),
            "initialized": self._initialized,
        }