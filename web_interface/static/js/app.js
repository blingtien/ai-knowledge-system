const { createApp } = Vue;
const { ElMessage, ElMessageBox } = ElementPlus;

createApp({
    data() {
        return {
            // 系统状态
            systemStatus: {
                type: 'info',
                text: '检查中...'
            },
            
            // 导航
            activeTab: 'knowledge-base',
            
            // 知识库管理
            knowledgeBases: [],
            createKBDialog: false,
            newKB: {
                name: '',
                description: ''
            },
            
            // 文件上传
            uploadForm: {
                knowledgeBase: ''
            },
            fileList: [],
            uploading: false,
            
            // 文件列表
            files: [],
            selectedKB: '',
            filesLoading: false,
            
            // 查询
            queryForm: {
                query: '',
                mode: 'hybrid'
            },
            queryResult: null,
            queryHistory: [],
            querying: false,
            queryStatus: ''
        };
    },
    
    mounted() {
        this.init();
    },
    
    methods: {
        async init() {
            await this.checkSystemStatus();
            await this.loadKnowledgeBases();
            await this.loadFiles();
            this.loadQueryHistory();
        },
        
        // 系统状态检查
        async checkSystemStatus() {
            try {
                const response = await fetch('/health');
                const data = await response.json();
                
                if (data.status === 'healthy') {
                    this.systemStatus = {
                        type: 'success',
                        text: '系统正常'
                    };
                } else {
                    this.systemStatus = {
                        type: 'warning',
                        text: '系统异常'
                    };
                }
            } catch (error) {
                this.systemStatus = {
                    type: 'danger',
                    text: '连接失败'
                };
            }
        },
        
        // 菜单选择
        handleMenuSelect(index) {
            this.activeTab = index;
            if (index === 'file-list') {
                this.loadFiles();
            }
        },
        
        // 知识库管理
        async loadKnowledgeBases() {
            try {
                const response = await fetch('/api/knowledge-bases');
                const data = await response.json();
                this.knowledgeBases = data.knowledge_bases;
            } catch (error) {
                ElMessage.error('加载知识库列表失败');
            }
        },
        
        showCreateKBDialog() {
            this.createKBDialog = true;
            this.newKB = { name: '', description: '' };
        },
        
        async createKnowledgeBase() {
            if (!this.newKB.name.trim()) {
                ElMessage.warning('请输入知识库名称');
                return;
            }
            
            try {
                const response = await fetch('/api/knowledge-bases', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(this.newKB)
                });
                
                if (response.ok) {
                    ElMessage.success('知识库创建成功');
                    this.createKBDialog = false;
                    await this.loadKnowledgeBases();
                } else {
                    const error = await response.json();
                    ElMessage.error(error.detail || '创建失败');
                }
            } catch (error) {
                ElMessage.error('创建知识库失败');
            }
        },
        
        // 文件上传
        handleFileChange(file, fileList) {
            this.fileList = fileList;
        },
        
        clearFiles() {
            this.fileList = [];
            this.$refs.uploadRef.clearFiles();
        },
        
        async uploadFiles() {
            if (!this.uploadForm.knowledgeBase) {
                ElMessage.warning('请选择知识库');
                return;
            }
            
            if (this.fileList.length === 0) {
                ElMessage.warning('请选择文件');
                return;
            }
            
            this.uploading = true;
            
            try {
                const formData = new FormData();
                formData.append('knowledge_base', this.uploadForm.knowledgeBase);
                
                this.fileList.forEach(file => {
                    formData.append('files', file.raw);
                });
                
                const response = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    const data = await response.json();
                    ElMessage.success(`成功上传 ${data.uploaded_files} 个文件`);
                    
                    // 使用后端返回的文件信息更新本地状态
                    if (data.files) {
                        data.files.forEach(fileInfo => {
                            this.addFileToLocalList(fileInfo);
                        });
                    }
                    
                    this.clearFiles();
                    await this.loadFiles();
                    this.activeTab = 'file-list';
                } else {
                    const error = await response.json();
                    ElMessage.error(error.detail || '上传失败');
                }
            } catch (error) {
                ElMessage.error('上传文件失败: ' + error.message);
            } finally {
                this.uploading = false;
            }
        },
        
        // 添加文件到本地列表
        addFileToLocalList(fileInfo) {
            // 使用 safe_filename 作为唯一标识符
            const fileKey = fileInfo.safe_filename;
            
            // 如果文件不在本地列表中，添加它
            const existingIndex = this.files.findIndex(f => 
                f.safe_filename === fileKey || 
                (f.filename === fileInfo.filename && f.knowledge_base === fileInfo.knowledge_base)
            );
            
            if (existingIndex === -1) {
                this.files.push(fileInfo);
            } else {
                // 更新现有文件信息
                this.files[existingIndex] = fileInfo;
            }
        },
        
        // 文件列表
        async loadFiles() {
            this.filesLoading = true;
            try {
                const url = this.selectedKB ? 
                    `/api/files?knowledge_base=${this.selectedKB}` : 
                    '/api/files';
                    
                const response = await fetch(url);
                const data = await response.json();
                this.files = data.files;
            } catch (error) {
                ElMessage.error('加载文件列表失败');
            } finally {
                this.filesLoading = false;
            }
        },
        
        async startParsing(file) {
            try {
                // 立即更新本地状态为处理中
                const index = this.files.findIndex(f => 
                    f.safe_filename === file.safe_filename ||
                    (f.knowledge_base === file.knowledge_base && f.filename === file.filename)
                );
                
                if (index !== -1) {
                    this.files[index] = {
                        ...this.files[index],
                        status: 'processing',
                        progress: 1,
                        message: '正在启动解析任务...'
                    };
                }
                
                // 显示启动提示
                ElMessage.info({
                    message: `正在启动解析任务: ${file.filename}`,
                    duration: 2000
                });
                
                const formData = new FormData();
                formData.append('filename', file.filename);
                formData.append('knowledge_base', file.knowledge_base);
                
                const response = await fetch('/api/parse', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    // 立即启动进度监控
                    this.monitorProgress(file);
                } else {
                    const error = await response.json();
                    ElMessage.error(error.detail || '启动解析失败');
                    
                    // 恢复文件状态
                    if (index !== -1) {
                        this.files[index].status = 'uploaded';
                        this.files[index].progress = 0;
                    }
                }
            } catch (error) {
                ElMessage.error('启动解析失败: ' + error.message);
                
                // 恢复文件状态
                const index = this.files.findIndex(f => 
                    f.safe_filename === file.safe_filename ||
                    (f.knowledge_base === file.knowledge_base && f.filename === file.filename)
                );
                if (index !== -1) {
                    this.files[index].status = 'uploaded';
                    this.files[index].progress = 0;
                }
            }
        },
        
        async monitorProgress(file) {
            // 优先使用 safe_filename，其次使用组合键
            const fileKey = file.safe_filename || `${file.knowledge_base}_${file.filename}`;
            
            // 🔧 添加进度监控状态
            const progressState = {
                lastProgress: 0,
                stuckCount: 0,
                maxStuckCount: 30  // 如果60秒（30次*2秒）没有进度更新则停止
            };
            
            const checkProgress = async () => {
                try {
                    const response = await fetch(`/api/files/${encodeURIComponent(fileKey)}/status`);
                    
                    if (!response.ok) {
                        console.error(`获取文件状态失败: ${response.status}`);
                        progressState.stuckCount++;
                        
                        // 如果连续失败太多次，停止监控
                        if (progressState.stuckCount >= progressState.maxStuckCount) {
                            ElMessage.warning(`文件 ${file.filename} 进度监控超时`);
                            return;
                        }
                        
                        // 继续重试
                        setTimeout(checkProgress, 2000);
                        return;
                    }
                    
                    const data = await response.json();
                    
                    // 重置失败计数
                    progressState.stuckCount = 0;
                    
                    // 更新本地文件状态
                    const index = this.files.findIndex(f => 
                        f.safe_filename === fileKey ||
                        (f.knowledge_base === file.knowledge_base && f.filename === file.filename)
                    );
                    
                    if (index !== -1) {
                        // 🔧 添加进度动画效果
                        const oldProgress = this.files[index].progress || 0;
                        const newProgress = data.progress || 0;
                        
                        // 如果进度有更新，显示消息
                        if (newProgress > oldProgress && data.message) {
                            // 使用 Element Plus 的 Notification 显示进度消息
                            this.$notify({
                                title: `解析进度: ${newProgress}%`,
                                message: data.message,
                                type: 'info',
                                duration: 3000,
                                position: 'bottom-right'
                            });
                        }
                        
                        // 更新文件状态
                        this.files[index] = {
                            ...this.files[index],
                            status: data.status,
                            progress: newProgress,
                            error: data.error,
                            message: data.message  // 🔧 添加消息字段
                        };
                        
                        // 检查进度是否卡住
                        if (data.status === 'processing') {
                            if (newProgress === progressState.lastProgress) {
                                progressState.stuckCount++;
                            } else {
                                progressState.stuckCount = 0;
                                progressState.lastProgress = newProgress;
                            }
                        }
                    }
                    
                    // 根据状态决定是否继续监控
                    if (data.status === 'processing') {
                        // 🔧 动态调整轮询间隔
                        const interval = data.progress < 50 ? 1500 : 2000;  // 前期更频繁
                        setTimeout(checkProgress, interval);
                    } else if (data.status === 'completed') {
                        ElMessage.success({
                            message: `文件 ${file.filename} 解析完成！`,
                            duration: 5000,
                            showClose: true
                        });
                        
                        // 🔧 完成后刷新文件列表以确保状态同步
                        setTimeout(() => this.loadFiles(), 1000);
                    } else if (data.status === 'error') {
                        ElMessage.error({
                            message: `文件 ${file.filename} 解析失败: ${data.error || '未知错误'}`,
                            duration: 0,  // 不自动关闭
                            showClose: true
                        });
                    }
                } catch (error) {
                    console.error('监控进度失败:', error);
                    progressState.stuckCount++;
                    
                    // 如果不是太多失败，继续重试
                    if (progressState.stuckCount < progressState.maxStuckCount) {
                        setTimeout(checkProgress, 3000);  // 错误时延长重试间隔
                    } else {
                        ElMessage.error(`文件 ${file.filename} 进度监控失败`);
                    }
                }
            };
            
            // 🔧 立即开始第一次检查（不延迟）
            checkProgress();
        },
       
        // 改进的查询方法，包含进度模拟
        async performQuery() {
            if (!this.queryForm.query.trim()) {
                ElMessage.warning('请输入查询问题');
                return;
            }
            
            this.querying = true;
            this.queryResult = null;
            
            // 获取对应模式的状态更新序列
            const statusUpdates = this.getQueryStatusUpdates(this.queryForm.mode);
            
            try {
                // 启动进度模拟（不等待，让它并行运行）
                const progressPromise = this.simulateQueryProgress(statusUpdates);
                
                // 发送查询请求
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(this.queryForm)
                });
                
                if (response.ok) {
                    const data = await response.json();
                    
                    // 等待进度模拟完成，确保用户看到完整的进度
                    await progressPromise;
                    
                    this.queryResult = {
                        result: data.result,
                        mode: data.mode,
                        timestamp: data.timestamp
                    };
                    
                    this.queryStatus = '查询完成';
                    
                    // 添加到历史记录
                    this.queryHistory.unshift({
                        query: this.queryForm.query,
                        result: data.result,
                        mode: data.mode,
                        timestamp: data.timestamp
                    });
                    
                    // 限制历史记录数量
                    if (this.queryHistory.length > 10) {
                        this.queryHistory = this.queryHistory.slice(0, 10);
                    }
                    
                    this.saveQueryHistory();
                    ElMessage.success('查询完成');
                    
                } else {
                    const error = await response.json();
                    this.queryStatus = '查询失败';
                    ElMessage.error(error.detail || '查询失败');
                }
            } catch (error) {
                console.error('查询错误:', error);
                this.queryStatus = '查询异常';
                ElMessage.error('查询失败: ' + error.message);
            } finally {
                this.querying = false;
                // 3秒后清空状态信息
                setTimeout(() => {
                    this.queryStatus = '';
                }, 3000);
            }
        },
        
        // 获取查询状态更新
        getQueryStatusUpdates(mode) {
            if (mode === 'naive') {
                return [
                    { status: '正在预处理查询请求...' },
                    { status: '正在计算文本向量...' },
                    { status: '正在搜索相关文档...' },
                    { status: '正在整理查询结果...' }
                ];
            } else if (mode === 'local') {
                return [
                    { status: '正在预处理查询请求...' },
                    { status: '正在计算文本向量...' },
                    { status: '正在分析局部知识图谱...' },
                    { status: '正在发送请求到LLM...' },
                    { status: '正在等待LLM深度分析...' },
                    { status: '正在遍历关联知识节点...' },
                    { status: '正在生成最终答案...' }
                ];
            } else if (mode === 'global') {
                return [
                    { status: '正在预处理查询请求...' },
                    { status: '正在计算文本向量...' },
                    { status: '正在检索全局知识图谱...' },
                    { status: '正在发送请求到LLM...' },
                    { status: '正在等待LLM全局分析...' },
                    { status: '正在整合多维度信息并生成答案...' }
                ];
            } else { // hybrid
                return [
                    { status: '正在预处理查询请求...' },
                    { status: '正在计算文本向量...' },
                    { status: '正在执行相似度检索...' },
                    { status: '正在分析知识图谱结构...' },
                    { status: '正在发送请求到LLM...' },
                    { status: '正在等待LLM智能推理...' },
                    { status: '正在融合检索和推理结果...' }
                ];
            }
        },
        
        // 模拟查询进度
        async simulateQueryProgress(statusUpdates) {
            for (let i = 0; i < statusUpdates.length; i++) {
                if (!this.querying) break;
                
                const update = statusUpdates[i];
                this.queryStatus = update.status;
                
                // 根据查询模式调整延迟
                const delay = this.getProgressDelay(this.queryForm.mode);
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        },
         // 🔧 添加：在文件列表中显示进度详情
        formatProgressDisplay(file) {
            if (file.status === 'processing' && file.message) {
                return `${file.progress}% - ${file.message}`;
            }
            return `${file.progress}%`;
        },
        // 获取进度条颜色
        getProgressColor(percentage) {
            if (percentage < 30) return '#E6A23C';  // 橙色
            if (percentage < 70) return '#409EFF';  // 蓝色
            if (percentage < 100) return '#67C23A'; // 绿色
            return '#67C23A';  // 完成时绿色
        },
        // 获取进度延迟
        getProgressDelay(mode) {
            const delays = {
                'naive': 200,    // 快速模式
                'global': 800,   // 中等延迟
                'hybrid': 1000,  // 较慢
                'local': 1500    // 最慢
            };
            return delays[mode] || 1000;
        },
        
        // 获取模式显示名称
        getModeDisplayName(mode) {
            const names = {
                'naive': '快速检索',
                'local': '深度分析',
                'global': '全局分析', 
                'hybrid': '智能融合'
            };
            return names[mode] || mode;
        },
        
        // 获取模式描述
        getModeDescription(mode) {
            const descriptions = {
                'naive': '基于向量相似度的快速检索，适合简单问答',
                'local': '深度分析局部知识图谱，适合复杂推理任务',
                'global': '全局知识图谱分析，适合宏观概览问题',
                'hybrid': '融合多种检索策略，平衡效果与效率'
            };
            return descriptions[mode] || '未知模式';
        },
        
        // 获取预计时间
        getEstimatedTime(mode) {
            const times = {
                'naive': '约1秒',
                'local': '约12秒',
                'global': '约6秒',
                'hybrid': '约9秒'
            };
            return times[mode] || '计算中...';
        },
        
        clearQuery() {
            this.queryForm.query = '';
            this.queryResult = null;
            this.queryHistory = [];
            this.queryStatus = '';
            // 清空本地存储的历史记录
            localStorage.removeItem('queryHistory');
            ElMessage.success('已清空查询内容和历史记录');
        },
        
        // 本地存储
        saveQueryHistory() {
            localStorage.setItem('queryHistory', JSON.stringify(this.queryHistory));
        },
        
        loadQueryHistory() {
            const saved = localStorage.getItem('queryHistory');
            if (saved) {
                this.queryHistory = JSON.parse(saved);
            }
        },
        
        // 工具函数
        formatDate(dateString) {
            const date = new Date(dateString);
            return date.toLocaleString('zh-CN');
        },
        
        formatFileSize(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        },
        
        getStatusType(status) {
            const statusMap = {
                'uploaded': 'info',
                'processing': 'warning',
                'completed': 'success',
                'error': 'danger'
            };
            return statusMap[status] || 'info';
        },
        
        getStatusText(status) {
            const statusMap = {
                'uploaded': '已上传',
                'processing': '解析中',
                'completed': '已完成',
                'error': '解析失败'
            };
            return statusMap[status] || status;
        },
        
        formatResult(text) {
            // 简单的格式化处理
            return text.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        },
        
        // 🔧 新增：重置单个文件状态
        async resetFileStatus(file) {
            try {
                const fileKey = file.safe_filename || `${file.knowledge_base}_${file.filename}`;
                const response = await fetch(`/api/files/${encodeURIComponent(fileKey)}/reset`, {
                    method: 'POST'
                });
                
                if (response.ok) {
                    ElMessage.success(`文件 ${file.filename} 状态已重置`);
                    await this.loadFiles();
                } else {
                    const error = await response.json();
                    ElMessage.error(`重置失败: ${error.detail}`);
                }
            } catch (error) {
                ElMessage.error('重置文件状态失败: ' + error.message);
            }
        },
        
        // 🔧 新增：重置所有文件状态
        async resetAllFileStatus() {
            try {
                const confirmResult = await ElMessageBox.confirm(
                    '确定要重置所有文件状态为"已上传"吗？',
                    '确认操作',
                    {
                        confirmButtonText: '确定',
                        cancelButtonText: '取消',
                        type: 'warning'
                    }
                );
                
                let resetCount = 0;
                let errorCount = 0;
                
                for (const file of this.files) {
                    if (file.status !== 'uploaded') {
                        try {
                            const fileKey = file.safe_filename || `${file.knowledge_base}_${file.filename}`;
                            const response = await fetch(`/api/files/${encodeURIComponent(fileKey)}/reset`, {
                                method: 'POST'
                            });
                            
                            if (response.ok) {
                                resetCount++;
                            } else {
                                errorCount++;
                            }
                        } catch (error) {
                            errorCount++;
                        }
                    }
                }
                
                if (resetCount > 0) {
                    ElMessage.success(`成功重置 ${resetCount} 个文件状态${errorCount > 0 ? `，${errorCount} 个文件重置失败` : ''}`);
                    await this.loadFiles();
                } else {
                    ElMessage.info('没有需要重置的文件');
                }
                
            } catch (error) {
                if (error !== 'cancel') {
                    ElMessage.error('批量重置失败: ' + error.message);
                }
            }
        },
        
        // 🔧 新增：删除文件
        async deleteFile(file) {
            try {
                const confirmResult = await ElMessageBox.confirm(
                    `确定要删除文件 "${file.filename}" 吗？`,
                    '确认删除',
                    {
                        confirmButtonText: '确定',
                        cancelButtonText: '取消',
                        type: 'warning'
                    }
                );
                
                const fileKey = file.safe_filename || `${file.knowledge_base}_${file.filename}`;
                const response = await fetch(`/api/files/${encodeURIComponent(fileKey)}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    const data = await response.json();
                    ElMessage.success(data.message || '文件删除成功');
                    await this.loadFiles(); // 重新加载文件列表
                } else {
                    const error = await response.json();
                    ElMessage.error(`删除失败: ${error.detail}`);
                }
                
            } catch (error) {
                if (error !== 'cancel') {
                    ElMessage.error('删除文件失败: ' + error.message);
                }
            }
        }
    }
}).use(ElementPlus).mount('#app');