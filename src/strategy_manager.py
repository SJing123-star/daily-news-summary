import re
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

class MatchPattern:
    EXACT = "exact"
    FUZZY = "fuzzy"
    REGEX = "regex"
    CONTAINS = "contains"

class TokenizerType:
    NONE = "none"
    CHINESE = "chinese"
    ENGLISH = "english"

class WeightMethod:
    TERM_FREQUENCY = "tf"
    INVERSE_DOCUMENT_FREQUENCY = "idf"
    POSITION = "position"
    COMBINED = "combined"

class MatchScope:
    TITLE = "title"
    CONTENT = "content"
    BOTH = "both"

class KeywordMatchingStrategy(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get("name", "Unknown")
        self.site_type = config.get("site_type", "default")
        self.strategy_class = config.get("strategy_class", "default")
        self.tokenizer_type = config.get("tokenizer", TokenizerType.NONE)
        self.match_pattern = config.get("match_pattern", MatchPattern.CONTAINS)
        self.weight_method = config.get("weight_method", WeightMethod.COMBINED)
        self.threshold = config.get("threshold", 0.5)
        self.stop_words = config.get("stop_words", [])
        self.keywords = config.get("keywords", [])
        self.match_scope = config.get("match_scope", MatchScope.TITLE)

    @abstractmethod
    def tokenize(self, text: str) -> List[str]:
        pass

    @abstractmethod
    def match(self, title: str, summary: str = "") -> Tuple[bool, float, List[str]]:
        pass

    def _apply_stop_words(self, tokens: List[str]) -> List[str]:
        return [t for t in tokens if t.lower() not in self.stop_words]

    def _calculate_weight(self, text: str, keywords: List[str]) -> float:
        tokens = self.tokenize(text)
        tokens = self._apply_stop_words(tokens)
        
        if self.weight_method == WeightMethod.TERM_FREQUENCY:
            return self._tf_weight(tokens, keywords)
        elif self.weight_method == WeightMethod.POSITION:
            return self._position_weight(text, keywords)
        elif self.weight_method == WeightMethod.INVERSE_DOCUMENT_FREQUENCY:
            return self._idf_weight(tokens, keywords)
        else:
            return (self._tf_weight(tokens, keywords) + self._position_weight(text, keywords)) / 2

    def _tf_weight(self, tokens: List[str], keywords: List[str]) -> float:
        if not tokens or not keywords:
            return 0.0
        text_lower = " ".join(tokens).lower()
        matches = sum(1 for kw in keywords if self._is_keyword_match_word_boundary(text_lower, kw.lower()))
        return matches / len(keywords)

    def _is_keyword_match_word_boundary(self, text_lower: str, kw_lower: str) -> bool:
        """检查关键词是否在文本中匹配（考虑单词边界）"""
        if kw_lower.encode('utf-8').isascii():
            # 英文关键词，使用单词边界
            pattern = r'(?:^|[^\w]|[\u4e00-\u9fff])' + re.escape(kw_lower) + r'(?:$|[^\w]|[\u4e00-\u9fff])'
            return bool(re.search(pattern, text_lower))
        else:
            # 中文关键词，直接包含匹配
            return kw_lower in text_lower

    def _position_weight(self, text: str, keywords: List[str]) -> float:
        if not text or not keywords:
            return 0.0
        score = 0.0
        text_lower = text.lower()
        for kw in keywords:
            kw_lower = kw.lower()
            if self._is_keyword_match_word_boundary(text_lower, kw_lower):
                idx = text_lower.find(kw_lower)
                position_factor = max(0.3, 1.0 - idx / len(text))
                score += position_factor
        return score / len(keywords) if keywords else 0.0

    def _idf_weight(self, tokens: List[str], keywords: List[str]) -> float:
        """
        计算IDF权重（Inverse Document Frequency）
        
        注意：标准IDF需要文档集合统计，这里使用简化版本：
        根据关键词在当前文本中的匹配情况来计算权重
        """
        if not tokens or not keywords:
            return 0.0
        
        text_lower = " ".join(tokens).lower()
        matches = sum(1 for kw in keywords if self._is_keyword_match_word_boundary(text_lower, kw.lower()))
        
        if matches == 0:
            return 0.0
        
        # IDF计算：匹配的关键词越多，权重越高（因为关键词覆盖度高）
        # 同时考虑关键词在文本中的分布
        coverage_ratio = matches / len(keywords)
        
        # 计算关键词在文本中的出现频率
        total_kw_occurrences = sum(
            len(re.findall(r'(?:^|[^\w]|[\u4e00-\u9fff])' + re.escape(kw.lower()) + r'(?:$|[^\w]|[\u4e00-\u9fff])', text_lower))
            for kw in keywords
        )
        
        # 综合权重：覆盖度 * (出现频率 + 1) / 文本长度
        text_len = len(text_lower) or 1
        frequency_factor = (total_kw_occurrences + 1) / text_len
        
        return min(1.0, coverage_ratio * 0.7 + frequency_factor * 10)

class ChineseKeywordStrategy(KeywordMatchingStrategy):
    def tokenize(self, text: str) -> List[str]:
        import jieba
        try:
            return jieba.lcut(text)
        except Exception:
            return list(text)

    def match(self, title: str, summary: str = "") -> Tuple[bool, float, List[str]]:
        if self.match_scope == MatchScope.TITLE:
            match_text = title
        elif self.match_scope == MatchScope.CONTENT:
            match_text = summary
        else:
            match_text = title + " " + summary
        
        matched_keywords = []
        
        for kw in self.keywords:
            kw_lower = kw.lower()
            text_lower = match_text.lower()
            
            if self.match_pattern == MatchPattern.EXACT:
                if kw_lower == text_lower.strip():
                    matched_keywords.append(kw)
            elif self.match_pattern == MatchPattern.FUZZY:
                kw_chars = set(kw_lower)
                text_chars = set(text_lower)
                intersection = kw_chars & text_chars
                if len(intersection) >= len(kw_chars) * 0.7:
                    matched_keywords.append(kw)
            elif self.match_pattern == MatchPattern.REGEX:
                try:
                    if re.search(kw_lower, text_lower):
                        matched_keywords.append(kw)
                except re.error:
                    if kw_lower in text_lower:
                        matched_keywords.append(kw)
            else:
                # 使用单词边界匹配，避免子串误匹配
                # 对于英文关键词，使用正则确保匹配完整单词（考虑中英文混合文本）
                # 对于中文关键词，直接使用包含匹配（因为中文没有单词边界）
                if kw_lower.encode('utf-8').isascii():
                    # 英文关键词，使用单词边界
                    # 匹配规则：关键词前后是空白、标点、中文字符或文本边界
                    pattern = r'(?:^|[^\w]|[\u4e00-\u9fff])' + re.escape(kw_lower) + r'(?:$|[^\w]|[\u4e00-\u9fff])'
                    if re.search(pattern, text_lower):
                        matched_keywords.append(kw)
                else:
                    # 中文关键词，直接包含匹配
                    if kw_lower in text_lower:
                        matched_keywords.append(kw)
        
        weight = self._calculate_weight(match_text, self.keywords)
        is_match = weight >= self.threshold or len(matched_keywords) > 0
        
        return is_match, weight, matched_keywords

class EnglishKeywordStrategy(KeywordMatchingStrategy):
    def tokenize(self, text: str) -> List[str]:
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
        tokens = text.lower().split()
        return tokens

    def match(self, title: str, summary: str = "") -> Tuple[bool, float, List[str]]:
        if self.match_scope == MatchScope.TITLE:
            match_text = title
        elif self.match_scope == MatchScope.CONTENT:
            match_text = summary
        else:
            match_text = title + " " + summary
        
        matched_keywords = []
        
        for kw in self.keywords:
            kw_lower = kw.lower()
            text_lower = match_text.lower()
            
            if self.match_pattern == MatchPattern.EXACT:
                if kw_lower == text_lower.strip():
                    matched_keywords.append(kw)
            elif self.match_pattern == MatchPattern.FUZZY:
                words = text_lower.split()
                for word in words:
                    if self._fuzzy_match(kw_lower, word):
                        matched_keywords.append(kw)
                        break
            elif self.match_pattern == MatchPattern.REGEX:
                try:
                    if re.search(kw_lower, text_lower):
                        matched_keywords.append(kw)
                except re.error:
                    if kw_lower in text_lower:
                        matched_keywords.append(kw)
            else:
                # 使用单词边界匹配，避免子串误匹配
                if kw_lower.encode('utf-8').isascii():
                    pattern = r'(?:^|[^\w]|[\u4e00-\u9fff])' + re.escape(kw_lower) + r'(?:$|[^\w]|[\u4e00-\u9fff])'
                    if re.search(pattern, text_lower):
                        matched_keywords.append(kw)
                else:
                    if kw_lower in text_lower:
                        matched_keywords.append(kw)
        
        weight = self._calculate_weight(match_text, self.keywords)
        is_match = weight >= self.threshold or len(matched_keywords) > 0
        
        return is_match, weight, matched_keywords

    def _fuzzy_match(self, pattern: str, text: str) -> bool:
        max_dist = max(1, len(pattern) // 3)
        return self._levenshtein_distance(pattern, text) <= max_dist

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

class DefaultKeywordStrategy(KeywordMatchingStrategy):
    def tokenize(self, text: str) -> List[str]:
        return text.lower().split()

    def match(self, title: str, summary: str = "") -> Tuple[bool, float, List[str]]:
        if self.match_scope == MatchScope.TITLE:
            match_text = title
        elif self.match_scope == MatchScope.CONTENT:
            match_text = summary
        else:
            match_text = title + " " + summary
        
        matched_keywords = []
        
        for kw in self.keywords:
            kw_lower = kw.lower()
            text_lower = match_text.lower()
            
            if self.match_pattern == MatchPattern.REGEX:
                try:
                    if re.search(kw_lower, text_lower):
                        matched_keywords.append(kw)
                except re.error:
                    if kw_lower in text_lower:
                        matched_keywords.append(kw)
            else:
                # 使用单词边界匹配，避免子串误匹配
                if kw_lower.encode('utf-8').isascii():
                    pattern = r'(?:^|[^\w]|[\u4e00-\u9fff])' + re.escape(kw_lower) + r'(?:$|[^\w]|[\u4e00-\u9fff])'
                    if re.search(pattern, text_lower):
                        matched_keywords.append(kw)
                else:
                    if kw_lower in text_lower:
                        matched_keywords.append(kw)
        
        weight = self._calculate_weight(match_text, self.keywords)
        is_match = weight >= self.threshold or len(matched_keywords) > 0
        
        return is_match, weight, matched_keywords

class StrategyManager:
    STRATEGY_CLASSES = {
        "chinese": ChineseKeywordStrategy,
        "english": EnglishKeywordStrategy,
        "default": DefaultKeywordStrategy,
    }

    def __init__(self, strategies: List[Dict[str, Any]] = None):
        self.strategies: Dict[str, KeywordMatchingStrategy] = {}
        self.site_type_map: Dict[str, str] = {}
        if strategies:
            self.load_strategies(strategies)

    def load_strategies(self, strategies: List[Dict[str, Any]]):
        for config in strategies:
            site_type = config.get("site_type", "default")
            strategy_class_name = config.get("strategy_class", site_type)
            strategy_class = self.STRATEGY_CLASSES.get(strategy_class_name, DefaultKeywordStrategy)
            self.strategies[site_type] = strategy_class(config)
            
            domain_patterns = config.get("domain_patterns", [])
            for pattern in domain_patterns:
                self.site_type_map[pattern.lower()] = site_type

    def get_strategy_for_url(self, url: str) -> KeywordMatchingStrategy:
        url_lower = url.lower()
        for pattern, site_type in self.site_type_map.items():
            if pattern in url_lower:
                return self.strategies.get(site_type, self.get_default_strategy())
        return self.get_default_strategy()

    def get_strategy_for_site_type(self, site_type: str) -> KeywordMatchingStrategy:
        """根据策略类型获取策略，如果不存在则返回默认策略"""
        if site_type and site_type in self.strategies:
            return self.strategies[site_type]
        return self.get_default_strategy()

    def get_strategy(self, site_type: str) -> Optional[KeywordMatchingStrategy]:
        return self.strategies.get(site_type)

    def get_default_strategy(self) -> KeywordMatchingStrategy:
        return self.strategies.get("default", DefaultKeywordStrategy({
            "name": "Default Strategy",
            "site_type": "default",
            "threshold": 0.5,
        }))

    def add_strategy(self, config: Dict[str, Any]) -> bool:
        site_type = config.get("site_type")
        if not site_type:
            logger.error("策略必须指定site_type")
            return False
        
        strategy_class_name = config.get("strategy_class", site_type)
        strategy_class = self.STRATEGY_CLASSES.get(strategy_class_name, DefaultKeywordStrategy)
        self.strategies[site_type] = strategy_class(config)
        
        domain_patterns = config.get("domain_patterns", [])
        for pattern in domain_patterns:
            self.site_type_map[pattern.lower()] = site_type
        
        logger.info(f"添加策略: {site_type} (策略类: {strategy_class_name})")
        return True

    def update_strategy(self, site_type: str, config: Dict[str, Any]) -> bool:
        if site_type not in self.strategies:
            logger.error(f"策略不存在: {site_type}")
            return False
        
        config["site_type"] = site_type
        strategy_class_name = config.get("strategy_class", site_type)
        strategy_class = self.STRATEGY_CLASSES.get(strategy_class_name, DefaultKeywordStrategy)
        self.strategies[site_type] = strategy_class(config)
        
        old_patterns = [p for p, t in self.site_type_map.items() if t == site_type]
        for pattern in old_patterns:
            del self.site_type_map[pattern]
        
        domain_patterns = config.get("domain_patterns", [])
        for pattern in domain_patterns:
            self.site_type_map[pattern.lower()] = site_type
        
        logger.info(f"更新策略: {site_type} (策略类: {strategy_class_name})")
        return True

    def delete_strategy(self, site_type: str) -> bool:
        if site_type not in self.strategies or site_type == "default":
            logger.error(f"无法删除策略: {site_type}")
            return False
        
        old_patterns = [p for p, t in self.site_type_map.items() if t == site_type]
        for pattern in old_patterns:
            del self.site_type_map[pattern]
        
        del self.strategies[site_type]
        logger.info(f"删除策略: {site_type}")
        return True

    def match(self, url: str, title: str, summary: str = "") -> Tuple[bool, float, List[str], str]:
        strategy = self.get_strategy_for_url(url)
        is_match, weight, matched_kws = strategy.match(title, summary)
        return is_match, weight, matched_kws, strategy.site_type

    def test_strategy(self, site_type: str, test_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        strategy = self.get_strategy(site_type)
        if not strategy:
            return {"error": f"策略不存在: {site_type}"}
        
        results = []
        true_positives = 0
        false_positives = 0
        true_negatives = 0
        false_negatives = 0
        
        for test_item in test_data:
            title = test_item.get("title", "")
            summary = test_item.get("summary", "")
            expected = test_item.get("expected", False)
            
            is_match, weight, matched_kws = strategy.match(title, summary)
            results.append({
                "title": title,
                "expected": expected,
                "actual": is_match,
                "weight": round(weight, 4),
                "matched_keywords": matched_kws,
                "correct": is_match == expected,
            })
            
            if expected and is_match:
                true_positives += 1
            elif expected and not is_match:
                false_negatives += 1
            elif not expected and is_match:
                false_positives += 1
            else:
                true_negatives += 1
        
        total = len(test_data)
        accuracy = (true_positives + true_negatives) / total if total > 0 else 0
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            "strategy_name": strategy.name,
            "site_type": site_type,
            "total_tests": total,
            "true_positives": true_positives,
            "false_positives": false_positives,
            "true_negatives": true_negatives,
            "false_negatives": false_negatives,
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "results": results,
        }

    def get_all_strategies(self) -> List[Dict[str, Any]]:
        strategies = []
        for site_type, strategy in self.strategies.items():
            strategies.append({
                "site_type": site_type,
                "name": strategy.name,
                "strategy_class": strategy.strategy_class,
                "tokenizer": strategy.tokenizer_type,
                "match_pattern": strategy.match_pattern,
                "weight_method": strategy.weight_method,
                "threshold": strategy.threshold,
                "stop_words": strategy.stop_words,
                "keywords": strategy.keywords,
                "match_scope": strategy.match_scope,
                "domain_patterns": [p for p, t in self.site_type_map.items() if t == site_type],
            })
        return strategies

    def register_strategy_class(self, site_type: str, strategy_class: type):
        if issubclass(strategy_class, KeywordMatchingStrategy):
            self.STRATEGY_CLASSES[site_type] = strategy_class
            logger.info(f"注册新策略类: {site_type}")
            return True
        return False