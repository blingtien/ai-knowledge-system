#!/usr/bin/env python3
"""
数据库模块 - 文件元数据持久化存储
使用项目现有的PostgreSQL数据库
"""

import os
import asyncio
import asyncpg
from datetime import datetime
from typing import List, Dict, Optional, Any
from contextlib import asynccontextmanager

# 从环境变量或配置中读取数据库连接信息
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '5432'))
DB_NAME = os.getenv('DB_NAME', 'ai_knowledge')
DB_USER = os.getenv('DB_USER', 'ai_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'ai_password')

# 构建数据库连接URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print(f"🔌 数据库连接配置:")
print(f"  - Host: {DB_HOST}:{DB_PORT}")
print(f"  - Database: {DB_NAME}")
print(f"  - User: {DB_USER}")

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        self.pool = None
    
    async def init_pool(self):
        """初始化连接池"""
        try:
            self.pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            print("✅ 数据库连接池初始化成功")
            await self.create_tables()
        except Exception as e:
            print(f"❌ 数据库连接池初始化失败: {e}")
            raise
    
    async def close_pool(self):
        """关闭连接池"""
        if self.pool:
            await self.pool.close()
            print("✅ 数据库连接池已关闭")
    
    @asynccontextmanager
    async def get_connection(self):
        """获取数据库连接的上下文管理器"""
        if not self.pool:
            await self.init_pool()
        
        conn = await self.pool.acquire()
        try:
            yield conn
        finally:
            await self.pool.release(conn)
    
    async def create_tables(self):
        """创建必要的数据表"""
        async with self.get_connection() as conn:
            # 创建知识库表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_bases (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    description TEXT DEFAULT '',
                    path VARCHAR(500) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建文件元数据表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS file_metadata (
                    id SERIAL PRIMARY KEY,
                    safe_filename VARCHAR(255) UNIQUE NOT NULL,
                    original_filename VARCHAR(255) NOT NULL,
                    knowledge_base VARCHAR(255) NOT NULL,
                    file_path VARCHAR(500) NOT NULL,
                    size BIGINT NOT NULL,
                    upload_time TIMESTAMP NOT NULL,
                    status VARCHAR(50) DEFAULT 'uploaded',
                    progress INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (knowledge_base) REFERENCES knowledge_bases(name) ON DELETE CASCADE
                )
            """)
            
            # 创建索引以提高查询性能
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_metadata_knowledge_base 
                ON file_metadata(knowledge_base)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_metadata_status 
                ON file_metadata(status)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_metadata_safe_filename 
                ON file_metadata(safe_filename)
            """)
            
            print("✅ 数据库表结构初始化完成")

# 全局数据库管理器实例
db_manager = DatabaseManager()

class KnowledgeBaseDB:
    """知识库数据库操作类"""
    
    @staticmethod
    async def create_knowledge_base(name: str, description: str = "", path: str = "") -> Dict[str, Any]:
        """创建知识库记录"""
        async with db_manager.get_connection() as conn:
            try:
                result = await conn.fetchrow("""
                    INSERT INTO knowledge_bases (name, description, path, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $4)
                    RETURNING id, name, description, path, created_at, updated_at
                """, name, description, path, datetime.now())
                
                return dict(result)
            except asyncpg.UniqueViolationError:
                raise ValueError(f"知识库 '{name}' 已存在")
    
    @staticmethod
    async def get_knowledge_base(name: str) -> Optional[Dict[str, Any]]:
        """获取知识库信息"""
        async with db_manager.get_connection() as conn:
            result = await conn.fetchrow("""
                SELECT * FROM knowledge_bases WHERE name = $1
            """, name)
            return dict(result) if result else None
    
    @staticmethod
    async def list_knowledge_bases() -> List[Dict[str, Any]]:
        """获取所有知识库列表"""
        async with db_manager.get_connection() as conn:
            results = await conn.fetch("""
                SELECT kb.*, 
                       COUNT(fm.id) as file_count
                FROM knowledge_bases kb
                LEFT JOIN file_metadata fm ON kb.name = fm.knowledge_base
                GROUP BY kb.id, kb.name, kb.description, kb.path, kb.created_at, kb.updated_at
                ORDER BY kb.created_at DESC
            """)
            return [dict(row) for row in results]
    
    @staticmethod
    async def delete_knowledge_base(name: str) -> bool:
        """删除知识库（级联删除相关文件记录）"""
        async with db_manager.get_connection() as conn:
            result = await conn.execute("""
                DELETE FROM knowledge_bases WHERE name = $1
            """, name)
            return result != "DELETE 0"

