"""
报告服务

生成舆情日报、周报等报告。
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid

from ..storage.repository import SentimentRepository
from ..analyzer.models import SentimentLabel


class ReportService:
    """
    报告服务
    
    负责:
    - 生成舆情日报
    - 生成舆情周报
    - 自定义报告生成
    """
    
    def __init__(
        self,
        repository: SentimentRepository,
        llm_client: Optional[Any] = None
    ):
        self.repository = repository
        self.llm_client = llm_client
    
    # ==================== 日报生成 ====================
    
    async def generate_daily_report(
        self,
        date: Optional[str] = None,
        topics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        生成日报
        
        Args:
            date: 日期 (YYYY-MM-DD)，默认今天
            topics: 关注的主题列表
        
        Returns:
            日报内容
        """
        if not date:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        # 解析日期范围
        try:
            report_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            report_date = datetime.utcnow()
        
        start_time = report_date.replace(hour=0, minute=0, second=0)
        end_time = report_date.replace(hour=23, minute=59, second=59)
        
        # 收集数据
        sentiment_stats = self.repository.get_sentiment_statistics(start_time, end_time)
        events = self.repository.find_events(start_time=start_time, end_time=end_time, limit=50)
        trending_topics = self.repository.get_trending_topics(days=1, limit=10)
        
        # 构建报告
        report = {
            "report_id": str(uuid.uuid4()),
            "report_type": "daily",
            "report_date": date,
            "generated_at": datetime.utcnow().isoformat(),
            
            # 数据概览
            "overview": {
                "total_documents": sentiment_stats.get("total", 0),
                "total_events": len(events),
                "positive_ratio": self._calculate_ratio(sentiment_stats, "positive"),
                "negative_ratio": self._calculate_ratio(sentiment_stats, "negative"),
                "neutral_ratio": self._calculate_ratio(sentiment_stats, "neutral")
            },
            
            # 情感分布
            "sentiment_distribution": {
                "positive": sentiment_stats.get("positive", {}).get("count", 0),
                "negative": sentiment_stats.get("negative", {}).get("count", 0),
                "neutral": sentiment_stats.get("neutral", {}).get("count", 0)
            },
            
            # 关键事件
            "key_events": [
                {
                    "event_id": e.get("event_id"),
                    "type": e.get("type"),
                    "title": e.get("title"),
                    "description": e.get("description"),
                    "sentiment": e.get("sentiment", {}).get("label") if e.get("sentiment") else None
                }
                for e in events[:10]
            ],
            
            # 热门话题
            "trending_topics": [
                {
                    "topic_id": t.get("topic_id"),
                    "keywords": t.get("keywords", [])[:5],
                    "document_count": t.get("document_count", 0)
                }
                for t in trending_topics
            ],
            
            # 摘要
            "summary": await self._generate_summary(sentiment_stats, events)
        }
        
        # 保存报告
        self.repository.save_daily_report(report)
        
        return report
    
    def generate_daily_report_sync(
        self,
        date: Optional[str] = None,
        topics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """同步生成日报"""
        import asyncio
        return asyncio.run(self.generate_daily_report(date, topics))
    
    # ==================== 周报生成 ====================
    
    async def generate_weekly_report(
        self,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成周报
        
        Args:
            end_date: 结束日期，默认今天
        
        Returns:
            周报内容
        """
        if not end_date:
            end_date = datetime.utcnow().strftime("%Y-%m-%d")
        
        try:
            report_date = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            report_date = datetime.utcnow()
        
        start_time = report_date - timedelta(days=7)
        
        # 收集数据
        sentiment_stats = self.repository.get_sentiment_statistics(start_time, report_date)
        events = self.repository.find_events(start_time=start_time, end_time=report_date, limit=100)
        
        # 按日期统计
        daily_stats = self._get_daily_breakdown(start_time, report_date)
        
        # 获取趋势
        sentiment_trend = self._get_sentiment_trend(start_time, report_date)
        
        report = {
            "report_id": str(uuid.uuid4()),
            "report_type": "weekly",
            "report_date": end_date,
            "date_range": {
                "start": start_time.strftime("%Y-%m-%d"),
                "end": end_date
            },
            "generated_at": datetime.utcnow().isoformat(),
            
            # 数据概览
            "overview": {
                "total_documents": sentiment_stats.get("total", 0),
                "total_events": len(events),
                "avg_daily_documents": sentiment_stats.get("total", 0) // 7,
                "positive_ratio": self._calculate_ratio(sentiment_stats, "positive"),
                "negative_ratio": self._calculate_ratio(sentiment_stats, "negative")
            },
            
            # 每日统计
            "daily_breakdown": daily_stats,
            
            # 情感趋势
            "sentiment_trend": sentiment_trend,
            
            # 关键事件
            "key_events": [
                {
                    "event_id": e.get("event_id"),
                    "type": e.get("type"),
                    "title": e.get("title"),
                    "extracted_at": e.get("extracted_at")
                }
                for e in events[:20]
            ],
            
            # 总结
            "summary": await self._generate_weekly_summary(sentiment_stats, events, sentiment_trend)
        }
        
        return report
    
    # ==================== 自定义报告 ====================
    
    async def generate_custom_report(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        topics: Optional[List[str]] = None,
        platforms: Optional[List[str]] = None,
        include_events: bool = True,
        include_sentiment_trend: bool = True,
        include_top_entities: bool = True
    ) -> Dict[str, Any]:
        """
        生成自定义报告
        
        Args:
            title: 报告标题
            start_time: 开始时间
            end_time: 结束时间
            topics: 主题过滤
            platforms: 平台过滤
            include_events: 是否包含事件
            include_sentiment_trend: 是否包含情感趋势
            include_top_entities: 是否包含热门实体
        
        Returns:
            自定义报告
        """
        report = {
            "report_id": str(uuid.uuid4()),
            "report_type": "custom",
            "title": title,
            "date_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            },
            "generated_at": datetime.utcnow().isoformat(),
            "filters": {
                "topics": topics,
                "platforms": platforms
            }
        }
        
        # 情感统计
        sentiment_stats = self.repository.get_sentiment_statistics(start_time, end_time)
        report["sentiment_overview"] = {
            "total": sentiment_stats.get("total", 0),
            "distribution": {
                "positive": sentiment_stats.get("positive", {}).get("count", 0),
                "negative": sentiment_stats.get("negative", {}).get("count", 0),
                "neutral": sentiment_stats.get("neutral", {}).get("count", 0)
            },
            "avg_positive_score": sentiment_stats.get("positive", {}).get("avg_score", 0),
            "avg_negative_score": sentiment_stats.get("negative", {}).get("avg_score", 0)
        }
        
        # 事件
        if include_events:
            events = self.repository.find_events(start_time=start_time, end_time=end_time, limit=50)
            report["events"] = [
                {
                    "event_id": e.get("event_id"),
                    "type": e.get("type"),
                    "title": e.get("title"),
                    "description": e.get("description"),
                    "confidence": e.get("confidence")
                }
                for e in events
            ]
        
        # 情感趋势
        if include_sentiment_trend:
            report["sentiment_trend"] = self._get_sentiment_trend(start_time, end_time)
        
        # 热门实体
        if include_top_entities:
            # 简化实现
            report["top_entities"] = []
        
        return report
    
    # ==================== 报告管理 ====================
    
    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """获取报告"""
        # 从数据库获取
        collection = self.repository.doc_repo.client.get_collection("daily_reports")
        return collection.find_one({"report_id": report_id})
    
    def list_reports(
        self,
        report_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """列出报告"""
        return self.repository.doc_repo.find_daily_reports(
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
    
    def delete_report(self, report_id: str) -> bool:
        """删除报告"""
        collection = self.repository.doc_repo.client.get_collection("daily_reports")
        result = collection.delete_one({"report_id": report_id})
        return result.deleted_count > 0
    
    # ==================== 定时任务 ====================
    
    async def schedule_daily_report(
        self,
        hour: int = 8,
        minute: int = 0
    ) -> str:
        """
        调度每日报告生成
        
        Args:
            hour: 生成时间 (小时)
            minute: 生成时间 (分钟)
        
        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())
        
        # 入队报告任务
        self.repository.enqueue_report_task({
            "task_id": task_id,
            "report_type": "daily",
            "schedule": {"hour": hour, "minute": minute},
            "created_at": datetime.utcnow().isoformat()
        })
        
        return task_id
    
    # ==================== 辅助方法 ====================
    
    def _calculate_ratio(self, stats: Dict[str, Any], label: str) -> float:
        """计算比例"""
        total = stats.get("total", 0)
        if total == 0:
            return 0.0
        
        count = stats.get(label, {}).get("count", 0)
        return round(count / total, 4)
    
    async def _generate_summary(
        self,
        sentiment_stats: Dict[str, Any],
        events: List[Dict[str, Any]]
    ) -> str:
        """生成摘要"""
        total = sentiment_stats.get("total", 0)
        positive = sentiment_stats.get("positive", {}).get("count", 0)
        negative = sentiment_stats.get("negative", {}).get("count", 0)
        
        # 简单摘要生成
        summary_parts = [f"今日共采集舆情数据 {total} 条。"]
        
        if positive > negative:
            summary_parts.append(f"整体情感偏向正面，正面信息 {positive} 条，负面信息 {negative} 条。")
        elif negative > positive:
            summary_parts.append(f"整体情感偏向负面，负面信息 {negative} 条，正面信息 {positive} 条。")
        else:
            summary_parts.append("整体情感分布较为均衡。")
        
        if events:
            summary_parts.append(f"检测到 {len(events)} 个关键事件。")
            
            # 按类型统计
            event_types = {}
            for e in events:
                et = e.get("type", "unknown")
                event_types[et] = event_types.get(et, 0) + 1
            
            for et, count in sorted(event_types.items(), key=lambda x: -x[1])[:3]:
                summary_parts.append(f"其中 {et} 类型事件 {count} 个。")
        
        # 如果有 LLM 客户端，使用 LLM 生成更好的摘要
        if self.llm_client:
            try:
                llm_summary = await self._generate_llm_summary(sentiment_stats, events)
                if llm_summary:
                    return llm_summary
            except Exception:
                pass
        
        return " ".join(summary_parts)
    
    async def _generate_llm_summary(
        self,
        sentiment_stats: Dict[str, Any],
        events: List[Dict[str, Any]]
    ) -> Optional[str]:
        """使用 LLM 生成摘要"""
        if not self.llm_client:
            return None
        
        # 构建提示词
        prompt = f"""
        请根据以下舆情数据生成一份简洁的日报摘要（不超过200字）：
        
        数据总量：{sentiment_stats.get('total', 0)}
        正面：{sentiment_stats.get('positive', {}).get('count', 0)}
        负面：{sentiment_stats.get('negative', {}).get('count', 0)}
        中性：{sentiment_stats.get('neutral', {}).get('count', 0)}
        
        关键事件：
        {chr(10).join([f'- {e.get("title", "未知事件")} ({e.get("type", "未知类型")})' for e in events[:5]])}
        """
        
        # 调用 LLM (具体实现取决于 LLM 客户端)
        # response = await self.llm_client.generate(prompt)
        # return response
        
        return None
    
    async def _generate_weekly_summary(
        self,
        sentiment_stats: Dict[str, Any],
        events: List[Dict[str, Any]],
        sentiment_trend: List[Dict[str, Any]]
    ) -> str:
        """生成周报摘要"""
        total = sentiment_stats.get("total", 0)
        avg_daily = total // 7
        
        summary_parts = [f"本周共采集舆情数据 {total} 条，日均 {avg_daily} 条。"]
        
        # 分析趋势
        if sentiment_trend:
            first_day = sentiment_trend[0] if sentiment_trend else {}
            last_day = sentiment_trend[-1] if sentiment_trend else {}
            
            first_negative = first_day.get("negative", 0)
            last_negative = last_day.get("negative", 0)
            
            if last_negative > first_negative * 1.5:
                summary_parts.append("负面舆情在本周呈上升趋势，需重点关注。")
            elif last_negative < first_negative * 0.5:
                summary_parts.append("负面舆情在本周呈下降趋势，舆情状况改善。")
        
        # 事件统计
        if events:
            summary_parts.append(f"本周共检测到 {len(events)} 个关键事件。")
        
        return " ".join(summary_parts)
    
    def _get_daily_breakdown(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """获取每日数据分解"""
        breakdown = []
        current = start_time
        
        while current <= end_time:
            day_start = current.replace(hour=0, minute=0, second=0)
            day_end = current.replace(hour=23, minute=59, second=59)
            
            stats = self.repository.get_sentiment_statistics(day_start, day_end)
            
            breakdown.append({
                "date": current.strftime("%Y-%m-%d"),
                "total": stats.get("total", 0),
                "positive": stats.get("positive", {}).get("count", 0),
                "negative": stats.get("negative", {}).get("count", 0),
                "neutral": stats.get("neutral", {}).get("count", 0)
            })
            
            current += timedelta(days=1)
        
        return breakdown
    
    def _get_sentiment_trend(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """获取情感趋势"""
        # 从分析服务获取趋势数据
        # 简化实现
        return self._get_daily_breakdown(start_time, end_time)