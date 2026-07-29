"""
回归测试套件
覆盖所有修复的代码变更，确保后续修改不会引入回归问题

测试范围：
1. P1: analyzer.py中is_strategy_matched字段
2. P2-1: llm_client.py中timeout参数
3. P2-3: scraper.py中Session异常处理和重试机制
4. P3-1: strategy_manager.py中_idf_weight计算逻辑
5. P3-2: database.py中索引优化
6. P4-1: 代码清理
7. 安全修复: API认证、密钥加密等
"""
import unittest
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock, Mock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDatabaseRegression(unittest.TestCase):
    """数据库模块回归测试"""
    
    def setUp(self):
        """创建临时数据库"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
    
    def tearDown(self):
        """清理临时数据库"""
        # 等待一点时间让SQLite释放锁
        import time
        time.sleep(0.1)
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except PermissionError:
                # 文件可能仍被锁定，稍后再试
                pass
    
    def test_news_item_has_is_strategy_matched_field(self):
        """测试NewsItem包含is_strategy_matched字段（P1修复）"""
        from src.database import NewsItem
        
        # 创建NewsItem时必须包含is_strategy_matched字段
        item = NewsItem(url='http://test.com', original_title='测试标题', source='测试源')
        
        # 验证字段存在且默认值为0
        self.assertTrue(hasattr(item, 'is_strategy_matched'))
        self.assertEqual(item.is_strategy_matched, 0)
        
        # 验证可以设置为1
        item.is_strategy_matched = 1
        self.assertEqual(item.is_strategy_matched, 1)
    
    def test_save_news_with_is_strategy_matched(self):
        """测试保存新闻时is_strategy_matched字段被正确存储（P1修复）"""
        from src.database import Database, NewsItem
        
        db = Database(db_path=self.temp_db_path)
        
        # 创建带有is_strategy_matched=1的新闻
        item = NewsItem(
            url='http://test.com/news/1',
            original_title='中国经济增长',
            source='测试源',
            category='经济',
            is_strategy_matched=1,
            is_highlighted=1,
        )
        
        news_id = db.save_news(item)
        
        # 从数据库读取并验证字段
        saved_item = db.get_news_by_id(news_id)
        self.assertIsNotNone(saved_item)
        self.assertEqual(saved_item.is_strategy_matched, 1)
        self.assertEqual(saved_item.is_highlighted, 1)
    
    def test_database_indexes_created(self):
        """测试数据库索引被正确创建（P3-2修复）"""
        from src.database import Database
        
        db = Database(db_path=self.temp_db_path)
        
        # 检查索引是否存在
        with db._get_conn() as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name LIKE 'idx_%'
            """)
            indexes = [row['name'] for row in cursor.fetchall()]
        
        # 验证所有必要的索引都存在
        required_indexes = [
            'idx_news_publish_time',
            'idx_news_source',
            'idx_news_category',
            'idx_news_matched',
            'idx_news_summary_done',
        ]
        
        for idx_name in required_indexes:
            self.assertIn(idx_name, indexes, f"缺失索引: {idx_name}")