class FileMetadataDB:
    """文件元数据数据库操作类"""
    
    @staticmethod
    async def create_file_record(
        safe_filename: str,
        original_filename: str,
        knowledge_base: str,
        file_path: str,
        size: int,
        upload_time: datetime = None
    ) -> Dict[str, Any]:
        """创建文件记录"""
        if upload_time is None:
            upload_time = datetime.now()
        
        async with db_manager.get_connection() as conn:
            try:
                result = await conn.fetchrow("""
                    INSERT INTO file_metadata 
                    (safe_filename, original_filename, knowledge_base, file_path, size, upload_time, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $7)
                    RETURNING *
                """, safe_filename, original_filename, knowledge_base, file_path, size, upload_time, datetime.now())
                
                return dict(result)
            except asyncpg.UniqueViolationError:
                raise ValueError(f"文件 '{safe_filename}' 已存在")
            except asyncpg.ForeignKeyViolationError:
                raise ValueError(f"知识库 '{knowledge_base}' 不存在")
    
    @staticmethod
    async def get_file_by_safe_filename(safe_filename: str) -> Optional[Dict[str, Any]]:
        """通过safe_filename获取文件信息"""
        async with db_manager.get_connection() as conn:
            result = await conn.fetchrow("""
                SELECT * FROM file_metadata WHERE safe_filename = $1
            """, safe_filename)
            return dict(result) if result else None
    
    @staticmethod
    async def get_file_by_original_filename(original_filename: str, knowledge_base: str = None) -> Optional[Dict[str, Any]]:
        """通过原始文件名获取文件信息"""
        async with db_manager.get_connection() as conn:
            if knowledge_base:
                result = await conn.fetchrow("""
                    SELECT * FROM file_metadata 
                    WHERE original_filename = $1 AND knowledge_base = $2
                    ORDER BY created_at DESC LIMIT 1
                """, original_filename, knowledge_base)
            else:
                result = await conn.fetchrow("""
                    SELECT * FROM file_metadata 
                    WHERE original_filename = $1
                    ORDER BY created_at DESC LIMIT 1
                """, original_filename)
            return dict(result) if result else None
    
    @staticmethod
    async def update_file_status(safe_filename: str, status: str, progress: int = None, error_message: str = None) -> bool:
        """更新文件处理状态"""
        async with db_manager.get_connection() as conn:
            update_fields = ["status = $2", "updated_at = $3"]
            params = [safe_filename, status, datetime.now()]
            
            if progress is not None:
                update_fields.append(f"progress = ${len(params) + 1}")
                params.append(progress)
            
            if error_message is not None:
                update_fields.append(f"error_message = ${len(params) + 1}")
                params.append(error_message)
            
            query = f"""
                UPDATE file_metadata 
                SET {', '.join(update_fields)}
                WHERE safe_filename = $1
            """
            
            result = await conn.execute(query, *params)
            return result != "UPDATE 0"
    
    @staticmethod
    async def list_files(knowledge_base: str = None) -> List[Dict[str, Any]]:
        """获取文件列表"""
        async with db_manager.get_connection() as conn:
            if knowledge_base:
                results = await conn.fetch("""
                    SELECT * FROM file_metadata 
                    WHERE knowledge_base = $1
                    ORDER BY created_at DESC
                """, knowledge_base)
            else:
                results = await conn.fetch("""
                    SELECT * FROM file_metadata 
                    ORDER BY created_at DESC
                """)
            return [dict(row) for row in results]
    
    @staticmethod
    async def delete_file(safe_filename: str) -> Optional[Dict[str, Any]]:
        """删除文件记录并返回被删除的记录信息"""
        async with db_manager.get_connection() as conn:
            result = await conn.fetchrow("""
                DELETE FROM file_metadata 
                WHERE safe_filename = $1
                RETURNING *
            """, safe_filename)
            return dict(result) if result else None
    
    @staticmethod
    async def get_files_by_status(status: str) -> List[Dict[str, Any]]:
        """按状态获取文件列表"""
        async with db_manager.get_connection() as conn:
            results = await conn.fetch("""
                SELECT * FROM file_metadata 
                WHERE status = $1
                ORDER BY created_at DESC
            """, status)
            return [dict(row) for row in results]

# 数据库初始化函数
async def init_database():
    """初始化数据库连接和表结构"""
    try:
        await db_manager.init_pool()
        print("🗄️ 数据库初始化完成")
        return True
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return False

# 数据库关闭函数
async def close_database():
    """关闭数据库连接"""
    await db_manager.close_pool()
    print("🗄️ 数据库连接已关闭")

if __name__ == "__main__":
    # 测试数据库连接
    async def test_db():
        success = await init_database()
        if success:
            print("✅ 数据库测试成功")
            await close_database()
        else:
            print("❌ 数据库测试失败")
    
    asyncio.run(test_db())