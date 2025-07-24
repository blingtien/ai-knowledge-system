#!/usr/bin/env python3
import os
import time
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from pydantic import BaseModel
import uvicorn

# 尝试导入RAG-Anything (优先)
try:
    from raganything import RAGAnything, RAGAnythingConfig
    RAG_ANYTHING_AVAILABLE = True
    print("✅ RAG-Anything导入成功")
except ImportError as e:
    RAG_ANYTHING_AVAILABLE = False
    print(f"⚠️ RAG-Anything不可用: {e}")

# 备用导入LightRAG
try:
    from lightrag import LightRAG, QueryParam
    from lightrag.llm.openai import openai_complete_if_cache
    from lightrag.utils import EmbeddingFunc
    LIGHTRAG_AVAILABLE = True
    print("✅ LightRAG导入成功")
except ImportError as e:
    LIGHTRAG_AVAILABLE = False
    print(f"⚠️ LightRAG不可用: {e}")

# 尝试导入本地模型
try:
    from sentence_transformers import SentenceTransformer
    LOCAL_EMBEDDING_AVAILABLE = True
    print("✅ 本地Embedding模型可用")
except ImportError:
    LOCAL_EMBEDDING_AVAILABLE = False
    print("⚠️ 本地Embedding模型不可用")



# 配置
WORKING_DIR = os.getenv('RAG_WORKING_DIR', './rag_storage')
PORT = 8001

# 从环境变量读取配置
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'Qwen/Qwen3-Embedding-0.6B')
EMBEDDING_MODEL_TYPE = os.getenv('EMBEDDING_MODEL_TYPE', 'local').strip()
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')
USE_LOCAL_EMBEDDING = EMBEDDING_MODEL_TYPE.lower() == 'local'

print(f"🔧 配置信息:")
print(f"  - Embedding模型: {EMBEDDING_MODEL}")
print(f"  - 模型类型: {EMBEDDING_MODEL_TYPE}")
print(f"  - API Base URL: {OPENAI_BASE_URL}")
print(f"  - 使用本地Embedding: {USE_LOCAL_EMBEDDING}")

os.makedirs(WORKING_DIR, exist_ok=True)

# 🎯 全局embedding模型实例 - 在服务启动时预加载
_global_embedding_model = None
_embedding_model_loaded = False

# 预加载embedding模型
async def load_embedding_model():
    """预加载embedding模型到全局变量"""
    global _global_embedding_model, _embedding_model_loaded
    
    if _embedding_model_loaded:
        print("✅ Embedding模型已预加载")
        return
        
    if USE_LOCAL_EMBEDDING and LOCAL_EMBEDDING_AVAILABLE:
        try:
            print(f"🔄 预加载本地embedding模型: {EMBEDDING_MODEL}...")
            _global_embedding_model = SentenceTransformer(EMBEDDING_MODEL)
            _embedding_model_loaded = True
            print("✅ Qwen3-Embedding模型预加载成功！")
        except Exception as e:
            print(f"⚠️ 本地模型加载失败: {e}")
            _embedding_model_loaded = False
    else:
        print("🔧 使用API embedding模式，无需预加载模型")
        _embedding_model_loaded = True

async def global_embedding_func(texts):
    """使用全局预加载的embedding模型"""
    global _global_embedding_model
    
    if isinstance(texts, str):
        texts = [texts]
    
    if _global_embedding_model is not None:
        # 使用预加载的本地模型
        embeddings = _global_embedding_model.encode(
            texts, 
            normalize_embeddings=True, 
            show_progress_bar=False
        )
        return embeddings.tolist()
    else:
        # 回退到API模式 - 使用简单的返回，实际不应该到达这里
        print("⚠️ 警告: 全局embedding函数回退到API模式")
        return [[0.0] * 1536 for _ in texts]  # 返回dummy embeddings

# 初始化Embedding函数
def get_embedding_func():
    if USE_LOCAL_EMBEDDING and LOCAL_EMBEDDING_AVAILABLE:
        return EmbeddingFunc(
            embedding_dim=1024,
            max_token_size=32768,
            func=global_embedding_func
        )
    else:
        # API模式暂不支持，返回dummy函数
        print("⚠️ API embedding模式暂不支持，请使用本地模型")
        async def dummy_embedding_func(texts):
            if isinstance(texts, str):
                texts = [texts]
            return [[0.0] * 1536 for _ in texts]
        
        return EmbeddingFunc(
            embedding_dim=1536,
            max_token_size=8192,
            func=dummy_embedding_func
        )

