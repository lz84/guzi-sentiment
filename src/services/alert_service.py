"""
预警服务

监控情感变化和事件，触发预警通知。
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable
import uuid
import asyncio
import re

from ..storage.repository import SentimentRepository
from ..analyzer.models import SentimentLabel


class AlertRule:
    """预警规则"""
    
    def __init__(
        self,
        rule_id: str,
        name: str,
        condition: str,
        severity: str = "medium",
        channels: List[str] = None,
        cooldown_minutes: int = 60,
        enabled: bool = True
    ):
        self.rule_id = rule_id
        self.name = name
        self.condition = condition
        self.severity = severity
        self.channels = channels or ["feishu"]
        self.cooldown_minutes = cooldown_minutes
        self.enabled = enabled
        self._last_triggered: Optional[datetime] = None
    
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """
        评估规则条件
        
        支持的条件表达式:
        - sentiment_score < -0.5
        - sentiment_score > 0.7
        - sentiment_label == "negative"
        - event_type == "scandal"
        - mention_count > 100
        """
        if not self.enabled:
            return False
        
        # 检查冷却时间
        if self._last_triggered:
            cooldown = timedelta(minutes=self.cooldown_minutes)
            if datetime.utcnow() - self._last_triggered < cooldown:
                return False
        
        try:
            # 简单的表达式解析
            result = self._evaluate_condition(self.condition, data)
            return bool(result)
        except Exception:
            return False
    
    def _evaluate_condition(self, condition: str, data: Dict[str, Any]) -> bool:
        """评估条件表达式"""
        # 替换变量
        expr = condition
        
        # 提取变量名
        variables = re.findall(r'(\w+)\s*([<>=!]+)', condition)
        
        for var_name, _ in variables:
            if var_name in data:
                value = data[var_name]
                if isinstance(value, str):
                    expr = expr.replace(var_name, f'"{value}"')
                elif isinstance(value, (int, float)):
                    expr = expr.replace(var_name, str(value))
                elif isinstance(value, bool):
                    expr = expr.replace(var_name, str(value).lower())
        
        # 安全评估
        try:
            return eval(expr, {"__builtins__": {}}, {})
        except:
            return False
    
    def mark_triggered(self):
        """标记触发时间"""
        self._last_triggered = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "condition": self.condition,
            "severity": self.severity,
            "channels": self.channels,
            "cooldown_minutes": self.cooldown_minutes,
            "enabled": self.enabled,
            "last_triggered": self._last_triggered.isoformat() if self._last_triggered else None
        }


class AlertService:
    """
    预警服务
    
    负责:
    - 预警规则管理
    - 实时监控
    - 预警触发和通知
    """
    
    # 预设规则
    DEFAULT_RULES = [
        {
            "rule_id": "negative_spike",
            "name": "负面情感激增",
            "condition": "sentiment_score < -0.5 and mention_count > 10",
            "severity": "high",
            "channels": ["feishu"]
        },
        {
            "rule_id": "positive_spike",
            "name": "正面情感激增",
            "condition": "sentiment_score > 0.7 and mention_count > 20",
            "severity": "medium",
            "channels": ["feishu"]
        },
        {
            "rule_id": "scandal_event",
            "name": "丑闻事件",
            "condition": "event_type == 'scandal'",
            "severity": "critical",
            "channels": ["feishu", "email"]
        },
        {
            "rule_id": "high_mention",
            "name": "高提及量",
            "condition": "mention_count > 100",
            "severity": "low",
            "channels": ["feishu"]
        }
    ]
    
    def __init__(
        self,
        repository: SentimentRepository,
        notification_handlers: Optional[Dict[str, Callable]] = None
    ):
        self.repository = repository
        self.notification_handlers = notification_handlers or {}
        self._rules: Dict[str, AlertRule] = {}
        self._subscriptions: Dict[str, List[str]] = {}  # agent_id -> rule_ids
        
        # 加载默认规则
        self._load_default_rules()
    
    def _load_default_rules(self):
        """加载默认规则"""
        for rule_data in self.DEFAULT_RULES:
            rule = AlertRule(**rule_data)
            self._rules[rule.rule_id] = rule
    
    # ==================== 规则管理 ====================
    
    def add_rule(self, rule: AlertRule) -> str:
        """添加预警规则"""
        self._rules[rule.rule_id] = rule
        return rule.rule_id
    
    def create_rule(
        self,
        name: str,
        condition: str,
        severity: str = "medium",
        channels: List[str] = None,
        cooldown_minutes: int = 60
    ) -> AlertRule:
        """创建预警规则"""
        rule_id = str(uuid.uuid4())
        rule = AlertRule(
            rule_id=rule_id,
            name=name,
            condition=condition,
            severity=severity,
            channels=channels,
            cooldown_minutes=cooldown_minutes
        )
        self._rules[rule_id] = rule
        return rule
    
    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """获取规则"""
        return self._rules.get(rule_id)
    
    def list_rules(self, enabled_only: bool = False) -> List[AlertRule]:
        """列出所有规则"""
        rules = list(self._rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return rules
    
    def update_rule(self, rule_id: str, **kwargs) -> bool:
        """更新规则"""
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        
        return True
    
    def delete_rule(self, rule_id: str) -> bool:
        """删除规则"""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False
    
    def enable_rule(self, rule_id: str) -> bool:
        """启用规则"""
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = True
            return True
        return False
    
    def disable_rule(self, rule_id: str) -> bool:
        """禁用规则"""
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = False
            return True
        return False
    
    # ==================== 订阅管理 ====================
    
    def subscribe(self, agent_id: str, rule_ids: List[str]) -> bool:
        """订阅预警"""
        if agent_id not in self._subscriptions:
            self._subscriptions[agent_id] = []
        
        for rule_id in rule_ids:
            if rule_id in self._rules and rule_id not in self._subscriptions[agent_id]:
                self._subscriptions[agent_id].append(rule_id)
        
        # 保存到数据库
        self.repository.create_subscription({
            "subscription_id": str(uuid.uuid4()),
            "agent_id": agent_id,
            "rule_ids": rule_ids,
            "channels": ["feishu"]
        })
        
        return True
    
    def unsubscribe(self, agent_id: str, rule_ids: List[str] = None) -> bool:
        """取消订阅"""
        if agent_id not in self._subscriptions:
            return False
        
        if rule_ids is None:
            # 取消所有订阅
            self._subscriptions[agent_id] = []
        else:
            # 取消指定订阅
            self._subscriptions[agent_id] = [
                r for r in self._subscriptions[agent_id] if r not in rule_ids
            ]
        
        return True
    
    def get_subscriptions(self, agent_id: str) -> List[str]:
        """获取订阅的规则"""
        return self._subscriptions.get(agent_id, [])
    
    # ==================== 监控和触发 ====================
    
    async def check_and_alert(
        self,
        data: Dict[str, Any],
        agent_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        检查数据并触发预警
        
        Args:
            data: 监控数据
            agent_id: 订阅的 Agent ID
        
        Returns:
            触发的预警列表
        """
        triggered_alerts = []
        
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            
            # 检查是否订阅
            if agent_id:
                subscribed_rules = self._subscriptions.get(agent_id, [])
                if rule.rule_id not in subscribed_rules:
                    continue
            
            # 评估规则
            if rule.evaluate(data):
                alert = await self._trigger_alert(rule, data)
                triggered_alerts.append(alert)
        
        return triggered_alerts
    
    async def _trigger_alert(
        self,
        rule: AlertRule,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """触发预警"""
        alert_id = str(uuid.uuid4())
        
        alert = {
            "alert_id": alert_id,
            "rule_id": rule.rule_id,
            "rule_name": rule.name,
            "severity": rule.severity,
            "condition": rule.condition,
            "triggered_data": data,
            "triggered_at": datetime.utcnow().isoformat(),
            "status": "pending",
            "channels": rule.channels
        }
        
        # 保存预警记录
        self.repository.create_alert(alert)
        
        # 标记规则触发
        rule.mark_triggered()
        
        # 发送通知
        await self._send_notification(alert)
        
        return alert
    
    async def _send_notification(self, alert: Dict[str, Any]) -> bool:
        """发送预警通知"""
        channels = alert.get("channels", ["feishu"])
        
        for channel in channels:
            handler = self.notification_handlers.get(channel)
            if handler:
                try:
                    await handler(alert)
                except Exception as e:
                    print(f"Failed to send notification via {channel}: {e}")
        
        # 发布预警消息
        if self.repository.task_queue:
            self.repository.task_queue.publish_alert(alert)
        
        return True
    
    # ==================== 监控任务 ====================
    
    async def monitor_sentiment(
        self,
        topic: Optional[str] = None,
        interval_seconds: int = 300
    ) -> None:
        """
        监控情感变化
        
        Args:
            topic: 监控主题
            interval_seconds: 检查间隔
        """
        while True:
            try:
                # 获取最近的情感统计
                stats = self.repository.get_sentiment_statistics(
                    start_time=datetime.utcnow() - timedelta(minutes=5)
                )
                
                # 构建监控数据
                data = {
                    "sentiment_score": self._calculate_avg_score(stats),
                    "mention_count": stats.get("total", 0),
                    "positive_count": stats.get("positive", {}).get("count", 0),
                    "negative_count": stats.get("negative", {}).get("count", 0),
                    "neutral_count": stats.get("neutral", {}).get("count", 0)
                }
                
                # 检查预警
                await self.check_and_alert(data)
            
            except Exception as e:
                print(f"Monitor error: {e}")
            
            await asyncio.sleep(interval_seconds)
    
    def _calculate_avg_score(self, stats: Dict[str, Any]) -> float:
        """计算平均情感分数"""
        total = stats.get("total", 0)
        if total == 0:
            return 0.0
        
        positive_score = stats.get("positive", {}).get("avg_score", 0)
        negative_score = stats.get("negative", {}).get("avg_score", 0)
        neutral_score = stats.get("neutral", {}).get("avg_score", 0)
        
        positive_count = stats.get("positive", {}).get("count", 0)
        negative_count = stats.get("negative", {}).get("count", 0)
        neutral_count = stats.get("neutral", {}).get("count", 0)
        
        weighted_sum = (
            positive_score * positive_count +
            negative_score * negative_count +
            neutral_score * neutral_count
        )
        
        return weighted_sum / total if total > 0 else 0.0
    
    async def monitor_events(
        self,
        event_types: List[str] = None,
        interval_seconds: int = 60
    ) -> None:
        """
        监控事件
        
        Args:
            event_types: 监控的事件类型
            interval_seconds: 检查间隔
        """
        while True:
            try:
                # 获取最近的事件
                events = self.repository.find_events(
                    start_time=datetime.utcnow() - timedelta(minutes=5)
                )
                
                for event in events:
                    if event_types and event.get("type") not in event_types:
                        continue
                    
                    data = {
                        "event_type": event.get("type"),
                        "event_title": event.get("title"),
                        "event_id": event.get("event_id")
                    }
                    
                    await self.check_and_alert(data)
            
            except Exception as e:
                print(f"Event monitor error: {e}")
            
            await asyncio.sleep(interval_seconds)
    
    # ==================== 预警管理 ====================
    
    def get_pending_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取待处理预警"""
        return self.repository.get_pending_alerts(limit)
    
    def resolve_alert(self, alert_id: str) -> bool:
        """解决预警"""
        return self.repository.resolve_alert(alert_id)
    
    def get_alert_history(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取预警历史"""
        return self.repository.doc_repo.find_alerts(
            status=None,  # 所有状态
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
    
    # ==================== 通知处理器注册 ====================
    
    def register_notification_handler(
        self,
        channel: str,
        handler: Callable
    ) -> None:
        """注册通知处理器"""
        self.notification_handlers[channel] = handler
    
    def unregister_notification_handler(self, channel: str) -> None:
        """注销通知处理器"""
        self.notification_handlers.pop(channel, None)