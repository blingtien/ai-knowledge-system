#!/bin/bash
while true; do
    clear
    echo "=== 10GB AI知识管理系统监控 $(date) ==="
    echo ""
    
    echo "=== 系统内存使用 ==="
    free -h
    echo ""
    
    echo "=== Docker容器资源使用 ==="
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}"
    echo ""
    
    echo "=== 内存分配达成度 ==="
    USED_MEM=$(free -m | awk '/^Mem:/{print $3}')
    TOTAL_MEM=$(free -m | awk '/^Mem:/{print $2}')
    USAGE_PERCENT=$((USED_MEM * 100 / TOTAL_MEM))
    echo "物理内存使用率: ${USAGE_PERCENT}% (${USED_MEM}MB / ${TOTAL_MEM}MB)"
    
    if [ $USAGE_PERCENT -gt 90 ]; then
        echo "🔴 内存使用率过高！"
    elif [ $USAGE_PERCENT -gt 80 ]; then
        echo "🟡 内存使用率较高"
    else
        echo "🟢 内存使用率正常"
    fi
    
    echo ""
    echo "按Ctrl+C退出监控"
    sleep 10
done
