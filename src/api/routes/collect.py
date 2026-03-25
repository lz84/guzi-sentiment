"""
采集 API 路由
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from ...services.collect_service import CollectService
from ...storage.repository import SentimentRepository

router = APIRouter()


# 请求/响应模型
class CollectRequest(BaseModel):
    channels: List[str] = Field(..., description="渠道ID列表")
    keywords: List[str] = Field(..., description="关键词列表")
    options: Optional[dict] = Field(default=None, description="采集选项")


class CollectResponse(BaseModel):
    task_id: str
    status: str
    message: str


class ScheduleRequest(BaseModel):
    channels: List[str]
    keywords: List[str]
    interval_minutes: int = Field(default=60, description="间隔分钟数")


# 服务依赖
def get_collect_service():
    repository = SentimentRepository.create()
    return CollectService(repository=repository)


@router.post("/", response_model=CollectResponse)
async def collect_data(
    request: CollectRequest,
    background_tasks: BackgroundTasks,
    service: CollectService = Depends(get_collect_service)
):
    """
    执行数据采集
    
    - **channels**: 渠道ID列表 (如 twitter, reddit, news)
    - **keywords**: 关键词列表
    - **options**: 可选配置 (limit, time_range, process)
    """
    try:
        # 异步执行采集
        result = await service.collect(
            channels=request.channels,
            keywords=request.keywords,
            options=request.options
        )
        
        return CollectResponse(
            task_id=result["task_id"],
            status=result.get("status", "completed"),
            message=f"采集完成，共收集 {result['total_collected']} 条数据"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule")
async def schedule_collect(
    request: ScheduleRequest,
    service: CollectService = Depends(get_collect_service)
):
    """
    调度定时采集任务
    """
    try:
        task_id = await service.schedule_collect(
            channels=request.channels,
            keywords=request.keywords,
            interval_minutes=request.interval_minutes
        )
        
        return {
            "task_id": task_id,
            "status": "scheduled",
            "interval_minutes": request.interval_minutes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}")
async def get_task_status(
    task_id: str,
    service: CollectService = Depends(get_collect_service)
):
    """
    获取采集任务状态
    """
    status = service.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return status


@router.get("/stats")
async def get_collection_stats(
    service: CollectService = Depends(get_collect_service)
):
    """
    获取采集统计
    """
    return service.get_collection_stats()


@router.post("/cancel/{task_id}")
async def cancel_task(
    task_id: str,
    service: CollectService = Depends(get_collect_service)
):
    """
    取消采集任务
    """
    success = service.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"task_id": task_id, "status": "cancelled"}