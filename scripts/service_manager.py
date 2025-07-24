#!/usr/bin/env python3
"""
AI知识管理系统服务管理器
支持服务启动、停止、监控和资源管理
"""
import os
import sys
import yaml
import json
import time
import signal
import psutil
import subprocess
import threading
from pathlib import Path
from datetime import datetime
import argparse


class ServiceManager:
    def __init__(self, base_dir="~/ai-knowledge-system"):
        self.base_dir = Path(base_dir).expanduser()
        self.configs_dir = self.base_dir / "configs"
        self.environments_dir = self.base_dir / "environments"
        self.services_dir = self.base_dir / "services"
        self.logs_dir = self.base_dir / "logs"
        self.state_file = self.base_dir / "services_state.json"

        # 创建必要目录
        for dir_path in [self.services_dir, self.logs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        self.load_state()

    def load_env_file(self):
        """加载.env文件中的环境变量"""
        env_vars = {}
        env_file = self.base_dir / ".env"

        if not env_file.exists():
            print(f"⚠️ 环境变量文件不存在: {env_file}")
            return env_vars

        print(f"🔄 加载环境变量文件: {env_file}")
        loaded_count = 0

        with open(env_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    try:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        env_vars[key] = value
                        loaded_count += 1

                        if (
                            key == "OPENAI_API_KEY"
                            and value != "your_openai_api_key_here"
                        ):
                            print(f"✓ API密钥已加载: {value[:10]}...{value[-4:]}")
                    except ValueError:
                        print(f"⚠️ 第{line_num}行格式错误: {line}")
                        continue

        print(f"✓ 从.env文件加载了 {loaded_count} 个环境变量")
        return env_vars

    def load_state(self):
        """加载服务状态"""
        if self.state_file.exists():
            with open(self.state_file, "r") as f:
                self.state = json.load(f)
        else:
            self.state = {"services": {}}
            self.save_state()

    def save_state(self):
        """保存服务状态"""
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def load_service_config(self, service_name):
        """加载服务配置"""
        # 尝试新的命名方式
        config_file = self.configs_dir / f"{service_name}_service_config.yaml"
        if not config_file.exists():
            # 尝试旧的命名方式
            config_file = self.configs_dir / f"{service_name}_config.yaml"

        if not config_file.exists():
            raise ValueError(f"配置文件不存在: {config_file}")

        with open(config_file, "r") as f:
            return yaml.safe_load(f)

    def start_service(self, service_name):
        """启动服务"""
        if self.is_service_running(service_name):
            print(f"服务 {service_name} 已在运行")
            return

        try:
            config = self.load_service_config(service_name)
            env_name = config["environment"]
            env_path = self.environments_dir / env_name

            if not env_path.exists():
                raise ValueError(f"虚拟环境不存在: {env_path}")

            # 设置环境变量
            env = os.environ.copy()
            env["PYTHONPATH"] = str(self.base_dir)

            # 加载.env文件 - 关键修复
            env_vars = self.load_env_file()
            env.update(env_vars)  # 将.env文件中的变量合并到环境中

            # 验证API密钥 - 增强验证
            api_key = env.get("OPENAI_API_KEY")
            if not api_key or api_key == "your_openai_api_key_here":
                print("❌ 错误: OPENAI_API_KEY未设置或使用默认值")
                print(f"请编辑 {self.base_dir}/.env 文件设置正确的API密钥")
                return False
            else:
                print(f"✓ API密钥验证通过: {api_key[:10]}...{api_key[-4:]}")

            # 启动服务
            service_script = self.services_dir / f"{service_name}.py"
            if not service_script.exists():
                self.create_service_script(service_name, config)

            python_path = env_path / "bin" / "python"
            log_file = self.logs_dir / f"{service_name}.log"

            print(f"🚀 启动服务 {service_name}...")
            with open(log_file, "a") as log:
                log.write(f"\n=== 服务启动 {datetime.now().isoformat()} ===\n")
                process = subprocess.Popen(
                    [str(python_path), str(service_script)],
                    env=env,
                    stdout=log,
                    stderr=log,
                )

            # 等待服务启动
            timeout = config.get("startup_timeout", 30)
            if self.wait_for_service_health(service_name, config, timeout):
                self.state["services"][service_name] = {
                    "pid": process.pid,
                    "port": config["port"],
                    "started_at": datetime.now().isoformat(),
                    "status": "running",
                    "config": config,
                }
                self.save_state()
                print(
                    f"✅ 服务 {service_name} 启动成功 (PID: {process.pid}, 端口: {config['port']})"
                )
                return True
            else:
                process.terminate()
                print(f"❌ 服务 {service_name} 启动失败 - 健康检查超时")

                # 显示最后几行日志
                if log_file.exists():
                    print("最后10行日志:")
                    try:
                        subprocess.run(["tail", "-10", str(log_file)])
                    except:
                        # 如果tail命令不可用，手动读取
                        with open(log_file, "r") as f:
                            lines = f.readlines()
                            for line in lines[-10:]:
                                print(line.strip())
                return False

        except Exception as e:
            print(f"❌ 启动服务 {service_name} 失败: {e}")
            return False

    def stop_service(self, service_name):
        """停止服务"""
        if service_name not in self.state["services"]:
            print(f"服务 {service_name} 未运行")
            return

        service_info = self.state["services"][service_name]
        pid = service_info["pid"]

        try:
            if psutil.pid_exists(pid):
                process = psutil.Process(pid)
                process.terminate()

                # 等待进程结束
                try:
                    process.wait(timeout=10)
                    print(f"✅ 服务 {service_name} 停止成功")
                except psutil.TimeoutExpired:
                    process.kill()
                    print(f"✅ 服务 {service_name} 强制停止")

            del self.state["services"][service_name]
            self.save_state()

        except Exception as e:
            print(f"❌ 停止服务 {service_name} 失败: {e}")

    def is_service_running(self, service_name):
        """检查服务是否运行"""
        if service_name not in self.state["services"]:
            return False

        pid = self.state["services"][service_name]["pid"]
        return psutil.pid_exists(pid)

    def wait_for_service_health(self, service_name, config, timeout):
        """等待服务健康检查"""
        import requests

        port = config["port"]
        health_endpoint = config.get("health_endpoint", "/health")
        url = f"http://localhost:{port}{health_endpoint}"

        print(f"⏳ 等待服务健康检查: {url}")
        for i in range(timeout):
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    print(f"✅ 健康检查通过 ({i+1}s)")
                    return True
            except:
                pass

            if i % 5 == 0 and i > 0:
                print(f"  ⏳ 等待中... ({i}s)")
            time.sleep(1)

        return False

    def create_service_script(self, service_name, config):
        """创建服务启动脚本"""
        script_content = ""

        if service_name == "rag":
            script_content = self.get_rag_service_script(config)
        elif service_name == "memory":
            script_content = self.get_memory_service_script(config)
        elif service_name == "mcp-rag":
            script_content = self.get_mcp_rag_service_script(config)
        elif service_name == "mcp-memory":
            script_content = self.get_mcp_memory_service_script(config)
        elif service_name == "viz":
            script_content = self.get_viz_service_script(config)
        else:
            raise ValueError(f"未知服务类型: {service_name}")

        script_file = self.services_dir / f"{service_name}.py"
        with open(script_file, "w") as f:
            f.write(script_content)

        os.chmod(script_file, 0o755)
        print(f"✓ 创建服务脚本: {script_file}")

    def get_rag_service_script(self, config):
        """获取RAG服务脚本 - 改进版本"""
        return f"""#!/usr/bin/env python3
import os
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# 尝试导入LightRAG
try:
    from lightrag import LightRAG, QueryParam
    from lightrag.llm import openai_complete_if_cache, openai_embedding
    from lightrag.utils import EmbeddingFunc
    LIGHTRAG_AVAILABLE = True
except ImportError:
    LIGHTRAG_AVAILABLE = False
    print("⚠️ LightRAG不可用")

# 尝试导入本地模型
try:
    from sentence_transformers import SentenceTransformer
    LOCAL_EMBEDDING_AVAILABLE = True
except ImportError:
    LOCAL_EMBEDDING_AVAILABLE = False
    print("⚠️ 本地Embedding模型不可用")

app = FastAPI(title="RAG Service - Persistent Config", version="2.0.0")

# 配置
WORKING_DIR = "{config.get('working_dir', './data/rag_storage')}"
PORT = {config['port']}
USE_LOCAL_EMBEDDING = os.getenv(
    'ENABLE_LOCAL_MODELS', 'true').lower() == 'true'

os.makedirs(WORKING_DIR, exist_ok=True)

# 初始化Embedding函数
def get_embedding_func():
    if USE_LOCAL_EMBEDDING and LOCAL_EMBEDDING_AVAILABLE:
        try:
            print("🔄 加载Qwen3-Embedding-0.6B本地模型...")
            model = SentenceTransformer('Qwen/Qwen3-Embedding-0.6B')

            def local_embedding(texts):
                if isinstance(texts, str):
                    texts = [texts]
                embeddings = model.encode(texts)
                return embeddings.tolist()

            print("✅ Qwen3 Embedding模型加载成功")
            return EmbeddingFunc(
                embedding_dim=1024,
                max_token_size=32768,
                func=local_embedding
            )
        except Exception as e:
            print(f"⚠️ 本地模型加载失败，切换到API模式: {{e}}")

    # 使用API模式
    return EmbeddingFunc(
        embedding_dim=1536,
        max_token_size=8192,
        func=lambda texts: openai_embedding(
            texts, model="text-embedding-3-small")
    )

# 初始化RAG系统
if LIGHTRAG_AVAILABLE:
    print("🚀 使用LightRAG引擎")
    rag = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=openai_complete_if_cache,
        embedding_func=get_embedding_func(),
    )
else:
    print("❌ 错误: LightRAG引擎不可用")
    rag = None

class QueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"

class InsertRequest(BaseModel):
    text: str

@app.get("/health")
async def health_check():
    embedding_type = "Qwen3-Local" if USE_LOCAL_EMBEDDING and LOCAL_EMBEDDING_AVAILABLE else "API"
    return {{
        "status": "healthy",
        "service": "rag-persistent",
        "engine": "lightrag" if LIGHTRAG_AVAILABLE else "none",
        "embedding": embedding_type,
        "memory_config": "{config.get('memory_limit', 'N/A')}",
        "api_key_configured": bool(os.getenv('OPENAI_API_KEY')),
        "working_dir": WORKING_DIR
    }}

@app.post("/api/query")
async def query_documents(request: QueryRequest):
    if not rag:
        raise HTTPException(status_code=500, detail="RAG引擎未初始化")

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: rag.query(
                request.query, param=QueryParam(mode=request.mode))
        )

        return {{"status": "success", "data": result, "mode": request.mode}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/insert")
async def insert_document(request: InsertRequest):
    if not rag:
        raise HTTPException(status_code=500, detail="RAG引擎未初始化")

    try:
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: rag.insert(request.text)
        )

        return {{"status": "success", "message": "文档插入成功"}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print(f"🚀 启动RAG服务 - 端口: {{PORT}}")
    print(f"📁 工作目录: {{WORKING_DIR}}")
    print(f"🔑 API密钥: {{'已配置' if os.getenv('OPENAI_API_KEY') else '未配置'}}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
"""

    def get_memory_service_script(self, config):
        """获取Memory服务脚本 - 完整API版本"""
        return f'''#!/usr/bin/env python3
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
    print(f"⚠️ mem0导入失败: {{e}}")
    print("将使用模拟Memory服务")
    MEM0_AVAILABLE = False

# 配置
PORT = {config['port']}
print(f"📍 端口: {{PORT}}")

# 检查API密钥
api_key = os.getenv('OPENAI_API_KEY')
if not api_key or api_key == 'your_openai_api_key_here':
    print("❌ 错误: OPENAI_API_KEY未设置")
    if MEM0_AVAILABLE:
        print("使用默认配置继续运行...")
else:
    print(f"✅ API密钥已配置: {{api_key[:10]}}...")

# 初始化Memory实例
memory_instances = {{}}

def get_memory_instance(user_id: str = "default_user"):
    """获取或创建用户的Memory实例"""
    if user_id not in memory_instances:
        if MEM0_AVAILABLE:
            try:
                if api_key and api_key != 'your_openai_api_key_here':
                    # 使用OpenAI配置
                    config = {{
                        "llm": {{
                            "provider": "openai",
                            "config": {{
                                "model": "gpt-4o-mini",
                                "api_key": api_key,
                            }}
                        }},
                        "embedder": {{
                            "provider": "openai",
                            "config": {{
                                "model": "text-embedding-3-small",
                                "api_key": api_key,
                            }}
                        }}
                    }}
                    memory_instances[user_id] = Memory.from_config(config)
                    print(f"✅ 为用户 {{user_id}} 创建了配置化Memory实例")
                else:
                    # 使用默认配置
                    memory_instances[user_id] = Memory()
                    print(f"✅ 为用户 {{user_id}} 创建了默认Memory实例")
            except Exception as e:
                print(f"❌ Memory实例创建失败: {{e}}")
                memory_instances[user_id] = MockMemory(user_id)
        else:
            memory_instances[user_id] = MockMemory(user_id)

    return memory_instances[user_id]

# 模拟Memory类
class MockMemory:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.memories = []
        print(f"⚠️ 为用户 {{user_id}} 创建模拟Memory服务")

    def add(self, text: str, **kwargs):
        memory_id = f"{{self.user_id}}_{{len(self.memories)}}"
        memory_item = {{
            "id": memory_id,
            "text": text,
            "user_id": self.user_id,
            "created_at": "2025-01-01T00:00:00Z"
        }}
        self.memories.append(memory_item)
        return {{"id": memory_id, "message": "Memory added successfully"}}

    def search(self, query: str, limit: int = 10, **kwargs):
        # 简单的文本匹配搜索
        results = []
        for memory in self.memories:
            if query.lower() in memory["text"].lower():
                results.append({{
                    "id": memory["id"],
                    "text": memory["text"],
                    "score": 0.9,  # 模拟相似度分数
                    "created_at": memory["created_at"]
                }})
        return results[:limit]

    def get_all(self, **kwargs):
        return self.memories

    def delete(self, memory_id: str, **kwargs):
        self.memories = [m for m in self.memories if m["id"] != memory_id]
        return {{"message": f"Memory {{memory_id}} deleted"}}

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
    return {{
        "message": "Memory API Service",
        "version": "1.0.0",
        "status": "running",
        "mem0_available": MEM0_AVAILABLE
    }}

@app.get("/health")
async def health_check():
    return {{
        "status": "healthy",
        "service": "memory-api",
        "port": PORT,
        "mem0_available": MEM0_AVAILABLE,
        "api_configured": bool(api_key and api_key != 'your_openai_api_key_here'),
        "active_users": len(memory_instances)
    }}

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

        return {{"status": "success", "data": result}}
    except Exception as e:
        print(f"添加记忆失败: {{e}}")
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

        return {{"status": "success", "data": result}}
    except Exception as e:
        print(f"搜索记忆失败: {{e}}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memories")
async def get_all_memories(user_id: str = "default_user"):
    try:
        memory = get_memory_instance(user_id)

        if MEM0_AVAILABLE:
            result = memory.get_all(user_id=user_id)
        else:
            result = memory.get_all()

        return {{"status": "success", "data": result}}
    except Exception as e:
        print(f"获取记忆失败: {{e}}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/memories/{{memory_id}}")
async def delete_memory(memory_id: str, user_id: str = "default_user"):
    try:
        memory = get_memory_instance(user_id)

        if hasattr(memory, 'delete'):
            result = memory.delete(memory_id, user_id=user_id)
        else:
            result = {{"message": f"Memory {{memory_id}} deletion requested"}}

        return {{"status": "success", "data": result}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users")
async def list_users():
    """列出所有活跃用户"""
    return {{
        "status": "success",
        "data": {{
            "active_users": list(memory_instances.keys()),
            "total_users": len(memory_instances)
        }}
    }}

if __name__ == "__main__":
    print(f"🚀 Memory API服务启动 - 端口: {{PORT}}")
    print(f"📝 Mem0状态: {{'已连接' if MEM0_AVAILABLE else '模拟模式'}}")
    print(
        f"🔑 API配置: {{'已配置' if api_key and api_key != 'your_openai_api_key_here' else '使用默认'}}")
    print(f"📚 访问文档: http://localhost:{{PORT}}/docs")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
'''

    def get_mcp_rag_service_script(self, config):
        """获取MCP RAG服务脚本 - 修复版本"""
        return f"""#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException
import httpx
import uvicorn
from typing import Any, Dict, List
            from pydantic import BaseModel

app = FastAPI(title="MCP RAG Expert - Fixed Version", version="2.0.0")

RAG_SERVICE_URL = "{config.get('target_service', 'http://localhost:8001')}"
PORT = {config['port']}

class MCPRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any]

@app.get("/health")
async def health_check():
    return {{
        "status": "healthy", 
        "service": "mcp-rag-expert",
        "target": RAG_SERVICE_URL,
        "tools": {config.get('tools', [])},
        "api_key_configured": bool(os.getenv('OPENAI_API_KEY'))
    }}

@app.post("/mcp/call")
async def call_tool(request: MCPRequest):
    async with httpx.AsyncClient() as client:
        try:
            if request.tool == "hybrid_search":
                response = await client.post(f"{{RAG_SERVICE_URL}}/api/query", json=request.arguments)
                return {{"content": [{{"type": "text", "text": str(response.json())}}]}}
            elif request.tool == "insert_document":
                response = await client.post(f"{{RAG_SERVICE_URL}}/api/insert", json=request.arguments)
                return {{"content": [{{"type": "text", "text": str(response.json())}}]}}
            else:
                raise HTTPException(status_code=400, detail=f"未知工具: {{request.tool}}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print(f"🔌 启动MCP RAG专家服务器 - 端口: {{PORT}}")
    print(f"🎯 目标服务: {{RAG_SERVICE_URL}}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
"""

    def get_mcp_memory_service_script(self, config):
        """获取MCP Memory服务脚本 - 修复版本"""
        return f"""#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException
import httpx
import uvicorn
from typing import Any, Dict, List
from pydantic import BaseModel

app = FastAPI(title="MCP Memory Expert - Fixed Version", version="2.0.0")

MEMORY_SERVICE_URL = "{config.get('target_service', 'http://localhost:8765')}"
PORT = {config['port']}

class MCPRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any]

@app.get("/health")
async def health_check():
    return {{
        "status": "healthy", 
        "service": "mcp-memory-expert",
        "target": MEMORY_SERVICE_URL,
        "tools": {config.get('tools', [])},
        "api_key_configured": bool(os.getenv('OPENAI_API_KEY'))
    }}

@app.post("/mcp/call")
async def call_tool(request: MCPRequest):
    async with httpx.AsyncClient() as client:
        try:
            if request.tool == "add_memories":
                response = await client.post(f"{{MEMORY_SERVICE_URL}}/memories", json=request.arguments)
                return {{"content": [{{"type": "text", "text": str(response.json())}}]}}
            elif request.tool == "search_memory":
                response = await client.get(f"{{MEMORY_SERVICE_URL}}/memories/search", params=request.arguments)
                return {{"content": [{{"type": "text", "text": str(response.json())}}]}}
            else:
                raise HTTPException(status_code=400, detail=f"未知工具: {{request.tool}}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print(f"🧠 启动MCP记忆专家服务器 - 端口: {{PORT}}")
    print(f"🎯 目标服务: {{MEMORY_SERVICE_URL}}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
"""

    def get_viz_service_script(self, config):
        """获取可视化服务脚本"""
        return f'''#!/usr/bin/env python3
from flask import Flask, render_template_string, jsonify
import json

app = Flask(__name__)
PORT = {config['port']}

@app.route("/health")
def health_check():
    return jsonify({{"status": "healthy", "service": "viz-fixed", "port": PORT}})

@app.route("/")
def index():
    return """
    <h1>🎨 知识图谱可视化服务</h1>
    <p><strong>端口:</strong> {config['port']}</p>
    <p><strong>状态:</strong> 运行中</p>
    <p><strong>配置:</strong> 持久化版本</p>
    """

if __name__ == "__main__":
    print(f"🎨 启动可视化服务 - 端口: {{PORT}}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
'''

    def list_services(self):
        """列出所有服务"""
        print("🚀 AI知识管理系统服务状态 (持久化版本)")
        print("=" * 120)
        print(
            f"{'服务名':<15} {'状态':<12} {'PID':<8} {'端口':<6} {'内存(MB)':<10} {'CPU%':<6} {'启动时间':<20} {'描述':<25}"
        )
        print("=" * 120)

        # 更新服务列表，包含两个MCP服务器
        all_services = ["rag", "memory", "mcp-rag", "mcp-memory", "viz"]

        for service_name in all_services:
            if service_name in self.state["services"]:
                service_info = self.state["services"][service_name]
                pid = service_info["pid"]
                port = service_info["port"]
                started_at = (
                    service_info["started_at"][:19]
                    if service_info.get("started_at")
                    else "N/A"
                )
                description = service_info.get("config", {}).get("description", "")[:25]

                if psutil.pid_exists(pid):
                    try:
                        process = psutil.Process(pid)
                        memory = round(process.memory_info().rss / 1024 / 1024, 1)
                        cpu = round(process.cpu_percent(), 1)
                        status = "🟢 运行中"
                    except:
                        memory = 0
                        cpu = 0
                        status = "🔴 错误"
                else:
                    memory = 0
                    cpu = 0
                    status = "🔴 已停止"
                    # 清理已停止的服务
                    del self.state["services"][service_name]
                    self.save_state()

                print(
                    f"{service_name:<15} {status:<12} {pid:<8} {port:<6} {memory:<10} {cpu:<6} {started_at:<20} {description:<25}"
                )
            else:
                print(
                    f"{service_name:<15} {'⚪ 未启动':<12} {'N/A':<8} {'N/A':<6} {'0':<10} {'0':<6} {'N/A':<20} {'N/A':<25}"
                )

    def get_system_status(self):
        """获取系统状态"""
        # 系统总体状态
        memory = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=1)

        print("\\n💻 系统资源状态:")
        print("-" * 60)
        print(f"总内存: {memory.total // 1024 // 1024 // 1024}GB")
        print(f"已用内存: {memory.used // 1024 // 1024}MB ({memory.percent:.1f}%)")
        print(f"可用内存: {memory.available // 1024 // 1024}MB")
        print(f"CPU使用率: {cpu:.1f}%")

        # 交换空间
        swap = psutil.swap_memory()
        if swap.total > 0:
            print(
                f"交换空间: {swap.used // 1024 // 1024}MB / {swap.total // 1024 // 1024}MB ({swap.percent:.1f}%)"
            )

        # 内存使用建议
        if memory.percent > 85:
            print("⚠️ 内存使用率较高，建议停止部分服务")
        elif memory.percent < 60:
            print("✅ 内存使用率正常，可以启动更多服务")
        else:
            print("🔄 内存使用率适中")


def main():
    parser = argparse.ArgumentParser(
        description="AI知识管理系统服务管理器 - 持久化版本"
    )
    parser.add_argument(
        "action", choices=["start", "stop", "restart", "list", "status"]
    )
    parser.add_argument(
        "--service",
        help="服务名称 (rag, memory, mcp-rag, mcp-memory, viz, core, mcp, all)",
    )

    args = parser.parse_args()
    manager = ServiceManager()

    if args.action == "start":
        if args.service == "all":
            # 按依赖顺序启动：先启动基础服务，再启动MCP服务
            services = ["rag", "memory", "mcp-rag", "mcp-memory", "viz"]
            print("🚀 启动所有服务...")
            for service in services:
                manager.start_service(service)
                time.sleep(3)  # 间隔启动避免资源冲突
        elif args.service == "core":
            # 只启动核心服务（节省内存）
            services = ["rag", "memory"]
            print("🎯 启动核心服务...")
            for service in services:
                manager.start_service(service)
                time.sleep(3)
        elif args.service == "mcp":
            # 启动所有MCP服务
            services = ["mcp-rag", "mcp-memory"]
            print("🔌 启动MCP专家服务器...")
            for service in services:
                manager.start_service(service)
                time.sleep(2)
        elif args.service:
            manager.start_service(args.service)
        else:
            print(
                "请指定要启动的服务: rag, memory, mcp-rag, mcp-memory, viz, core, mcp, all"
            )

    elif args.action == "stop":
        if args.service == "all":
            services = ["viz", "mcp-memory", "mcp-rag", "memory", "rag"]  # 反向停止
            print("🛑 停止所有服务...")
            for service in services:
                if manager.is_service_running(service):
                    manager.stop_service(service)
        elif args.service == "mcp":
            services = ["mcp-rag", "mcp-memory"]
            for service in services:
                if manager.is_service_running(service):
                    manager.stop_service(service)
        elif args.service:
            manager.stop_service(args.service)
        else:
            print("请指定要停止的服务")

    elif args.action == "restart":
        if args.service:
            print(f"🔄 重启服务: {args.service}")
            manager.stop_service(args.service)
            time.sleep(3)
            manager.start_service(args.service)
        else:
            print("请指定要重启的服务")

    elif args.action == "list":
        manager.list_services()

    elif args.action == "status":
        manager.list_services()
        manager.get_system_status()


if __name__ == "__main__":
    main()
