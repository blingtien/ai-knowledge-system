#!/usr/bin/env python3
import os
import sys
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import uvicorn
from typing import List, Optional, Dict, Any

print("🧠 启动完整Memory API服务")

# 导入mem0
try:
    from mem0 import Memory
    print("✅ mem0 Memory类导入成功")
    MEM0_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ mem0导入失败: {e}")
    print("将使用模拟Memory服务")
    MEM0_AVAILABLE = False

# 配置
PORT = 8765
print(f"📍 端口: {PORT}")

# 检查API密钥
api_key = os.getenv('OPENAI_API_KEY')
if not api_key or api_key == 'your_openai_api_key_here':
    print("❌ 错误: OPENAI_API_KEY未设置")
    if MEM0_AVAILABLE:
        print("使用默认配置继续运行...")
else:
    print(f"✅ API密钥已配置: {api_key[:10]}...")

# 初始化Memory实例
memory_instances = {}

def get_memory_instance(user_id: str = "default_user"):
    """获取或创建用户的Memory实例"""
    if user_id not in memory_instances:
        if MEM0_AVAILABLE:
            try:
                if api_key and api_key != 'your_openai_api_key_here':
                    # 使用OpenAI配置
                    config = {
                        "llm": {
                            "provider": "openai",
                            "config": {
                                "model": "gpt-4o-mini",
                                "api_key": api_key,
                            }
                        },
                        "embedder": {
                            "provider": "openai",
                            "config": {
                                "model": "text-embedding-3-small",
                                "api_key": api_key,
                            }
                        }
                    }
                    memory_instances[user_id] = Memory.from_config(config)
                    print(f"✅ 为用户 {user_id} 创建了配置化Memory实例")
                else:
                    # 使用默认配置
                    memory_instances[user_id] = Memory()
                    print(f"✅ 为用户 {user_id} 创建了默认Memory实例")
            except Exception as e:
                print(f"❌ Memory实例创建失败: {e}")
                memory_instances[user_id] = MockMemory(user_id)
        else:
            memory_instances[user_id] = MockMemory(user_id)

    return memory_instances[user_id]

# 模拟Memory类
class MockMemory:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.memories = []
        print(f"⚠️ 为用户 {user_id} 创建模拟Memory服务")

    def add(self, text: str, **kwargs):
        memory_id = f"{self.user_id}_{len(self.memories)}"
        memory_item = {
            "id": memory_id,
            "text": text,
            "user_id": self.user_id,
            "created_at": "2025-01-01T00:00:00Z"
        }
        self.memories.append(memory_item)
        return {"id": memory_id, "message": "Memory added successfully"}

    def search(self, query: str, limit: int = 10, **kwargs):
        # 简单的文本匹配搜索
        results = []
        for memory in self.memories:
            if query.lower() in memory["text"].lower():
                results.append({
                    "id": memory["id"],
                    "text": memory["text"],
                    "score": 0.9,  # 模拟相似度分数
                    "created_at": memory["created_at"]
                })
        return results[:limit]

    def get_all(self, **kwargs):
        return self.memories

    def delete(self, memory_id: str, **kwargs):
        self.memories = [m for m in self.memories if m["id"] != memory_id]
        return {"message": f"Memory {memory_id} deleted"}

# 创建FastAPI应用
app = FastAPI(
    title="Memory API Service",
    version="1.0.0",
    description="基于mem0的记忆管理API服务"
)

class AddMemoryRequest(BaseModel):
    text: str
    user_id: str = "default_user"
    metadata: Optional[Dict[str, Any]] = None

@app.get("/")
async def root():
    return {
        "message": "Memory API Service",
        "version": "1.0.0",
        "status": "running",
        "mem0_available": MEM0_AVAILABLE
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "memory-api",
        "port": PORT,
        "mem0_available": MEM0_AVAILABLE,
        "api_configured": bool(api_key and api_key != 'your_openai_api_key_here'),
        "active_users": len(memory_instances)
    }

@app.post("/memories")
async def add_memory(request: AddMemoryRequest):
    try:
        memory = get_memory_instance(request.user_id)

        if MEM0_AVAILABLE:
            result = memory.add(
                request.text,
                user_id=request.user_id,
                metadata=request.metadata
            )
        else:
            result = memory.add(request.text)

        return {"status": "success", "data": result}
    except Exception as e:
        print(f"添加记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memories/search")
async def search_memory(
    query: str,
    user_id: str = "default_user",
    limit: int = 10
):
    try:
        memory = get_memory_instance(user_id)

        if MEM0_AVAILABLE:
            result = memory.search(query, user_id=user_id, limit=limit)
        else:
            result = memory.search(query, limit=limit)

        return {"status": "success", "data": result}
    except Exception as e:
        print(f"搜索记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memories")
async def get_all_memories(user_id: str = "default_user"):
    try:
        memory = get_memory_instance(user_id)

        if MEM0_AVAILABLE:
            result = memory.get_all(user_id=user_id)
        else:
            result = memory.get_all()

        return {"status": "success", "data": result}
    except Exception as e:
        print(f"获取记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str, user_id: str = "default_user"):
    try:
        memory = get_memory_instance(user_id)

        if hasattr(memory, 'delete'):
            result = memory.delete(memory_id, user_id=user_id)
        else:
            result = {"message": f"Memory {memory_id} deletion requested"}

        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users")
async def list_users():
    """列出所有活跃用户"""
    return {
        "status": "success",
        "data": {
            "active_users": list(memory_instances.keys()),
            "total_users": len(memory_instances)
        }
    }

if __name__ == "__main__":
    print(f"🚀 Memory API服务启动 - 端口: {PORT}")
    print(f"📝 Mem0状态: {'已连接' if MEM0_AVAILABLE else '模拟模式'}")
    print(
        f"🔑 API配置: {'已配置' if api_key and api_key != 'your_openai_api_key_here' else '使用默认'}")
    print(f"📚 访问文档: http://localhost:{PORT}/docs")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
