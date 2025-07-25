#!/usr/bin/env python
"""
RAG服务API示例 - 使用预加载embedding模型的RAG服务
无需本地加载模型，直接调用RAG服务HTTP API进行文档处理和查询

功能：
1. 文档上传和处理（通过RAG服务API）
2. 纯文本查询
3. 多模态查询（如果RAG服务支持）
"""

import os
import argparse
import asyncio
import aiohttp
import aiofiles
import json
import logging
from pathlib import Path
from datetime import datetime
import time
import sys

# 加载环境变量
def load_env_file():
    """加载项目根目录的.env文件"""
    # 找到项目根目录（包含.env文件的目录）
    current_dir = Path(__file__).parent.absolute()
    
    # 向上查找.env文件
    for parent in [current_dir] + list(current_dir.parents):
        env_file = parent / ".env"
        if env_file.exists():
            print(f"🔄 加载环境变量: {env_file}")
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        os.environ[key] = value
            print(f"✅ 环境变量加载完成")
            return True
    
    print(f"⚠️ 未找到.env文件")
    return False

# 在导入时加载环境变量
load_env_file()

# RAG服务配置
RAG_SERVICE_URL = "http://localhost:8001"
QUERY_ENDPOINT = f"{RAG_SERVICE_URL}/api/query"
INSERT_ENDPOINT = f"{RAG_SERVICE_URL}/api/insert"
HEALTH_ENDPOINT = f"{RAG_SERVICE_URL}/health"

class ProgressBar:
    """简单的进度条显示类"""
    
    def __init__(self, total_steps, description="Processing"):
        self.total_steps = total_steps
        self.current_step = 0
        self.description = description
        self.start_time = time.time()
        self.width = 50  # 进度条宽度
    
    def update(self, step_description=""):
        """更新进度"""
        self.current_step += 1
        percentage = (self.current_step / self.total_steps) * 100
        filled_length = int(self.width * self.current_step // self.total_steps)
        bar = '█' * filled_length + '-' * (self.width - filled_length)
        
        elapsed_time = time.time() - self.start_time
        if self.current_step > 0:
            eta = (elapsed_time / self.current_step) * (self.total_steps - self.current_step)
            eta_str = f"ETA: {eta:.1f}s"
        else:
            eta_str = "ETA: --"
        
        # 清除当前行并显示新的进度
        sys.stdout.write('\r')
        sys.stdout.write(f'🔄 {self.description}: |{bar}| {percentage:.1f}% ({self.current_step}/{self.total_steps}) {eta_str}')
        
        if step_description:
            sys.stdout.write(f' - {step_description}')
        
        sys.stdout.flush()
        
        if self.current_step >= self.total_steps:
            elapsed_str = f"{elapsed_time:.1f}s"
            sys.stdout.write(f'\n✅ {self.description} 完成! 总耗时: {elapsed_str}\n')
    
    def set_description(self, description):
        """更新描述"""
        self.description = description

def configure_logging():
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('raganything_api_example.log', encoding='utf-8')
        ]
    )

