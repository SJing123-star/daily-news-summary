"""
API认证测试脚本
验证API认证装饰器是否正确生效

测试场景：
1. 未认证请求受保护的API端点 - 应返回401/403
2. 使用有效API密钥请求 - 应成功
3. 使用无效API密钥请求 - 应返回403
"""
import requests
import json

BASE_URL = "http://127.0.0.1:5000"

# 测试配置
TEST_CONFIG = {
    "api_key": "",  # 从环境变量读取或手动设置
    "test_endpoints": [
        # (URL, Method, 需要认证, 描述)
        ("/api/collect", "POST", True, "新闻抓取 - require_api_key"),
        ("/api/clear", "POST", True, "清空数据 - require_admin"),
        ("/api/rematch", "POST", True, "重新匹配 - require_admin"),
        ("/api/llm/configs", "GET", True, "获取LLM配置列表 - require_admin"),
        ("/api/llm/configs", "POST", True, "创建LLM配置 - require_admin"),
        ("/api/strategies", "GET", True, "获取策略列表 - require_admin"),
        ("/api/strategies", "POST", True, "保存策略 - require_admin"),
        ("/api/subscriptions", "POST", True, "保存订阅 - require_admin"),
        ("/api/config", "POST", True, "保存配置 - require_admin"),
        ("/api/autostart/enable", "POST", True, "启用自启动 - require_admin"),
        ("/api/autostart/disable", "POST", True, "禁用自启动 - require_admin"),
        ("/api/news/filter", "GET", True, "新闻筛选 - require_api_key"),
        ("/api/test-source", "POST", True, "测试新闻源 - require_admin"),
        ("/api/llm/test/1", "POST", True, "测试LLM - require_admin"),
        ("/api/collect/progress", "GET", False, "抓取进度 - 公共接口"),
        ("/api/rematch/progress", "GET", False, "匹配进度 - 公共接口"),
    ]
}


def test_unauthenticated_requests():
    """测试未认证请求"""
    print("\n" + "=" * 70)
    print("【测试场景1】未认证请求受保护的API端点")
    print("=" * 70)
    
    failed_tests = []
    
    for url, method, requires_auth, desc in TEST_CONFIG["test_endpoints"]:
        full_url = f"{BASE_URL}{url}"
        
        try:
            if method.upper() == "GET":
                resp = requests.get(full_url, timeout=5)
            elif method.upper() == "POST":
                resp = requests.post(full_url, json={}, timeout=5)
            else:
                continue
            
            if requires_auth:
                # 未认证请求受保护端点应该返回401或403
                if resp.status_code in (401, 403):
                    print(f"✅ [{resp.status_code}] {method} {url}")
                    print(f"   {desc}")
                    print(f"   响应: {resp.json().get('error', '')}")
                else:
                    print(f"❌ [{resp.status_code}] {method} {url}")
                    print(f"   {desc}")
                    print(f"   警告: 未认证请求成功了！")
                    failed_tests.append(f"未认证请求成功: {method} {url}")
            else:
                # 公共接口应该正常响应
                if resp.status_code == 200:
                    print(f"✅ [{resp.status_code}] {method} {url}")
                    print(f"   {desc}")
                else:
                    print(f"⚠️ [{resp.status_code}] {method} {url}")
                    print(f"   {desc}")
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 请求失败: {method} {url}")
            print(f"   错误: {e}")
            failed_tests.append(f"请求失败: {method} {url}")
        
        print()
    
    return failed_tests


def test_with_invalid_api_key():
    """测试使用无效API密钥"""
    print("\n" + "=" * 70)
    print("【测试场景2】使用无效API密钥请求")
    print("=" * 70)
    
    invalid_keys = ["invalid_key_123", "sk-xxxx", "test_key", ""]
    test_endpoint = "/api/collect"
    full_url = f"{BASE_URL}{test_endpoint}"
    
    failed_tests = []
    
    for api_key in invalid_keys:
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key
        
        try:
            resp = requests.post(full_url, json={}, headers=headers, timeout=5)
            
            if resp.status_code == 401 or resp.status_code == 403:
                print(f"✅ [{resp.status_code}] 无效密钥 '{api_key[:10]}...'")
            else:
                print(f"❌ [{resp.status_code}] 无效密钥 '{api_key[:10]}...'")
                print(f"   警告: 无效密钥被接受了！")
                failed_tests.append(f"无效密钥被接受: {api_key}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 请求失败: {e}")
            failed_tests.append(f"请求失败: {api_key}")
    
    return failed_tests


