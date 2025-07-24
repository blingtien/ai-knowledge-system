#!/bin/bash
# RAG Knowledge Management Web Interface 启动脚本

echo "🚀 启动RAG知识管理Web界面"
echo "📍 访问地址: http://localhost:4000"
echo "🔗 或者: http://$(hostname -I | awk '{print $1}'):4000"
echo ""

# 进入项目目录
cd "$(dirname "$0")"

# 激活虚拟环境
echo "🔄 激活虚拟环境..."
source environments/rag-env/bin/activate

# 检查RAG服务状态
echo "🔍 检查RAG服务状态..."
if curl -s http://localhost:8001/health > /dev/null; then
    echo "✅ RAG服务运行正常"
else
    echo "❌ RAG服务未运行，请先启动RAG服务："
    echo "   source environments/rag-env/bin/activate"
    echo "   python scripts/service_manager.py start --service rag"
    exit 1
fi

# 启动Web界面
echo "🌐 启动Web界面服务..."
cd web_interface
python app.py