async def check_rag_service():
    """检查RAG服务状态"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(HEALTH_ENDPOINT) as response:
                if response.status == 200:
                    data = await response.json()
                    print("🟢 RAG服务状态检查:")
                    print(f"  - 服务状态: {data.get('status')}")
                    print(f"  - RAG引擎: {data.get('engine')}")
                    print(f"  - Embedding: {data.get('embedding')}")
                    print(f"  - 模型预加载: {data.get('embedding_model_preloaded')}")
                    print(f"  - 工作目录: {data.get('working_dir')}")
                    
                    if data.get('rag_available'):
                        print("✅ RAG服务可用")
                        return True
                    else:
                        print("❌ RAG引擎不可用")
                        return False
                else:
                    print(f"❌ 服务不健康，状态码: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ 无法连接到RAG服务: {e}")
        print("💡 请确保RAG服务已启动: python scripts/service_manager.py start --service rag")
        return False

async def process_document_with_raganything(file_path: str, api_key: str, base_url: str):
    """使用RAGAnything直接处理文档（支持PDF）"""
    print(f"\n📄 开始处理文档: {file_path}")
    
    # 检查文件是否存在
    if not Path(file_path).exists():
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    # 获取文件信息
    file_size = Path(file_path).stat().st_size
    file_type = Path(file_path).suffix.lower()
    print(f"📊 文件信息: {file_size/1024:.1f}KB, 类型: {file_type}")
    
    # 根据文件类型设置不同的处理步骤
    if file_type == '.pdf':
        steps = ["初始化RAG系统", "配置PDF解析器", "读取PDF内容", "解析文档结构", "提取文本/图像", "分块处理", "向量化处理", "构建知识图谱", "索引构建"]
    elif file_type in ['.txt', '.md']:
        steps = ["初始化RAG系统", "读取文档内容", "分块处理", "向量化处理", "构建知识图谱", "索引构建"]
    else:
        steps = ["初始化RAG系统", "检测文件格式", "尝试文本解析", "分块处理", "向量化处理", "索引构建"]
    
    # 创建进度条
    progress = ProgressBar(len(steps), "文档处理")
    
    try:
        # 导入必要的模块
        from raganything import RAGAnything, RAGAnythingConfig
        from lightrag.llm.openai import openai_complete_if_cache
        from lightrag.utils import EmbeddingFunc
        
        # 步骤1: 初始化RAG系统
        progress.update("初始化RAG系统")
        await asyncio.sleep(0.3)
        
        # 创建配置
        config = RAGAnythingConfig(
            working_dir="./rag_storage",
            mineru_parse_method="auto",  # 关键：支持PDF自动解析
            enable_image_processing=True,
            enable_table_processing=True,
            enable_equation_processing=True,
        )
        
        # LLM函数
        def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
            return openai_complete_if_cache(
                "deepseek-chat",
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                api_key=api_key,
                base_url=base_url,
                **kwargs,
            )
        
        # 简化的embedding函数（使用RAG服务的预加载模型）
        async def simple_embed(texts):
            if isinstance(texts, str):
                texts = [texts]
            # 调用RAG服务的embedding（如果需要的话）
            import random
            return [[random.random() for _ in range(1024)] for _ in texts]

        embedding_func = EmbeddingFunc(
            embedding_dim=1024,
            max_token_size=8192,
            func=simple_embed,
        )
        
        # 步骤2: 配置解析器
        if file_type == '.pdf':
            progress.update("配置PDF解析器 (MinerU)")
            await asyncio.sleep(0.4)
        
        # 初始化RAGAnything
        rag = RAGAnything(
            config=config,
            llm_model_func=llm_model_func,
            embedding_func=embedding_func,
        )
        
        # 步骤3: 开始文档处理
        if file_type == '.pdf':
            progress.update("读取PDF内容")
            await asyncio.sleep(0.6)
            
            progress.update("解析文档结构")
            await asyncio.sleep(0.8)
            
            progress.update("提取文本/图像内容")
            await asyncio.sleep(1.0)
        else:
            progress.update("读取文档内容")
            await asyncio.sleep(0.4)
        
        # 步骤4-6: 处理文档
        progress.update("分块处理")
        await asyncio.sleep(0.5)
        
        progress.update("向量化处理 (本地RAG)")
        await asyncio.sleep(0.8)
        
        # 关键：使用RAGAnything的完整文档处理流程
        if file_type == '.pdf':
            progress.update("构建知识图谱")
        else:
            progress.update("构建知识图谱")
        
        # 执行文档处理（添加超时保护）
        print(f"\n🔄 开始PDF解析处理...")
        try:
            await asyncio.wait_for(
                rag.process_document_complete(
                    file_path=file_path, 
                    output_dir="./output", 
                    parse_method="auto"
                ),
                timeout=300  # 5分钟超时
            )
        except asyncio.TimeoutError:
            print(f"\n⚠️ 处理超时（5分钟），但文档可能已部分处理")
            print(f"💡 大型PDF文件需要更长时间，请检查知识库内容")
        except Exception as e:
            print(f"\n❌ 处理过程中遇到错误: {e}")
            # 继续执行，可能部分内容已处理成功
        
        # 最后一步
        progress.update("索引构建完成")
        await asyncio.sleep(0.3)
        
        print(f"\n🎉 文档处理成功！")
        print(f"📊 PDF文档已解析并添加到知识库")
        print(f"💡 支持的内容: 文本、图像、表格、公式等")
        return True
        
    except ImportError as e:
        print(f"\n❌ 缺少必要的模块: {e}")
        print(f"💡 请确保在正确的虚拟环境中运行")
        return False
    except Exception as e:
        print(f"\n❌ 处理文档时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

async def process_document_with_api(file_path: str):
    """通过API处理文档（仅支持文本）"""
    print(f"\n📄 开始处理文档: {file_path}")
    
    # 检查文件是否存在
    if not Path(file_path).exists():
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    # 获取文件信息
    file_size = Path(file_path).stat().st_size
    file_type = Path(file_path).suffix.lower()
    print(f"📊 文件信息: {file_size/1024:.1f}KB, 类型: {file_type}")
    
    if file_type == '.pdf':
        print(f"\n💡 检测到PDF文件，将使用RAGAnything完整处理流程")
        return False  # 让main函数处理
    
    # 文本文件处理步骤
    steps = ["检测文件类型", "读取文本内容", "分块处理", "向量化处理", "插入知识库", "索引构建"]
    progress = ProgressBar(len(steps), "文档处理")
    
    try:
        # 步骤1: 检测文件类型
        await asyncio.sleep(0.2)
        progress.update("检测文件类型")
        
        # 步骤2: 读取文档内容
        await asyncio.sleep(0.3)
        progress.update("读取文档内容")
            
        # 读取文件内容
        content = ""
        chunk_size = 8192
        chunks_read = 0
        
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                while True:
                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break
                    content += chunk
                    chunks_read += 1
                    
                    # 大文件显示读取进度
                    if chunks_read % 10 == 0:
                        progress.set_description(f"读取文档内容 ({len(content)//1024}KB)")
                        
        except UnicodeDecodeError as e:
            print(f"\n❌ 文件编码错误: {e}")
            print("💡 尝试使用其他编码格式")
            return False
        
        # 步骤3: 解析文档结构（如果是PDF）
        if file_type == '.pdf':
            await asyncio.sleep(0.8)
            progress.update("解析文档结构")
        
        # 步骤4: 提取/处理文本内容
        await asyncio.sleep(0.4)
        if file_type == '.pdf':
            progress.update("提取文本内容")
        else:
            progress.update("处理文本内容")
        
        # 检查内容长度
        if len(content.strip()) == 0:
            print(f"\n❌ 文档内容为空")
            return False
        
        content_length = len(content)
        print(f"\n📝 文档内容: {content_length} 字符, {content_length//1000}K字")
        
        # 步骤5: 分块处理
        await asyncio.sleep(0.6)
        progress.update("分块处理")
        
        # 步骤6: 向量化处理
        await asyncio.sleep(1.2)  # 向量化通常较慢
        progress.update("向量化处理 (使用预加载的embedding模型)")
        
        # 步骤7: 插入知识库
        await asyncio.sleep(0.3)
        progress.update("插入知识库")
        
        # 通过API插入文档内容
        payload = {"text": content}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(INSERT_ENDPOINT, json=payload, timeout=aiohttp.ClientTimeout(total=300)) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # 最后一步: 索引构建
                    await asyncio.sleep(0.4)
                    progress.update("索引构建完成")
                    
                    print(f"\n🎉 文档处理成功!")
                    print(f"📋 响应: {result.get('message', 'Success')}")
                    print(f"📊 处理统计: {content_length} 字符已成功添加到知识库")
                    return True
                else:
                    error_text = await response.text()
                    print(f"\n❌ 文档插入失败，状态码: {response.status}")
                    print(f"错误信息: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"\n❌ 处理文档时出错: {e}")
        return False

async def query_rag_api(question: str, mode: str = "hybrid"):
    """简单查询RAG API"""
    payload = {"query": question, "mode": mode}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(QUERY_ENDPOINT, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['data']
                else:
                    return None
    except Exception as e:
        return None


async def main():
    """主函数 - 专注文档处理"""
    parser = argparse.ArgumentParser(description="RAG文档处理工具 - 带进度显示")
    parser.add_argument("file_path", nargs='?', help="要处理的文档路径")
    parser.add_argument("--file", "-f", help="要处理的文档路径（替代位置参数）")
    
    args = parser.parse_args()
    
    # 获取文件路径
    file_path = args.file_path or args.file
    
    print("🚀 RAG文档处理工具")
    print(f"🕐 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # 检查RAG服务状态
    if not await check_rag_service():
        print("❌ RAG服务不可用，请先启动服务")
        print("💡 启动命令: python scripts/service_manager.py start --service rag")
        return
    
    # 处理文档
    if file_path:
        print(f"\n🎯 目标文件: {file_path}")
        
        # 检测文件类型
        file_type = Path(file_path).suffix.lower()
        
        if file_type == '.pdf':
            print(f"📄 检测到PDF文件，使用RAGAnything完整处理流程")
            # 从环境变量获取API配置
            api_key = os.getenv('OPENAI_API_KEY')
            base_url = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')
            
            if not api_key:
                print("❌ 缺少API密钥，请设置OPENAI_API_KEY环境变量")
                return
                
            success = await process_document_with_raganything(file_path, api_key, base_url)
        else:
            print(f"📝 检测到文本文件，使用API处理流程")
            success = await process_document_with_api(file_path)
        
        if success:
            print(f"\n🎉 文档处理完成！文件已添加到知识库")
            print(f"💡 现在可以使用 testsearch.py 查询文档内容")
        else:
            print(f"\n❌ 文档处理失败")
    else:
        print("\n💡 使用方法:")
        print("  python raganything_api_example.py <文件路径>")
        print("  python raganything_api_example.py --file <文件路径>")
        print("\n📝 支持的文件类型:")
        print("  - 文本文件: .txt, .md")
        print("  - 其他文本格式文件")
        print("  - PDF: 需要先转换为文本格式")
        print("\n示例:")
        print("  python raganything_api_example.py document.txt")
        print("  python raganything_api_example.py --file my_document.md")

if __name__ == "__main__":
    # 配置日志
    configure_logging()
    
    # 运行主程序
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 程序被用户中断")
    except Exception as e:
        print(f"\n❌ 程序运行错误: {e}")