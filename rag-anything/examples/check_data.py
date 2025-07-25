import os
import json

# 检查所有可能的存储位置
storage_paths = [
    "./rag_storage",
    "../rag_storage", 
    "/home/ragadmin/ai-knowledge-system/rag-anything/rag_storage"
]

for path in storage_paths:
    abs_path = os.path.abspath(path)
    print(f"\n🔍 Checking: {abs_path}")
    
    if os.path.exists(abs_path):
        files = os.listdir(abs_path)
        print(f"📁 Files: {files}")
        
        # 检查关键文件
        for filename in ["vdb_entities.json", "vdb_relationships.json", "vdb_chunks.json"]:
            filepath = os.path.join(abs_path, filename)
            if os.path.exists(filepath):
                size = os.path.getsize(filepath)
                print(f"📄 {filename}: {size} bytes")
                
                # 尝试读取JSON查看内容
                if size > 10:
                    try:
                        with open(filepath, 'r') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                print(f"   📊 Contains {len(data)} records")
                            elif isinstance(data, dict):
                                print(f"   📊 Contains keys: {list(data.keys())}")
                    except Exception as e:
                        print(f"   ❌ Error reading: {e}")
                else:
                    print(f"   ⚠️  File is empty or too small")
    else:
        print(f"❌ Directory does not exist")
