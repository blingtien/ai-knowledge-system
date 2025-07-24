#!/usr/bin/env python3
"""
找到虚拟环境中 mineru_parser.py 的实际位置
"""

import sys
import os
from pathlib import Path

def find_mineru_parser_location():
    """找到mineru_parser.py的实际位置"""
    
    print("🔍 查找 mineru_parser.py 的实际位置...")
    print(f"🐍 当前Python解释器: {sys.executable}")
    print(f"📁 当前工作目录: {os.getcwd()}")
    
    # 方法1: 尝试导入并查看模块位置
    try:
        from raganything import mineru_parser
        module_file = mineru_parser.__file__
        print(f"✅ 找到模块文件: {module_file}")
        
        # 显示完整路径信息
        module_path = Path(module_file)
        print(f"📂 模块目录: {module_path.parent}")
        print(f"📄 文件名: {module_path.name}")
        print(f"📊 文件大小: {module_path.stat().st_size} bytes")
        
        return str(module_path)
        
    except ImportError as e:
        print(f"❌ 无法导入 raganything.mineru_parser: {e}")
    
    # 方法2: 在sys.path中搜索
    print("\n🔍 在sys.path中搜索...")
    for path in sys.path:
        if path:
            search_path = Path(path)
            
            # 搜索可能的位置
            possible_locations = [
                search_path / "raganything" / "mineru_parser.py",
                search_path / "raganything" / "__init__.py",  # 检查raganything包是否存在
            ]
            
            for location in possible_locations:
                if location.exists():
                    print(f"✅ 找到: {location}")
                    if location.name == "mineru_parser.py":
                        return str(location)
    
    # 方法3: 使用pip show查看包位置
    print("\n🔍 使用pip查看raganything包信息...")
    try:
        import subprocess
        result = subprocess.run([sys.executable, "-m", "pip", "show", "raganything"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("📦 RAG-Anything包信息:")
            print(result.stdout)
            
            # 从输出中提取Location
            for line in result.stdout.split('\n'):
                if line.startswith('Location:'):
                    location = line.split(':', 1)[1].strip()
                    potential_file = Path(location) / "raganything" / "mineru_parser.py"
                    print(f"🎯 推测文件位置: {potential_file}")
                    if potential_file.exists():
                        return str(potential_file)
    except Exception as e:
        print(f"⚠️ pip show失败: {e}")
    
    print("❌ 未找到mineru_parser.py文件")
    return None

def show_backup_commands(file_path):
    """显示备份和替换命令"""
    if not file_path:
        return
        
    file_path = Path(file_path)
    backup_path = file_path.with_suffix('.py.backup')
    
    print(f"\n📋 替换文件的命令:")
    print(f"# 1. 备份原文件")
    print(f"cp '{file_path}' '{backup_path}'")
    
    print(f"\n# 2. 替换文件 (将修复后的文件复制过去)")
    print(f"cp /path/to/your/fixed/mineru_parser.py '{file_path}'")
    
    print(f"\n# 3. 如需恢复原文件")
    print(f"cp '{backup_path}' '{file_path}'")

if __name__ == "__main__":
    file_location = find_mineru_parser_location()
    show_backup_commands(file_location)
    
    if file_location:
        print(f"\n✅ 请将修复后的 mineru_parser.py 替换到:")
        print(f"   {file_location}")
    else:
        print(f"\n❌ 未找到文件位置，请手动查找")