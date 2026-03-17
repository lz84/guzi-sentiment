# 谷子舆情系统 - Agent 原生系统设计

## 文档信息
- **项目名称**: 谷子舆情系统 (Guzi Sentiment System)
- **文档类型**: 系统设计说明书
- **版本**: 1.0
- **创建日期**: 2026-03-17
- **创建者**: 麻子 (Paperclip Agent)
- **Issue**: MAK-9 - 系统设计
- **方案基础**: Agent Skill + 自研系统混合方案

---

## 一、需求分析

### 1.1 项目背景

谷子舆情系统是一个 Agent 原生的舆情情报收集与分析平台，采用 Agent Skill + 自研系统混合架构，为 Polymarket 预测市场提供信息优势。

### 1.2 Agent 原生系统特色

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent 原生系统核心特色                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 技能即模块: Agent Skill 作为系统核心组件                      │
│     - agent-reach → 数据采集模块                                │
│     - tavily-search → 新闻搜索模块                              │
│     - LLM Skill → 情感分析模块                                  │
│                                                                 │
│  2. 对话即接口: 通过自然语言与系统交互                            │
│     - Agent 指令 → 系统操作                                     │
│     - 自然语言查询 → 数据检索                                   │
│     - 智能推荐 → 主动预警                                       │
│                                                                 │
│  3. 自主执行: Agent 驱动的自动化工作流                           │
│     - 定时任务 → Agent 自动调度                                 │
│     - 事件触发 → Agent 自动响应                                 │
│     - 异常处理 → Agent 自动恢复                                 │
│                                                                 │
│  4. 能力扩展: 动态加载新技能                                     │
│     - 插件化架构 → 按需加载 Skill                               │
│     - 热更新 → 无需重启添加新能力                               │
│     - 技能市场 → 快速获取新功能                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 功能性需求

#### 1.3.1 数据采集需求

| 需求编号 | 需求描述 | 优先级 | 实现方式 |
|----------|----------|--------|----------|
| FR-001 | Agent 可通过自然语言指令启动数据采集 | P0 | Agent Skill 调用 |
| FR-002 | 支持采集 Twitter/X 平台数据 | P0 | agent-reach Skill |
| FR-003 | 支持采集 Reddit 平台数据 | P0 | agent-reach Skill |
| FR-004 | 支持采集新闻网站数据 | P0 | tavily-search Skill |
| FR-005 | 支持采集 YouTube 视频内容 | P1 | agent-reach Skill |
| FR-006 | 支持采集微信公众号文章 | P2 | 自研爬虫 |
| FR-007 | 支持采集微博数据 | P1 | agent-reach Skill |
| FR-008 | Agent 可根据关键词自动发现新数据源 | P2 | LLM 推荐 |

#### 1.3.2 数据处理需求

| 需求编号 | 需求描述 | 优先级 | 实现方式 |
|----------|----------|--------|----------|
| FR-010 | Agent 可实时查看数据处理进度 | P0 | 状态查询接口 |
| FR-011 | 支持情感分析（正/负/中性） | P0 | LLM Skill |
| FR-012 | 支持实体识别（人名、地名、机构） | P0 | spaCy + LLM |
| FR-013 | 支持事件提取与分类 | P1 | LLM + 规则引擎 |
| FR-014 | 支持文本去重 | P0 | 向量相似度 |
| FR-015 | Agent 可动态调整处理参数 | P1 | 配置接口 |

#### 1.3.3 分析输出需求

| 需求编号 | 需求描述 | 优先级 | 实现方式 |
|----------|----------|--------|----------|
| FR-020 | Agent 可生成自然语言报告 | P0 | LLM 生成 |
| FR-021 | 支持实时预警推送 | P0 | 飞书/微信 |
| FR-022 | 支持历史数据对话式查询 | P1 | LLM + RAG |
| FR-023 | 支持情感趋势分析 | P1 | 图表生成 |
| FR-024 | Agent 可主动发现异常并报告 | P1 | 异常检测 |

#### 1.3.4 Agent 交互需求

| 需求编号 | 需求描述 | 优先级 | 实现方式 |
|----------|----------|--------|----------|
| FR-030 | 支持自然语言指令控制 | P0 | LLM 意图识别 |
| FR-031 | 支持对话式数据查询 | P0 | LLM + RAG |
| FR-032 | 支持任务状态跟踪 | P0 | 状态管理 |
| FR-033 | 支持多轮对话上下文 | P0 | 会话管理 |
| FR-034 | 支持 Agent 主动推送 | P1 | Webhook |
| FR-035 | 支持技能动态加载 | P2 | 插件系统 |

