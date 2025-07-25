#!/usr/bin/env python3
"""
检查PDF处理进度和知识库状态
"""
import os
import json
from pathlib import Path
from datetime import datetime

def check_knowledge_base_status():
    """检查知识库状态"""
    storage_dir = Path("./rag_storage")
    
    print("📊 知识库状态检查")
    print("=" * 50)
    print(f"🕐 检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 存储目录: {storage_dir.absolute()}")
    
    if not storage_dir.exists():
        print("❌ 知识库目录不存在")
        return
    
    # 检查各个文件
    files_to_check = [
        ("vdb_entities.json", "实体向量数据库"),
        ("vdb_relationships.json", "关系向量数据库"), 
        ("vdb_chunks.json", "文本块向量数据库"),
        ("graph_chunk_entity_relation.graphml", "知识图谱文件"),
        ("kv_store_full_docs.json", "文档存储"),
        ("kv_store_text_chunks.json", "文本块存储"),
        ("kv_store_doc_status.json", "文档状态")
    ]
    
    total_size = 0
    file_count = 0
    
    for filename, description in files_to_check:
        file_path = storage_dir / filename
        if file_path.exists():
            size = file_path.stat().st_size
            total_size += size
            file_count += 1
            
            # 尝试读取JSON文件获取更多信息
            if filename.endswith('.json'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if filename.startswith('vdb_'):
                        # 向量数据库文件
                        if isinstance(data, list):
                            count = len(data)
                            print(f"✅ {description}: {size/1024:.1f}KB ({count} 条记录)")
                        else:
                            print(f"✅ {description}: {size/1024:.1f}KB")
                    else:
                        # 其他JSON文件
                        if isinstance(data, dict):
                            count = len(data)
                            print(f"✅ {description}: {size/1024:.1f}KB ({count} 项)")
                        elif isinstance(data, list):
                            count = len(data)
                            print(f"✅ {description}: {size/1024:.1f}KB ({count} 条)")
                        else:
                            print(f"✅ {description}: {size/1024:.1f}KB")
                            
                except Exception as e:
                    print(f"✅ {description}: {size/1024:.1f}KB (无法解析内容)")
            else:
                # 非JSON文件
                print(f"✅ {description}: {size/1024:.1f}KB")
        else:
            print(f"❌ {description}: 文件不存在")
    
    print(f"\n📈 总计: {file_count}/{len(files_to_check)} 个文件, 总大小: {total_size/1024:.1f}KB")
    
    # 检查最近的更新
    print(f"\n⏰ 最近更新:")
    for filename, description in files_to_check:
        file_path = storage_dir / filename
        if file_path.exists():
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            print(f"  {filename}: {mtime.strftime('%H:%M:%S')}")

def check_output_directory():
    """检查输出目录"""
    output_dir = Path("./output")
    
    print(f"\n📁 输出目录检查")
    print("=" * 50)
    
    if output_dir.exists():
        files = list(output_dir.iterdir())
        print(f"✅ 输出目录存在: {len(files)} 个文件")
        
        for file_path in files[:10]:  # 只显示前10个文件
            if file_path.is_file():
                size = file_path.stat().st_size
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                print(f"  📄 {file_path.name}: {size/1024:.1f}KB ({mtime.strftime('%H:%M:%S')})")
    else:
        print("❌ 输出目录不存在")

if __name__ == "__main__":
    try:
        check_knowledge_base_status()
        check_output_directory()
        
        print(f"\n💡 提示:")
        print(f"  - 如果看到数据更新，说明PDF处理可能已成功")
        print(f"  - 可以使用 testsearch.py 测试查询功能")
        print(f"  - 如果文件大小没有变化，可能需要重新处理")
        
    except Exception as e:
        print(f"❌ 检查过程中出错: {e}")