# 每日新闻速览 —— 建设方案

> 项目路径：`d:\每日新闻速览`

---

## 一、需求分析（Summary）

| 维度 | 描述 |
|---|---|
| **核心目标** | 每天一键抓取指定国内外新闻网站的政治/经济新闻（尤其中国相关），产出标题列表 + 可点击查看的深度分析简报 |
| **使用方式** | Web 网页（浏览器打开） + 本地一键执行脚本 |
| **关键技术** | Python 爬虫 + SQLite 存储 + LLM 摘要/分析 + Flask Web 界面 |
| **使用场景** | 个人阅读，每日信息摄入 |

### 功能清单

1. **新闻源配置**：可在配置文件中添加/修改新闻网站列表（国内：新华社、人民日报、财经网等；国外：BBC、Reuters、Bloomberg、CNN 等）
2. **一键抓取**：运行脚本后自动抓取所有配置源的最新新闻
3. **关键词过滤**：优先抓取与"中国"、"政治"、"经济"相关的新闻
4. **AI 摘要**：LLM 将每条新闻提炼为"一句话标题"
5. **点击查看详情**：点击某条新闻时，LLM 再输出深度分析简报
6. **新闻列表页**：Web 网页展示新闻卡片（标题、来源、时间、一句话摘要）
7. **本地存储**：SQLite 保存历史记录，避免重复处理

---

## 二、技术架构（Architecture）

```
┌──────────────────────────────────────────────────────────┐
│                   用户浏览器 (Web UI)                       │
│  ┌──────────────┐   ┌──────────────────────────────┐      │
│  │ 新闻列表页    │   │ 新闻详情 / 分析简报           │      │
│  └──────┬───────┘   └──────────────────────────────┘      │
└─────────┼─────────────────────────────────────────────────┘
          │ HTTP (Flask)
┌─────────▼─────────────────────────────────────────────────┐
│                    Flask Web Server                         │
│   routes.py · templates/ · static/                          │
└─────────┬─────────────────────────────────────────────────┘
          │
    ┌─────▼────────────────┐         ┌───────────────────┐
    │  SQLite 数据库        │◄────────┤  新闻源配置文件    │
    │  (news.db)            │         │  (config.yaml)    │
    └─────┬────────────────┘         └───────────────────┘
          │
    ┌─────▼────────────────┐         ┌───────────────────┐
    │  爬虫模块 (Scraper)   │         │  LLM 分析模块     │
    │  · feed 解析          │         │  · 一句话标题     │
    │  · 页面抓取           │         │  · 深度简报       │
    │  · 反爬虫处理         │         │  · 多模型支持     │
    └──────────────────────┘         └───────────────────┘
```

### 技术选型

| 层级 | 选型 | 理由 |
|---|---|---|
| 后端 | Python 3.11+ | 爬虫生态成熟（requests + BeautifulSoup + feedparser），LLM 集成方便 |
| Web 框架 | Flask | 轻量、模板系统好用，适合个人项目 |
| 数据库 | SQLite | 零配置，Python 内置 `sqlite3` 模块 |
| 前端 | 原生 HTML + Jinja2 + Bootstrap | 无需构建工具，直接打开即用 |
| LLM | OpenAI / Anthropic / DeepSeek / 本地 Ollama（可配置切换） | 统一接口层，灵活切换 |
| 定时任务 | APScheduler + 手动一键执行 | 提供自动定时 + 手动触发两种方式 |

### 目录结构

```
d:\每日新闻速览\
├── app.py                    # Flask 应用入口
├── run_collector.py          # 一键抓取脚本（双击或命令行运行）
├── requirements.txt          # 依赖清单
├── config.yaml               # 用户配置：新闻源、关键词、LLM API Key
├── news.db                   # SQLite 数据库（运行后自动生成）
├── .env                      # 环境变量（API Key 等敏感信息）
│
├── src/
│   ├── __init__.py
│   ├── scraper.py            # 爬虫核心（抓取、解析、去重）
│   ├── llm_client.py         # LLM 客户端（统一接口，多模型支持）
│   ├── database.py           # 数据库操作（读写新闻数据）
│   ├── config_loader.py      # 配置加载
│   ├── analyzer.py           # 分析逻辑（调用 LLM 生成简报）
│   └── scheduler.py          # 定时任务（可选）
│
├── templates/
│   ├── index.html            # 新闻列表页
│   └── detail.html           # 新闻详情 + 分析简报页
│
├── static/
│   ├── css/
│   │   └── style.css         # 自定义样式
│   └── js/
│       └── main.js           # 交互逻辑（点击加载分析等）
│
└── logs/                     # 运行日志目录（自动创建）
```

