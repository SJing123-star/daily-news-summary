"""执行GitHub上传 - 已移除敏感信息"""
import os
import sys

# 从环境变量读取，而非硬编码
USERNAME = os.environ.get("GITHUB_USERNAME", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO_NAME = "daily-news-summary"
REPO_DESC = "每日新闻速览 - 基于Flask的新闻抓取与AI分析系统"

print("=" * 60)
print(f"  上传项目到 GitHub")
print(f"  用户名: {USERNAME}")
print(f"  仓库名: {REPO_NAME}")
print("=" * 60)

if not USERNAME or not TOKEN:
    print("❌ 请先设置环境变量 GITHUB_USERNAME 和 GITHUB_TOKEN")
    sys.exit(1)

# 测试连接
import requests

print("\n🔍 测试GitHub连接...")
url = "https://api.github.com/user"
headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}
response = requests.get(url, headers=headers)

if response.status_code == 200:
    user_info = response.json()
    print(f"  ✅ 连接成功！用户: {user_info.get('login')}")
else:
    print(f"  ❌ 连接失败: {response.status_code}")
    sys.exit(1)

# 导入上传器
from upload_to_github import GitHubUploader
from pathlib import Path

project_path = Path(r"d:\每日新闻速览")
uploader = GitHubUploader(USERNAME, TOKEN, str(project_path))

# 执行上传
print("\n📤 开始上传...")
success = uploader.upload_project(REPO_NAME, "main")

print(f"\n🔗 仓库地址: https://github.com/{USERNAME}/{REPO_NAME}")