# 创建LLM函数（支持DeepSeek）
def create_llm_func():
    """创建支持DeepSeek的LLM函数"""
    try:
        from lightrag.llm.openai import openai_complete_if_cache
        
        # 使用DeepSeek API
        def deepseek_llm_func(prompt, system_prompt=None, history_messages=[], **kwargs):
            return openai_complete_if_cache(
                model="deepseek-chat",
                prompt=prompt,
                system_prompt=system_prompt, 
                history_messages=history_messages,
                base_url=OPENAI_BASE_URL,
                **kwargs
            )
        return deepseek_llm_func
    except Exception as e:
        print(f"⚠️ 创建LLM函数失败: {e}")
        return None

# 初始化RAG系统
rag = None

# 优先使用RAG-Anything（更先进的文档处理能力）
if RAG_ANYTHING_AVAILABLE:
    try:
        print("🚀 使用RAG-Anything引擎初始化...")
        
        # 创建必要的函数
        llm_func = create_llm_func()
        embedding_func = get_embedding_func()
        
        if llm_func and embedding_func:
            # 创建RAG-Anything配置
            config = RAGAnythingConfig(
                working_dir=WORKING_DIR,
                display_content_stats=True,
                enable_image_processing=True,
                enable_table_processing=True,
                max_concurrent_files=1,
                max_context_tokens=2000
            )
            
            # 使用正确的参数创建RAG-Anything
            rag = RAGAnything(
                config=config,
                llm_model_func=llm_func,
                vision_model_func=llm_func,  # 使用同一个LLM函数作为视觉模型
                embedding_func=embedding_func,
            )
            print("✅ RAG-Anything引擎初始化成功")
        else:
            print("❌ LLM或embedding函数创建失败，无法初始化RAG-Anything")
            rag = None
    except Exception as e:
        print(f"❌ RAG-Anything初始化失败: {e}")
        import traceback
        traceback.print_exc()
        rag = None

# 备用LightRAG（如果RAG-Anything失败）
if rag is None and LIGHTRAG_AVAILABLE:
    try:
        print("🚀 回退到LightRAG引擎...")
        llm_func = create_llm_func()
        if llm_func:
            rag = LightRAG(
                working_dir=WORKING_DIR,
                llm_model_func=llm_func,
                embedding_func=get_embedding_func(),
            )
            print("✅ LightRAG引擎初始化成功")
        else:
            print("❌ LLM函数创建失败")
    except Exception as e:
        print(f"❌ LightRAG初始化失败: {e}")
        rag = None

if rag is None:
    print("❌ 没有可用的RAG引擎")
    rag = None

# 全局进度存储
file_progress = {}

class QueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"

class InsertRequest(BaseModel):
    text: str

class ParseDocumentRequest(BaseModel):
    file_path: str
    knowledge_base: str = "default"
    parse_method: str = "auto"
    output_dir: str = None
    display_stats: bool = True

# 添加服务启动事件
#@app.on_event("startup")

# 添加 lifespan 管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时的初始化
    print("🚀 RAG服务启动中...")
    await load_embedding_model()
    print("✅ RAG服务启动完成!")
    
    yield  # 应用运行期间
    
    # 关闭时的清理（如果需要）
    print("🔄 RAG服务关闭中...")
# 创建FastAPI应用，使用lifespan
app = FastAPI(
    title="RAG Service - RAG-Anything Edition", 
    version="2.1.0",
    lifespan=lifespan
)


@app.get("/api/progress/{file_key}")
async def get_file_progress(file_key: str):
    """获取文件处理进度"""
    if file_key in file_progress:
        return file_progress[file_key]
    else:
        return {"progress": 0, "message": "未找到文件处理记录"}