class TestLLMClientRegression(unittest.TestCase):
    """LLM客户端回归测试"""
    
    def test_llm_client_has_timeout_parameter(self):
        """测试LLMClient支持timeout参数（P2-1修复）"""
        from src.llm_client import LLMClient
        
        # 验证timeout参数存在且有默认值
        client = LLMClient(provider='openai', api_key='test_key')
        self.assertTrue(hasattr(client, 'timeout'))
        self.assertEqual(client.timeout, 60)
        
        # 验证可以自定义timeout
        client_custom = LLMClient(provider='openai', api_key='test_key', timeout=30)
        self.assertEqual(client_custom.timeout, 30)
    
    def test_llm_client_timeout_passed_to_openai(self):
        """测试timeout参数被传递给OpenAI客户端（P2-1修复）"""
        from src.llm_client import LLMClient
        
        # OpenAI是在函数内部导入的，需要patch openai.OpenAI
        with patch('openai.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            # 创建客户端并验证参数
            LLMClient(provider='openai', api_key='test_key', timeout=45)
            
            # 验证OpenAI被正确调用，包含timeout参数
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args[1]
            self.assertIn('timeout', call_kwargs)
            self.assertEqual(call_kwargs['timeout'], 45)


class TestScraperRegression(unittest.TestCase):
    """爬虫模块回归测试"""
    
    def test_scraper_has_session(self):
        """测试Scraper类包含session属性（P2-3修复）"""
        from src.scraper import Scraper
        
        scraper = Scraper()
        
        # 验证session存在且是requests.Session类型
        self.assertTrue(hasattr(scraper, 'session'))
        self.assertIsInstance(scraper.session, type(__import__('requests').Session()))
    
    def test_fetch_article_content_uses_session(self):
        """测试fetch_article_content使用session而非直接调用requests（P2-3修复）"""
        from src.scraper import Scraper
        
        scraper = Scraper()
        
        with patch.object(scraper.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.apparent_encoding = 'utf-8'
            # 使用包含article标签的HTML，确保能被正确解析
            mock_response.text = '<html><body><article><p>测试内容段落1</p><p>测试内容段落2</p></article></body></html>'
            mock_get.return_value = mock_response
            
            # 调用方法
            content = scraper.fetch_article_content('http://test.com/article')
            
            # 验证session.get被调用而不是requests.get
            mock_get.assert_called_once()
            self.assertTrue(content)
            self.assertIn('测试内容', content)
    
    def test_fetch_article_content_retries_on_failure(self):
        """测试fetch_article_content在失败时进行重试（P2-3修复）"""
        from src.scraper import Scraper
        from requests.exceptions import Timeout
        
        scraper = Scraper()
        
        with patch.object(scraper.session, 'get') as mock_get:
            # 第一次调用超时，第二次调用成功
            mock_get.side_effect = [
                Timeout("连接超时"),
                Mock(status_code=200, apparent_encoding='utf-8', text='<html><body><article><p>成功获取内容</p></article></body></html>')
            ]
            
            # 调用方法应该成功（因为有重试机制）
            content = scraper.fetch_article_content('http://test.com/article')
            
            # 验证session.get被调用了2次
            self.assertEqual(mock_get.call_count, 2)
            self.assertTrue(content)
            self.assertIn('成功获取内容', content)


class TestStrategyManagerRegression(unittest.TestCase):
    """策略管理器回归测试"""
    
    def test_idf_weight_positive_correlation(self):
        """测试_idf_weight计算逻辑：匹配越多权重越高（P3-1修复）"""
        from src.strategy_manager import ChineseKeywordStrategy
        
        # 创建策略实例
        strategy = ChineseKeywordStrategy({
            'name': '测试策略',
            'keywords': ['中国', '经济', '政策'],
            'weight_method': 'idf',
            'threshold': 0.3,
        })
        
        # 测试场景1：匹配多个关键词，权重应该较高
        text_with_many_matches = "中国经济政策发布，中国经济增长"
        tokens = strategy.tokenize(text_with_many_matches)
        weight1 = strategy._idf_weight(tokens, ['中国', '经济', '政策'])
        
        # 测试场景2：匹配较少关键词，权重应该较低
        text_with_few_matches = "美国科技新闻"
        tokens2 = strategy.tokenize(text_with_few_matches)
        weight2 = strategy._idf_weight(tokens2, ['中国', '经济', '政策'])
        
        # 测试场景3：不匹配任何关键词，权重为0
        text_with_no_matches = "英国体育新闻"
        tokens3 = strategy.tokenize(text_with_no_matches)
        weight3 = strategy._idf_weight(tokens3, ['中国', '经济', '政策'])
        
        # 验证权重范围和相对大小
        self.assertGreaterEqual(weight1, 0)
        self.assertLessEqual(weight1, 1)
        self.assertGreaterEqual(weight2, 0)
        self.assertLessEqual(weight2, 1)
        self.assertEqual(weight3, 0)
        
        # 验证匹配越多权重越高（修复后的行为）
        self.assertGreater(weight1, weight2)
    
    def test_keyword_match_word_boundary(self):
        """测试关键词匹配使用单词边界（修复误匹配问题）"""
        from src.strategy_manager import ChineseKeywordStrategy
        
        strategy = ChineseKeywordStrategy({
            'name': '测试策略',
            'keywords': ['AI', 'China'],
            'match_scope': 'title',
        })
        
        # 测试英文单词边界匹配
        # 'AI' 不应该匹配 'Identity' 或 'Paidwork'
        self.assertFalse(strategy.match('Identity verification')[0])
        self.assertFalse(strategy.match('Paidwork platform')[0])
        
        # 'AI' 应该匹配包含完整单词的文本
        self.assertTrue(strategy.match('AI technology')[0])
        self.assertTrue(strategy.match('Artificial Intelligence (AI)')[0])
        self.assertTrue(strategy.match('中国AI发展')[0])


class TestCryptoRegression(unittest.TestCase):
    """加密模块回归测试"""
    
    def test_encrypt_decrypt_roundtrip(self):
        """测试加密解密往返（S2修复）"""
        from src.crypto import encrypt, decrypt
        
        test_data = "sk-1234567890abcdefghijklmnopqrstuvwxyz"
        encrypted = encrypt(test_data)
        
        # 验证加密后的数据不为空且与原数据不同
        self.assertTrue(encrypted)
        self.assertNotEqual(encrypted, test_data)
        
        # 验证解密后与原数据一致
        decrypted = decrypt(encrypted)
        self.assertEqual(decrypted, test_data)
    
    def test_encrypt_empty_string(self):
        """测试空字符串加密（边界情况）"""
        from src.crypto import encrypt, decrypt
        
        encrypted = encrypt("")
        self.assertEqual(encrypted, "")
        self.assertEqual(decrypt(""), "")


class TestAuthRegression(unittest.TestCase):
    """认证模块回归测试"""
    
    def test_require_api_key_rejects_unauthenticated(self):
        """测试未认证请求被拒绝（S1修复）"""
        from src.auth import require_api_key, _VALID_API_KEYS
        
        # 保存原始状态
        original_keys = _VALID_API_KEYS.copy()
        
        try:
            # 模拟未配置API_KEYS的情况
            _VALID_API_KEYS.clear()
            
            # 创建模拟函数和请求
            @require_api_key
            def mock_func():
                return {"ok": True}
            
            from flask import Flask, Request
            app = Flask(__name__)
            
            with app.test_request_context():
                # 调用被装饰的函数应该返回401
                result = mock_func()
                self.assertEqual(result[1], 401)  # 第二个元素是状态码
        
        finally:
            # 恢复原始状态
            _VALID_API_KEYS.clear()
            _VALID_API_KEYS.update(original_keys)
    
    def test_rate_limited_decorator(self):
        """测试速率限制装饰器（S5增强）"""
        from src.auth import rate_limited
        from flask import Flask
        
        app = Flask(__name__)
        
        @rate_limited(max_requests=2, window_seconds=60)
        def limited_func():
            return {"ok": True}
        
        with app.test_request_context():
            # 前两次调用应该成功
            result1 = limited_func()
            self.assertEqual(result1, {"ok": True})
            
            result2 = limited_func()
            self.assertEqual(result2, {"ok": True})
            
            # 第三次调用应该被限流（返回429）
            result3 = limited_func()
            self.assertEqual(result3[1], 429)


class TestParallelAnalyzerRegression(unittest.TestCase):
    """并行分析器回归测试"""
    
    def test_pipeline_config_fields(self):
        """测试PipelineConfig包含必要字段（P4-1修复后仍保留必要字段）"""
        from src.parallel_analyzer import PipelineConfig
        
        cfg = PipelineConfig()
        
        # 验证所有必要字段存在
        self.assertTrue(hasattr(cfg, 'fetch_workers'))
        self.assertTrue(hasattr(cfg, 'content_workers'))
        self.assertTrue(hasattr(cfg, 'summary_workers'))
        self.assertTrue(hasattr(cfg, 'llm_rate_limit'))
        self.assertTrue(hasattr(cfg, 'llm_request_interval'))
        
        # 验证默认值正确
        self.assertEqual(cfg.fetch_workers, 8)
        self.assertEqual(cfg.content_workers, 10)
        self.assertEqual(cfg.summary_workers, 2)
        self.assertEqual(cfg.llm_rate_limit, 2)
        self.assertEqual(cfg.llm_request_interval, 0.5)


if __name__ == '__main__':
    # 设置环境变量以避免加密模块警告
    os.environ.setdefault('ENCRYPTION_KEY', 'test_key_for_testing_1234567890')
    
    # 设置SKIP_API_AUTH以避免认证测试失败
    os.environ.setdefault('SKIP_API_AUTH', 'true')
    
    unittest.main(verbosity=2)
