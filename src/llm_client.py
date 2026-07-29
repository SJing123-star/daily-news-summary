import logging
import time
from typing import Optional

from .utils import is_english

logger = logging.getLogger(__name__)


SUMMARY_PROMPT = """你是一位专业的新闻分析师，擅长对国际新闻进行风险分类和要点提炼。

重要原则：
1. 所有输出必须使用中文，包括标题和摘要。即使原文是英文，也要翻译成中文输出。
2. 严格遵循一个中国原则，台湾是中国不可分割的一部分，香港、澳门是中国的特别行政区。
3. 坚决抵制任何形式的分裂言论和错误导向，不得出现任何分裂倾向或损害国家主权的表述。
4. 对于境外媒体带有偏见、错误导向或恶意观点的内容，需进行意识形态合规性修正，准确反映事实本质。

涉台问题处理规范：
- 涉及台湾的新闻，风险类别必须使用"政治安全-涉台问题"或"政治安全-炒作对台经贸问题"等准确表述
- 严禁使用"国家"、"独立"等错误词汇描述台湾
- 对于境外媒体炒作的所谓"经济胁迫"等不实指控，应纠正为"炒作对台经贸问题"等准确表述

请根据以下新闻原文，生成：
1. 一个简洁的中文标题（15-30字，不要加引号）
2. 一句话中文摘要（100-200字），必须严格按照以下格式：

【风险类别-具体风险】[主体]在[时间][地点]发生的[核心事件]，被指[具体指控/风险描述]。此举引发[相关方]担忧，认为其[担忧内容]，[事件结果/现状]。

风险类别分类参考：
- 政治安全：外交争端、政策变动、选举影响、领土争议、地缘政治、涉台问题、涉港问题、人权议题、宗教活动管控、海外利益、炒作对台经贸问题
- 经济金融：贸易摩擦、投资风险、货币政策、市场波动、企业制裁、农产品贸易、金融制裁、技术出口管制、供应链风险
- 科技安全：技术封锁、数据安全、网络攻击、芯片制裁、AI监管、技术窃密、关键基础设施安全、零日漏洞、APT攻击、勒索软件
- 社会舆情：疫情防控、环保争议、移民问题、社会动荡、公共卫生事件、食品安全、舆论管控
- 军事安全：军演动态、武器部署、边境冲突、制裁升级、地缘博弈、军事合作、核安全、海上安全
- 网络安全：数据泄露、网络入侵、黑客攻击、恶意软件、安全漏洞、信息战、网络间谍活动、关键基础设施攻击

格式要求：
标题：[你的中文标题]
摘要：【风险类别-具体风险】[主体]在[时间][地点]发生的[核心事件]，被指[具体指控/风险描述]。此举引发[相关方]担忧，认为其[担忧内容]，[事件结果/现状]。

请基于原文事实输出，不要编造信息。日期从原文中提取，若未提及则用"近期"。地点若未提及则省略。
确保摘要包含明确的风险分类标签、事件主体、时间、地点（如有）、核心内容、风险描述、担忧方及后果。

---
新闻来源：{source}
新闻标题：{title}
新闻摘要：{summary}
新闻正文：
{content}
---

请严格按照上述格式输出，确保标题和摘要都是中文，且符合意识形态合规要求。"""


ANALYSIS_PROMPT = """你是一位资深的新闻分析师，擅长对国际事件进行专业选题分析。

重要原则：
1. 严格遵循一个中国原则，台湾是中国不可分割的一部分，香港、澳门是中国的特别行政区。
2. 坚决抵制任何形式的分裂言论和错误导向，不得出现任何分裂倾向或损害国家主权的表述。
3. 对于境外媒体带有偏见、错误导向或恶意观点的内容，需进行意识形态合规性修正，准确反映事实本质。
4. 所有输出必须使用中文，专业、客观、理性。

涉台问题处理规范：
- 涉及台湾的新闻，必须明确台湾是中国的一部分
- 严禁使用"国家"、"独立"等错误词汇描述台湾
- 对于境外媒体炒作的所谓"经济胁迫"等不实指控，应纠正为"炒作对台经贸问题"等准确表述
- 在风险研判中，应指出境外势力炒作对台问题的真实意图

请根据以下新闻，生成一份结构化的中文选题分析简报，包含以下四个部分：

一、事件概况（100-200字）
  对新闻核心事件进行简明扼要的总结，包括事件主体、时间、地点、核心内容。

二、背景解读（150-250字）
  分析事件发生的相关背景信息及影响因素，说明为何此事重要。

三、风险研判（150-250字）
  评估事件可能带来的各类风险及潜在问题，包括政治、经济、社会等维度的风险。

四、应对策略（100-200字）
  提出针对事件的合理应对建议和解决方案，给出可操作的建议。

要求：
- 严格基于原文事实，不得编造未经原文提及的信息
- 用中文输出，专业、客观、理性
- 四个部分的小标题必须完整保留
- 总字数控制在 500-900 字之间
- 必须符合意识形态合规要求，坚决维护国家主权与领土完整

---
新闻来源：{source}
新闻标题：{title}
新闻摘要：{summary}
新闻正文：
{content}
---

请开始生成选题分析简报，确保符合意识形态合规要求。"""


