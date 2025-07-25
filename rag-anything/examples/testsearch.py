#!/usr/bin/env python3
"""
RAG服务HTTP API测试 - 使用预加载的embedding模型
无需本地加载模型，直接调用RAG服务API
"""
import asyncio
import aiohttp
import json
import time
from datetime import datetime

# RAG服务配置
RAG_SERVICE_URL = "http://localhost:8001"
QUERY_ENDPOINT = f"{RAG_SERVICE_URL}/api/query"
HEALTH_ENDPOINT = f"{RAG_SERVICE_URL}/health"

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

async def query_rag_api(question: str, mode: str = "hybrid"):
    """调用RAG服务API进行查询"""
    payload = {
        "query": question,
        "mode": mode
    }
    
    start_time = time.time()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(QUERY_ENDPOINT, json=payload) as response:
                end_time = time.time()
                duration = end_time - start_time
                
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ {mode.upper()}模式查询成功 (耗时: {duration:.2f}秒)")
                    return data['data'], duration
                else:
                    error_text = await response.text()
                    print(f"❌ {mode.upper()}模式查询失败 (耗时: {duration:.2f}秒)")
                    print(f"  状态码: {response.status}")
                    print(f"  错误: {error_text}")
                    return None, duration
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"❌ {mode.upper()}模式查询异常 (耗时: {duration:.2f}秒): {e}")
        return None, duration

async def test_different_modes():
    """测试不同查询模式"""
    print("🚀 RAG API测试开始")
    print(f"🕐 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 检查服务状态
    if not await check_rag_service():
        return
    
    # 获取用户输入的问题
    print(f"\n💬 请输入您的问题:")
    question = input("❓ 问题: ").strip()
    
    if not question:
        print("❌ 问题不能为空，使用默认问题")
        question = "什么是需求响应？"
    
    print(f"\n📝 查询问题: {question}")
    print("=" * 60)
    
    # 测试不同模式
    modes = [
        ("hybrid", "混合检索"),
        ("local", "局部检索"), 
        ("global", "全局检索"),
        ("naive", "简单检索")
    ]
    
    results = {}
    total_time = 0
    
    for mode, description in modes:
        print(f"\n🔧 {mode.title()}模式 ({description}):")
        result, duration = await query_rag_api(question, mode)
        
        if result:
            # 灵活显示长度：短回答完整显示，长回答智能截取
            if len(result) <= 300:
                # 短回答完整显示
                print(f"📋 回答: {result}")
            elif len(result) <= 800:
                # 中等长度显示更多
                print(f"📋 回答: {result[:600]}{'...' if len(result) > 600 else ''}")
            else:
                # 长回答显示开头部分
                print(f"📋 回答: {result[:800]}...")
                print(f"💡 完整回答共{len(result)}字符，已显示前800字符")
            
            results[mode] = {"result": result, "duration": duration}
            total_time += duration
        
        # 短暂等待避免过快请求
        await asyncio.sleep(0.5)
    
    # 性能总结
    print(f"\n📊 性能总结:")
    print(f"  - 成功查询: {len(results)}/{len(modes)}")
    if results:
        durations = [r["duration"] for r in results.values()]
        print(f"  - 总耗时: {total_time:.2f}秒")
        print(f"  - 平均耗时: {sum(durations)/len(durations):.2f}秒")
        print(f"  - 最快查询: {min(durations):.2f}秒")
        print(f"  - 最慢查询: {max(durations):.2f}秒")
        
        # 性能分析
        first_duration = durations[0] if durations else 0
        avg_subsequent = sum(durations[1:]) / len(durations[1:]) if len(durations) > 1 else 0
        
        if len(durations) > 1 and first_duration > avg_subsequent * 1.5:
            print(f"⚠️  首次查询较慢: {first_duration:.2f}s vs 后续平均: {avg_subsequent:.2f}s")
        else:
            print(f"✅ 性能稳定 - embedding模型预加载优化生效!")
    
    print(f"\n✅ 测试完成!")

if __name__ == "__main__":
    try:
        asyncio.run(test_different_modes())
    except KeyboardInterrupt:
        print("\n🛑 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
