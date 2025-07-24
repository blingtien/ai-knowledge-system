#!/usr/bin/env python3
"""
测试MinerU进度回调机制 - 不执行实际解析
"""
import asyncio
import requests
import time

async def test_progress_callback():
    """模拟MinerU进度回调测试"""
    
    # 测试文件key
    test_file_key = "test_progress.pdf"
    
    print("🔧 开始测试MinerU进度回调机制...")
    
    # 模拟进度回调函数
    async def mock_progress_callback(progress: int, message: str):
        print(f"📊 模拟进度回调: {progress}% - {message}")
        
        # 直接向RAG服务的file_progress字典写入进度
        # 这模拟了MinerU parser中progress_callback的行为
        try:
            # 这里我们测试RAG服务是否能接收和存储进度信息
            # 实际的进度存储在services/rag.py的file_progress全局字典中
            pass
        except Exception as e:
            print(f"❌ 进度回调失败: {e}")
    
    # 模拟进度更新序列
    progress_sequence = [
        (10, "开始文档解析..."),
        (25, "正在识别文档结构..."),  
        (40, "正在提取文本内容..."),
        (60, "正在处理表格和图像..."),
        (80, "正在生成Markdown格式..."),
        (95, "正在完成最终处理..."),
        (100, "文档解析完成!")
    ]
    
    # 执行模拟进度更新
    for progress, message in progress_sequence:
        await mock_progress_callback(progress, message)
        
        # 测试能否从RAG服务查询到这个进度
        try:
            response = requests.get(f"http://localhost:8001/api/progress/{test_file_key}", timeout=2)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ RAG服务进度查询成功: {data}")
            else:
                print(f"⚠️ RAG服务进度查询失败: {response.status_code}")
        except Exception as e:
            print(f"❌ 进度查询异常: {e}")
        
        await asyncio.sleep(1)  # 间隔1秒
    
    print("🎯 MinerU进度回调测试完成!")

if __name__ == "__main__":
    asyncio.run(test_progress_callback())