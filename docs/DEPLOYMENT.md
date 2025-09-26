# 部署指南

## 🚀 快速部署

### 1. 环境准备

```bash
# 克隆项目
cd /Users/phoenine/Documents/github/supabase/test-project/pyapp

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装Playwright浏览器
playwright install chromium
```

### 2. 配置Supabase

#### 2.1 创建Supabase项目
1. 访问 [Supabase](https://supabase.com)
2. 创建新项目
3. 获取项目URL和API密钥

#### 2.2 执行数据库迁移
在Supabase SQL编辑器中依次执行：

```sql
-- 1. 执行 migrations/001_create_tables.sql
-- 2. 执行 migrations/002_create_storage.sql
-- 3. 执行 migrations/003_add_aplus_content.sql
-- 4. 执行 migrations/004_create_rls.sql
```

#### 2.3 配置环境变量
```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件
nano .env
```

填入你的Supabase配置：
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

### 3. 测试系统

```bash
# 运行快速测试
python quick_test.py
```

### 4. 启动服务

```bash
# 启动API服务器
python run.py
```

服务将在 http://localhost:8000 启动

### 5. API测试

```bash
# 测试健康检查
curl http://localhost:8000/health

# 抓取单个产品
curl "http://localhost:8000/asin/B08N5WRWNW?wait=true"

# 批量抓取
curl -X POST http://localhost:8000/asin/scrape \
  -H "Content-Type: application/json" \
  -d '{"items": [{"asin": "B08N5WRWNW"}, {"asin": "B07XJ8C8F5"}]}'
```

## 📊 API文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🐳 Docker部署

```bash
# 构建镜像
docker build -t amazon-scraper .

# 运行容器
docker run -p 8000:8000 --env-file .env amazon-scraper
```

## 🔧 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `SUPABASE_URL` | Supabase项目URL | 必填 |
| `SUPABASE_SERVICE_ROLE_KEY` | 服务角色密钥 | 必填 |
| `SCRAPER_CONCURRENCY_PER_DOMAIN` | 每域名并发数 | 3 |
| `SCRAPER_GLOBAL_CONCURRENCY` | 全局并发数 | 6 |
| `SCRAPER_TTL_SECONDS` | 缓存TTL(秒) | 86400 |
| `WORKER_COUNT` | 工作进程数 | 3 |
| `BROWSER_HEADLESS` | 无头模式 | true |

### 性能调优

1. **并发控制**: 根据服务器性能调整 `WORKER_COUNT` 和并发参数
2. **缓存策略**: 调整 `SCRAPER_TTL_SECONDS` 平衡数据新鲜度和性能
3. **内存管理**: 监控内存使用，必要时重启浏览器实例

## 🚨 注意事项

1. **合规使用**: 遵守Amazon服务条款，控制抓取频率
2. **IP限制**: 使用代理池避免IP被封
3. **监控告警**: 设置失败率和延迟监控
4. **数据备份**: 定期备份Supabase数据

## 🔍 故障排除

### 常见问题

1. **浏览器启动失败**
   ```bash
   # 重新安装浏览器
   playwright install chromium --with-deps
   ```

2. **数据库连接失败**
   - 检查 `.env` 文件配置
   - 确认Supabase项目状态
   - 验证网络连接

3. **抓取失败**
   - 检查目标网站可访问性
   - 调整并发参数
   - 查看日志错误信息

### 日志查看

```bash
# 查看实时日志
tail -f logs/scraper.log

# 查看错误日志
grep ERROR logs/scraper.log
```