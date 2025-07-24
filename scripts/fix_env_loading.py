#!/usr/bin/env python3
"""
修复环境变量加载问题
"""
import os
from pathlib import Path

def load_env_file(env_path=".env"):
    """加载.env文件"""
    env_file = Path(env_path)
    if not env_file.exists():
        print(f"⚠️ .env文件不存在: {env_file}")
        return False
    
    loaded_vars = 0
    with open(env_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                try:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")  # 移除引号
                    os.environ[key] = value
                    loaded_vars += 1
                    if key == 'OPENAI_API_KEY':
                        print(f"✓ 加载API密钥: {value[:10]}...{value[-4:] if len(value) > 10 else value}")
                except ValueError:
                    print(f"⚠️ 第{line_num}行格式错误: {line}")
    
    print(f"✓ 从.env文件加载了 {loaded_vars} 个环境变量")
    return True

if __name__ == "__main__":
    print("修复环境变量加载...")
    success = load_env_file()
    
    if success:
        # 测试API密钥
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key and api_key != 'your_openai_api_key_here':
            print("✓ API密钥配置正确")
        else:
            print("✗ API密钥仍未正确配置")
            print("请检查.env文件中的OPENAI_API_KEY设置")
