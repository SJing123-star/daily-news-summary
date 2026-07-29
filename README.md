# 📰 每日新闻速览

一款基于 Flask 的智能新闻聚合与分析系统，自动抓取全球主流媒体新闻，结合 AI 大模型生成中文摘要与深度分析简报。

![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0+-green.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)

---

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 🌐 **多源新闻抓取** | 支持 RSS/HTML 两种抓取方式，覆盖 BBC、纽约时报、路透社、联合早报、36氪等主流媒体 |
| 🤖 **AI 智能摘要** | 自动为每条新闻生成一句话中文摘要，支持标题翻译 |
| 🔍 **深度分析简报** | 一键生成包含事件概要、背景解读、影响评估、趋势展望四部分的深度分析 |
| 🎯 **关键词过滤** | 根据用户自定义关键词自动筛选与中国/政治/经济相关的新闻 |
| 📊 **策略匹配** | 多策略关键词匹配引擎，支持"外网涉华"、"科技"、"网络安全"等策略 |
| 🖥️ **响应式界面** | 基于 Flask 模板引擎的响应式卡片布局，支持手机和电脑访问 |
| ⚡ **并行处理** | 多线程并行抓取与摘要生成，大幅提升处理效率 |
| 🔒 **API 认证** | 支持 API Key 认证与管理员权限，保护敏感操作 |

---

## 🏗️ 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| Web 框架 | Flask 3.0 | 轻量级 Python Web 框架 |
| 数据库 | SQLite 3 | 零配置，Python 内置 |
| 爬虫 | feedparser + requests + BeautifulSoup4 | RSS 解析 + HTML 正文提取 |
| AI 大模型 | OpenAI / DeepSeek / 兼容 OpenAI 协议 | 统一的 LLM 客户端 |
| 前端 | Jinja2 + 原生 HTML/CSS | 响应式卡片布局 |
| 配置 | YAML + 环境变量 | 灵活的配置管理 |

---

## 🚀 快速开始

### 环境要求

- Python **3.11** 或更高版本
- 一个兼容 OpenAI 协议的 LLM API Key

### 三步启动

**第一步：克隆项目 & 安装依赖**

```bash
# 克隆仓库
git clone https://github.com/SJing123-star/daily-news-summary.git
cd daily-news-summary

# 安装依赖
pip install -r requirements.txt
```

**第二步：配置 API Key**

创建 `.env` 文件：

```bash
# Windows PowerShell
# 新建 .env 文件，添加以下内容
DEEPSEEK_API_KEY=你的API密钥
```

**第三步：启动服务**

```bash
python app.py
```

浏览器访问 `http://127.0.0.1:5000` 即可使用。

---

## ⚙️ 配置说明

### LLM 配置

编辑 `config.yaml`：

```yaml
llm:
  provider: deepseek          # 服务商：openai / deepseek / anthropic
  api_key: env:DEEPSEEK_API_KEY  # API Key 来源
  model: deepseek-v4-flash    # 模型名称
  base_url: https://zhenze-huhehaote.cmecloud.cn/v1  # API 地址
```

**推荐模型：**

| 服务商 | 推荐模型 | 特点 |
|--------|----------|------|
| 阿里云 | deepseek-v4-flash | 中文能力强，价格便宜 |
| 腾讯云 | glm-5 | 通用大模型 |
| OpenAI | gpt-4o-mini | 速度快，支持多语言 |

### 新闻源配置

```yaml
news_sources:
  - name: BBC-国际新闻
    type: rss
    url: https://feeds.bbci.co.uk/news/world/rss.xml
    category: 政治
    strategy: chinese
    enabled: true
    max_items: 10
```

**已支持的新闻源（默认配置）：**

- BBC（国际/商业）
- 纽约时报（国际/商业/科技）
- 路透社
- 联合早报
- 36氪
- 海峡时报
- 金融时报
- 华尔街日报
- 经济学人
- 半岛电视台
- Dark Reading / The Hacker News / SecurityWeek（网络安全）

### 策略配置

系统内置三种关键词匹配策略：

| 策略 | 适用 | 关键词示例 |
|------|------|-----------|
| **外网涉华** | 政治/经济新闻源 | 中国、台湾、中美、制裁、一带一路 |
| **科技** | 科技新闻源 | 人工智能、AI、机器学习、云计算 |
| **网络安全** | 网络安全源 | 黑客、漏洞、数据泄露、勒索软件 |

