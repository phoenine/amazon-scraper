# Amazon Product Scraper

基于FastAPI和Playwright的Amazon产品信息抓取系统，支持多站点、并发抓取、数据持久化到Supabase。

## 功能特性

- 🚀 **高性能抓取**: 基于Playwright的异步抓取引擎
- 🌍 **多站点支持**: 支持amazon.com, amazon.co.jp等多个站点
- 📊 **完整数据**: 抓取标题、评分、价格、图片、要点、属性等完整信息
- 💾 **数据持久化**: 使用Supabase (PostgreSQL + Storage) 存储
- 🔄 **智能缓存**: TTL缓存策略，避免重复抓取
- 🛡️ **反爬应对**: 浏览器指纹伪装、并发控制、重试机制
- 📈 **可观测性**: 任务状态跟踪、统计信息

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
cd /Users/phoenine/Documents/github/supabase/test-project/pyapp

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -r requirements.txt

# 安装Playwright浏览器
playwright install chromium
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入你的Supabase配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

### 3. 设置Supabase数据库

在Supabase SQL编辑器中执行以下迁移文件：

1. `migrations/001_create_tables.sql` - 创建数据表
2. `migrations/002_create_storage.sql` - 创建存储桶
3. `migrations/003_create_