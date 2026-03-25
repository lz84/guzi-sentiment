"""
分析 API 路由
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from ...services.analyze_service import AnalyzeService
from ...storage.repository import SentimentRepository

router = APIRouter()


# 请求/响应模型
class SentimentRequest(BaseModel):
    texts: List[str] = Field(..., description="文本列表")
    model: Optional[str] = Field(default="default", description="分析模型")


class EntityRequest(BaseModel):
    texts: List[str] = Field(..., description="文本列表")


class EventRequest(BaseModel):
    texts: List[str] = Field(..., description="文本列表")
    doc_ids: Optional[List[str]] = Field(default=None, description="文档ID列表")


class DocumentAnalyzeRequest(BaseModel):
    doc_id: str
    include_entities: bool = Field(default=True)
    include_events: bool = Field(default=True)


# 服务依赖
def get_analyze_service():
    repository = SentimentRepository.create()
    return AnalyzeService(repository=repository)


@router.post("/sentiment")
async def analyze_sentiment(
    request: SentimentRequest,
    service: AnalyzeService = Depends(get_analyze_service)
):
    """
    批量情感分析
    
    - **texts**: 待分析文本列表
    - **model**: 分析模型 (default, finbert, llm)
    """
    try:
        results = await service.analyze_sentiment(request.texts, request.model)
        return {
            "success": True,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entities")
async def extract_entities(
    request: EntityRequest,
    service: AnalyzeService = Depends(get_analyze_service)
):
    """
    批量实体识别
    
    识别文本中的人名、地名、机构等实体
    """
    try:
        results = await service.extract_entities(request.texts)
        return {
            "success": True,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/events")
async def extract_events(
    request: EventRequest,
    service: AnalyzeService = Depends(get_analyze_service)
):
    """
    批量事件提取
    
    从文本中提取选举、政策、经济等类型事件
    """
    try:
        results = await service.extract_events(request.texts, request.doc_ids)
        return {
            "success": True,
            "events": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/document")
async def analyze_document(
    request: DocumentAnalyzeRequest,
    service: AnalyzeService = Depends(get_analyze_service)
):
    """
    完整文档分析
    
    对单个文档执行情感分析、实体识别、事件提取
    """
    try:
        result = await service.analyze_document(
            doc_id=request.doc_id,
            include_entities=request.include_entities,
            include_events=request.include_events
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
async def analyze_batch(
    doc_ids: List[str],
    background_tasks: BackgroundTasks,
    service: AnalyzeService = Depends(get_analyze_service)
):
    """
    批量文档分析
    
    后台执行批量分析任务
    """
    try:
        results = await service.analyze_batch(doc_ids)
        return {
            "success": True,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_sentiment_statistics(
    days: int = 7,
    service: AnalyzeService = Depends(get_analyze_service)
):
    """
    获取情感统计
    
    返回指定天数内的情感分布统计
    """
    from datetime import datetime, timedelta
    
    start_time = datetime.utcnow() - timedelta(days=days)
    stats = service.get_sentiment_statistics(start_time=start_time)
    
    return {
        "period_days": days,
        "statistics": stats
    }


@router.get("/trend")
async def get_sentiment_trend(
    days: int = 7,
    topic: Optional[str] = None,
    service: AnalyzeService = Depends(get_analyze_service)
):
    """
    获取情感趋势
    
    返回每日情感变化趋势
    """
    trend = service.get_sentiment_trend(topic=topic, days=days)
    return {
        "period_days": days,
        "topic": topic,
        "trend": trend
    }


@router.get("/entities/trending")
async def get_trending_entities(
    entity_type: Optional[str] = None,
    days: int = 7,
    limit: int = 20,
    service: AnalyzeService = Depends(get_analyze_service)
):
    """
    获取热门实体
    
    返回提及次数最多的实体
    """
    entities = service.get_trending_entities(
        entity_type=entity_type,
        days=days,
        limit=limit
    )
    return {
        "entity_type": entity_type,
        "entities": entities
    }