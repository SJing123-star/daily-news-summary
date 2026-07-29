"""
GitHub项目上传脚本
使用GitHub REST API将项目上传到GitHub

使用方法:
    python upload_to_github.py

需要配置:
    在脚本下方的 CONFIG 区域填写你的GitHub信息
"""

import os
import sys
import json
import base64
import hashlib
import time
from pathlib import Path
from typing import Optional, List, Set

import requests


# ==================== CONFIGURATION ====================
# 请在这里填写你的GitHub信息

GITHUB_USERNAME = ""  # 你的GitHub用户名，例如: "microsoft"
GITHUB_TOKEN = ""     # 你的GitHub Personal Access Token

# 仓库配置
REPO_NAME = "daily-news-summary"  # 仓库名称
REPO_DESCRIPTION = "每日新闻速览 - 基于Flask的新闻抓取与AI分析系统"
REPO_PRIVATE = False  # 是否为私有仓库

# 本地项目路径
PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))

# 分支名称
BRANCH = "main"

# ==================== GITHUB API ====================
GITHUB_API = "https://api.github.com"

# ==================== FILE FILTER ====================
# 这些文件/目录会被忽略（不会上传）
IGNORE_PATTERNS = [
    # Python缓存
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".pytest_cache",
    ".coverage",
    ".mypy_cache",
    
    # 数据库和数据文件
    "news.db",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    
    # 环境配置（包含敏感信息）
    ".env",
    ".env.local",
    ".env.production",
    
    # 日志
    "*.log",
    "logs/",
    
    # 构建产物
    "build/",
    "dist/",
    "*.egg-info/",
    ".eggs/",
    
    # 编辑器和IDE
    ".vscode/",
    ".idea/",
    "*.swp",
    "*.swo",
    "*~",
    
    # 操作系统
    ".DS_Store",
    "Thumbs.db",
    "ehthumbs.db",
    
    # 临时文件
    "*.tmp",
    "*.bak",
    "*.temp",
    
    # 测试报告
    "rematch_report_*.json",
    "strategy_test_report_*.json",
    "strategy_update_report_*.json",
    "performance_report.json",
    
    # 自启动配置
    "autostart_config.json",
    
    # 配置备份
    "config.yaml.backup.*",
]


