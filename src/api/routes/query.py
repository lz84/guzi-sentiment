"""
查询 API 路由
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from ...services.query_service import QueryService
from ...storage.repository import SentimentRepository

router = APIRouter()


# 请求/响应模型
class NaturalQueryRequest(BaseModel):
    query: str = Field(..., description="自然语言查询")
    context: Optional[dict] = Field(default=None, description="查询上下文")


class KeywordQueryRequest(BaseModel):
    keywords: List[str] = Field(..., description="关键词列表")
    platform: Optional[str] = None
    days: int = Field(default=7, description="查询天数")


# 服务依赖
def get_query_service():
    repository = SentimentRepository.create()
    return QueryService(repository=repository)


@router.post("/")
async def natural_query(
    request: NaturalQueryRequest,
    service: QueryService = Depends(get_query_service)
):
    """
    自然语言查询
    
    支持的查询类型:
    - 情感查询: "今天的负面舆情有哪些"
    - 事件查询: "过去一周有哪些丑闻事件"
    - 统计查询: "本周舆情数据统计"
    - 语义搜索: "关于选举的最新消息"
    """
    try:
        result = await service.query(request.query, request.context)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/keywords")
async def query_by_keywords(
    request: KeywordQueryRequest,
    service: QueryService = Depends(get_query_service)
):
    """
    按关键词查询
    
    - **keywords**: 关键词列表
    - **platform**: 平台过滤
    - **days**: 查询天数
    """
    from datetime import datetime, timedelta
    
    start_time = datetime.utcnow() - timedelta(days=request.days)
    
    docs = service.find_documents_by_keywords(
        keywords=request.keywords,
        platform=request.platform,
        start_time=start_time,
        limit=100
    )
    
    return {
        "keywords": request.keywords,
        "platform": request.platform,
        "days": request.days,
        "documents": docs[:20],
        "total": len(docs)
    }


@router.get("/search")
async def semantic_search(
    q: str = Query(..., description="搜索查询"),
    sentiment: Optional[str] = Query(None, description="情感过滤"),
    limit: int = Query(10, description="结果数量"),
    service: QueryService = Depends(get_query_service)
):
    """
    语义搜索
    
    使用向量相似度进行语义搜索
    """
    try:
        repository = SentimentRepository.create()
        results = repository.semantic_search(
            query=q,
            n_results=limit,
            sentiment=sentiment
        )
        
        return {
            "query": q,
            "sentiment": sentiment,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/similar/{doc_id}")
async def find_similar(
    doc_id: str,
    limit: int = 10,
    service: QueryService = Depends(get_query_service)
):
    """
    查找相似文档
    """
    try:
        similar = service.find_similar_documents(doc_id, limit)
        return {
            "doc_id": doc_id,
            "similar_documents": similar,
            "total": len(similar)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline")
async def get_timeline(
    topic: Optional[str] = None,
    platform: Optional[str] = None,
    days: int = 7,
    service: QueryService = Depends(get_query_service)
):
    """
    获取文档时间线
    
    返回每日文档数量分布
    """
    timeline = service.get_document_timeline(
        topic=topic,
        platform=platform,
        days=days
    )
    
    return {
        "topic": topic,
        "platform": platform,
        "days": days,
        "timeline": timeline
    }


@router.get("/platforms")
async def get_platform_distribution(
    days: int = 7,
    service: QueryService = Depends(get_query_service)
):
    """
    获取平台分布
    
    返回各平台数据量分布
    """
    from datetime import datetime, timedelta
    
    start_time = datetime.utcnow() - timedelta(days=days)
    distribution = service.get_platform_distribution(start_time=start_time)
    
    return {
        "days": days,
        "distribution": distribution
    }


@router.get("/entity/{entity_text}")
async def get_entity_mentions(
    entity_text: str,
    days: int = 30,
    service: QueryService = Depends(get_query_service)
):
    """
    获取实体提及历史
    """
    mentions = service.get_entity_mentions(entity_text, days)
    
    return {
        "entity": entity_text,
        "days": days,
        "mentions": mentions,
        "total": len(mentions)
    }


@router.get("/today")
async def get_today_summary(
    service: QueryService = Depends(get_query_service)
):
    """
    获取今日摘要
    """
    return service.get_today_summary()


@router.get("/weekly")
async def get_weekly_overview(
    service: QueryService = Depends(get_query_service)
):
    """
    获取本周概览
    """
    return service.get_weekly_overview()