### 应用参数

```yaml
app:
  host: "127.0.0.1"        # 监听地址
  port: 5000               # 端口
  max_news_per_source: 10  # 每个源最大抓取数
  days_to_keep: 30         # 数据库保留天数
  fetch_hours: 24          # 抓取时间窗口
```

---

## 📖 使用指南

### Web 界面操作

启动后访问 `http://127.0.0.1:5000`：

1. **首页** - 查看新闻列表，点击「🔄 立即抓取新新闻」开始数据收集
2. **详情页** - 点击任意新闻卡片进入详情页
3. **AI 分析** - 在详情页点击「🧠 生成深度分析简报」获取四段式分析

### 命令行操作

```bash
# 一键抓取
python run_collector.py

# 指定每个源抓取条数
python run_collector.py --items 5

# 重试失败的摘要
python run_collector.py --retry
```

### API 接口

| 接口 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/api/collect` | POST | 触发新闻抓取 | API Key |
| `/api/retry` | POST | 重试失败摘要 | API Key |
| `/api/news` | GET | 查询新闻列表 | 无需 |
| `/api/news/{id}` | GET | 获取新闻详情 | 无需 |
| `/api/clear` | POST | 清空数据库 | 管理员 |
| `/api/config` | GET/POST | 获取/修改配置 | 管理员 |

---

## 📁 项目结构

```
daily-news-summary/
├── app.py                    # Flask 应用入口
├── run_collector.py          # 命令行抓取脚本
├── config.yaml               # 核心配置文件
├── .env                      # API 密钥（请勿提交）
├── requirements.txt          # Python 依赖
├── upload_to_github.py       # GitHub 上传工具
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── config_loader.py      # 配置加载器（YAML + 数据库）
│   ├── database.py           # SQLite 数据库操作
│   ├── scraper.py            # RSS/HTML 抓取器
│   ├── llm_client.py         # LLM 统一客户端
│   ├── strategy_manager.py   # 策略匹配引擎
│   ├── analyzer.py           # 单线程分析器
│   ├── parallel_analyzer.py  # 多线程并行分析器
│   ├── autostart_manager.py  # 自启动管理
│   ├── auth.py               # API 认证与限流
│   ├── crypto.py             # 加密工具
│   └── utils.py              # 通用工具函数
│
├── templates/
│   ├── index.html            # 新闻列表页
│   ├── detail.html           # 新闻详情页
│   ├── subscriptions.html    # 订阅管理页
│   ├── strategy.html         # 策略配置页
│   └── llm_management.html   # LLM 管理页
│
├── static/
│   ├── css/style.css         # 样式表
│   └── js/common.js          # 通用 JS 函数
│
└── tests/
    └── test_regression.py    # 回归测试
```

---

## 🔧 常见问题

### Q1：抓取时部分源失败？

- 检查网络连接，某些境外站点可能被墙
- 在 `config.yaml` 中临时禁用失败的源（设置 `enabled: false`）
- 查看 `logs/` 目录下的日志文件定位具体错误

### Q2：API Key 如何配置？

方式一（推荐）：使用环境变量
```bash
# .env 文件
DEEPSEEK_API_KEY=你的密钥
```

方式二：直接写入 config.yaml
```yaml
llm:
  api_key: "sk-xxxxxxxx"  # 不推荐，会被提交到 Git
```

### Q3：如何扩展新闻源？

在 `config.yaml` 的 `news_sources` 列表中添加：
```yaml
- name: 自定义源
  type: rss
  url: https://example.com/rss.xml
  category: 政治
  strategy: chinese
  enabled: true
```

### Q4：手机如何访问？

修改 `config.yaml`：
```yaml
app:
  host: "0.0.0.0"
  port: 5000
```
重启后，同局域网手机访问 `http://电脑IP:5000`

---

## 🛡️ 安全说明

- `.env` 文件包含敏感的 API Key，已加入 `.gitignore`
- 生产环境建议设置 `API_KEYS` 环境变量保护 API
- 管理员操作（清空数据、修改配置）需要 `ADMIN_API_KEYS`
- 系统仅适用于本地个人使用，请勿直接暴露到公网

---

## 📄 许可证

本项目基于 MIT 许可证开源。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

---

**⭐ 如果觉得有用，请给本项目点个 Star！**
