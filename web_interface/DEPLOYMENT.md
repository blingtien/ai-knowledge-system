# RAG Web Interface 部署指南

## 版本信息
- 版本: v2.0 (2025-01-22)
- 最新修复: 文件名处理、进度跟踪、状态查询优化

## 快速部署

### 1. 解压源码
```bash
tar -xzf web_interface_source_complete.tar.gz
cd web_interface/
```

### 2. 安装依赖
```bash
pip install --break-system-packages fastapi[all] uvicorn aiofiles aiohttp
```

### 3. 配置环境变量
确保 `.env` 文件中包含：
```env
# RAG服务配置
RAG_WORKING_DIR=/path/to/rag_storage  # 绝对路径
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.deepseek.com/v1
```

### 4. 启动服务
```bash
python3 app.py
```

## 访问界面
- 本地访问: http://localhost:4000
- 网络访问: http://your_ip:4000

## 功能特性

### ✅ 已修复的问题
1. **文件名处理不一致** - 统一使用safe_filename进行状态跟踪
2. **查询进度模拟** - 实现了真实的查询进度展示
3. **后端文件状态查询** - 多重匹配策略，支持URL编码
4. **文件上传状态跟踪** - 完整的文件信息返回和状态管理
5. **favicon.ico 404错误** - 添加了网站图标

### 📋 核心功能
- 📚 知识库管理（创建、查看）
- 📤 批量文件上传（支持长中文文件名）
- 🔄 实时解析进度跟踪（真实进度，非模拟）
- 🔍 4种查询模式：
  - 快速检索 (naive) - ~1秒
  - 全局分析 (global) - ~6秒  
  - 智能融合 (hybrid) - ~9秒
  - 深度分析 (local) - ~12秒
- 📋 文件列表管理和状态监控
- 📚 查询历史记录

### 🔧 技术架构
- **后端**: FastAPI + Python 3.12
- **前端**: Vue.js 3 + Element Plus
- **文件处理**: UUID安全文件名 + 真实进度跟踪
- **状态管理**: 多重匹配策略 + 本地状态同步

### 📁 目录结构
```
web_interface/
├── app.py                 # FastAPI后端主程序
├── static/
│   ├── index.html        # Vue.js前端页面
│   ├── favicon.ico       # 网站图标
│   ├── js/
│   │   └── app.js        # 前端逻辑（481行）
│   └── css/
│       └── styles.css    # 界面样式
├── README.md             # 使用说明
├── DEPLOYMENT.md         # 本部署指南
├── uploads/              # 文件上传目录（运行时创建）
├── knowledge_bases/      # 知识库目录（运行时创建）
└── web.log              # 运行日志
```

## 依赖服务

### 必需服务
- **RAG服务**: 运行在 localhost:8001
- **Python环境**: 3.8+

### 可选优化
- **Qdrant向量数据库**: localhost:6333
- **Redis缓存**: localhost:6379
- **PostgreSQL**: localhost:5432

## API接口文档

### 核心API
- `GET /` - 主页面
- `GET /health` - 健康检查
- `POST /api/upload` - 文件上传
- `POST /api/parse` - 启动文件解析
- `GET /api/files/{file_key}/status` - 文件状态查询
- `POST /api/query` - 知识库查询

### 文件上传响应格式
```json
{
  "status": "success",
  "uploaded_files": 2,
  "files": [
    {
      "filename": "original_name.pdf",
      "safe_filename": "kb_uuid.pdf", 
      "size": 1024,
      "status": "uploaded",
      "progress": 0,
      "knowledge_base": "kb_name",
      "upload_time": "2025-01-22T14:00:00"
    }
  ]
}
```

## 故障排除

### 常见问题
1. **端口4000被占用**: `lsof -i :4000` 查看占用进程
2. **RAG服务连接失败**: 确保localhost:8001可访问
3. **文件上传失败**: 检查uploads目录权限
4. **中文文件名错误**: 已通过UUID安全文件名解决

### 日志查看
```bash
tail -f web.log
```

## 更新记录

### v2.0 (2025-01-22)
- ✅ 修复文件名处理不一致问题
- ✅ 实现真实的查询进度模拟
- ✅ 改进后端文件状态查询逻辑
- ✅ 优化文件上传状态跟踪
- ✅ 添加favicon.ico支持
- ✅ 统一RAG存储路径配置

### v1.0 (2025-01-21)
- 🎉 初始版本发布
- 📚 基础知识库管理
- 📤 文件上传和解析
- 🔍 多模式查询功能