# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## System Architecture

This is an AI Knowledge Management System with microservices architecture:

- **RAG Service** (`services/rag.py`) - Document retrieval using LightRAG, supports local Qwen3 embeddings or OpenAI API
- **Memory Service** (`services/memory.py`) - Memory management using mem0, supports multi-user instances
- **MCP Services** - Expert servers that wrap core services for Model Context Protocol integration
- **Infrastructure** - PostgreSQL, Qdrant vector DB, Redis cache, Nginx reverse proxy

## Service Management

### Primary Commands

Start/stop services using the service manager:

```bash
python scripts/service_manager.py start --service <service_name>
python scripts/service_manager.py stop --service <service_name>
python scripts/service_manager.py status
```

Service options:
- `all` - All services 
- `core` - Just RAG and Memory (resource-efficient)
- `mcp` - MCP expert servers only
- `rag`, `memory`, `mcp-rag`, `mcp-memory`, `viz` - Individual services

### Docker Infrastructure

Start supporting services:
```bash
cd configs/
docker-compose up -d
```

This starts Qdrant (port 6333), PostgreSQL (port 5432), Redis (port 6379), and Nginx (port 80).

## Configuration

### Environment Setup

1. Copy environment template: `.env` file required in project root
2. Set `OPENAI_API_KEY` (required unless using local models only)
3. Virtual environments are in `environments/` directory

### Service Configurations

Service configs in `configs/` directory:
- `rag_service_config.yaml` - RAG service settings
- `memory_service_config.yaml` - Memory service settings
- `mcp_*_config.yaml` - MCP server configurations

## Key Service Details

### RAG Service (Port 8001)
- Uses LightRAG engine with graph-based retrieval
- Working directory: `/home/ragadmin/ai-knowledge-system/rag_storage`
- Supports local Qwen3-Embedding-0.6B model or OpenAI embeddings
- Endpoints: `/api/query`, `/api/insert`, `/health`

### Memory Service (Port 8765)
- Multi-user memory management with mem0
- Falls back to mock implementation if mem0 unavailable
- Endpoints: `/memories`, `/memories/search`, `/health`

### Health Checks

All services expose `/health` endpoints for status monitoring. The service manager automatically performs health checks during startup with configurable timeouts.

## Development Notes

- Services auto-generate from templates in `service_manager.py` if scripts don't exist
- State tracking in `services_state.json`
- Logs in `logs/` directory with rotation
- Memory limits configured per service in Docker Compose (total ~4.5GB)
- Services support graceful shutdown and restart