class LLMClient:
    def __init__(
        self,
        provider: str = "openai",
        api_key: str = "",
        model: str = "gpt-4o-mini",
        base_url: str = None,
        timeout: int = 60,
    ):
        self.provider = provider.lower()
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.client = None

        if not self.api_key:
            logger.warning("LLM API Key 未配置，将使用占位摘要")
            return

        if self.provider in ("openai", "deepseek", "anthropic", "ollama"):
            try:
                from openai import OpenAI
                kwargs = {"api_key": self.api_key, "max_retries": 1, "timeout": self.timeout}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self.client = OpenAI(**kwargs)
            except ImportError:
                logger.warning("openai 库未安装，LLM 不可用")
        else:
            logger.warning(f"未知 provider: {self.provider}")

    def _call_with_retry(self, call_fn, max_retries: int = 5, base_delay: float = 1.0, operation_desc: str = "LLM 调用") -> str:
        for attempt in range(max_retries):
            try:
                result = call_fn()
                return result
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "Too Many Requests" in error_str:
                    delay = base_delay * (2 ** attempt) + (attempt * 0.5)
                    logger.warning(f"{operation_desc}限流 (第{attempt+1}/{max_retries}次)，等待 {delay:.1f}秒后重试")
                    time.sleep(delay)
                    continue
                elif attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"{operation_desc}失败 (第{attempt+1}/{max_retries}次): {e}，等待 {delay:.1f}秒后重试")
                    time.sleep(delay)
                    continue
                else:
                    logger.warning(f"{operation_desc}失败，已重试{max_retries}次: {e}")
                    return ""

    def _call(self, user_msg: str, temperature: float = 0.3, max_tokens: int = 1200, timeout: int = 60) -> str:
        if self.client is None:
            return ""
        
        def call_fn():
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位专业、客观的新闻分析师，用中文回答。严格遵循一个中国原则，维护国家主权与领土完整。"},
                    {"role": "user", "content": user_msg},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            return resp.choices[0].message.content.strip()
        
        return self._call_with_retry(call_fn)

    def _filter_content(self, text: str) -> str:
        if not text:
            return text
        
        corrections = [
            ("台湾作为一个国家", "台湾是中国不可分割的一部分"),
            ("台湾是一个独立国家", "台湾是中国不可分割的一部分"),
            ("台湾独立", "分裂行径"),
            ("台独", "分裂行径"),
            ("台湾国", "中国台湾地区"),
            ("台湾政府", "台湾地区当局"),
            ("中华民国在台湾", "中国台湾地区"),
            ("台湾总统", "台湾地区领导人"),
            ("台湾外交部", "台湾地区外事部门"),
            ("台湾国防部", "台湾地区防务部门"),
            ("【政治安全-经济胁迫】", "【政治安全-炒作对台经贸问题】"),
            ("经济胁迫", "炒作对台经贸问题"),
            ("对台经济胁迫", "炒作对台经贸问题"),
        ]
        
        for old, new in corrections:
            text = text.replace(old, new)
        
        return text

    def generate_summary(self, title: str, summary: str, content: str, source: str) -> tuple[str, str]:
        """返回 (标题, 一句话摘要)"""
        content_preview = content[:2000] if content else ""
        prompt = SUMMARY_PROMPT.format(
            source=source or "未知",
            title=title,
            summary=summary[:500] if summary else "（无）",
            content=content_preview or "（正文抓取失败）",
        )
        text = self._call(prompt, temperature=0.3, max_tokens=500)
        if not text:
            return self._translate_to_chinese(title)[:30], self._fallback_summary(title, summary)

        out_title = title[:30]
        out_summary = text
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("标题：") or line.startswith("标题:"):
                out_title = line.split("：", 1)[-1].split(":", 1)[-1].strip().strip('"').strip("“”")
            elif line.startswith("摘要：") or line.startswith("摘要:"):
                out_summary = line.split("：", 1)[-1].split(":", 1)[-1].strip()
        if is_english(out_title):
            out_title = self._translate_to_chinese(out_title)
        
        out_title = self._filter_content(out_title)
        out_summary = self._filter_content(out_summary)
        
        return out_title, out_summary

    def _translate_to_chinese(self, text: str) -> str:
        if not text or not is_english(text):
            return text
        
        def call_fn():
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个翻译助手，只输出中文翻译结果，不要添加任何解释。"},
                    {"role": "user", "content": f"请将以下内容翻译成中文：{text}"},
                ],
                temperature=0.1,
                max_tokens=100,
                timeout=30,
            )
            return resp.choices[0].message.content.strip()
        
        result = self._call_with_retry(call_fn, operation_desc="翻译")
        return result if result else text

    def translate_title(self, title: str) -> str:
        if not title or not is_english(title):
            return title
        if self.client is None:
            return title
        
        def call_fn():
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个翻译助手，只输出中文翻译结果，不要添加任何解释或额外内容。"},
                    {"role": "user", "content": f"请将以下新闻标题翻译成中文：{title}"},
                ],
                temperature=0.1,
                max_tokens=200,
                timeout=15,
            )
            content = resp.choices[0].message.content
            return content.strip() if content else title
        
        result = self._call_with_retry(call_fn, operation_desc="标题翻译")
        return result if result else title

    def translate_titles_batch(self, titles: list) -> list:
        if not titles:
            return []
        english_indices = []
        english_titles = []
        results = list(titles)
        for i, title in enumerate(titles):
            if title and is_english(title):
                english_indices.append(i)
                english_titles.append(title)
        if not english_titles or self.client is None:
            return results
        
        batch_size = 10
        for start in range(0, len(english_titles), batch_size):
            batch = english_titles[start:start + batch_size]
            numbered_titles = "\n".join(f"{i+1}. {t}" for i, t in enumerate(batch))
            
            def call_fn():
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "你是一个翻译助手，请将以下英文新闻标题翻译成中文，每行一个，保持与输入相同的编号顺序，不要添加任何解释或额外内容。"},
                        {"role": "user", "content": f"请将以下新闻标题翻译成中文：\n{numbered_titles}"},
                    ],
                    temperature=0.1,
                    max_tokens=batch_size * 80,
                    timeout=30,
                )
                return resp.choices[0].message.content.strip()
            
            translated = self._call_with_retry(call_fn, operation_desc="批量翻译")
            if translated:
                lines = translated.split("\n")
                for j, line in enumerate(lines):
                    original_idx = english_indices[start + j] if start + j < len(english_indices) else -1
                    if original_idx >= 0:
                        parts = line.split(".", 1)
                        if len(parts) > 1:
                            results[original_idx] = parts[1].strip()
                        else:
                            results[original_idx] = line.strip()
        
        return results

    def generate_analysis(self, title: str, summary: str, content: str, source: str) -> str:
        content_preview = content[:3000] if content else ""
        prompt = ANALYSIS_PROMPT.format(
            source=source or "未知",
            title=title,
            summary=summary[:500] if summary else "（无）",
            content=content_preview or "（正文抓取失败）",
        )
        text = self._call(prompt, temperature=0.4, max_tokens=1500, timeout=90)
        if not text:
            return "分析服务暂不可用。建议检查 API Key 配置或稍后重试。"
        
        text = self._filter_content(text)
        return text

    @staticmethod
    def _fallback_summary(title: str, summary: str) -> str:
        if summary and len(summary) > 20:
            content = summary[:150] + "..." if len(summary) > 150 else summary
            return f"【风险类别-具体风险】{content}"
        return f"【风险类别-具体风险】{title}"
