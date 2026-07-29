"""
跨平台自启动管理模块
支持 Windows / Linux / macOS 的自启动配置
"""
import os
import sys
import platform
import json
import shutil
from typing import Optional, Dict, Any


class AutoStartManager:
    """自启动管理器"""

    APP_NAME = "每日新闻速览"
    APP_ID = "daily-news-collector"

    def __init__(self):
        self.os_type = platform.system().lower()
        self.config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "autostart_config.json"
        )

    def is_enabled(self) -> bool:
        """检查自启动是否已启用"""
        try:
            config = self._load_config()
            return config.get("enabled", False)
        except Exception:
            return False

    def enable(self) -> Dict[str, Any]:
        """启用自启动"""
        try:
            if self.os_type == "windows":
                result = self._enable_windows()
            elif self.os_type == "linux":
                result = self._enable_linux()
            elif self.os_type == "darwin":
                result = self._enable_macos()
            else:
                result = {"ok": False, "error": f"不支持的操作系统: {self.os_type}"}

            if result.get("ok"):
                self._save_config({"enabled": True, "os": self.os_type})
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def disable(self) -> Dict[str, Any]:
        """禁用自启动"""
        try:
            if self.os_type == "windows":
                result = self._disable_windows()
            elif self.os_type == "linux":
                result = self._disable_linux()
            elif self.os_type == "darwin":
                result = self._disable_macos()
            else:
                result = {"ok": False, "error": f"不支持的操作系统: {self.os_type}"}

            if result.get("ok"):
                self._save_config({"enabled": False, "os": self.os_type})
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """获取自启动状态"""
        return {
            "enabled": self.is_enabled(),
            "os": self.os_type,
            "os_display": self._get_os_display(),
            "method": self._get_method(),
            "path": self._get_autostart_path(),
        }

    def get_script_path(self) -> str:
        """获取启动脚本路径"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if self.os_type == "windows":
            return os.path.join(base_dir, "startup.bat")
        else:
            return os.path.join(base_dir, "startup.sh")

    def create_startup_script(self) -> str:
        """创建启动脚本"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path = self.get_script_path()

        if self.os_type == "windows":
            content = f'''@echo off
cd /d "{base_dir}"
echo Starting 每日新闻速览...
python launcher.py
pause
'''
        else:
            content = f'''#!/bin/bash
cd "{base_dir}"
echo "Starting {self.APP_NAME}..."
python launcher.py
'''

        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(content)

        if self.os_type != "windows":
            os.chmod(script_path, 0o755)

        return script_path

    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_config(self, config: Dict[str, Any]):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def _get_os_display(self) -> str:
        mapping = {
            "windows": "Windows",
            "linux": "Linux",
            "darwin": "macOS",
        }
        return mapping.get(self.os_type, self.os_type)

    def _get_method(self) -> str:
        mapping = {
            "windows": "注册表 (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)",
            "linux": "systemd 服务",
            "darwin": "launchd 配置",
        }
        return mapping.get(self.os_type, "未知")

    def _get_autostart_path(self) -> str:
        if self.os_type == "windows":
            return "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        elif self.os_type == "linux":
            return "~/.config/systemd/user/daily-news-collector.service"
        elif self.os_type == "darwin":
            return "~/Library/LaunchAgents/com.daily.news.collector.plist"
        return ""

    def _enable_windows(self) -> Dict[str, Any]:
        """Windows: 使用注册表实现自启动"""
        import winreg

        script_path = self.create_startup_script()
        python_exe = sys.executable
        launcher_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "launcher.py"
        )

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            ) as key:
                command = f'"{python_exe}" "{launcher_path}"'
                winreg.SetValueEx(key, self.APP_NAME, 0, winreg.REG_SZ, command)

            return {
                "ok": True,
                "message": f"已在注册表 {key_path} 添加自启动项",
                "command": command,
            }
        except PermissionError:
            return {"ok": False, "error": "权限不足，请以管理员身份运行"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _disable_windows(self) -> Dict[str, Any]:
        """Windows: 删除注册表自启动项"""
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS
            ) as key:
                try:
                    winreg.DeleteValue(key, self.APP_NAME)
                    return {
                        "ok": True,
                        "message": f"已从注册表 {key_path} 删除自启动项",
                    }
                except FileNotFoundError:
                    return {"ok": True, "message": "自启动项不存在"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _enable_linux(self) -> Dict[str, Any]:
        """Linux: 使用 systemd 用户服务实现自启动"""
        user_config_dir = os.path.expanduser("~/.config/systemd/user")
        service_path = os.path.join(user_config_dir, f"{self.APP_ID}.service")

        os.makedirs(user_config_dir, exist_ok=True)

        python_exe = sys.executable
        launcher_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "launcher.py"
        )
        working_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        service_content = f'''[Unit]
Description={self.APP_NAME} - 每日新闻速览服务
After=network.target

[Service]
Type=simple
WorkingDirectory={working_dir}
ExecStart={python_exe} {launcher_path}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
'''

        with open(service_path, 'w', encoding='utf-8') as f:
            f.write(service_content)

        import subprocess
        try:
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                check=True, capture_output=True
            )
            subprocess.run(
                ["systemctl", "--user", "enable", self.APP_ID],
                check=True, capture_output=True
            )
            subprocess.run(
                ["systemctl", "--user", "start", self.APP_ID],
                check=True, capture_output=True
            )
            return {
                "ok": True,
                "message": f"已创建并启用 systemd 用户服务: {service_path}",
                "service_path": service_path,
            }
        except subprocess.CalledProcessError as e:
            return {"ok": False, "error": e.stderr.decode('utf-8', errors='ignore')}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _disable_linux(self) -> Dict[str, Any]:
        """Linux: 禁用并删除 systemd 用户服务"""
        import subprocess

        try:
            subprocess.run(
                ["systemctl", "--user", "stop", self.APP_ID],
                capture_output=True
            )
            subprocess.run(
                ["systemctl", "--user", "disable", self.APP_ID],
                capture_output=True
            )

            service_path = os.path.expanduser(
                f"~/.config/systemd/user/{self.APP_ID}.service"
            )
            if os.path.exists(service_path):
                os.remove(service_path)

            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                capture_output=True
            )

            return {"ok": True, "message": "已禁用并删除 systemd 用户服务"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _enable_macos(self) -> Dict[str, Any]:
        """macOS: 使用 launchd 实现自启动"""
        launch_agents_dir = os.path.expanduser("~/Library/LaunchAgents")
        plist_path = os.path.join(
            launch_agents_dir, f"com.{self.APP_ID.replace('-', '.')}.plist"
        )

        os.makedirs(launch_agents_dir, exist_ok=True)

        python_exe = sys.executable
        launcher_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "launcher.py"
        )
        working_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.{self.APP_ID.replace('-', '.')}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_exe}</string>
        <string>{launcher_path}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{working_dir}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{os.path.join(working_dir, "logs", "launchd.log")}</string>
    <key>StandardErrorPath</key>
    <string>{os.path.join(working_dir, "logs", "launchd.err")}</string>
</dict>
</plist>
'''

        with open(plist_path, 'w', encoding='utf-8') as f:
            f.write(plist_content)

        import subprocess
        try:
            subprocess.run(
                ["launchctl", "load", plist_path],
                check=True, capture_output=True
            )
            return {
                "ok": True,
                "message": f"已创建并加载 launchd 配置: {plist_path}",
                "plist_path": plist_path,
            }
        except subprocess.CalledProcessError as e:
            return {"ok": False, "error": e.stderr.decode('utf-8', errors='ignore')}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _disable_macos(self) -> Dict[str, Any]:
        """macOS: 卸载 launchd 配置"""
        import subprocess

        plist_path = os.path.expanduser(
            f"~/Library/LaunchAgents/com.{self.APP_ID.replace('-', '.')}.plist"
        )

        try:
            subprocess.run(
                ["launchctl", "unload", plist_path],
                capture_output=True
            )
            if os.path.exists(plist_path):
                os.remove(plist_path)
            return {"ok": True, "message": "已卸载并删除 launchd 配置"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