@app.get("/health")
async def health_check():
    embedding_type = "Qwen3-Local-Preloaded" if USE_LOCAL_EMBEDDING and _embedding_model_loaded else "API"
    engine_type = "none"
    if rag:
        if RAG_ANYTHING_AVAILABLE and isinstance(rag, RAGAnything):
            engine_type = "rag-anything"
        elif LIGHTRAG_AVAILABLE:
            engine_type = "lightrag"
    
    # 🎯 新增：检查 MineruParser 修复状态
    mineru_fix_status = "unknown"
    mineru_fix_info = {}
    
    try:
        from raganything.mineru_parser import MineruParser, MINERU_PARSER_VERSION, MINERU_PARSER_FIX_INFO
        
        # 验证修复是否生效
        if MineruParser.verify_fix_active():
            mineru_fix_status = "active"
            mineru_fix_info = MineruParser.get_fix_info()
            print(f"🔧 MineruParser 修复状态: {mineru_fix_status}")
            print(f"🔧 修复版本: {MINERU_PARSER_VERSION}")
        else:
            mineru_fix_status = "inactive"
            
    except Exception as e:
        mineru_fix_status = "error"
        mineru_fix_info = {"error": str(e)}
        print(f"❌ MineruParser 修复状态检查失败: {e}")
    return {
        "status": "healthy", 
        "service": "rag-persistent",
        "engine": engine_type,
        "embedding": embedding_type,
        "embedding_model_preloaded": _embedding_model_loaded,
        "embedding_model_name": EMBEDDING_MODEL,
        "memory_config": "4.5GB",
        "api_key_configured": bool(os.getenv('OPENAI_API_KEY')),
        "working_dir": WORKING_DIR,
        "rag_available": rag is not None,
        
        # 🎯 新增修复状态信息
        "mineru_parser_fix": {
            "status": mineru_fix_status,
            "info": mineru_fix_info,
            "timestamp": datetime.now().isoformat()
        }
    }

# 🎯 新增：专门的修复状态检查接口
@app.get("/api/mineru-fix-status")
async def check_mineru_fix_status():
    """专门检查 MineruParser 修复状态的接口"""
    
    try:
        from raganything.mineru_parser import MineruParser, MINERU_PARSER_VERSION, MINERU_PARSER_FIX_INFO
        
        # 获取详细的修复信息
        fix_info = MineruParser.get_fix_info()
        is_active = MineruParser.verify_fix_active()
        
        # 检查方法签名
        import inspect
        sig = inspect.signature(MineruParser._run_mineru_command)
        has_progress_callback = 'progress_callback' in sig.parameters
        
        return {
            "status": "success",
            "fix_active": is_active,
            "fix_version": MINERU_PARSER_VERSION,
            "fix_info": fix_info,
            "progress_callback_supported": has_progress_callback,
            "method_signature": list(sig.parameters.keys()),
            "timestamp": datetime.now().isoformat(),
            "message": "MineruParser 修复状态检查完成"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "MineruParser 修复状态检查失败",
            "timestamp": datetime.now().isoformat()
        }


@app.post("/api/query")
async def query_documents(request: QueryRequest):
    if not rag:
        raise HTTPException(status_code=500, detail="RAG引擎未初始化")
    
    try:
        if RAG_ANYTHING_AVAILABLE and isinstance(rag, RAGAnything):
            # 使用RAG-Anything的查询方法
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: rag.query(request.query)
            )
        else:
            # 使用LightRAG的查询方法
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: rag.query(request.query, param=QueryParam(mode=request.mode))
            )
        
        return {"status": "success", "data": result, "mode": request.mode}
    except Exception as e:
        print(f"查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/query-profile")
async def query_with_profiling(request: QueryRequest):
    """带性能分析的查询接口"""
    if not rag:
        raise HTTPException(status_code=500, detail="RAG引擎未初始化")
    
    import time
    import tracemalloc
    
    # 开始内存追踪
    tracemalloc.start()
    
    # 记录各阶段时间
    timings = {}
    start_total = time.time()
    
    try:
        print(f"🔍 开始性能分析查询: {request.query[:50]}...")
        
        # 阶段1: 查询预处理
        start_prep = time.time()
        query_text = request.query.strip()
        mode = request.mode
        timings["preprocessing"] = time.time() - start_prep
        
        # 阶段2: Embedding计算 (如果需要)
        start_embed = time.time()
        # 这里实际的embedding计算在LightRAG内部进行
        timings["embedding_prep"] = time.time() - start_embed
        
        # 阶段3: 主要查询过程
        start_query = time.time()
        
        if RAG_ANYTHING_AVAILABLE and isinstance(rag, RAGAnything):
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: rag.query(query_text)
            )
        else:
            # 包装查询以获取更详细的时间信息
            def timed_query():
                inner_start = time.time()
                print(f"📊 LightRAG查询开始 - 模式: {mode}")
                
                result = rag.query(query_text, param=QueryParam(mode=mode))
                
                inner_duration = time.time() - inner_start
                print(f"📊 LightRAG查询完成 - 耗时: {inner_duration:.2f}秒")
                return result
            
            result = await asyncio.get_event_loop().run_in_executor(None, timed_query)
        
        timings["main_query"] = time.time() - start_query
        
        # 总时间
        timings["total"] = time.time() - start_total
        
        # 内存使用情况
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # 性能统计
        performance_stats = {
            "timings": {k: round(v, 3) for k, v in timings.items()},
            "memory": {
                "current_mb": round(current / 1024 / 1024, 2),
                "peak_mb": round(peak / 1024 / 1024, 2)
            },
            "query_info": {
                "mode": mode,
                "query_length": len(query_text),
                "result_length": len(result) if result else 0
            }
        }
        
        print(f"📊 查询性能统计:")
        print(f"  - 预处理: {timings['preprocessing']:.3f}s")
        print(f"  - 主查询: {timings['main_query']:.3f}s") 
        print(f"  - 总耗时: {timings['total']:.3f}s")
        print(f"  - 内存峰值: {performance_stats['memory']['peak_mb']}MB")
        
        return {
            "status": "success",
            "data": result,
            "mode": mode,
            "performance": performance_stats
        }
        
    except Exception as e:
        tracemalloc.stop()
        print(f"查询失败: {e}")
        timings["total"] = time.time() - start_total
        raise HTTPException(status_code=500, detail={
            "error": str(e),
            "timings": timings
        })

