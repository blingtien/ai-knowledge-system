#!/bin/bash
echo "=== 启动10GB优化版AI知识管理系统 ==="

# 检查可用内存
AVAILABLE_MEM=$(free -m | awk '/^Mem:/{print $7}')
if [ $AVAILABLE_MEM -lt 8000 ]; then
    echo "警告: 可用内存少于8GB，建议释放内存后再启动"
    free -h
    exit 1
fi

# 优化系统参数
echo "优化系统参数..."
echo 1 > /proc/sys/vm/drop_caches 2>/dev/null || sudo sh -c 'echo 1 > /proc/sys/vm/drop_caches'
echo 5 > /proc/sys/vm/swappiness 2>/dev/null || echo "vm.swappiness=5" | sudo tee -a /etc/sysctl.conf

# 启动基础服务
echo "启动基础数据服务..."
docker-compose -f configs/docker-compose.yml up -d

# 等待基础服务就绪
sleep 15

# 启动AI服务 - 使用优化配置
echo "启动AI服务..."
python3 scripts/service_manager.py start --service rag --config configs/rag_service_config.yaml
sleep 10

python3 scripts/service_manager.py start --service memory --config configs/memory_service_config.yaml
sleep 10

# 验证服务状态
echo "验证服务状态:"
python3 scripts/service_manager.py status

echo "系统内存使用情况:"
free -h

echo "Docker容器资源使用:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

echo ""
echo "🎉 10GB优化版系统启动完成!"
echo "📊 监控命令: watch -n 5 'free -h && echo && docker stats --no-stream'"
