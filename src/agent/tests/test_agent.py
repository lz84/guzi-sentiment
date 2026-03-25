"""
Tests for Agent interface module.
"""

import pytest
import asyncio
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent import (
    CommandParser,
    IntentRecognizer,
    TaskScheduler,
    StateManager,
    AgentGateway,
    IntentType,
    TaskStatus,
    ParsedCommand,
    Intent,
    Task,
    SessionState,
)


class TestCommandParser:
    """Test CommandParser functionality."""
    
    def setup_method(self):
        self.parser = CommandParser()
    
    def test_parse_collect_command(self):
        """Test parsing collect command."""
        result = self.parser.parse("采集Twitter关于选举的最新数据")
        
        assert result.intent_type == IntentType.COLLECT
        assert result.params.get("platform") == "twitter"
        assert result.confidence > 0.5
    
    def test_parse_query_command(self):
        """Test parsing query command."""
        result = self.parser.parse("查询过去一周的负面事件")
        
        assert result.intent_type == IntentType.QUERY
        assert result.params.get("sentiment") == "negative"
        assert result.params.get("time_range") == "7d"
    
    def test_parse_report_command(self):
        """Test parsing report command."""
        result = self.parser.parse("生成今天舆情日报")
        
        assert result.intent_type == IntentType.REPORT
        assert result.params.get("time_range") == "24h"
    
    def test_parse_subscribe_command(self):
        """Test parsing subscribe command."""
        result = self.parser.parse("订阅选举相关的重大事件预警")
        
        assert result.intent_type == IntentType.SUBSCRIBE
    
    def test_parse_unknown_command(self):
        """Test parsing unknown command."""
        result = self.parser.parse("这是一条无法识别的消息")
        
        assert result.intent_type == IntentType.UNKNOWN
    
    def test_suggest_commands(self):
        """Test command suggestions."""
        suggestions = self.parser.suggest_command("采集")
        
        assert len(suggestions) > 0
        assert any("采集" in s for s in suggestions)


class TestIntentRecognizer:
    """Test IntentRecognizer functionality."""
    
    def setup_method(self):
        self.recognizer = IntentRecognizer(use_llm=False)
    
    def test_recognize_collect_intent(self):
        """Test recognizing collect intent."""
        intent = self.recognizer.recognize("采集Twitter关于选举的数据")
        
        assert intent.intent_type == IntentType.COLLECT
        assert intent.params.get("platform") == "twitter"
    
    def test_recognize_analyze_intent(self):
        """Test recognizing analyze intent."""
        intent = self.recognizer.recognize("分析今天选举话题的情感倾向")
        
        assert intent.intent_type == IntentType.ANALYZE
    
    def test_recognize_query_intent(self):
        """Test recognizing query intent."""
        intent = self.recognizer.recognize("查询过去一周的负面事件")
        
        assert intent.intent_type == IntentType.QUERY
        assert intent.params.get("sentiment") == "negative"
    
    def test_get_supported_intents(self):
        """Test getting supported intents."""
        intents = self.recognizer.get_supported_intents()
        
        assert "collect" in intents
        assert "analyze" in intents
        assert "query" in intents


class TestTaskScheduler:
    """Test TaskScheduler functionality."""
    
    def setup_method(self):
        self.scheduler = TaskScheduler(max_concurrent=3)
    
    @pytest.mark.asyncio
    async def test_submit_task(self):
        """Test submitting a task."""
        task = Task(
            intent_type=IntentType.COLLECT,
            params={"platform": "twitter"},
        )
        
        task_id = await self.scheduler.submit(task)
        
        assert task_id == task.task_id
        assert task.status == TaskStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_get_task(self):
        """Test getting a task."""
        task = Task(intent_type=IntentType.QUERY)
        task_id = await self.scheduler.submit(task)
        
        retrieved = self.scheduler.get_task(task_id)
        
        assert retrieved is not None
        assert retrieved.task_id == task_id
    
    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting scheduler stats."""
        stats = self.scheduler.get_stats()
        
        assert "total_tasks" in stats
        assert "max_concurrent" in stats
        assert stats["max_concurrent"] == 3


class TestStateManager:
    """Test StateManager functionality."""
    
    def setup_method(self):
        self.manager = StateManager()
    
    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test creating a session."""
        session = await self.manager.create_session("agent_001")
        
        assert session.agent_id == "agent_001"
        assert session.status.value == "active"
    
    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test getting a session."""
        created = await self.manager.create_session("agent_001")
        retrieved = await self.manager.get_session(created.session_id)
        
        assert retrieved is not None
        assert retrieved.session_id == created.session_id
    
    @pytest.mark.asyncio
    async def test_update_session_context(self):
        """Test updating session context."""
        session = await self.manager.create_session("agent_001")
        
        result = await self.manager.update_session_context(
            session.session_id, {"key": "value"}
        )
        
        assert result is True
        updated = await self.manager.get_session(session.session_id)
        assert updated.context.get("key") == "value"
    
    @pytest.mark.asyncio
    async def test_create_task_state(self):
        """Test creating task state."""
        state = await self.manager.create_task_state("task_001")
        
        assert state.task_id == "task_001"
        assert state.status == TaskStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_complete_task(self):
        """Test completing a task."""
        await self.manager.create_task_state("task_001")
        
        result = await self.manager.complete_task("task_001", "Done")
        
        assert result is True
        state = await self.manager.get_task_state("task_001")
        assert state.status == TaskStatus.COMPLETED
        assert state.progress == 1.0


class TestAgentGateway:
    """Test AgentGateway functionality."""
    
    def setup_method(self):
        self.gateway = AgentGateway()
    
    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test gateway initialization."""
        await self.gateway.initialize()
        
        assert self.gateway._initialized is True
        
        await self.gateway.shutdown()
    
    @pytest.mark.asyncio
    async def test_process_message(self):
        """Test processing a message."""
        await self.gateway.initialize()
        
        result = await self.gateway.process_message(
            agent_id="agent_001",
            message="采集Twitter关于选举的数据",
        )
        
        assert result["success"] is True
        assert "task_id" in result["data"]
        assert result["data"]["intent"] == "collect"
        
        await self.gateway.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])