### 1.4 非功能性需求

| 需求编号 | 需求描述 | 指标 |
|----------|----------|------|
| NFR-001 | Agent 指令响应时间 | < 2 秒 |
| NFR-002 | 数据采集延迟 | < 5 分钟 |
| NFR-003 | 系统可用性 | > 99% |
| NFR-004 | 情感分析准确率 | > 80% |
| NFR-005 | 支持并发 Agent 会话 | > 10 |

### 1.5 Agent 与系统交互能力设计

#### 1.5.1 交互模式

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent 与系统交互模式                          │
└─────────────────────────────────────────────────────────────────┘

                    ┌─────────────────┐
                    │     Agent       │
                    │  (刚子/麻子/谷子) │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
   ┌───────────┐       ┌───────────┐       ┌───────────┐
   │ 指令模式   │       │ 查询模式   │       │ 订阅模式   │
   │           │       │           │       │           │
   │ "采集Twitter │     │ "今天选举话题 │     │ 订阅特定事件 │
   │  选举相关"  │       │  舆情如何？" │     │ 自动推送   │
   └─────┬─────┘       └─────┬─────┘       └─────┬─────┘
         │                   │                   │
         ▼                   ▼                   ▼
   ┌───────────┐       ┌───────────┐       ┌───────────┐
   │ Skill调用 │       │ RAG查询   │       │ Webhook   │
   └───────────┘       └───────────┘       └───────────┘
