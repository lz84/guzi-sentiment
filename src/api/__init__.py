"""
API 模块 - 谷子舆情系统

提供 REST API 接口。
"""

from fastapi import FastAPI
from .routes import collect, analyze, alerts, reports, query, channels
from .middleware import setup_middleware

def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="谷子舆情系统 API",
        description="Agent 原生舆情情报收集与分析平台",
        version="1.0.0"
    )
    
    # 设置中间件
    setup_middleware(app)
    
    # 注册路由
    app.include_router(collect.router, prefix="/api/v1/collect", tags=["采集"])
    app.include_router(analyze.router, prefix="/api/v1/analyze", tags=["分析"])
    app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["预警"])
    app.include_router(reports.router, prefix="/api/v1/reports", tags=["报告"])
    app.include_router(query.router, prefix="/api/v1/query", tags=["查询"])
    app.include_router(channels.router, prefix="/api/v1/channels", tags=["渠道"])
    
    @app.get("/")
    async def root():
        return {
            "name": "谷子舆情系统",
            "version": "1.0.0",
            "status": "running"
        }
    
    @app.get("/health")
    async def health():
        return {"status": "healthy"}
    
    return app

__all__ = ["create_app"]