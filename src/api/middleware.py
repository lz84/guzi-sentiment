"""
API 中间件配置
"""

import time
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """简单的限流中间件"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._requests = {}
    
    async def dispatch(self, request: Request, call_next):
        # 简化实现：实际生产环境应使用 Redis
        client_ip = request.client.host if request.client else "unknown"
        
        response = await call_next(request)
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        # 添加处理时间头
        response.headers["X-Process-Time"] = f"{process_time:.3f}s"
        
        return response


def setup_middleware(app: FastAPI):
    """配置中间件"""
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Gzip 压缩
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # 日志
    app.add_middleware(LoggingMiddleware)
    
    # 限流 (可选)
    # app.add_middleware(RateLimitMiddleware, requests_per_minute=60)