```

#### 1.5.2 Agent 指令定义

| 指令类型 | 示例 | 系统动作 |
|----------|------|----------|
| 采集指令 | "采集Twitter关于选举的最新数据" | 调用 agent-reach Skill |
| 分析指令 | "分析今天选举话题的情感倾向" | 调用 LLM 分析 |
| 报告指令 | "生成今天舆情日报" | 调用报告生成模块 |
| 查询指令 | "过去一周有哪些负面事件" | RAG 查询 |
| 订阅指令 | "订阅选举相关重大事件预警" | 配置推送规则 |
| 配置指令 | "添加新关键词：降息" | 更新配置 |

---

## 二、渠道扩展性设计

### 2.1 渠道插件架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    渠道插件架构                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       渠道管理层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ 渠道注册器   │  │ 渠道路由器   │  │ 渠道监控器   │            │
│  │ ChannelReg  │  │ ChannelRouter│ │ChannelMonitor│            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       渠道适配层                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 Channel Adapter Interface                │   │
│  │  - collect(keywords, options) → List[RawData]           │   │
│  │  - test_connection() → bool                             │   │
│  │  - get_status() → ChannelStatus                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐     │
│  ▼          ▼          ▼          ▼          ▼          ▼     │
│ ┌────┐    ┌────┐    ┌────┐    ┌────┐    ┌────┐    ┌────┐    │
│ │Twit│    │Redd│    │News│    │YouT│    │Weib│    │ Cust│    │
│ │ter │    │it  │    │    │    │ube │    │o   │    │om  │    │
│ └────┘    └────┘    └────┘    └────┘    └────┘    └────┘    │
│                                                              │
│  Agent    Agent    Tavily    Agent    Agent    自研          │
│  Reach    Reach    Search    Reach    Reach    爬虫          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       渠道配置层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ 渠道配置     │  │ 采集策略     │  │ 限流配置     │            │
│  │ YAML/JSON   │  │ Policy      │  │ RateLimit   │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 渠道适配器接口

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class ChannelStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"

@dataclass
class ChannelConfig:
    """渠道配置"""
    channel_id: str
    channel_name: str
    channel_type: str  # "agent_skill" | "api" | "crawler"
    skill_name: Optional[str] = None  # Agent Skill 名称
    api_endpoint: Optional[str] = None
    rate_limit: int = 100  # 每分钟请求限制
    enabled: bool = True
    config: Dict[str, Any] = None

@dataclass
class RawData:
    """原始数据"""
    channel_id: str
    external_id: str
    content: str
    author: str
    published_at: str
    url: str
    metadata: Dict[str, Any] = None

class ChannelAdapter(ABC):
    """渠道适配器基类"""
    
    def __init__(self, config: ChannelConfig):
        self.config = config
        self.status = ChannelStatus.INACTIVE
    
    @abstractmethod
    async def collect(self, keywords: List[str], options: Dict = None) -> List[RawData]:
        """采集数据"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """测试连接"""
        pass
    
    def get_status(self) -> ChannelStatus:
        """获取状态"""
        return self.status
    
    async def enable(self):
        """启用渠道"""
        self.config.enabled = True
        self.status = ChannelStatus.ACTIVE
    
    async def disable(self):
        """禁用渠道"""
        self.config.enabled = False
        self.status = ChannelStatus.INACTIVE


class AgentSkillAdapter(ChannelAdapter):
    """Agent Skill 适配器"""
    
    def __init__(self, config: ChannelConfig, skill_executor):
        super().__init__(config)
        self.skill_executor = skill_executor  # Agent Skill 执行器
        self.skill_name = config.skill_name
    
    async def collect(self, keywords: List[str], options: Dict = None) -> List[RawData]:
        """通过 Agent Skill 采集数据"""
        result = await self.skill_executor.execute(
            skill_name=self.skill_name,
            params={
                "keywords": keywords,
                "limit": options.get("limit", 100) if options else 100
            }
        )
        
        # 转换为标准格式
        return [self._convert(item) for item in result.get("data", [])]
    
    async def test_connection(self) -> bool:
        """测试 Skill 可用性"""
        try:
            result = await self.skill_executor.test_skill(self.skill_name)
            return result.get("available", False)
        except:
            return False
    
    def _convert(self, item: Dict) -> RawData:
        """转换为标准格式"""
        return RawData(
            channel_id=self.config.channel_id,
            external_id=item.get("id", ""),
            content=item.get("content", item.get("text", "")),
            author=item.get("author", item.get("user", "")),
            published_at=item.get("created_at", item.get("published_at", "")),
            url=item.get("url", ""),
            metadata=item
        )


class TavilySearchAdapter(ChannelAdapter):
    """Tavily 搜索适配器"""
    
    def __init__(self, config: ChannelConfig, tavily_client):
        super().__init__(config)
        self.client = tavily_client
    
    async def collect(self, keywords: List[str], options: Dict = None) -> List[RawData]:
        """通过 Tavily 搜索采集"""
        query = " ".join(keywords)
        result = self.client.search(query, max_results=options.get("limit", 20))
        
        return [self._convert(item) for item in result.get("results", [])]
    
    async def test_connection(self) -> bool:
        """测试 Tavily API"""
        try:
            self.client.search("test", max_results=1)
            return True
        except:
            return False
    
    def _convert(self, item: Dict) -> RawData:
        return RawData(
            channel_id=self.config.channel_id,
            external_id=item.get("url", ""),
            content=item.get("content", ""),
            author=item.get("author", ""),
            published_at=item.get("published_date", ""),
            url=item.get("url", ""),
            metadata=item
        )
```

### 2.3 渠道动态注册

```python
class ChannelRegistry:
    """渠道注册器"""
    
    def __init__(self):
        self.channels: Dict[str, ChannelAdapter] = {}
        self.factories: Dict[str, Callable] = {}
    
    def register_factory(self, channel_type: str, factory: Callable):
        """注册渠道工厂"""
        self.factories[channel_type] = factory
    
    async def register_channel(self, config: ChannelConfig) -> bool:
        """注册新渠道"""
        factory = self.factories.get(config.channel_type)
        if not factory:
            raise ValueError(f"Unknown channel type: {config.channel_type}")
        
        adapter = factory(config)
        if await adapter.test_connection():
            self.channels[config.channel_id] = adapter
            return True
        return False
    
    async def unregister_channel(self, channel_id: str):
        """注销渠道"""
        if channel_id in self.channels:
            del self.channels[channel_id]
    
    def get_channel(self, channel_id: str) -> Optional[ChannelAdapter]:
        """获取渠道"""
        return self.channels.get(channel_id)
    
    def list_channels(self) -> List[ChannelConfig]:
        """列出所有渠道"""
        return [ch.config for ch in self.channels.values()]
```

### 2.4 新渠道扩展流程