def test_with_valid_api_key(api_key):
    """测试使用有效API密钥"""
    print("\n" + "=" * 70)
    print("【测试场景3】使用有效API密钥请求")
    print("=" * 70)
    
    if not api_key:
        print("⚠️ 未配置有效API密钥，跳过此测试")
        return []
    
    headers = {"X-API-Key": api_key}
    failed_tests = []
    
    # 测试 require_api_key 装饰的端点
    print("\n--- require_api_key 端点 ---")
    api_key_endpoints = [
        ("/api/collect", "POST"),
        ("/api/news/filter?start_date=2024-01-01&end_date=2024-01-02", "GET"),
    ]
    
    for url, method in api_key_endpoints:
        full_url = f"{BASE_URL}{url}"
        
        try:
            if method.upper() == "GET":
                resp = requests.get(full_url, headers=headers, timeout=5)
            elif method.upper() == "POST":
                resp = requests.post(full_url, json={}, headers=headers, timeout=5)
            
            if resp.status_code == 200 or resp.status_code == 429:  # 429是正在执行中的正常响应
                print(f"✅ [{resp.status_code}] {method} {url}")
            else:
                print(f"❌ [{resp.status_code}] {method} {url}")
                print(f"   响应: {resp.text[:100]}")
                failed_tests.append(f"有效密钥请求失败: {method} {url}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 请求失败: {method} {url}")
            failed_tests.append(f"请求失败: {method} {url}")
    
    # 测试 require_admin 装饰的端点
    print("\n--- require_admin 端点 ---")
    admin_endpoints = [
        ("/api/llm/configs", "GET"),
        ("/api/strategies", "GET"),
    ]
    
    for url, method in admin_endpoints:
        full_url = f"{BASE_URL}{url}"
        
        try:
            if method.upper() == "GET":
                resp = requests.get(full_url, headers=headers, timeout=5)
            elif method.upper() == "POST":
                resp = requests.post(full_url, json={}, headers=headers, timeout=5)
            
            if resp.status_code == 200:
                print(f"✅ [{resp.status_code}] {method} {url}")
            else:
                print(f"❌ [{resp.status_code}] {method} {url}")
                print(f"   响应: {resp.text[:100]}")
                failed_tests.append(f"有效密钥请求失败: {method} {url}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 请求失败: {method} {url}")
            failed_tests.append(f"请求失败: {method} {url}")
    
    return failed_tests


def test_different_auth_methods(api_key):
    """测试不同的认证方式"""
    print("\n" + "=" * 70)
    print("【测试场景4】不同认证方式测试")
    print("=" * 70)
    
    if not api_key:
        print("⚠️ 未配置有效API密钥，跳过此测试")
        return []
    
    test_url = f"{BASE_URL}/api/collect"
    failed_tests = []
    
    auth_methods = [
        ("Authorization: Bearer", {"Authorization": f"Bearer {api_key}"}),
        ("X-API-Key", {"X-API-Key": api_key}),
        ("Query parameter", {}, {"api_key": api_key}),
    ]
    
    for method_name, headers, params in auth_methods:
        try:
            resp = requests.post(test_url, json={}, headers=headers, params=params, timeout=5)
            
            if resp.status_code == 200 or resp.status_code == 429:
                print(f"✅ [{resp.status_code}] {method_name}")
            else:
                print(f"❌ [{resp.status_code}] {method_name}")
                print(f"   响应: {resp.text[:100]}")
                failed_tests.append(f"认证方式失败: {method_name}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 请求失败: {method_name}")
            failed_tests.append(f"请求失败: {method_name}")
    
    return failed_tests


def main():
    print("=" * 70)
    print("API认证测试脚本")
    print("验证API认证装饰器是否正确生效")
    print("=" * 70)
    
    # 从环境变量获取API密钥
    import os
    api_key = os.environ.get("API_KEYS", "").split(",")[0].strip() or TEST_CONFIG["api_key"]
    
    if api_key:
        print(f"\n使用API密钥: {api_key[:8]}...")
    else:
        print("\n⚠️ 未检测到API_KEYS环境变量，部分测试将跳过")
    
    all_failed = []
    
    # 运行所有测试
    all_failed.extend(test_unauthenticated_requests())
    all_failed.extend(test_with_invalid_api_key())
    all_failed.extend(test_with_valid_api_key(api_key))
    all_failed.extend(test_different_auth_methods(api_key))
    
    # 输出总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    if all_failed:
        print(f"❌ 发现 {len(all_failed)} 个安全问题:")
        for i, issue in enumerate(all_failed, 1):
            print(f"   {i}. {issue}")
        return 1
    else:
        print("✅ 所有测试通过，API认证装饰器工作正常")
        return 0


if __name__ == "__main__":
    exit(main())