---

## 三、模块设计与实现步骤

### 模块 1：配置系统 [config.yaml + config_loader.py]

**目标**：将新闻源、关键词、LLM API Key 等外部化到配置文件，用户可自行编辑。

```yaml
# config.yaml 示例
llm:
  provider: "openai"          # openai | anthropic | deepseek | ollama
  api_key: "env:OPENAI_API_KEY"
  model: "gpt-4o-mini"
  base_url: ""                # 可自定义 API 端点

news_sources:
  - name: "新华社"
    type: "rss"               # rss | html
    url: "http://www.xinhuanet.com/rss/news.xml"
    category: "国内"
  - name: "Reuters"
    type: "rss"
    url: "https://feeds.reuters.com/Reuters/worldNews"
    category: "国际"
  - name: "BBC 中文网"
    type: "rss"
    url: "https://www.bbc.com/zhongwen/simp/index.xml"
    category: "国际"

filters:
  keywords: ["中国", "经济", "政治", "政策", "贸易", "金融", "中美"]
  min_title_length: 8

app:
  max_news_per_source: 10
  days_to_keep: 30            # 保留近 30 天新闻
  host: "127.0.0.1"
  port: 5000
```

### 模块 2：爬虫模块 [src/scraper.py]

**目标**：从配置文件读取新闻源列表，抓取最新新闻标题、内容、来源、时间。

**实现思路**：
- **RSS 源**：使用 `feedparser` 库解析，直接获得标题、链接、发布时间、摘要
- **HTML 页面**：使用 `requests` + `BeautifulSoup4` 解析，需为每个网站编写定制化选择器
- **内容抓取**：拿到文章 URL 后，再抓正文（优先用 `newspaper3k` 库自动提取正文，失败则回退到手工解析）
- **去重**：根据 URL 或标题哈希在数据库中查重
- **异常处理**：每个网站独立 try/except，一个失败不影响其他

### 模块 3：LLM 客户端 [src/llm_client.py]

**目标**：统一封装 LLM 调用接口，支持多种提供商切换。

**关键能力**：
- `generate_one_line_title(news_item)` → 返回一句话精华标题（中文）
- `generate_analysis_brief(news_item)` → 返回深度分析简报（5-8 个段落，包含：事件概要、背景、影响、趋势）
- Prompt 模板可外部化（放在 `prompts/` 或直接代码字符串常量）
- 调用失败时返回友好占位文案，不阻断流程

### 模块 4：数据库模块 [src/database.py]

**目标**：使用 SQLite 存储新闻，避免重复抓取和重复调用 LLM。

**表结构**：

| 表名 | 字段 | 说明 |
|---|---|---|
| `news` | id, url, title, original_title, source, category, publish_time, content, one_line_summary, analysis_brief, is_analyzed, created_at | 主表 |
| `sources` | id, name, url, type, last_fetched | 抓取源元信息 |

**索引**：`url` 唯一索引；`publish_time` 时间索引

### 模块 5：分析逻辑 [src/analyzer.py]

**目标**：串联爬虫 → 过滤 → 存储 → LLM 摘要的完整流水线。

**工作流**：
1. 读取配置
2. 遍历所有新闻源抓取
3. 关键词过滤（标题 + 摘要含关键词优先保留）
4. 去重后写入数据库（未分析状态）
5. 对新入库的新闻调用 LLM 生成一句话标题
6. 返回本次抓取统计

### 模块 6：Web 界面 [app.py + templates/ + static/]

**目标**：提供美观的新闻列表和点击查看深度分析的入口。

**页面设计**：

| 页面 | 路由 | 内容 |
|---|---|---|
| 首页列表 | `/` | 按时间倒序的新闻卡片，每张卡片含：一句话标题、来源、时间、分类标签、"查看分析"按钮 |
| 详情页 | `/news/<id>` | 原始标题 + 原文摘要 + LLM 深度分析简报（点击"生成分析"后异步生成并展示） |
| 配置页 | `/config` | 展示当前配置（只读） |
| 手动触发 | `/api/collect` | AJAX 调用，返回 JSON 状态 |

---

## 四、依赖清单（requirements.txt）

```
# Web 框架
Flask==3.0.0
Jinja2==3.1.3

# 爬虫
requests==2.31.0
feedparser==6.0.11
beautifulsoup4==4.12.3
newspaper3k==0.2.8
lxml==5.1.0

# LLM
openai==1.12.0
tiktoken==0.6.0

# 配置与工具
PyYAML==6.0.1
python-dotenv==1.0.0

# 定时任务（可选）
APScheduler==3.10.4
```

---