```
1. 定义渠道配置
   ┌─────────────────────────────────┐
   │ channels:                       │
   │   - channel_id: weibo_hot       │
   │     channel_name: 微博热搜       │
   │     channel_type: crawler       │
   │     config:                     │
   │       url: https://weibo.com    │
   │       parse_mode: json          │
   └─────────────────────────────────┘
             │
             ▼
2. 实现适配器
   ┌─────────────────────────────────┐
   │ class WeiboCrawlerAdapter:      │
   │     async def collect():        │
   │         # 实现采集逻辑           │
   └─────────────────────────────────┘
             │
             ▼
3. 注册渠道
   ┌─────────────────────────────────┐
   │ POST /api/v1/channels/register  │
   │ {                               │
   │   "channel_id": "weibo_hot",    │
   │   "channel_type": "crawler"     │
   │ }                               │
   └─────────────────────────────────┘
             │
             ▼
4. Agent 可使用
   ┌─────────────────────────────────┐
   │ "采集微博热搜数据"               │
   │ → 系统自动路由到 weibo_hot 渠道  │
   └─────────────────────────────────┘
```

---

## 三、模块设计

### 3.1 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent 原生舆情系统架构                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       Agent 接入层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ 指令解析器   │  │ 会话管理器   │  │ 推送服务    │            │
│  │ IntentParser│  │SessionMgr   │  │PushService │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       技能调度层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ 技能注册器   │  │ 技能执行器   │  │ 技能路由器   │            │
│  │SkillRegistry│  │SkillExecutor│  │SkillRouter  │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                 │
│  已集成技能:                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │agent-    │ │tavily-   │ │LLM       │ │自研      │         │
│  │reach     │ │search    │ │Analysis  │ │Crawler   │         │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       业务逻辑层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ 采集服务     │  │ 分析服务     │  │ 报告服务    │            │
│  │CollectSvc   │  │AnalyzeSvc   │  │ReportSvc   │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ 预警服务     │  │ 查询服务     │  │ 配置服务    │            │
│  │AlertSvc    │  │QuerySvc     │  │ConfigSvc   │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       数据存储层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ MongoDB     │  │ Redis       │  │ 向量存储     │            │
│  │ (文档存储)  │  │ (缓存/队列) │  │ (语义检索)   │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 核心模块设计

#### 3.2.1 Agent 接入模块 (agent_gateway)

```python
# src/agent_gateway/__init__.py

class AgentGateway:
    """Agent 接入网关"""
    
    def __init__(self):
        self.intent_parser = IntentParser()
        self.session_manager = SessionManager()
        self.skill_router = SkillRouter()
        self.push_service = PushService()
    
    async def process_message(self, agent_id: str, message: str, context: dict = None) -> str:
        """处理 Agent 消息"""
        # 1. 获取/创建会话
        session = self.session_manager.get_or_create(agent_id)
        
        # 2. 解析意图
        intent = await self.intent_parser.parse(message, session.context)
        
        # 3. 执行对应操作
        result = await self.execute_intent(intent, session)
        
        # 4. 更新会话上下文
        session.update_context(intent, result)
        
        # 5. 返回结果
        return self.format_response(result)
    
    async def execute_intent(self, intent: Intent, session: Session) -> dict:
        """执行意图"""
        handlers = {
            "collect": self._handle_collect,
            "analyze": self._handle_analyze,
            "query": self._handle_query,
            "report": self._handle_report,
            "subscribe": self._handle_subscribe,
            "config": self._handle_config,
        }
        
        handler = handlers.get(intent.type)
        if handler:
            return await handler(intent, session)
        return {"error": f"Unknown intent: {intent.type}"}
```

#### 3.2.2 意图解析器 (intent_parser)

```python
class IntentParser:
    """意图解析器"""
    
    def __init__(self, llm_client):
        self.llm = llm_client
        self.intent_templates = {
            "collect": [
                "采集{platform}关于{topic}的数据",
                "获取{platform}的{topic}相关内容",
                "抓取{platform}上{topic}的信息"
            ],
            "analyze": [
                "分析{topic}的情感倾向",
                "查看{topic}的舆情",
                "{topic}最近怎么样"
            ],
            "query": [
                "查询过去{time_range}的{event_type}",
                "有哪些{event_type}",
                "显示{topic}的历史数据"
            ],
            "report": [
                "生成{time_range}舆情报告",
                "给我今天的日报",
                "输出舆情摘要"
            ],
            "subscribe": [
                "订阅{topic}的预警",
                "关注{topic}的变化",
                "有{event_type}时通知我"
            ]
        }
    
    async def parse(self, message: str, context: dict = None) -> Intent:
        """解析用户消息为意图"""
        prompt = f"""
        分析以下消息的意图，返回 JSON 格式：
        
        消息: {message}
        上下文: {context or {}}
        
        返回格式:
        {{
            "type": "collect|analyze|query|report|subscribe|config",
            "params": {{
                "platform": "twitter|reddit|news|...",
                "topic": "主题关键词",
                "time_range": "1h|24h|7d|30d",
                "event_type": "election|policy|economic|social"
            }},
            "confidence": 0.0-1.0
        }}
        """
        
        response = await self.llm.generate(prompt)
        result = json.loads(response)
        
        return Intent(
            type=result["type"],
            params=result["params"],
            confidence=result["confidence"]
        )
```

