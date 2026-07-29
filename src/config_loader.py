"""
配置加载模块
负责加载应用配置（YAML配置文件 + 环境变量 + 数据库配置）

配置加载优先级（从低到高）：
1. YAML配置文件默认值
2. 环境变量（env:前缀）
3. 数据库配置（LLM配置优先）
"""
import os
import yaml
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 找到项目根目录的 .env 文件
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_dotenv_path = os.path.join(_project_root, ".env")
load_dotenv(_dotenv_path)


class YAMLConfigLoader:
    """YAML配置文件加载器"""
    
    DEFAULT_CONFIG = {
        "llm": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "base_url": "",
            "api_key": "",
        },
        "filters": {
            "keywords": [],
            "min_title_length": 8,
        },
        "app": {
            "max_news_per_source": 10,
            "days_to_keep": 30,
            "host": "127.0.0.1",
            "port": 5000,
            "log_level": "INFO",
            "fetch_hours": 24,
        },
        "news_sources": [],
        "strategies": [],
    }

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config.yaml"
            )
        self.config_path = config_path
        self.data = self._load_config()

    def _load_config(self) -> dict:
        """加载YAML配置文件，不存在则返回默认配置"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return self._merge_with_defaults(data)
        except FileNotFoundError:
            logger.warning(f"配置文件不存在: {self.config_path}，使用默认配置")
            return self.DEFAULT_CONFIG.copy()
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}，使用默认配置")
            return self.DEFAULT_CONFIG.copy()

    def _merge_with_defaults(self, data: dict) -> dict:
        """将用户配置与默认配置合并"""
        result = self.DEFAULT_CONFIG.copy()
        self._deep_merge(result, data)
        return result

    @staticmethod
    def _deep_merge(target: dict, source: dict):
        """深度合并字典"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                YAMLConfigLoader._deep_merge(target[key], value)
            else:
                target[key] = value

    def save(self):
        """保存配置到YAML文件"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    self.data,
                    f,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False
                )
            logger.info(f"配置已保存到: {self.config_path}")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")


class DBConfigLoader:
    """数据库配置加载器"""
    
    @staticmethod
    def load_llm_config():
        """从数据库加载激活的LLM配置"""
        try:
            from .database import Database
            db = Database()
            return db.get_active_llm_config()
        except Exception as e:
            logger.warning(f"从数据库加载LLM配置失败: {e}")
            return None


class AppConfig:
    """应用配置管理器"""
    
    def __init__(self, config_path: str = None):
        self.yaml_loader = YAMLConfigLoader(config_path)
        # 保持向后兼容性：暴露config_path属性
        self.config_path = self.yaml_loader.config_path
        # 保持向后兼容性：暴露data属性
        self.data = self.yaml_loader.data
        self._load_llm_config()
        self._load_app_config()
        self._load_filters_config()
        self._load_strategies()
        self._load_sources()

    def _load_llm_config(self):
        """加载LLM配置（YAML + 环境变量 + 数据库）"""
        # 1. 从YAML配置加载基础值
        llm_cfg = self.yaml_loader.data.get("llm", {})
        
        # 2. 处理API Key（支持env:前缀从环境变量读取）
        api_key_raw = llm_cfg.get("api_key", "")
        if api_key_raw.startswith("env:"):
            env_key = api_key_raw[len("env:"):]
            self.llm_api_key = os.environ.get(env_key, "")
        else:
            self.llm_api_key = api_key_raw

        self.llm_provider = llm_cfg.get("provider", "openai")
        self.llm_model = llm_cfg.get("model", "gpt-4o-mini")
        self.llm_base_url = llm_cfg.get("base_url", "") or None

        # 3. 从数据库加载激活的LLM配置（优先级最高）
        db_llm_config = DBConfigLoader.load_llm_config()
        if db_llm_config:
            if db_llm_config.api_key:
                self.llm_api_key = db_llm_config.api_key
            if db_llm_config.provider:
                self.llm_provider = db_llm_config.provider
            if db_llm_config.model:
                self.llm_model = db_llm_config.model
            if db_llm_config.base_url:
                self.llm_base_url = db_llm_config.base_url

    def _load_app_config(self):
        """加载应用配置"""
        app_cfg = self.yaml_loader.data.get("app", {})
        self.max_news_per_source = app_cfg.get("max_news_per_source", 10)
        self.days_to_keep = app_cfg.get("days_to_keep", 30)
        self.host = app_cfg.get("host", "127.0.0.1")
        self.port = app_cfg.get("port", 5000)
        self.log_level = app_cfg.get("log_level", "INFO")
        self.fetch_hours = app_cfg.get("fetch_hours", 24)

    def _load_filters_config(self):
        """加载过滤器配置"""
        filters = self.yaml_loader.data.get("filters", {})
        self.keywords = filters.get("keywords", [])
        self.min_title_length = filters.get("min_title_length", 8)

    def _load_strategies(self):
        """加载策略配置"""
        self.strategies = self.yaml_loader.data.get("strategies", [])

    def _load_sources(self):
        """加载新闻源配置"""
        self.news_sources = self.yaml_loader.data.get("news_sources", [])

    def __repr__(self):
        return (
            f"AppConfig(llm_provider={self.llm_provider}, "
            f"llm_model={self.llm_model}, sources={len(self.news_sources)}, "
            f"keywords={len(self.keywords)})"
        )

    def save_sources(self, sources: list):
        self.yaml_loader.data["news_sources"] = sources
        self.news_sources = sources
        self.yaml_loader.save()

    def save_app_config(self, app_config: dict):
        self.yaml_loader.data["app"] = app_config
        self._load_app_config()
        self.yaml_loader.save()

    def save_keywords(self, keywords: list):
        if "filters" not in self.yaml_loader.data:
            self.yaml_loader.data["filters"] = {}
        self.yaml_loader.data["filters"]["keywords"] = keywords
        self.keywords = keywords
        self.yaml_loader.save()

    def save_strategies(self, strategies: list):
        self.yaml_loader.data["strategies"] = strategies
        self.strategies = strategies
        self.yaml_loader.save()