class GitHubUploader:
    """GitHub文件上传器"""
    
    def __init__(self, username: str, token: str, project_path: str):
        self.username = username
        self.token = token
        self.project_path = Path(project_path)
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHubUploader/1.0",
        })
        self._uploaded_files = 0
        self._failed_files = 0
        self._skipped_files = 0
    
    def create_repository(self, name: str, description: str = "", 
                         private: bool = False) -> bool:
        """创建GitHub仓库"""
        print(f"📦 创建仓库: {name}")
        
        # 检查仓库是否已存在
        existing_url = f"{GITHUB_API}/repos/{self.username}/{name}"
        response = self.session.get(existing_url)
        if response.status_code == 200:
            print(f"  ✅ 仓库已存在，跳过创建")
            return True
        
        # 创建新仓库
        data = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": False,  # 不自动初始化，我们会自己上传文件
        }
        
        response = self.session.post(f"{GITHUB_API}/user/repos", json=data)
        
        if response.status_code == 201:
            print(f"  ✅ 仓库创建成功")
            return True
        elif response.status_code == 422:
            print(f"  ⚠️ 仓库可能已存在")
            return True
        else:
            print(f"  ❌ 创建仓库失败: {response.status_code}")
            print(f"  {response.json()}")
            return False
    
    def get_file_sha(self, repo: str, file_path: str, 
                    branch: str = BRANCH) -> Optional[str]:
        """获取远程文件的SHA值"""
        url = f"{GITHUB_API}/repos/{self.username}/{repo}/contents/{file_path}"
        params = {"ref": branch}
        response = self.session.get(url, params=params)
        
        if response.status_code == 200:
            return response.json().get("sha")
        return None
    
    def upload_file(self, repo: str, file_path: str, 
                    branch: str = BRANCH) -> bool:
        """上传单个文件"""
        local_path = self.project_path / file_path
        if not local_path.exists():
            return False
        
        try:
            # 读取文件内容
            content = local_path.read_bytes()
            
            # 计算本地文件的SHA
            local_sha = hashlib.sha1(content).hexdigest()
            
            # 获取远程文件的SHA（如果存在）
            remote_sha = self.get_file_sha(repo, file_path, branch)
            
            # 读取.gitignore
            ignore_path = self.project_path / ".gitignore"
            ignore_content = ""
            if ignore_path.exists():
                ignore_content = ignore_path.read_text(encoding="utf-8")
            
            # 检查是否在ignore列表中
            if self._should_ignore(file_path):
                self._skipped_files += 1
                return True
            
            # 如果远程文件存在且SHA相同，跳过
            if remote_sha:
                # 比较本地和远程SHA
                # 注意：GitHub的SHA是git blob的hash，与本地文件hash不同
                # 所以我们需要总是上传，让GitHub处理版本
                pass
            
            # 编码文件内容
            if len(content) > 100 * 1024 * 1024:  # 100MB限制
                print(f"  ⚠️ 文件过大，跳过: {file_path}")
                self._skipped_files += 1
                return False
            
            encoded_content = base64.b64encode(content).decode("utf-8")
            
            # 构建请求数据
            data = {
                "message": f"upload: {file_path}",
                "content": encoded_content,
                "branch": branch,
            }
            
            # 如果远程文件存在，需要提供sha
            if remote_sha:
                data["sha"] = remote_sha
            
            # 上传文件
            url = f"{GITHUB_API}/repos/{self.username}/{repo}/contents/{file_path}"
            
            if remote_sha:
                response = self.session.put(url, json=data)
            else:
                response = self.session.put(url, json=data)
            
            if response.status_code in [200, 201]:
                self._uploaded_files += 1
                if self._uploaded_files % 10 == 0:
                    print(f"  📊 已上传 {self._uploaded_files} 个文件...")
                return True
            else:
                self._failed_files += 1
                error_msg = response.text[:200] if response.text else "未知错误"
                print(f"  ❌ 上传失败: {file_path} - {error_msg}")
                return False
                
        except Exception as e:
            self._failed_files += 1
            print(f"  ❌ 上传异常: {file_path} - {str(e)}")
            return False
    
    def upload_file_safe(self, repo: str, file_path: str, 
                         branch: str = BRANCH, retries: int = 3) -> bool:
        """安全上传文件（带重试）"""
        for attempt in range(retries):
            try:
                result = self.upload_file(repo, file_path, branch)
                return result
            except requests.exceptions.RateLimitExceeded:
                wait_time = 2 ** attempt
                print(f"  ⏳ API限流，等待 {wait_time}s...")
                time.sleep(wait_time)
            except Exception as e:
                if attempt == retries - 1:
                    print(f"  ❌ 重试{retries}次后仍失败: {file_path}")
                    return False
                time.sleep(1)
        return False
    
    def _should_ignore(self, file_path: str) -> bool:
        """检查文件是否应该被忽略"""
        path_str = str(file_path).replace("\\", "/")
        file_name = os.path.basename(path_str)
        
        # 检查.gitignore文件
        gitignore_path = self.project_path / ".gitignore"
        if gitignore_path.exists():
            try:
                import fnmatch
                patterns = gitignore_path.read_text(encoding="utf-8").splitlines()
                for pattern in patterns:
                    pattern = pattern.strip()
                    if not pattern or pattern.startswith("#"):
                        continue
                    if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(file_name, pattern):
                        return True
            except Exception:
                pass
        
        # 检查内置ignore列表
        for pattern in IGNORE_PATTERNS:
            if pattern.endswith("/"):
                # 目录模式
                dir_name = pattern[:-1]
                if dir_name in path_str.split("/"):
                    return True
            elif "*" in pattern:
                # 通配符模式
                import fnmatch
                if fnmatch.fnmatch(file_name, pattern):
                    return True
            else:
                # 精确匹配
                if path_str.endswith(pattern) or file_name == pattern:
                    return True
        
        return False
    
    def get_all_files(self) -> List[str]:
        """获取所有需要上传的文件"""
        files = []
        ignore_set: Set[str] = set()
        
        for root, dirs, filenames in os.walk(self.project_path):
            # 过滤目录
            dirs_to_remove = []
            for d in dirs:
                d_path = os.path.join(root, d)
                rel_path = os.path.relpath(d_path, self.project_path).replace("\\", "/")
                
                if self._should_ignore(rel_path + "/"):
                    ignore_set.add(rel_path)
                    dirs_to_remove.append(d)
            
            for d in dirs_to_remove:
                dirs.remove(d)
            
            # 过滤文件
            for filename in filenames:
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, self.project_path).replace("\\", "/")
                
                if not self._should_ignore(rel_path):
                    files.append(rel_path)
        
        return files
    
    def upload_project(self, repo: str, branch: str = BRANCH):
        """上传整个项目"""
        print(f"\n🚀 开始上传项目到 GitHub...")
        print(f"   用户名: {self.username}")
        print(f"   仓库名: {repo}")
        print(f"   分支: {branch}")
        print(f"   项目路径: {self.project_path}")
        
        # 获取所有文件
        all_files = self.get_all_files()
        print(f"\n📁 发现 {len(all_files)} 个文件待上传")
        
        # 创建仓库
        if not self.create_repository(repo, REPO_DESCRIPTION, REPO_PRIVATE):
            print("\n❌ 无法创建仓库，上传终止")
            return False
        
        print("\n📤 开始上传文件...")
        
        # 逐个上传文件
        for i, file_path in enumerate(all_files, 1):
            print(f"  [{i}/{len(all_files)}] {file_path}")
            self.upload_file_safe(repo, file_path, branch)
            
            # 避免API限流（每小时5000次）
            if i % 100 == 0:
                print(f"  ⏳ 进度: {i}/{len(all_files)}，等待1秒避免限流...")
                time.sleep(1)
        
        # 打印结果
        print(f"\n{'='*50}")
        print(f"📊 上传完成！")
        print(f"   ✅ 成功上传: {self._uploaded_files} 个文件")
        print(f"   ⏭️  跳过文件: {self._skipped_files} 个")
        print(f"   ❌ 失败文件: {self._failed_files} 个")
        print(f"\n🔗 仓库地址: https://github.com/{self.username}/{repo}")
        
        return self._failed_files == 0


