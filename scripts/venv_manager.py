#!/usr/bin/env python3
"""
AI知识管理系统虚拟环境管理器
支持环境创建、激活、监控和资源管理
"""
import os
import subprocess
import psutil
import json
import argparse
from pathlib import Path
from datetime import datetime

class VirtualEnvManager:
    def __init__(self, base_dir="~/ai-knowledge-system/environments"):
        self.base_dir = Path(base_dir).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.base_dir / "env_config.json"
        self.load_config()
    
    def load_config(self):
        """加载环境配置"""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                "environments": {},
                "created_at": datetime.now().isoformat()
            }
            self.save_config()
    
    def save_config(self):
        """保存环境配置"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def create_env(self, env_name, description="", requirements=None):
        """创建虚拟环境"""
        env_path = self.base_dir / env_name
        if env_path.exists():
            print(f"环境 {env_name} 已存在")
            return
        
        print(f"创建虚拟环境: {env_name}")
        subprocess.run([
            "python3", "-m", "venv", str(env_path)
        ], check=True)
        
        # 升级pip
        pip_path = env_path / "bin" / "pip"
        subprocess.run([
            str(pip_path), "install", "--upgrade", "pip", "setuptools", "wheel"
        ], check=True)
        
        # 安装依赖
        if requirements:
            for req in requirements:
                print(f"安装: {req}")
                subprocess.run([str(pip_path), "install", req], check=True)
        
        # 记录环境信息
        self.config["environments"][env_name] = {
            "path": str(env_path),
            "description": description,
            "created_at": datetime.now().isoformat(),
            "status": "inactive",
            "pid": None,
            "memory_usage": 0
        }
        self.save_config()
        print(f"环境 {env_name} 创建完成")
    
    def list_envs(self):
        """列出所有环境"""
        print("虚拟环境列表:")
        print("-" * 80)
        print(f"{'环境名':<15} {'状态':<10} {'PID':<10} {'内存(MB)':<10} {'描述':<30}")
        print("-" * 80)
        
        for env_name, env_info in self.config["environments"].items():
            status = self.check_env_status(env_name)
            memory = self.get_env_memory_usage(env_name)
            
            # 确保所有值都是字符串
            pid_display = str(env_info.get('pid', 'N/A')) if env_info.get('pid') is not None else 'N/A'
            memory_display = str(memory) if memory is not None else '0'
            description = env_info.get('description', '')
            
            print(f"{env_name:<15} {status:<10} {pid_display:<10} {memory_display:<10} {description:<30}")
    
    def check_env_status(self, env_name):
        """检查环境状态"""
        if env_name not in self.config["environments"]:
            return "unknown"
        
        env_info = self.config["environments"][env_name]
        pid = env_info.get("pid")
        
        if pid and psutil.pid_exists(pid):
            return "running"
        else:
            return "inactive"
    
    def get_env_memory_usage(self, env_name):
        """获取环境内存使用"""
        if env_name not in self.config["environments"]:
            return 0
        
        env_info = self.config["environments"][env_name]
        pid = env_info.get("pid")
        
        if pid and psutil.pid_exists(pid):
            try:
                process = psutil.Process(pid)
                return round(process.memory_info().rss / 1024 / 1024, 1)
            except:
                return 0
        return 0
    
    def remove_env(self, env_name):
        """删除虚拟环境"""
        if env_name not in self.config["environments"]:
            print(f"环境 {env_name} 不存在")
            return
        
        env_path = Path(self.config["environments"][env_name]["path"])
        if env_path.exists():
            import shutil
            shutil.rmtree(env_path)
        
        del self.config["environments"][env_name]
        self.save_config()
        print(f"环境 {env_name} 已删除")

def main():
    parser = argparse.ArgumentParser(description="AI知识管理系统虚拟环境管理器")
    parser.add_argument("action", choices=["create", "list", "remove"])
    parser.add_argument("--name", help="环境名称")
    parser.add_argument("--desc", help="环境描述")
    parser.add_argument("--requirements", nargs="+", help="依赖包列表")
    
    args = parser.parse_args()
    manager = VirtualEnvManager()
    
    if args.action == "create":
        if not args.name:
            print("创建环境需要指定名称")
            return
        manager.create_env(args.name, args.desc or "", args.requirements or [])
    
    elif args.action == "list":
        manager.list_envs()
    
    elif args.action == "remove":
        if not args.name:
            print("删除环境需要指定名称")
            return
        manager.remove_env(args.name)

if __name__ == "__main__":
    main()
