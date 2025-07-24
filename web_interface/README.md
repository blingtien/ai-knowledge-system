# RAG Knowledge Management Web Interface

## 文件说明

这是一个基于FastAPI和Vue.js构建的RAG知识管理Web界面，运行在端口4000。

### 核心文件

1. **app.py** - FastAPI后端服务主程序
   - 提供知识库管理API
   - 文件上传和解析功能
   - 查询代理服务
   - 真实进度跟踪

2. **static/index.html** - 主页面HTML模板
   - 使用Vue.js 3和Element Plus UI框架
   - 响应式布局设计

3. **static/js/app.js** - Vue.js应用逻辑
   - 知识库管理
   - 文件上传和解析监控
   - 4种查询模式（快速检索、全局分析、智能融合、深度分析）
   - 查询历史管理

4. **static/css/styles.css** - 界面样式文件

### 功能特性

- 📚 知识库管理（创建、查看）
- 📤 批量文件上传
- 🔄 实时解析进度跟踪
- 🔍 多模式智能查询
- 📋 文件列表管理
- 📚 查询历史记录

### 安装依赖

```bash
pip install fastapi[all] uvicorn aiofiles aiohttp
```

### 运行服务

```bash
python3 app.py
```

访问地址：http://localhost:4000

### 目录结构

```
web_interface/
├── app.py                 # 后端主程序
├── static/
│   ├── index.html        # 前端页面
│   ├── js/
│   │   └── app.js        # Vue.js应用
│   └── css/
│       └── styles.css    # 样式文件
├── uploads/              # 文件上传目录（运行时创建）
├── knowledge_bases/      # 知识库目录（运行时创建）
└── web.log              # 运行日志
```

### API接口

- `GET /` - 主页面
- `GET /health` - 健康检查
- `GET /api/knowledge-bases` - 获取知识库列表
- `POST /api/knowledge-bases` - 创建知识库
- `GET /api/files` - 获取文件列表
- `POST /api/upload` - 上传文件
- `POST /api/parse` - 开始解析文件
- `GET /api/files/{file_key}/status` - 获取文件状态
- `POST /api/query` - 查询知识库

### 注意事项

- 需要RAG服务运行在localhost:8001
- 支持PDF、TXT、MD等格式文件
- 使用UUID生成安全文件名避免中文文件名过长问题
- 实现了真实的文件解析进度跟踪