#### 3.2.3 技能调度器 (skill_scheduler)

```python
class SkillScheduler:
    """技能调度器"""
    
    def __init__(self):
        self.registry = SkillRegistry()
        self.executor = SkillExecutor()
    
    async def dispatch(self, skill_name: str, params: dict) -> dict:
        """调度技能执行"""
        skill = self.registry.get_skill(skill_name)
        if not skill:
            raise SkillNotFoundError(f"Skill not found: {skill_name}")
        
        # 检查技能状态
        if not skill.is_available():
            raise SkillUnavailableError(f"Skill unavailable: {skill_name}")
        
        # 执行技能
        result = await self.executor.execute(skill, params)
        
        return result
    
    async def execute_pipeline(self, pipeline: List[dict]) -> List[dict]:
        """执行技能流水线"""
        results = []
        for step in pipeline:
            skill_name = step["skill"]
            params = step["params"]
            result = await self.dispatch(skill_name, params)
            results.append(result)
        return results
```

### 3.3 目录结构

```
guzi-sentiment/
├── src/
│   ├── agent_gateway/           # Agent 接入层
│   │   ├── __init__.py
│   │   ├── gateway.py           # 接入网关
│   │   ├── intent_parser.py     # 意图解析
│   │   ├── session_manager.py   # 会话管理
│   │   └── push_service.py      # 推送服务
│   │
│   ├── skill_layer/             # 技能调度层
│   │   ├── __init__.py
│   │   ├── registry.py          # 技能注册
│   │   ├── executor.py          # 技能执行
│   │   ├── router.py            # 技能路由
│   │   └── skills/              # 技能实现
│   │       ├── agent_reach.py
│   │       ├── tavily_search.py
│   │       ├── llm_analysis.py
│   │       └── custom_crawler.py
│   │
│   ├── services/                # 业务服务层
│   │   ├── __init__.py
│   │   ├── collect_service.py   # 采集服务
│   │   ├── analyze_service.py   # 分析服务
│   │   ├── alert_service.py     # 预警服务
│   │   ├── report_service.py    # 报告服务
│   │   └── query_service.py     # 查询服务
│   │
│   ├── storage/                 # 数据存储层
│   │   ├── __init__.py
│   │   ├── mongodb.py           # MongoDB 操作
│   │   ├── redis_client.py      # Redis 操作
│   │   └── vector_store.py      # 向量存储
│   │
│   ├── channels/                # 渠道适配层
│   │   ├── __init__.py
│   │   ├── base.py              # 基类
│   │   ├── registry.py          # 渠道注册
│   │   └── adapters/            # 适配器实现
│   │       ├── twitter.py
│   │       ├── reddit.py
│   │       ├── news.py
│   │       └── weibo.py
│   │
│   └── main.py                  # 主入口
│
├── config/                      # 配置文件
│   ├── channels.yaml            # 渠道配置
│   ├── skills.yaml              # 技能配置
│   └── alerts.yaml              # 预警规则
│
├── tests/                       # 测试代码
│   ├── test_gateway.py
│   ├── test_skills.py
│   └── test_services.py
│
├── docs/                        # 文档
│   └── ...
│
├── requirements.txt             # 依赖
└── README.md
```

---

## 四、接口设计

### 4.1 Agent 指令接口

```yaml
# Agent 指令协议
AgentInstruction:
  type: object
  properties:
    instruction:
      type: string
      description: 自然语言指令
    context:
      type: object
      description: 上下文信息
  required:
    - instruction

# 响应格式
AgentResponse:
  type: object
  properties:
    success:
      type: boolean
    message:
      type: string
    data:
      type: object
    suggestions:
      type: array
      items:
        type: string
```

