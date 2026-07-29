# 每日新闻速览 · 用户使用手册

> 版本：v1.0  
> 适用系统：Windows / macOS / Linux  
> 依赖环境：Python 3.11+

---

## 目录

1. [系统概述](#1-系统概述)
2. [快速开始](#2-快速开始)
3. [配置文件详解](#3-配置文件详解)
4. [Web 界面操作指南](#4-web-界面操作指南)
5. [命令行操作指南](#5-命令行操作指南)
6. [常见问题 FAQ](#6-常见问题-faq)
7. [文件结构参考](#7-文件结构参考)

---

## 1. 系统概述

### 1.1 功能定位

**每日新闻速览** 是一款面向个人用户的信息聚合与智能分析软件，它：

- 自动从多个主流新闻网站抓取最新资讯（优先 RSS 源，辅以 HTML 抓取）
- 根据用户自定义关键词筛选与"中国、政治、经济"相关的事件
- 调用大语言模型（LLM）为每条新闻生成一句话中文摘要
- 支持用户点击单条新闻，调用 LLM 生成包含"事件概要、背景解读、影响评估、趋势展望"四部分的深度分析简报
- 以响应式 Web 网页方式呈现新闻卡片列表，支持电脑浏览器和手机访问

### 1.2 工作流程

```
用户启动 Web / 运行脚本
     │
     ▼
读取 config.yaml（新闻源 + 关键词 + LLM 配置）
     │
     ▼
遍历所有新闻源 ──► RSS 解析 / HTML 抓取
     │
     ▼
关键词过滤 + 标题长度过滤
     │
     ▼
URL 去重（已存在的不重复入库）
     │
     ▼
抓取正文内容（进入 article 页面）
     │
     ▼
SQLite 数据库保存（news.db）
     │
     ▼
LLM 生成一句话标题 + 摘要（写入数据库）
     │
     ▼
Web 页面呈现卡片列表
     │
     ▼
用户点击卡片 → 进入详情页 → 点击"生成深度分析" → LLM 返回简报
```

### 1.3 技术栈

| 组件 | 技术 | 说明 |
|---|---|---|
| Web 框架 | Flask 3.0 | 轻量 Python Web 框架 |
| 数据库 | SQLite 3 | Python 内置，零配置 |
| 爬虫 | feedparser + requests + BeautifulSoup4 | RSS 解析 + HTML 正文提取 |
| LLM | OpenAI 兼容协议 | 支持 OpenAI / DeepSeek / Anthropic / 本地 Ollama |
| 前端 | Jinja2 + 原生 HTML/CSS | 响应式卡片布局 |

---

## 2. 快速开始

### 2.1 准备工作

在开始使用前，请确保以下两项已准备好：

1. **Python 3.11 或更高版本**（可在命令行输入 `python --version` 确认）
2. **LLM API Key**（如 OpenAI / DeepSeek / Anthropic / 其他兼容 OpenAI 协议的服务）

### 2.2 三步启动法

**第一步：安装依赖**

在本项目目录下（`d:\每日新闻速览`），打开命令行终端（PowerShell 或 CMD），执行：

```powershell
pip install -r requirements.txt
```

或手动安装：

```powershell
pip install flask requests feedparser beautifulsoup4 lxml pyyaml python-dotenv openai werkzeug==3.0.0
```

**第二步：配置 LLM API Key**

打开项目目录中的 `.env` 文件，将内容修改为：

```
OPENAI_API_KEY=你的真实API密钥
```

例如：

```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> 💡 如果使用 DeepSeek 等其他服务，请参考 [3.1 节](#31-llm-配置) 的 `base_url` 设置。

**第三步：启动 Web 服务**

在命令行执行：

```powershell
python app.py
```

终端显示类似以下内容即表示成功：

```
INFO: 启动 Flask 服务: http://127.0.0.1:5000
```

**第四步：浏览器访问**

打开浏览器，访问：

```
http://127.0.0.1:5000
```

首次进入会看到"欢迎使用"空状态页面，点击顶部的 **🔄 立即抓取新新闻** 按钮开始第一次数据收集。

---

## 3. 配置文件详解

系统核心配置保存在 `config.yaml` 文件。你可以用任何文本编辑器（记事本、VS Code 等）打开并编辑。

### 3.1 LLM 配置

```yaml
llm:
  provider: "openai"              # 服务商类型
  api_key: "env:OPENAI_API_KEY"   # API Key 的来源
  model: "gpt-4o-mini"            # 使用的模型名称
  base_url: ""                    # 自定义 API 地址（可选）
```

**字段说明：**

| 字段 | 作用 | 取值 |
|---|---|---|
| `provider` | 指定 LLM 服务类型 | `openai` / `deepseek` / `anthropic` / `ollama` |
| `api_key` | API 密钥 | 推荐写法 `env:变量名`（从 `.env` 文件读取）；也可直接写死 `sk-xxxxx`（不安全，不推荐） |
| `model` | 使用的大模型名称 | 如 `gpt-4o-mini`、`deepseek-chat`、`claude-3-haiku-20240307` |
| `base_url` | 自定义 API 基础地址 | 例如 DeepSeek 写 `https://api.deepseek.com/v1` |

**典型配置示例：**

使用 **OpenAI**：
```yaml
llm:
  provider: "openai"
  api_key: "env:OPENAI_API_KEY"
  model: "gpt-4o-mini"
  base_url: ""
```

使用 **DeepSeek**：
```yaml
llm:
  provider: "deepseek"
  api_key: "env:DEEPSEEK_API_KEY"
  model: "deepseek-chat"
  base_url: "https://api.deepseek.com/v1"
```

使用 **本地 Ollama**（需先在 Ollama 中 `ollama serve` 启动服务）：
```yaml
llm:
  provider: "ollama"
  api_key: "ollama"
  model: "qwen2.5:7b"
  base_url: "http://localhost:11434/v1"
```

### 3.2 新闻源配置

```yaml
news_sources:
  - name: "人民日报-政治"
    type: "rss"
    url: "http://www.people.com.cn/rss/politics.xml"
    category: "国内"
  - name: "人民日报-经济"
    type: "rss"
    url: "http://www.people.com.cn/rss/finance.xml"
    category: "国内"
  - name: "CNBC-财经"
    type: "rss"
    url: "https://www.cnbc.com/id/10000664/device/rss/rss.html"
    category: "国际"
```

**字段说明：**

| 字段 | 作用 |
|---|---|
| `name` | 展示在新闻卡片上的来源名称（中文可直接写） |
| `type` | 抓取方式：`rss` 为 RSS 订阅；`html` 为 HTML 页面抓取 |
| `url` | 新闻源的完整 URL 地址 |
| `category` | 新闻分类标签，用于卡片右上角标记（"国内"或"国际"） |

**如何添加新的 RSS 源？**

1. 找到你关注的网站（如新华社、路透社中文网、BBC 中文、联合早报等），查找其 "RSS" / "订阅" 页面，获取 XML 链接
2. 在 `news_sources` 列表末尾追加一条配置，格式与上述一致
3. 保存文件，重新抓取即可

**推荐 RSS 源清单（可自行测试）：**

| 名称 | RSS URL | 类别 |
|---|---|---|
| 人民日报-政治 | `http://www.people.com.cn/rss/politics.xml` | 国内 |
| 人民日报-经济 | `http://www.people.com.cn/rss/finance.xml` | 国内 |
| 中国新闻网-滚动 | `http://www.chinanews.com/rss/scroll-news.xml` | 国内 |
| CNBC-财经 | `https://www.cnbc.com/id/10000664/device/rss/rss.html` | 国际 |
| Reuters | `https://feeds.reuters.com/reuters/worldNews` | 国际 |
| BBC 中文 | `https://www.bbc.com/zhongwen/simp/index.xml` | 国际 |
| Reddit-worldnews | `https://www.reddit.com/r/worldnews/.rss` | 国际 |
| HackerNews | `https://hnrss.org/frontpage` | 国际 |

### 3.3 过滤与筛选配置

```yaml
filters:
  keywords: ["中国", "经济", "政治", "政策", "贸易", "金融", "中美", "央行", "GDP", "投资"]
  min_title_length: 8
```

| 字段 | 作用 |
|---|---|
| `keywords` | 关键词列表。当新闻标题或 RSS 摘要包含任一关键词时，优先保留（无关键词匹配的新闻不会被过滤，但有匹配的优先显示） |
| `min_title_length` | 标题最小字符数，过滤过短标题（如纯数字或无意义标题） |

### 3.4 应用参数配置

```yaml
app:
  max_news_per_source: 10   # 每个新闻源最多抓取条数
  days_to_keep: 30           # 数据库保留最近多少天的记录
  host: "127.0.0.1"          # Web 监听地址（127.0.0.1 仅本机，0.0.0.0 局域网可访问）
  port: 5000                 # Web 端口
  log_level: "INFO"          # 日志级别（INFO / WARNING / ERROR）
```

---

## 4. Web 界面操作指南

### 4.1 登录与访问

Web 服务启动后，浏览器访问：

```
http://127.0.0.1:5000
```

> ⚠️ 本系统仅供本地个人阅读使用，未设计用户登录/权限系统。请勿暴露到公网。

### 4.2 页面一：新闻列表（首页 `/`）

进入首页后，页面呈现以下结构：

```
┌────────────────────────────────────────────────┐
│  📰 每日新闻速览                                  │
│  政治 · 经济 · 涉华新闻 · AI 智能摘要              │
│  ┌──────────────────────────────────────────┐  │
│  │  44条新闻 | 44已摘要 | 0已深度分析 | 最近抓取 │  │
│  └──────────────────────────────────────────┘  │
│  [🔄 立即抓取新新闻]  [⏰ 重试待处理摘要]          │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐   │
│  │ 来源:人民日报  │ │ 新闻标题1    │ │ 新闻标题2   │   │
│  │ 国内 ✓已分析 │ │ 一句话摘要   │ │ 一句话摘要  │   │
│  │ 2026-06-22   │ │ 2026-06-22 │ │ 2026-06-22│   │
│  └────────────┘ └────────────┘ └────────────┘   │
│  （响应式网格，随屏幕宽度自动排列）                 │
└────────────────────────────────────────────────┘
```

**顶部统计条的 4 个数字含义：**

| 数字 | 含义 |
|---|---|
| `44 条新闻` | 当前数据库中总的新闻条数 |
| `44 已摘要` | 已通过 LLM（或 fallback）生成一句话摘要的条数 |
| `0 已深度分析` | 用户点击过"生成深度分析简报"并成功保存的条数 |
| `最近抓取: 2026-06-22 09:30:15` | 进入页面时的系统时间 |

**三个核心按钮：**

| 按钮 | 功能 | 点击后的行为 |
|---|---|---|
| 🔄 立即抓取新新闻 | 触发一次完整抓取流水线 | 调用 `POST /api/collect`，遍历所有新闻源 → 过滤 → 入库 → 调用 LLM 生成摘要。耗时 1~3 分钟。成功后页面自动刷新 |
| ⏰ 重试待处理摘要 | 对数据库中 `is_summary_done = 0` 的记录，重试 LLM 摘要生成 | 调用 `POST /api/retry`，最多处理 30 条。用于首次抓取时网络抖动导致 LLM 失败的场景 |
| 卡片（整张） | 点击任意新闻卡片 | 跳转到该新闻的详情页 `GET /news/{id}` |

**新闻卡片字段详解：**

| 卡片元素 | 来源 | 说明 |
|---|---|---|
| 右上角标签（"人民日报-政治"） | `source` 字段 | 抓取时写入，来自配置文件的 `name` |
| 分类标签（"国内"/"国际"） | `category` 字段 | 抓取时写入，来自配置文件 |
| "✓ 已分析"或"点击查看分析" | `is_analysis_done` 字段 | 区分该新闻是否已生成深度简报 |
| 新闻标题（大字号） | `title` 字段 | LLM 生成的中文标题；若 LLM 失败，使用原始标题 |
| 灰色副文本（一句话摘要） | `one_line_summary` 字段 | LLM 生成的一句话中文摘要；失败时使用 RSS 摘要或原始标题 |
| 卡片底部时间 | `publish_time` 字段 | RSS 源提供的发布时间（如果源无时间，则显示"时间未知"） |

### 4.3 页面二：新闻详情页（`/news/{id}`）

在列表页点击任意卡片，进入详情页。页面结构：

```
┌────────────────────────────────────────────────┐
│  ← 返回新闻列表                                   │
│  LLM 生成的中文大标题                              │
│  [人民日报-政治] [国内] 2026-06-22 09:15:00       │
│  原始标题：国务院常务会议：部署进一步...（原文链接）│
│  🔗 查看原文（新窗口打开）                           │
├────────────────────────────────────────────────┤
│  📋 AI 一句话摘要                                  │
│  （蓝色背景的高亮段落，LLM 生成的中文一句话摘要）     │
├────────────────────────────────────────────────┤
│  🔬 深度分析简报                                   │
│  [🧠 生成深度分析简报]  ← 未分析时显示这个按钮       │
│  （或显示已生成的四部分分析内容）                   │
│  一、事件概要                                       │
│  ...                                               │
│  二、背景解读                                       │
│  ...                                               │
│  三、影响评估                                       │
│  ...                                               │
│  四、趋势展望                                       │
│  ...                                               │
├────────────────────────────────────────────────┤
│  📄 原文抓取内容（节选）                            │
│  （自动抓取的 article 正文，滚动条可查看）           │
└────────────────────────────────────────────────┘
```

**"生成深度分析简报"按钮操作流程：**

1. 在详情页点击 **🧠 生成深度分析简报** 按钮
2. 按钮变为灰色并显示 `⏳ AI 正在分析中...（约需 20-40 秒）`
3. 下方状态条显示 `正在调用 LLM 生成深度分析简报...`
4. 若成功：按钮自动隐藏，页面显示完整的四段分析内容
5. 若失败：按钮恢复可点击，状态条显示错误原因（通常为 `❌ 分析失败: 请检查 LLM API Key 配置`）

**分析简报四部分含义：**

| 章节 | 内容 |
|---|---|
| 一、事件概要 | 用简洁中文重述新闻核心事件（100-200 字） |
| 二、背景解读 | 解释事件发生的政治、经济或历史背景，说明为什么此事重要（150-250 字） |
| 三、影响评估 | 分析对中国、相关行业、市场或国际格局的潜在影响（150-250 字） |
| 四、趋势展望 | 给出对未来发展趋势的合理判断（100-200 字） |

### 4.4 空状态提示（首启动或数据库清空时）

当数据库中尚无新闻时，首页显示：

```
👋 欢迎使用
目前数据库中还没有新闻。
点击上方"立即抓取新新闻"开始收集国内外大事。
💡 小提示: 首次运行会抓取 6 个配置的新闻源。LLM 摘要需要配置 API Key。
```

**操作步骤：**

1. 点击 🔄 **立即抓取新新闻**
2. 等待 1~3 分钟（进度条提示）
3. 页面自动刷新，即可看到抓取到的新闻卡片

### 4.5 状态提示与反馈

| 提示类型 | 背景色 | 示例场景 |
|---|---|---|
| ℹ️ 信息提示（info） | 蓝色 | 抓取按钮点击后，显示"开始抓取新闻源..." |
| ✅ 成功提示（success） | 绿色 | 抓取完成："✅ 完成！处理源 6，抓取 25 条..." |
| ❌ 错误提示（error） | 红色 | "❌ 错误: HTTPSConnectionPool... 超时" |

在详情页的 LLM 分析按钮同样使用这三种状态颜色。

---

## 5. 命令行操作指南

### 5.1 一键抓取脚本 `run_collector.py`

如果你不想启动 Web 服务，也可以直接在命令行执行完整抓取流水线：

```powershell
python run_collector.py
```

**输出示例：**

```
2026-06-22 09:35:12 [INFO] run_collector: ============================================================
2026-06-22 09:35:12 [INFO] run_collector: 启动新闻收集服务...
2026-06-22 09:35:13 [INFO] run_collector: 配置: 6 个新闻源, LLM: openai/gpt-4o-mini
... (中间日志显示每个源的抓取情况) ...
2026-06-22 09:37:21 [INFO] run_collector: ============================================================
2026-06-22 09:37:21 [INFO] run_collector: 执行完成 用时 128.4s
2026-06-22 09:37:21 [INFO] run_collector: 统计: 处理源=6  抓取=25  新增入库=15  AI 摘要=15  错误=0
2026-06-22 09:37:21 [INFO] run_collector: 数据库: 总条数=59  已摘要=59  已分析=0
2026-06-22 09:37:21 [INFO] run_collector: ============================================================
```

**命令行参数：**

| 参数 | 作用 | 示例 |
|---|---|---|
| `--items N` | 每个源最多抓取 N 条（覆盖 config.yaml 的 max_news_per_source） | `python run_collector.py --items 5` |
| `--retry` | 不执行新抓取，仅对数据库中尚未生成摘要的记录重试 LLM | `python run_collector.py --retry` |

### 5.2 日志文件

系统运行日志保存在 `logs/collector.log`，可查看历史抓取的详细过程。

### 5.3 数据库查看（进阶）

新闻数据保存在 `news.db`（标准 SQLite 文件）。你可以使用任何 SQLite 客户端（如 DB Browser for SQLite、DBeaver 等）查看原始数据：

```sql
-- 查看总条数
SELECT COUNT(*) FROM news;

-- 查看最新10条
SELECT id, title, source, publish_time, is_analysis_done
FROM news ORDER BY id DESC LIMIT 10;

-- 查看已深度分析的新闻
SELECT title, source FROM news WHERE is_analysis_done = 1;

-- 清空数据库（慎用！）
DELETE FROM news;
```

**数据表结构：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INTEGER | 主键，自动递增 |
| `url` | TEXT | 原文链接，唯一索引，用于去重 |
| `original_title` | TEXT | RSS 抓取的原始标题 |
| `title` | TEXT | LLM 生成的中文标题 |
| `source` | TEXT | 来源名称（来自配置文件） |
| `category` | TEXT | 分类标签（国内/国际） |
| `publish_time` | TEXT | 发布时间，格式 YYYY-MM-DD HH:MM:SS |
| `content` | TEXT | 抓取的文章正文（节选，最多 4000 字） |
| `one_line_summary` | TEXT | LLM 生成的一句话摘要 |
| `analysis_brief` | TEXT | LLM 生成的深度分析简报 |
| `is_summary_done` | INTEGER | 是否已生成摘要（0=否，1=是） |
| `is_analysis_done` | INTEGER | 是否已深度分析（0=否，1=是） |
| `created_at` | TEXT | 入库时间 |

---

## 6. 常见问题 FAQ

### Q1：点击"立即抓取新新闻"后显示红色错误？

**典型原因：**
- 部分 RSS 源在你当前网络环境下无法访问（如某些境外站点被墙）
- LLM API Key 未配置或无效

**处理方法：**
1. 确认 `.env` 文件中 `OPENAI_API_KEY` 已填入真实密钥
2. 检查日志文件 `logs/collector.log`，定位具体失败的新闻源
3. 在 `config.yaml` 中移除或替换无法访问的源
4. 点击 **⏰ 重试待处理摘要** 按钮，让已入库但摘要失败的记录重新生成

### Q2：LLM 摘要/分析失败，新闻标题显示为英文原文？

这是正常的**降级行为**。当 LLM 调用超时或返回错误时，系统会：
- 将 RSS 原文标题作为卡片标题
- 将 RSS 摘要字段作为一句话摘要
- 卡片上仍显示"点击查看分析"，可随时在详情页手动触发

**如何改善：**
- 使用网络更稳的 LLM 服务商（如 DeepSeek、国内云厂商的 API）
- 在 `config.yaml` 中填写 `base_url` 指向代理或镜像服务

### Q3：数据库中出现重复新闻？

系统以 `url`（原文链接）作为唯一键，理论上不会重复。如果你看到内容相似但链接不同的新闻，那是多个源报道了同一事件，属正常现象。

### Q4：如何切换为中文版的 LLM 模型？

编辑 `config.yaml`，将 `llm` 配置修改为：

```yaml
llm:
  provider: "deepseek"
  api_key: "env:DEEPSEEK_API_KEY"
  model: "deepseek-chat"
  base_url: "https://api.deepseek.com/v1"
```

并在 `.env` 中添加：

```
DEEPSEEK_API_KEY=你的deepseek密钥
```

### Q5：想让抓取的新闻只保留最近 7 天？

编辑 `config.yaml`：

```yaml
app:
  days_to_keep: 7
```

### Q6：Web 页面访问不了，浏览器显示"无法访问此网站"？

请确认：
1. 命令行 `python app.py` 仍在运行中（不要关闭终端窗口）
2. 访问地址为 `http://127.0.0.1:5000`（注意是 http 不是 https）
3. 5000 端口未被其他程序占用

**换端口方法：** 修改 `config.yaml` 中的 `port` 字段，例如改为 `5001`。

### Q7：想在手机上查看？

将 `config.yaml` 中的 `host` 改为 `0.0.0.0`：

```yaml
app:
  host: "0.0.0.0"
  port: 5000
```

然后重启 `python app.py`，在同一局域网的手机浏览器访问：

```
http://电脑IP:5000
```

> ⚠️ 注意：`0.0.0.0` 暴露到整个局域网，请确认网络环境安全。

### Q8：某些新闻源的 RSS 链接失效了怎么办？

1. 打开浏览器访问该 RSS URL，确认是否返回 XML 内容
2. 如果失效，访问新闻网站首页，查找新的 RSS 订阅链接
3. 更新 `config.yaml` 对应源的 `url` 字段
4. 无需重启 Web 服务，下次抓取自动生效

### Q9：想彻底重置数据库？

直接删除项目目录中的 `news.db` 文件即可，下次运行会自动创建全新的数据库。

---

## 7. 文件结构参考

```
d:\每日新闻速览\
├── app.py                    # Flask Web 应用入口（启动用）
├── run_collector.py          # 命令行一键抓取脚本
├── config.yaml               # ⭐ 核心配置（新闻源、LLM、关键词）
├── .env                      # ⭐ LLM API Key（不要提交到 Git）
├── requirements.txt          # Python 依赖列表
├── news.db                   # SQLite 数据库（运行后自动生成）
│
├── src\
│   ├── config_loader.py      # 配置文件解析
│   ├── database.py           # SQLite 读写
│   ├── scraper.py            # RSS/HTML 抓取 + 正文提取
│   ├── llm_client.py         # LLM 统一客户端 + Prompt 模板
│   └── analyzer.py           # "抓取 → 入库 → 摘要" 流水线编排
│
├── templates\
│   ├── index.html            # 新闻列表页模板
│   └── detail.html           # 新闻详情页模板
│
├── static\css\style.css      # 页面样式（卡片布局、配色）
│
└── logs\
    └── collector.log         # 运行日志（自动按日期追加）
```

---

**手册结束**

如有功能建议或问题反馈，可直接编辑配置文件、修改源代码进行扩展。祝使用愉快！🎉