## 五、实现计划（分步实施）

### Step 1：项目骨架与配置系统
- 创建目录结构
- 编写 `requirements.txt`
- 编写 `config.yaml` 模板（含 5-8 个预置新闻源）
- 编写 `src/config_loader.py` 读取配置

### Step 2：数据库模块
- 设计并创建 `news.db` 的表结构
- 实现 CRUD 函数：`save_news`, `get_news_by_id`, `exists_by_url`, `get_recent_news`

### Step 3：爬虫模块
- 实现 RSS 源解析
- 实现 HTML 源解析（针对新华社、Reuters 等典型站点编写 CSS 选择器）
- 实现内容抓取（优先 `newspaper3k`，回退手动解析）
- 实现关键词过滤与去重

### Step 4：LLM 客户端
- 实现统一的 `LLMClient` 类
- 支持 OpenAI 兼容接口（DeepSeek、通义千问都兼容 OpenAI 协议）
- 编写一句话标题生成 Prompt
- 编写深度分析简报生成 Prompt

### Step 5：分析流水线
- 串联爬虫 → 过滤 → 存储 → LLM 摘要
- 编写 `run_collector.py` 一键执行脚本
- 加入日志系统

### Step 6：Web 界面
- 编写 `app.py` Flask 路由
- 编写 `templates/index.html` 新闻列表页（Bootstrap 样式）
- 编写 `templates/detail.html` 详情页（包含异步生成分析功能）
- 编写基础 CSS/JS

### Step 7：可选增强
- 定时任务：每天早上 8:00 自动抓取
- 多语言/多模型切换的 UI 配置
- 新闻收藏/标记功能
- 导出 PDF/Markdown 简报

---

## 六、关键决策与假设

| 决策项 | 选择 | 理由 |
|---|---|---|
| **LLM 模型** | 支持多种，默认 OpenAI（GPT-4o-mini），用户可切到 DeepSeek/本地模型 | 不同用户的 API 可用性不同，统一接口层保证灵活性 |
| **数据库** | SQLite | 零配置，个人项目足够 |
| **爬虫方式** | RSS 优先，HTML 抓取为补充 | RSS 稳定且结构清晰，是最可靠的抓取方式 |
| **前端** | Jinja2 模板 + Bootstrap | 无需构建工具，改动立即可见 |
| **反爬虫策略** | User-Agent 轮换、请求间隔 1-3 秒、失败重试 2 次 | 遵守 robots 规则，温和抓取 |
| **中文处理** | 所有摘要和简报输出中文 | 目标用户中文阅读 |

---

## 七、使用流程

1. **初次使用**
   ```
   pip install -r requirements.txt
   # 编辑 config.yaml 添加新闻源
   # 编辑 .env 添加 API Key
   python run_collector.py          # 首次抓取
   python app.py                    # 启动 Web 界面
   # 浏览器打开 http://127.0.0.1:5000
   ```

2. **日常使用**
   - 方式 A：浏览器访问后点击"重新抓取"按钮
   - 方式 B：运行 `python run_collector.py`
   - 浏览新闻列表，点击感兴趣的条目，查看 AI 生成的分析简报

---

## 八、风险与应对

| 风险 | 影响 | 应对方案 |
|---|---|---|
| 新闻网站改版导致选择器失效 | 爬虫抓不到内容 | 以 RSS 为主，HTML 选择器配置化，失效时用户可编辑 `config.yaml` |
| LLM API 调用失败/限流 | 无法生成摘要 | 加缓存 + 重试 + 错误占位文案；失败的新闻标记为"待分析"，下次重试 |
| 抓取速度过快被封 IP | 单个源不可用 | 随机 User-Agent、请求间隔、单源并发=1、超时处理 |
| 中文 LLM 摘要质量不稳定 | 分析简报信息不准 | 使用较强模型（GPT-4o / Claude / DeepSeek-Pro）；Prompt 中加入"基于原文事实，不编造"指令 |
| 新闻重复（多源报道同一事件） | 列表冗余 | URL 去重 + 标题相似度去重（后续可加标题聚类） |

---

## 九、验证与验收

完成后可通过以下步骤验证：

1. ✅ 运行 `python run_collector.py` → 无报错，控制台输出抓取统计
2. ✅ 运行 `python app.py` → 浏览器访问 `http://127.0.0.1:5000` 能看到新闻列表
3. ✅ 点击任意新闻 → 进入详情页，能看到 AI 生成的一句话标题和深度分析
4. ✅ 再次运行抓取脚本 → 已存在的新闻不再重复入库
5. ✅ 编辑 `config.yaml` 添加新的 RSS 源 → 下次抓取自动包含新源