### 4.2 REST API 接口

```yaml
# API 端点设计

# 1. Agent 指令接口
POST /api/v1/agent/instruction
  请求体:
    {
      "instruction": "采集Twitter关于选举的最新数据",
      "context": {}
    }
  响应:
    {
      "success": true,
      "message": "已启动采集任务，预计5分钟完成",
      "data": {
        "task_id": "task_xxx",
        "status": "running"
      }
    }

# 2. 数据采集接口
POST /api/v1/collect
  请求体:
    {
      "channels": ["twitter", "reddit"],
      "keywords": ["选举", "政策"],
      "options": {
        "limit": 100,
        "time_range": "24h"
      }
    }

# 3. 情感分析接口
POST /api/v1/analyze/sentiment
  请求体:
    {
      "texts": ["文本1", "文本2"],
      "model": "finbert"
    }
  响应:
    {
      "results": [
        {"text": "文本1", "sentiment": "positive", "score": 0.85},
        {"text": "文本2", "sentiment": "negative", "score": -0.65}
      ]
    }

# 4. 查询接口
GET /api/v1/query
  参数:
    - q: 查询语句
    - time_range: 时间范围
    - sentiment: 情感过滤
  响应:
    {
      "results": [...],
      "total": 100,
      "summary": {
        "sentiment_distribution": {...}
      }
    }

# 5. 报告生成接口
POST /api/v1/report/generate
  请求体:
    {
      "type": "daily",
      "topics": ["选举", "经济"]
    }

# 6. 预警订阅接口
POST /api/v1/alerts/subscribe
  请求体:
    {
      "rules": [
        {
          "topic": "选举",
          "condition": "sentiment < -0.5",
          "channels": ["feishu"]
        }
      ]
    }

# 7. 渠道管理接口
GET /api/v1/channels
POST /api/v1/channels/register
DELETE /api/v1/channels/{channel_id}

# 8. 技能管理接口
GET /api/v1/skills
POST /api/v1/skills/execute
  请求体:
    {
      "skill": "agent-reach",
      "params": {...}
    }
```

### 4.3 Webhook 推送接口

```python
# Webhook 推送格式
WEBHOOK_PAYLOAD = {
    "event": "sentiment_spike|event_detected|daily_report",
    "timestamp": "2026-03-17T06:00:00Z",
    "data": {
        "topic": "选举",
        "sentiment_change": -0.25,
        "trigger": "负面情感激增25%"
    },
    "signature": "hmac_sha256_signature"
}

# 推送配置
WEBHOOK_CONFIG = {
    "url": "https://guzi-decision.local/api/webhook/sentiment",
    "secret": "webhook_secret_key",
    "retry": 3,
    "timeout": 30
}
```

---

## 五、测试设计

### 5.1 测试策略

```
┌─────────────────────────────────────────────────────────────────┐
│                       测试策略                                   │
└─────────────────────────────────────────────────────────────────┘

                        ▲ E2E 测试 (10%)
                       /│\
                      / │ \
                     /  │  \   - 完整 Agent 交互流程
                    /   │   \  - 技能调度流程
                   /    │    \
                  /─────┼─────\
                 /      │      \ 集成测试 (20%)
                /       │       \ - 模块间接口
               /        │        \ - 技能集成
              /         │         \
             /──────────┼──────────\
            /           │           \ 单元测试 (70%)
           /            │            \ - 函数、类方法
          /             │             \ - 意图解析
         /──────────────┼──────────────\
```

### 5.2 测试用例设计

#### 5.2.1 Agent 指令测试

| 用例编号 | 用例名称 | 输入 | 预期输出 |
|----------|----------|------|----------|
| TC-001 | 采集指令解析 | "采集Twitter关于选举的数据" | type=collect, platform=twitter, topic=选举 |
| TC-002 | 分析指令解析 | "分析选举话题的情感" | type=analyze, topic=选举 |
| TC-003 | 查询指令解析 | "过去一周有哪些负面事件" | type=query, time_range=7d, sentiment=negative |
| TC-004 | 报告指令解析 | "生成今天舆情日报" | type=report, time_range=1d |
| TC-005 | 订阅指令解析 | "订阅选举重大事件预警" | type=subscribe, topic=选举 |

#### 5.2.2 技能调度测试

