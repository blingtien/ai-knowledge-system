#!/usr/bin/env python3
"""
RAG Knowledge Management Web Interface - 优化版
提供知识库管理和查询的Web界面，运行在端口4000
与rag.py服务(端口8001)协作
"""
import os
import json
import asyncio
import aiofiles
import aiohttp
import hashlib
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
import uvicorn

# 导入数据库模块
from database import (
    init_database, close_database, 
    KnowledgeBaseDB, FileMetadataDB
)

# 应用配置
app = FastAPI(title="RAG Knowledge Management Web Interface", version="1.1.0")

# 配置目录
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = BASE_DIR / "uploads"
KNOWLEDGE_BASES_DIR = BASE_DIR / "knowledge_bases"

# 确保目录存在
for dir_path in [UPLOADS_DIR, KNOWLEDGE_BASES_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)


# 🔧 RAG服务配置 - 匹配你的rag.py设置
RAG_SERVICE_URL = "http://localhost:8001"
RAG_HEALTH_URL = f"{RAG_SERVICE_URL}/health"
RAG_QUERY_URL = f"{RAG_SERVICE_URL}/api/query"
RAG_INSERT_URL = f"{RAG_SERVICE_URL}/api/insert"
RAG_PARSE_DOCUMENT_URL = f"{RAG_SERVICE_URL}/api/parse-document"
RAG_PROGRESS_URL = f"{RAG_SERVICE_URL}/api/progress"

# 数据模型
class QueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"
    
class QueryResponse(BaseModel):
    status: str
    result: str
    mode: str
    timestamp: datetime

class KnowledgeBase(BaseModel):
    name: str
    description: str = ""
    
class FileInfo(BaseModel):
    filename: str
    size: int
    upload_time: datetime
    status: str = "uploaded"  # uploaded, processing, completed, error
    progress: int = 0
    knowledge_base: str

# 数据库状态管理 - 替换内存存储
# knowledge_bases 和 file_status 现在从数据库中获取

async def sync_filesystem_to_database():
    """
    同步文件系统到数据库
    处理现有文件系统中的知识库和文件，确保数据库同步
    """
    print("🔄 同步文件系统到数据库...")
    
    # 同步知识库目录
    if KNOWLEDGE_BASES_DIR.exists():
        for kb_dir in KNOWLEDGE_BASES_DIR.iterdir():
            if kb_dir.is_dir():
                try:
                    # 检查数据库中是否已存在
                    existing_kb = await KnowledgeBaseDB.get_knowledge_base(kb_dir.name)
                    if not existing_kb:
                        await KnowledgeBaseDB.create_knowledge_base(
                            name=kb_dir.name,
                            description="",
                            path=str(kb_dir)
                        )
                        print(f"📂 同步知识库到数据库: {kb_dir.name}")
                    else:
                        print(f"📂 知识库已存在: {kb_dir.name}")
                except Exception as e:
                    print(f"❌ 同步知识库失败 {kb_dir.name}: {e}")
    
    # 同步上传的文件
    if UPLOADS_DIR.exists():
        for file_path in UPLOADS_DIR.glob("*"):
            if file_path.is_file():
                safe_filename = file_path.name
                try:
                    # 检查数据库中是否已存在
                    existing_file = await FileMetadataDB.get_file_by_safe_filename(safe_filename)
                    if not existing_file:
                        # 尝试从文件名推断信息
                        if "_" in safe_filename:
                            kb_name = safe_filename.split("_")[0]
                            # 推断原始文件名（这里可能不准确，但至少保持记录）
                            original_filename = safe_filename
                            
                            # 确保知识库存在
                            kb_exists = await KnowledgeBaseDB.get_knowledge_base(kb_name)
                            if kb_exists:
                                await FileMetadataDB.create_file_record(
                                    safe_filename=safe_filename,
                                    original_filename=original_filename,
                                    knowledge_base=kb_name,
                                    file_path=str(file_path),
                                    size=file_path.stat().st_size,
                                    upload_time=datetime.fromtimestamp(file_path.stat().st_ctime)
                                )
                                print(f"📄 同步文件到数据库: {safe_filename}")
                            else:
                                print(f"⚠️ 跳过文件（知识库不存在）: {safe_filename}")
                    else:
                        print(f"📄 文件已存在: {safe_filename}")
                except Exception as e:
                    print(f"❌ 同步文件失败 {safe_filename}: {e}")
    
    print("✅ 文件系统同步完成")