@app.post("/api/parse-document")
async def parse_document_complete(request: ParseDocumentRequest):
    """使用 RAG-Anything 的 process_document_complete 进行完整文档处理"""
    # 🎯 调试埋点：验证代码是否加载
    print("🔧 DEBUG: parse_document_complete 被调用，测试修复版本加载")
    print(f"🔧 DEBUG: 请求文件路径: {request.file_path}")
    
    if not rag:
        raise HTTPException(status_code=500, detail="RAG引擎未初始化")
    
    try:
        if RAG_ANYTHING_AVAILABLE and isinstance(rag, RAGAnything):
            print(f"🔄 开始完整文档处理: {request.file_path}")
            
            # 生成文件key（使用文件路径的basename）
            file_key = os.path.basename(request.file_path)
            
            # 定义进度回调函数
            async def progress_callback(progress: int, message: str):
                file_progress[file_key] = {
                    "progress": progress,
                    "message": message,
                    "file_path": request.file_path,
                    "timestamp": time.time()
                }
                print(f"📊 处理进度 [{file_key}]: {progress}% - {message}")
            
            try:
                # 初始化进度
                await progress_callback(0, "准备开始文档处理...")
                
                # 使用 RAG-Anything 的 process_document_complete 与进度回调
                await rag.process_document_complete(
                    file_path=request.file_path,
                    output_dir=request.output_dir,
                    parse_method=request.parse_method,
                    display_stats=request.display_stats,
                    progress_callback=progress_callback
                )
                print(f"✅ 文档处理完成: {request.file_path}")
            except Exception as e:
                await progress_callback(-1, f"处理失败: {str(e)}")
                print(f"❌ 文档处理异常: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            return {
                "status": "success", 
                "message": "文档完整处理成功",
                "file_path": request.file_path,
                "engine": "rag-anything"
            }
        else:
            # 回退到简单的文本插入（如果不是RAG-Anything引擎）
            raise HTTPException(
                status_code=501, 
                detail="完整文档处理需要 RAG-Anything 引擎"
            )
        
    except Exception as e:
        print(f"文档处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/insert")
async def insert_document(request: InsertRequest):
    """传统的文本插入接口，保持向后兼容"""
    if not rag:
        raise HTTPException(status_code=500, detail="RAG引擎未初始化")
    
    try:
        if RAG_ANYTHING_AVAILABLE and isinstance(rag, RAGAnything):
            # 使用RAG-Anything的插入方法
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: rag.insert(request.text)
            )
        else:
            # 使用LightRAG的插入方法
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: rag.insert(request.text)
            )
        
        return {"status": "success", "message": "文档插入成功"}
    except Exception as e:
        print(f"插入文档失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print(f"🚀 启动RAG服务 - 端口: {PORT}")
    print(f"📁 工作目录: {WORKING_DIR}")
    print(f"🔑 API密钥: {'已配置' if os.getenv('OPENAI_API_KEY') else '未配置'}")
    if rag:
        if RAG_ANYTHING_AVAILABLE and isinstance(rag, RAGAnything):
            print("🔧 使用引擎: RAG-Anything")
        else:
            print("🔧 使用引擎: LightRAG")
    else:
        print("⚠️ 警告: 没有可用的RAG引擎")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