def test_connection(username: str, token: str) -> bool:
    """测试GitHub连接"""
    print("🔍 测试GitHub连接...")
    
    url = f"{GITHUB_API}/user"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print(f"  ✅ 连接成功！用户: {data.get('login', '未知')}")
        return True
    elif response.status_code == 401:
        print(f"  ❌ 认证失败，请检查Token是否正确")
        return False
    else:
        print(f"  ❌ 连接失败: {response.status_code}")
        return False


def main():
    """主函数"""
    global GITHUB_USERNAME, GITHUB_TOKEN
    
    print("=" * 60)
    print("  GitHub 项目上传工具")
    print("=" * 60)
    
    # 检查配置
    if not GITHUB_USERNAME or not GITHUB_TOKEN:
        print("\n⚠️  请先配置 GitHub 信息！")
        print("\n需要提供:")
        print("  1. GitHub 用户名")
        print("  2. GitHub Personal Access Token")
        print("\n获取Token:")
        print("  1. 访问 https://github.com/settings/tokens")
        print("  2. 点击 'Generate new token (classic)'")
        print("  3. 权限选择: repo (完整的仓库控制)")
        print("  4. 生成后复制Token")
        print("\n⚠️  Token只会显示一次，请妥善保存！")
        
        # 交互式输入
        print("\n" + "-" * 40)
        print("请输入GitHub信息:")
        
        username = input("GitHub用户名: ").strip()
        if not username:
            print("❌ 用户名不能为空")
            return
        
        token = input("GitHub Token: ").strip()
        if not token:
            print("❌ Token不能为空")
            return
        
        GITHUB_USERNAME = username
        GITHUB_TOKEN = token
    
    # 测试连接
    if not test_connection(GITHUB_USERNAME, GITHUB_TOKEN):
        return
    
    # 创建上传器
    uploader = GitHubUploader(GITHUB_USERNAME, GITHUB_TOKEN, PROJECT_PATH)
    
    # 执行上传
    success = uploader.upload_project(REPO_NAME, BRANCH)
    
    if success:
        print("\n🎉 项目已成功上传到GitHub！")
    else:
        print("\n⚠️  部分文件上传失败，请检查日志")


if __name__ == "__main__":
    main()