| 用例编号 | 用例名称 | 测试内容 | 预期结果 |
|----------|----------|----------|----------|
| TC-010 | agent-reach 技能调用 | 调用采集 Twitter | 返回推文数据 |
| TC-011 | tavily-search 技能调用 | 搜索新闻 | 返回新闻列表 |
| TC-012 | LLM 分析技能调用 | 情感分析 | 返回情感分数 |
| TC-013 | 技能流水线执行 | 采集→分析流水线 | 按序执行完成 |
| TC-014 | 技能失败重试 | 模拟网络错误 | 自动重试3次 |

#### 5.2.3 渠道适配测试

| 用例编号 | 用例名称 | 测试内容 | 预期结果 |
|----------|----------|----------|----------|
| TC-020 | 渠道注册 | 注册新渠道 | 注册成功 |
| TC-021 | 渠道采集 | 通过渠道采集数据 | 返回数据列表 |
| TC-022 | 渠道限流 | 超过请求限制 | 触发限流 |
| TC-023 | 渠道故障恢复 | 模拟渠道故障 | 自动恢复 |

#### 5.2.4 性能测试

| 用例编号 | 用例名称 | 测试内容 | 预期结果 |
|----------|----------|----------|----------|
| PT-001 | Agent 指令响应时间 | 发送指令测量响应 | < 2 秒 |
| PT-002 | 并发 Agent 会话 | 10 个并发会话 | 正常处理 |
| PT-003 | 数据采集吞吐量 | 批量采集测试 | > 100 条/分钟 |

### 5.3 测试代码示例

```python
import pytest
from src.agent_gateway import AgentGateway
from src.skill_layer import SkillScheduler

class TestAgentGateway:
    """Agent 接入网关测试"""
    
    @pytest.fixture
    def gateway(self):
        return AgentGateway()
    
    @pytest.mark.asyncio
    async def test_collect_instruction(self, gateway):
        """测试采集指令"""
        result = await gateway.process_message(
            agent_id="test_agent",
            message="采集Twitter关于选举的最新数据"
        )
        
        assert result["success"] == True
        assert "task_id" in result["data"]
    
    @pytest.mark.asyncio
    async def test_query_instruction(self, gateway):
        """测试查询指令"""
        result = await gateway.process_message(
            agent_id="test_agent",
            message="过去一周选举话题的舆情如何？"
        )
        
        assert result["success"] == True
        assert "sentiment" in result["data"]


class TestSkillScheduler:
    """技能调度器测试"""
    
    @pytest.fixture
    def scheduler(self):
        return SkillScheduler()
    
    @pytest.mark.asyncio
    async def test_agent_reach_skill(self, scheduler):
        """测试 agent-reach 技能"""
        result = await scheduler.dispatch(
            skill_name="agent-reach",
            params={
                "platform": "twitter",
                "keywords": ["选举"],
                "limit": 10
            }
        )
        
        assert result["success"] == True
        assert len(result["data"]) <= 10
```

### 5.4 验收标准

| 类别 | 指标 | 目标值 |
|------|------|--------|
| 功能 | 指令识别准确率 | > 90% |
| 功能 | 技能调用成功率 | > 95% |
| 功能 | 情感分析准确率 | > 80% |
| 性能 | Agent 指令响应时间 | < 2 秒 |
| 性能 | 并发会话支持 | > 10 |
| 可靠性 | 系统可用性 | > 99% |

---

## 六、实施路线图

### 6.1 阶段规划

| 阶段 | 时间 | 内容 | 交付物 |
|------|------|------|--------|
| 第一阶段 | 1 周 | Agent 接入层 + 基础技能 | 指令解析、agent-reach 集成 |
| 第二阶段 | 1 周 | 业务服务层 + 存储 | 采集/分析/预警服务 |
| 第三阶段 | 1 周 | 渠道扩展 + 测试 | 新渠道、测试报告 |
| 第四阶段 | 持续 | 优化迭代 | 性能优化、功能扩展 |

### 6.2 MVP 交付清单

- [ ] Agent 指令解析与执行
- [ ] agent-reach 技能集成
- [ ] tavily-search 技能集成
- [ ] LLM 情感分析
- [ ] 基础 REST API
- [ ] 预警推送功能
- [ ] 基础测试用例

---

*本文档由麻子 (Paperclip Agent) 生成，基于 Agent 原生系统设计理念。*