async def check_rag_service_health():
    """检查RAG服务是否可用"""
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(RAG_HEALTH_URL) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ RAG服务健康检查通过: {data}")
                    return True, data
                else:
                    print(f"❌ RAG服务健康检查失败: {response.status}")
                    return False, f"HTTP {response.status}"
    except Exception as e:
        print(f"❌ RAG服务连接失败: {e}")
        return False, str(e)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Web界面生命周期管理"""
    # 启动时初始化
    print("🚀 Web界面启动中...")
    
    # 初始化数据库
    print("🗄️ 初始化数据库连接...")
    db_success = await init_database()
    if not db_success:
        print("❌ 数据库初始化失败，服务可能无法正常工作")
    else:
        print("✅ 数据库连接成功")
        await sync_filesystem_to_database()
    
    # 检查RAG服务
    print("⏳ 等待RAG服务启动...")
    await asyncio.sleep(2)
    
    health_ok, health_info = await check_rag_service_health()
    if health_ok:
        print("✅ RAG服务连接正常")
        print(f"📊 RAG服务状态: {health_info}")
    else:
        print(f"⚠️ RAG服务未就绪: {health_info}")
        print("💡 请确保 rag.py 服务正在运行: python rag.py")
    
    yield  # 应用运行期间
    
    # 关闭时清理
    print("🔄 Web界面关闭中...")
    await close_database()
    print("✅ 数据库连接已关闭")

# 创建FastAPI应用
app = FastAPI(
    title="RAG Knowledge Management Web Interface", 
    version="1.1.0",
    lifespan=lifespan
)
# 挂载静态文件
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """返回主页面"""
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        async with aiofiles.open(html_file, 'r', encoding='utf-8') as f:
            content = await f.read()
        return HTMLResponse(content=content)
    else:
        return HTMLResponse(content="""
        <html><body>
        <h1>RAG Knowledge Management System</h1>
        <p>静态文件未找到，请检查 static/index.html</p>
        </body></html>
        """)

@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 检查RAG服务状态
        rag_healthy, rag_info = await check_rag_service_health()
        
        # 从数据库获取统计信息
        knowledge_bases_list = await KnowledgeBaseDB.list_knowledge_bases()
        files_list = await FileMetadataDB.list_files()
        
        return {
            "status": "healthy",
            "service": "rag-web-interface",
            "port": 4000,
            "database": "postgresql",
            "rag_service": {
                "healthy": rag_healthy,
                "info": rag_info,
                "url": RAG_SERVICE_URL
            },
            "knowledge_bases": len(knowledge_bases_list),
            "total_files": len(files_list),
        }
    except Exception as e:
        return {
            "status": "error",
            "service": "rag-web-interface",
            "error": str(e)
        }

@app.get("/api/knowledge-bases")
async def list_knowledge_bases():
    """获取知识库列表"""
    try:
        knowledge_bases_list = await KnowledgeBaseDB.list_knowledge_bases()
        # 转换格式以保持兼容性
        formatted_kbs = []
        for kb in knowledge_bases_list:
            formatted_kbs.append({
                "name": kb["name"],
                "description": kb["description"],
                "created_time": kb["created_at"],
                "file_count": kb["file_count"],
                "path": kb["path"]
            })
        return {"knowledge_bases": formatted_kbs}
    except Exception as e:
        print(f"❌ 获取知识库列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/knowledge-bases")
async def create_knowledge_base(kb: KnowledgeBase):
    """创建新的知识库"""
    try:
        # 检查知识库是否已存在
        existing_kb = await KnowledgeBaseDB.get_knowledge_base(kb.name)
        if existing_kb:
            raise HTTPException(status_code=400, detail="Knowledge base already exists")
        
        # 创建文件系统目录
        kb_dir = KNOWLEDGE_BASES_DIR / kb.name
        kb_dir.mkdir(exist_ok=True)
        
        # 在数据库中创建记录
        await KnowledgeBaseDB.create_knowledge_base(
            name=kb.name,
            description=kb.description,
            path=str(kb_dir)
        )
        
        return {"status": "success", "message": f"Knowledge base '{kb.name}' created"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ 创建知识库失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files")
async def list_files(knowledge_base: Optional[str] = None):
    """获取文件列表"""
    try:
        files_list = await FileMetadataDB.list_files(knowledge_base)
        # 转换格式以保持兼容性
        formatted_files = []
        for file_data in files_list:
            formatted_files.append({
                "filename": file_data["original_filename"],
                "safe_filename": file_data["safe_filename"],
                "size": file_data["size"],
                "upload_time": file_data["upload_time"],
                "status": file_data["status"],
                "progress": file_data["progress"],
                "knowledge_base": file_data["knowledge_base"],
                "file_path": file_data["file_path"],
                "error": file_data.get("error_message")
            })
        return {"files": formatted_files}
    except Exception as e:
        print(f"❌ 获取文件列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    knowledge_base: str = Form(...)
):
    """上传文件到指定知识库"""
    print(f"📤 收到上传请求: 知识库={knowledge_base}, 文件数={len(files)}")
    
    # 检查知识库是否存在
    try:
        existing_kb = await KnowledgeBaseDB.get_knowledge_base(knowledge_base)
        if not existing_kb:
            print(f"❌ 知识库不存在: {knowledge_base}")
            raise HTTPException(status_code=400, detail=f"知识库 '{knowledge_base}' 不存在，请先创建知识库")
    except Exception as e:
        print(f"❌ 检查知识库失败: {e}")
        raise HTTPException(status_code=500, detail="检查知识库失败")
    
    uploaded_files = []
    
    try:
        for file in files:
            print(f"📄 处理文件: {file.filename}")
            
            file_ext = Path(file.filename).suffix
            safe_filename = f"{knowledge_base}_{uuid.uuid4().hex[:8]}{file_ext}"
            file_path = UPLOADS_DIR / safe_filename
            
            # 保存物理文件
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            # 在数据库中创建记录
            file_record = await FileMetadataDB.create_file_record(
                safe_filename=safe_filename,
                original_filename=file.filename,
                knowledge_base=knowledge_base,
                file_path=str(file_path),
                size=len(content),
                upload_time=datetime.now()
            )
            
            # 格式化返回信息
            upload_info = {
                "filename": file.filename,
                "safe_filename": safe_filename,
                "size": len(content),
                "upload_time": file_record["upload_time"],
                "status": file_record["status"],
                "progress": file_record["progress"],
                "knowledge_base": knowledge_base,
                "file_path": str(file_path)
            }
            
            uploaded_files.append(upload_info)
            print(f"✅ 文件上传成功: {file.filename}")
            
    except Exception as e:
        print(f"❌ 上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")
    
    return {
        "status": "success", 
        "uploaded_files": len(uploaded_files),
        "files": [
            {
                "filename": info["filename"],
                "safe_filename": info["safe_filename"],
                "size": info["size"],
                "status": info["status"],
                "progress": info["progress"],
                "knowledge_base": info["knowledge_base"],
                "upload_time": info["upload_time"].isoformat()
            }
            for info in uploaded_files
        ]
    }

@app.post("/api/parse")
async def start_parsing(
    background_tasks: BackgroundTasks,
    filename: str = Form(...),
    knowledge_base: str = Form(...)
):
    """开始解析指定文件"""
    print(f"🔍 收到解析请求: filename={filename}, kb={knowledge_base}")
    
    try:
        # 从数据库查找文件
        file_record = await FileMetadataDB.get_file_by_original_filename(filename, knowledge_base)
        
        if not file_record:
            print(f"❌ 文件未找到: {filename}")
            raise HTTPException(status_code=404, detail=f"File not found: {filename}")
        
        safe_filename = file_record["safe_filename"]
        
        # 🔧 优化：先检查RAG服务状态
        rag_healthy, rag_info = await check_rag_service_health()
        if not rag_healthy:
            raise HTTPException(
                status_code=503, 
                detail=f"RAG服务不可用: {rag_info}。请确保 rag.py 服务正在运行。"
            )
        
        # 初始化状态 - 更新数据库
        await FileMetadataDB.update_file_status(safe_filename, "processing", progress=0, error_message=None)
        print(f"📊 初始化状态: {safe_filename} -> processing, progress=0%")
        
        # 启动后台解析任务
        background_tasks.add_task(process_file_parsing_optimized, safe_filename)
        
        return {"status": "success", "message": f"Started parsing {filename}"}
    
    except Exception as e:
        print(f"❌ 启动解析失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动解析失败: {str(e)}")

async def process_file_parsing_optimized(safe_filename: str):
    """优化版的后台文件解析任务"""
    try:
        print(f"🔄 开始解析文件: {safe_filename}")
        
        # 从数据库获取文件信息
        file_record = await FileMetadataDB.get_file_by_safe_filename(safe_filename)
        if not file_record:
            print(f"❌ 文件记录未找到: {safe_filename}")
            return
        
        file_path = file_record["file_path"]
        knowledge_base_name = file_record["knowledge_base"]
        original_filename = file_record["original_filename"]
        
        # 🔧 添加：创建进度追踪 key（用于前端查询）
        progress_key = safe_filename
        
        # 🔧 添加：在本地也维护一份进度信息
        local_progress = {
            "safe_filename": safe_filename,
            "original_filename": original_filename,
            "progress": 0,
            "message": "准备开始解析...",
            "status": "processing"
        }
        
        # 定义进度回调函数
        async def local_progress_callback(progress: int, message: str):
            """本地进度回调，同时更新数据库和内存缓存"""
            local_progress["progress"] = progress
            local_progress["message"] = message
            
            # 更新数据库
            await FileMetadataDB.update_file_status(
                safe_filename, 
                "processing", 
                progress=progress, 
                error_message=None
            )
            
            print(f"📊 进度更新 [{safe_filename}]: {progress}% - {message}")
        
        # 初始进度
        await local_progress_callback(5, "正在初始化解析任务...")
        await asyncio.sleep(0.5)
        
        await local_progress_callback(10, "验证文件存在...")
        await asyncio.sleep(1)
        
        # 检查文件是否存在
        if not Path(file_path).exists():
            raise Exception(f"文件不存在: {file_path}")
        
        await local_progress_callback(20, "文件验证完成，准备发送给RAG服务...")
        await asyncio.sleep(1)
        
        # 🔧 准备文档处理的payload
        payload = {
            "file_path": file_path,
            "knowledge_base": knowledge_base_name,
            "parse_method": "auto",
            "display_stats": True
        }
        
        await local_progress_callback(30, "正在连接RAG服务...")
        
        print(f"📤 发送到RAG服务进行文档处理:")
        print(f"   - 文件名: {original_filename}")
        print(f"   - 文件路径: {file_path}")
        print(f"   - 知识库: {knowledge_base_name}")
        print(f"   - RAG服务URL: {RAG_PARSE_DOCUMENT_URL}")
        
        # 设置超时
        timeout = aiohttp.ClientTimeout(total=14400, connect=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                # 🔧 创建一个任务来定期查询RAG服务的进度
                async def poll_rag_progress():
                    """定期查询RAG服务的进度"""
                    last_progress = 30
                    while local_progress["status"] == "processing":
                        try:
                            # 尝试多个可能的key来查询进度
                            possible_keys = [
                                os.path.basename(file_path),
                                safe_filename,
                                original_filename,
                                os.path.splitext(original_filename)[0]
                            ]
                            
                            for key in possible_keys:
                                try:
                                    progress_url = f"{RAG_SERVICE_URL}/api/progress/{key}"
                                    async with session.get(progress_url) as resp:
                                        if resp.status == 200:
                                            data = await resp.json()
                                            if data.get("progress", 0) > last_progress:
                                                last_progress = data["progress"]
                                                await local_progress_callback(
                                                    data["progress"],
                                                    data.get("message", "处理中...")
                                                )
                                                break
                                except:
                                    continue
                        except Exception as e:
                            print(f"⚠️ 查询RAG进度失败: {e}")
                        
                        await asyncio.sleep(2)  # 每2秒查询一次
                
                # 启动进度轮询任务
                progress_task = asyncio.create_task(poll_rag_progress())
                
                # 发送文档处理请求
                async with session.post(RAG_PARSE_DOCUMENT_URL, json=payload) as response:
                    response_status = response.status
                    response_text = await response.text()
                    
                    print(f"📥 RAG服务响应: 状态码={response_status}")
                    
                    if response_status == 200:
                        local_progress["status"] = "completed"
                        await local_progress_callback(90, "RAG服务处理完成，正在验证...")
                        
                        # 取消进度轮询
                        progress_task.cancel()
                        
                        # 验证处理结果
                        verification_result = await verify_insertion_advanced(
                            knowledge_base_name, 
                            original_filename, 
                            original_filename.split('.')[0]
                        )
                        
                        if verification_result:
                            await local_progress_callback(100, "文档处理成功完成！")
                            await FileMetadataDB.update_file_status(safe_filename, "completed", progress=100)
                        else:
                            await FileMetadataDB.update_file_status(
                                safe_filename, "completed", progress=100, 
                                error_message="文档处理成功但验证查询未通过"
                            )
                    else:
                        local_progress["status"] = "error"
                        progress_task.cancel()
                        error_msg = f"RAG服务错误: HTTP {response_status}"
                        await FileMetadataDB.update_file_status(safe_filename, "error", progress=0, error_message=error_msg)
                        
            except asyncio.TimeoutError:
                if 'progress_task' in locals():
                    progress_task.cancel()
                error_msg = "RAG服务请求超时"
                await FileMetadataDB.update_file_status(safe_filename, "error", progress=0, error_message=error_msg)
                
    except Exception as e:
        error_msg = f"解析异常: {str(e)}"
        print(f"❌ {error_msg}")
        await FileMetadataDB.update_file_status(safe_filename, "error", progress=0, error_message=error_msg)
        
        import traceback
        traceback.print_exc()

async def read_file_with_multiple_encodings(file_path: str) -> str:
    """多编码方式读取文件"""
    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin1']
    
    for encoding in encodings:
        try:
            async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
                content = await f.read()
                print(f"✅ 成功使用 {encoding} 编码读取文件")
                return content
        except (UnicodeDecodeError, UnicodeError):
            print(f"⚠️ {encoding} 编码读取失败，尝试下一个...")
            continue
    
    # 最后尝试二进制读取
    try:
        async with aiofiles.open(file_path, 'rb') as f:
            raw_content = await f.read()
            content = raw_content.decode('utf-8', errors='ignore')
            print(f"✅ 使用二进制+忽略错误模式读取文件")
            return content
    except Exception as e:
        raise Exception(f"无法读取文件 {file_path}: {e}")

async def verify_insertion_advanced(knowledge_base: str, filename: str, content_sample: str):
    """高级插入验证"""
    try:
        print(f"🔍 验证插入: 知识库={knowledge_base}, 文件={filename}")
        
        # 等待一定时间让RAG服务完成索引
        await asyncio.sleep(3)
        
        # 准备多种查询词进行验证
        test_queries = []
        
        # 1. 使用文件名（去掉扩展名）
        if filename:
            base_name = filename.split('.')[0]
            if len(base_name) > 3:
                test_queries.append(base_name[:20])
        
        # 2. 使用内容的关键词
        if content_sample and len(content_sample) > 10:
            # 简单提取一些可能的关键词
            words = content_sample.split()
            if len(words) >= 3:
                test_queries.append(' '.join(words[:3]))
            test_queries.append(content_sample[:30])
        
        if not test_queries:
            test_queries = ["测试查询"]
        
        print(f"🔍 测试查询词: {test_queries}")
        
        # 尝试不同的查询模式
        for query in test_queries[:2]:  # 最多测试2个查询词
            for mode in ["naive", "hybrid"]:
                try:
                    payload = {
                        "query": query,
                        "mode": mode
                    }
                    
                    timeout = aiohttp.ClientTimeout(total=30)
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.post(RAG_QUERY_URL, json=payload) as response:
                            if response.status == 200:
                                response_text = await response.text()
                                try:
                                    response_data = json.loads(response_text)
                                    result_data = response_data.get('data', response_text)
                                except json.JSONDecodeError:
                                    result_data = response_text
                                
                                print(f"🔍 验证查询响应 ({mode}): {str(result_data)[:200]}...")
                                
                                # 检查响应中是否包含相关内容
                                result_str = str(result_data).lower()
                                query_lower = query.lower()
                                
                                if (query_lower in result_str or 
                                    len(result_str.strip()) > 50):  # 如果有实质性的响应
                                    print(f"✅ 验证成功: 查询 '{query}' ({mode}) 返回了相关内容")
                                    return True
                                else:
                                    print(f"⚠️ 查询 '{query}' ({mode}) 未返回预期内容")
                            else:
                                print(f"❌ 验证查询失败: {response.status}")
                                
                except Exception as e:
                    print(f"❌ 验证查询异常: {e}")
                    continue
        
        print(f"❌ 所有验证查询都未通过")
        return False
        
    except Exception as e:
        print(f"❌ 验证异常: {e}")
        return False

@app.get("/api/files/{file_key}/status")
async def get_file_status(file_key: str):
    """获取文件解析状态 - 整合数据库和RAG服务的实时进度"""
    print(f"🔍 查询文件状态: {file_key}")
    
    try:
        # URL解码文件key
        import urllib.parse
        decoded_file_key = urllib.parse.unquote(file_key)
        
        # 首先从数据库获取基本文件信息
        file_record = await FileMetadataDB.get_file_by_safe_filename(decoded_file_key)
        if not file_record:
            file_record = await FileMetadataDB.get_file_by_safe_filename(file_key)
        
        if not file_record:
            print(f"❌ 文件未找到: {file_key}")
            raise HTTPException(status_code=404, detail=f"File not found: {file_key}")
        
        # 构建基本响应
        response = {
            "filename": file_record["original_filename"],
            "safe_filename": file_record["safe_filename"],
            "size": file_record["size"],
            "upload_time": file_record["upload_time"],
            "status": file_record["status"],
            "progress": file_record["progress"],
            "knowledge_base": file_record["knowledge_base"],
            "file_path": file_record["file_path"],
            "error": file_record.get("error_message"),
            "message": ""
        }
        
        # 如果文件正在处理中，尝试从RAG服务获取实时进度
        if file_record["status"] == "processing":
            try:
                # 使用原始文件名作为key来查询RAG服务
                original_filename = file_record["original_filename"]
                file_basename = os.path.basename(file_record["file_path"])
                
                # 尝试多个可能的key
                possible_keys = [
                    os.path.basename(file_record["file_path"]),  # 文件路径的basename
                    file_record["safe_filename"],  # safe_filename
                    original_filename,  # 原始文件名
                    os.path.splitext(original_filename)[0]  # 不带扩展名的原始文件名
                ]
                
                for key in possible_keys:
                    try:
                        timeout = aiohttp.ClientTimeout(total=2)
                        async with aiohttp.ClientSession(timeout=timeout) as session:
                            rag_progress_url = f"{RAG_SERVICE_URL}/api/progress/{key}"
                            async with session.get(rag_progress_url) as rag_response:
                                if rag_response.status == 200:
                                    rag_data = await rag_response.json()
                                    if rag_data.get("progress", 0) > 0:
                                        print(f"📊 找到RAG进度 (key={key}): {rag_data}")
                                        response["progress"] = rag_data["progress"]
                                        response["message"] = rag_data.get("message", "")
                                        break
                    except:
                        continue
                        
            except Exception as rag_e:
                print(f"⚠️ 查询RAG服务进度失败: {rag_e}")
        
        return response
        
    except Exception as e:
        print(f"❌ 查询文件状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询文件状态失败: {str(e)}")

# 🔧 新增：文件状态重置接口，用于调试
@app.post("/api/files/{file_key}/reset")
async def reset_file_status(file_key: str):
    """重置文件状态为uploaded（用于调试）"""
    try:
        # URL解码
        import urllib.parse
        decoded_file_key = urllib.parse.unquote(file_key)
        
        # 查找文件记录
        file_record = await FileMetadataDB.get_file_by_safe_filename(decoded_file_key)
        if not file_record:
            file_record = await FileMetadataDB.get_file_by_safe_filename(file_key)
        
        if not file_record:
            raise HTTPException(status_code=404, detail=f"File not found: {file_key}")
        
        # 重置状态
        await FileMetadataDB.update_file_status(
            file_record["safe_filename"], "uploaded", progress=0, error_message=None
        )
        
        return {"status": "success", "message": f"File {file_record['original_filename']} status reset"}
    
    except Exception as e:
        print(f"❌ 重置文件状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"重置文件状态失败: {str(e)}")

# 🔧 新增：删除文件接口
@app.delete("/api/files/{file_key}")
async def delete_file(file_key: str):
    """删除指定文件"""
    print(f"🗑️ 收到删除请求: {file_key}")
    
    try:
        # URL解码
        import urllib.parse
        decoded_file_key = urllib.parse.unquote(file_key)
        
        # 从数据库删除文件记录
        deleted_record = await FileMetadataDB.delete_file(decoded_file_key)
        if not deleted_record:
            # 尝试原始file_key
            deleted_record = await FileMetadataDB.delete_file(file_key)
        
        if not deleted_record:
            print(f"❌ 文件未找到: {file_key}")
            raise HTTPException(status_code=404, detail=f"File not found: {file_key}")
        
        # 删除物理文件
        file_path = Path(deleted_record["file_path"])
        if file_path.exists():
            file_path.unlink()
            print(f"✅ 删除物理文件: {file_path}")
        else:
            print(f"⚠️ 物理文件不存在: {file_path}")
        
        print(f"✅ 删除数据库记录: {deleted_record['safe_filename']}")
        
        return {
            "status": "success", 
            "message": f"文件 {deleted_record['original_filename']} 删除成功",
            "deleted_file": deleted_record["original_filename"]
        }
        
    except Exception as e:
        print(f"❌ 删除文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")

@app.post("/api/query")
async def query_knowledge_base(request: QueryRequest):
    """查询知识库"""
    try:
        print(f"🔍 收到查询请求: {request.query[:50]}... (mode: {request.mode})")
        
        # 检查RAG服务状态
        rag_healthy, rag_info = await check_rag_service_health()
        if not rag_healthy:
            raise HTTPException(
                status_code=503, 
                detail=f"RAG服务不可用: {rag_info}"
            )
        
        # 转发查询请求到RAG服务
        payload = {
            "query": request.query,
            "mode": request.mode
        }
        
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(RAG_QUERY_URL, json=payload) as response:
                response_status = response.status
                response_text = await response.text()
                
                if response_status == 200:
                    try:
                        response_data = json.loads(response_text)
                        result = response_data.get('data', response_text)
                        print(f"✅ 查询完成，结果长度: {len(str(result))}")
                        
                        return QueryResponse(
                            status="success",
                            result=str(result) if result else "未找到相关信息",
                            mode=request.mode,
                            timestamp=datetime.now()
                        )
                    except json.JSONDecodeError:
                        # 如果响应不是JSON，直接返回文本
                        print(f"✅ 查询完成，返回文本结果")
                        return QueryResponse(
                            status="success",
                            result=response_text if response_text else "未找到相关信息",
                            mode=request.mode,
                            timestamp=datetime.now()
                        )
                else:
                    error_msg = f"RAG查询失败: HTTP {response_status} - {response_text}"
                    print(f"❌ {error_msg}")
                    raise HTTPException(status_code=500, detail=error_msg)
                    
    except aiohttp.ClientError as e:
        error_msg = f"连接RAG服务失败: {str(e)}"
        print(f"❌ {error_msg}")
        raise HTTPException(status_code=503, detail=error_msg)
    except Exception as e:
        print(f"❌ 查询异常: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

# 🔧 调试API接口
@app.get("/api/rag-service-status")
async def detailed_rag_service_status():
    """详细的RAG服务状态检查"""
    results = {}
    
    # 测试不同的端点
    test_endpoints = [
        {"name": "health_check", "url": f"{RAG_SERVICE_URL}/health", "method": "GET"},
        {"name": "query_test", "url": f"{RAG_SERVICE_URL}/api/query", "method": "POST", 
         "payload": {"query": "测试", "mode": "naive"}},
    ]
    
    for endpoint in test_endpoints:
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                if endpoint["method"] == "GET":
                    async with session.get(endpoint["url"]) as response:
                        status = response.status
                        data = await response.text()
                        results[endpoint["name"]] = {
                            "url": endpoint["url"],
                            "status": status,
                            "response": data[:300],
                            "success": status == 200
                        }
                else:  # POST
                    async with session.post(endpoint["url"], json=endpoint["payload"]) as response:
                        status = response.status
                        data = await response.text()
                        results[endpoint["name"]] = {
                            "url": endpoint["url"],
                            "status": status,
                            "response": data[:300],
                            "success": status == 200,
                            "payload": endpoint["payload"]
                        }
        except Exception as e:
            results[endpoint["name"]] = {
                "url": endpoint["url"],
                "error": str(e),
                "success": False
            }
    
    return {
        "rag_service_url": RAG_SERVICE_URL,
        "test_results": results,
        "summary": {
            "total_tests": len(test_endpoints),
            "successful_tests": sum(1 for r in results.values() if r.get("success", False)),
            "all_tests_passed": all(r.get("success", False) for r in results.values())
        }
    }

@app.post("/api/manual-test-insert")
async def manual_test_insert():
    """手动测试RAG插入功能"""
    test_content = f"""手动测试文档 - {datetime.now().isoformat()}
    
    这是一个用于测试RAG系统插入功能的文档。
    
    关键信息：
    1. 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    2. 测试关键词: 蓝天白云晴朗天气
    3. 特殊标识: MANUAL_TEST_DOC_12345
    
    如果你能通过查询找到这些内容，说明RAG插入功能正常工作。
    """
    
    try:
        print("🧪 开始手动测试RAG插入功能...")
        
        # 检查RAG服务状态
        rag_healthy, rag_info = await check_rag_service_health()
        if not rag_healthy:
            return {
                "status": "error",
                "error": f"RAG服务不可用: {rag_info}"
            }
        
        # 测试插入
        payload = {"text": test_content}
        
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(RAG_INSERT_URL, json=payload) as response:
                response_status = response.status
                response_text = await response.text()
                
                insert_result = {
                    "status": response_status,
                    "response": response_text[:500],
                    "success": response_status == 200
                }
                
                if response_status == 200:
                    print("✅ 手动插入测试成功")
                    
                    # 等待索引完成
                    await asyncio.sleep(3)
                    
                    # 测试查询
                    query_result = await test_query_after_insert("蓝天白云晴朗天气")
                    
                    return {
                        "status": "success",
                        "test_content_length": len(test_content),
                        "insert_result": insert_result,
                        "query_result": query_result
                    }
                else:
                    print(f"❌ 手动插入测试失败: {response_status} - {response_text}")
                    return {
                        "status": "error", 
                        "insert_result": insert_result
                    }
        
    except Exception as e:
        print(f"❌ 手动测试失败: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

async def test_query_after_insert(query_text: str):
    """插入后的查询测试"""
    try:
        payload = {"query": query_text, "mode": "naive"}
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(RAG_QUERY_URL, json=payload) as response:
                response_status = response.status
                response_text = await response.text()
                
                return {
                    "query": query_text,
                    "status": response_status,
                    "response": response_text[:500],
                    "success": response_status == 200,
                    "found_expected_content": "蓝天白云" in response_text or "MANUAL_TEST" in response_text
                }
    except Exception as e:
        return {
            "query": query_text,
            "error": str(e),
            "success": False
        }

if __name__ == "__main__":
    print("🚀 启动RAG Knowledge Management Web Interface")
    print("📍 访问地址: http://localhost:4000") 
    print("🔗 RAG服务地址: http://localhost:8001")
    print("💡 请确保先启动 rag.py 服务: python rag.py")
    uvicorn.run(app, host="0.0.0.0", port=4000)