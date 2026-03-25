"""
谷子舆情系统 - Agent 原生系统主入口

Usage:
    python -m src.main
    uvicorn src.main:app --host 0.0.0.0 --port 8000
"""

import os
import sys
import yaml
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import uvicorn

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api import create_app
from src.storage.repository import SentimentRepository
from src.services.alert_service import AlertService
from src.services.report_service import ReportService


# 加载配置
def load_config(config_path: Optional[str] = None) -> dict:
    """加载配置文件"""
    if config_path is None:
        config_path = os.environ.get(
            "GUZI_CONFIG",
            str(project_root / "config" / "config.yaml")
        )
    
    config_file = Path(config_path)
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    
    return {}


# 全局变量
config = load_config()
app = create_app()
scheduler = AsyncIOScheduler()
repository: Optional[SentimentRepository] = None
alert_service: Optional[AlertService] = None
report_service: Optional[ReportService] = None


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    global repository, alert_service, report_service
    
    print("[START] 谷子舆情系统启动中...")
    
    # 初始化存储
    mongo_config = config.get("mongodb", {})
    redis_config = config.get("redis", {})
    vector_config = config.get("vector_store", {})
    
    repository = SentimentRepository.create(
        mongo_host=mongo_config.get("host", "localhost"),
        mongo_port=mongo_config.get("port", 27017),
        mongo_db=mongo_config.get("database", "guzi_sentiment"),
        redis_host=redis_config.get("host", "localhost"),
        redis_port=redis_config.get("port", 6379),
        vector_persist_dir=vector_config.get("persist_directory")
    )
    
    # 初始化服务
    alert_service = AlertService(repository=repository)
    report_service = ReportService(repository=repository)
    
    # 加载预警规则
    alerts_config_path = project_root / "config" / "alerts.yaml"
    if alerts_config_path.exists():
        with open(alerts_config_path, "r", encoding="utf-8") as f:
            alerts_config = yaml.safe_load(f)
        
        for rule_data in alerts_config.get("rules", []):
            from src.services.alert_service import AlertRule
            rule = AlertRule(**rule_data)
            alert_service.add_rule(rule)
    
    # 启动定时任务
    reports_config = config.get("reports", {})
    
    # 日报调度
    daily_config = reports_config.get("daily", {})
    if daily_config.get("enabled", True):
        schedule = daily_config.get("schedule", "0 8 * * *")
        parts = schedule.split()
        if len(parts) == 5:
            scheduler.add_job(
                generate_daily_report_job,
                CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4]
                ),
                id="daily_report",
                replace_existing=True
            )
    
    # 周报调度
    weekly_config = reports_config.get("weekly", {})
    if weekly_config.get("enabled", True):
        schedule = weekly_config.get("schedule", "0 9 * * 1")
        parts = schedule.split()
        if len(parts) == 5:
            scheduler.add_job(
                generate_weekly_report_job,
                CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4]
                ),
                id="weekly_report",
                replace_existing=True
            )
    
    scheduler.start()
    print("[OK] 谷子舆情系统启动完成")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    print("[STOP] 谷子舆情系统关闭中...")
    
    if scheduler.running:
        scheduler.shutdown()
    
    print("[OK] 谷子舆情系统已关闭")


async def generate_daily_report_job():
    """日报生成任务"""
    print("[REPORT] 生成日报...")
    try:
        report = await report_service.generate_daily_report()
        print(f"[OK] 日报生成完成: {report['report_id']}")
    except Exception as e:
        print(f"[ERROR] 日报生成失败: {e}")


async def generate_weekly_report_job():
    """周报生成任务"""
    print("[REPORT] 生成周报...")
    try:
        report = await report_service.generate_weekly_report()
        print(f"[OK] 周报生成完成: {report['report_id']}")
    except Exception as e:
        print(f"[ERROR] 周报生成失败: {e}")


# 异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc),
            "path": str(request.url)
        }
    )


def main():
    """主函数"""
    api_config = config.get("api", {})
    host = api_config.get("host", "0.0.0.0")
    port = api_config.get("port", 8000)
    debug = api_config.get("debug", False)
    
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=debug
    )


if __name__ == "__main__":
    main()