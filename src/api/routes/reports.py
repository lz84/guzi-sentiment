"""
报告 API 路由
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from ...services.report_service import ReportService
from ...storage.repository import SentimentRepository

router = APIRouter()


# 请求/响应模型
class DailyReportRequest(BaseModel):
    date: Optional[str] = Field(default=None, description="日期 YYYY-MM-DD")
    topics: Optional[List[str]] = Field(default=None, description="关注主题")


class WeeklyReportRequest(BaseModel):
    end_date: Optional[str] = Field(default=None, description="结束日期 YYYY-MM-DD")


class CustomReportRequest(BaseModel):
    title: str
    start_time: str
    end_time: str
    topics: Optional[List[str]] = None
    platforms: Optional[List[str]] = None
    include_events: bool = True
    include_sentiment_trend: bool = True
    include_top_entities: bool = True


# 服务依赖
def get_report_service():
    repository = SentimentRepository.create()
    return ReportService(repository=repository)


@router.post("/daily")
async def generate_daily_report(
    request: DailyReportRequest = None,
    background_tasks: BackgroundTasks = None,
    service: ReportService = Depends(get_report_service)
):
    """
    生成日报
    
    - **date**: 报告日期，默认今天
    - **topics**: 关注的主题列表
    """
    try:
        if request is None:
            request = DailyReportRequest()
        
        report = await service.generate_daily_report(
            date=request.date,
            topics=request.topics
        )
        
        return {
            "success": True,
            "report": report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/weekly")
async def generate_weekly_report(
    request: WeeklyReportRequest = None,
    service: ReportService = Depends(get_report_service)
):
    """
    生成周报
    
    - **end_date**: 周报结束日期，默认今天
    """
    try:
        if request is None:
            request = WeeklyReportRequest()
        
        report = await service.generate_weekly_report(end_date=request.end_date)
        
        return {
            "success": True,
            "report": report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/custom")
async def generate_custom_report(
    request: CustomReportRequest,
    service: ReportService = Depends(get_report_service)
):
    """
    生成自定义报告
    
    - **title**: 报告标题
    - **start_time**: 开始时间
    - **end_time**: 结束时间
    - **topics**: 主题过滤
    - **platforms**: 平台过滤
    """
    try:
        start_time = datetime.fromisoformat(request.start_time)
        end_time = datetime.fromisoformat(request.end_time)
        
        report = await service.generate_custom_report(
            title=request.title,
            start_time=start_time,
            end_time=end_time,
            topics=request.topics,
            platforms=request.platforms,
            include_events=request.include_events,
            include_sentiment_trend=request.include_sentiment_trend,
            include_top_entities=request.include_top_entities
        )
        
        return {
            "success": True,
            "report": report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_reports(
    report_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 30,
    service: ReportService = Depends(get_report_service)
):
    """
    列出报告
    
    - **report_type**: 报告类型 (daily, weekly, custom)
    - **start_date**: 开始日期
    - **end_date**: 结束日期
    """
    reports = service.list_reports(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    
    return {
        "reports": reports,
        "total": len(reports)
    }


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    service: ReportService = Depends(get_report_service)
):
    """
    获取报告详情
    """
    report = service.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return report


@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    service: ReportService = Depends(get_report_service)
):
    """
    删除报告
    """
    success = service.delete_report(report_id)
    if not success:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return {"report_id": report_id, "status": "deleted"}


@router.post("/schedule/daily")
async def schedule_daily_report(
    hour: int = 8,
    minute: int = 0,
    service: ReportService = Depends(get_report_service)
):
    """
    调度每日报告
    
    - **hour**: 生成时间 (小时)
    - **minute**: 生成时间 (分钟)
    """
    task_id = await service.schedule_daily_report(hour=hour, minute=minute)
    
    return {
        "task_id": task_id,
        "status": "scheduled",
        "schedule": {"hour": hour, "minute": minute}
    }