"""
预警 API 路由
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ...services.alert_service import AlertService, AlertRule
from ...storage.repository import SentimentRepository

router = APIRouter()


# 请求/响应模型
class RuleCreateRequest(BaseModel):
    name: str = Field(..., description="规则名称")
    condition: str = Field(..., description="条件表达式")
    severity: str = Field(default="medium", description="严重级别")
    channels: List[str] = Field(default=["feishu"], description="通知渠道")
    cooldown_minutes: int = Field(default=60, description="冷却时间(分钟)")


class SubscribeRequest(BaseModel):
    agent_id: str
    rule_ids: List[str]


# 服务依赖
def get_alert_service():
    repository = SentimentRepository.create()
    return AlertService(repository=repository)


@router.post("/rules")
async def create_rule(
    request: RuleCreateRequest,
    service: AlertService = Depends(get_alert_service)
):
    """
    创建预警规则
    
    支持的条件表达式:
    - sentiment_score < -0.5
    - sentiment_label == "negative"
    - event_type == "scandal"
    - mention_count > 100
    """
    rule = service.create_rule(
        name=request.name,
        condition=request.condition,
        severity=request.severity,
        channels=request.channels,
        cooldown_minutes=request.cooldown_minutes
    )
    
    return {
        "rule_id": rule.rule_id,
        "name": rule.name,
        "status": "created"
    }


@router.get("/rules")
async def list_rules(
    enabled_only: bool = False,
    service: AlertService = Depends(get_alert_service)
):
    """
    列出所有预警规则
    """
    rules = service.list_rules(enabled_only=enabled_only)
    return {
        "rules": [r.to_dict() for r in rules],
        "total": len(rules)
    }


@router.get("/rules/{rule_id}")
async def get_rule(
    rule_id: str,
    service: AlertService = Depends(get_alert_service)
):
    """
    获取规则详情
    """
    rule = service.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return rule.to_dict()


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    name: Optional[str] = None,
    condition: Optional[str] = None,
    severity: Optional[str] = None,
    enabled: Optional[bool] = None,
    service: AlertService = Depends(get_alert_service)
):
    """
    更新预警规则
    """
    updates = {}
    if name is not None:
        updates["name"] = name
    if condition is not None:
        updates["condition"] = condition
    if severity is not None:
        updates["severity"] = severity
    if enabled is not None:
        updates["enabled"] = enabled
    
    success = service.update_rule(rule_id, **updates)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return {"rule_id": rule_id, "status": "updated"}


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    service: AlertService = Depends(get_alert_service)
):
    """
    删除预警规则
    """
    success = service.delete_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return {"rule_id": rule_id, "status": "deleted"}


@router.post("/rules/{rule_id}/enable")
async def enable_rule(
    rule_id: str,
    service: AlertService = Depends(get_alert_service)
):
    """
    启用规则
    """
    success = service.enable_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return {"rule_id": rule_id, "status": "enabled"}


@router.post("/rules/{rule_id}/disable")
async def disable_rule(
    rule_id: str,
    service: AlertService = Depends(get_alert_service)
):
    """
    禁用规则
    """
    success = service.disable_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return {"rule_id": rule_id, "status": "disabled"}


# ==================== 订阅管理 ====================

@router.post("/subscribe")
async def subscribe_alerts(
    request: SubscribeRequest,
    service: AlertService = Depends(get_alert_service)
):
    """
    订阅预警
    
    Agent 订阅指定的预警规则
    """
    success = service.subscribe(request.agent_id, request.rule_ids)
    return {
        "agent_id": request.agent_id,
        "rule_ids": request.rule_ids,
        "status": "subscribed"
    }


@router.delete("/subscribe")
async def unsubscribe_alerts(
    agent_id: str,
    rule_ids: Optional[List[str]] = None,
    service: AlertService = Depends(get_alert_service)
):
    """
    取消订阅
    
    不指定 rule_ids 则取消所有订阅
    """
    success = service.unsubscribe(agent_id, rule_ids)
    return {
        "agent_id": agent_id,
        "status": "unsubscribed"
    }


@router.get("/subscribe/{agent_id}")
async def get_subscriptions(
    agent_id: str,
    service: AlertService = Depends(get_alert_service)
):
    """
    获取订阅列表
    """
    rule_ids = service.get_subscriptions(agent_id)
    return {
        "agent_id": agent_id,
        "rule_ids": rule_ids
    }


# ==================== 预警管理 ====================

@router.get("/pending")
async def get_pending_alerts(
    limit: int = 100,
    service: AlertService = Depends(get_alert_service)
):
    """
    获取待处理预警
    """
    alerts = service.get_pending_alerts(limit)
    return {
        "alerts": alerts,
        "total": len(alerts)
    }


@router.get("/history")
async def get_alert_history(
    days: int = 7,
    severity: Optional[str] = None,
    limit: int = 100,
    service: AlertService = Depends(get_alert_service)
):
    """
    获取预警历史
    """
    from datetime import timedelta
    
    start_time = datetime.utcnow() - timedelta(days=days)
    alerts = service.get_alert_history(
        start_time=start_time,
        severity=severity,
        limit=limit
    )
    
    return {
        "period_days": days,
        "alerts": alerts,
        "total": len(alerts)
    }


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    service: AlertService = Depends(get_alert_service)
):
    """
    解决预警
    """
    success = service.resolve_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return {"alert_id": alert_id, "status": "resolved"}