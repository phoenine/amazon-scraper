## 1. 目标与范围

目标
	•	输入：ASIN和站点（站点默认，如 amazon.com, amazon.co.jp）。
	•	输出：标题（title）、评分（rating/ratings_count）、价格（price/currency）、主图（hero image）、橱窗图/轮播图（gallery）、五点要点（5 bullets）、产品信息（Tech Details / Product information）、主图分辨率与 URL、可选 A+ 内容（MVP 可不抓）。
	•	提供 REST API：GET /asin/{asin}（查询/拉起抓取）、POST /asin/scrape（批量抓取）。
	•	持久化至 Supabase（Postgres + Storage），并设置 RLS 与索引，支持缓存与更新策略。

非目标（MVP 之外，可后续扩展）
	•	变体矩阵（颜色/尺码）全量展开
	•	页面 A/B 不同 DOM 结构全覆盖
	•	高级反爬（如深度指纹拟合、验证码自动识别）


## 2. 系统架构

```md
[Client/CI] ──HTTP──> [FastAPI 服务层] ──async queue──> [抓取 Worker池 (Playwright)]
                                   │                      │
                                   │                      ├─ 并发控制 / 重试 / 解析
                                   │                      └─ Supabase SDK 写库/存储
                                   └──> [读缓存层] <── Supabase (Postgres + Storage)
```


关键点
	•	服务层（FastAPI）：接收请求→查缓存→若需要更新则投递到内部 async 队列；支持同步等待或异步返回任务 ID。
	•	抓取层（Playwright async）：单进程多协程，按域名/会话限速；必要时多浏览器上下文（browser context）隔离。
	•	并发模型：asyncio + Semaphore 控制每域并发；图片下载可用 aiohttp；如需“异步 + 多线程”，仅在 CPU-bound（如大图压缩）或阻塞库场景使用 ThreadPoolExecutor。
	•	存储层（Supabase）：结构化字段入 Postgres，图片落 Supabase Storage（或先存 URL 再异步拉取到 Storage）。
	•	可观测：Prometheus 指标（成功率/耗时/429 率/验证码率）、结构化日志、任务表状态。

## 3. 数据模型（Supabase）

命名空间建议：public.amazon_...（或按项目 schema）

### 3.1 核心表
	•	amazon_products（产品主表）
    	•	id (PK, uuid)
    	•	asin (text, not null, unique with marketplace，联合唯一)
    	•	marketplace (text, e.g., amazon.com)
    	•	title (text)
    	•	rating (numeric(3,2))  — 如 4.6
    	•	ratings_count (int)
    	•	price_amount (numeric(12,2))
    	•	price_currency (text, 3-letter)
    	•	hero_image_url (text)  — 原始 URL
    	•	hero_image_path (text) — Storage 内对象路径（抓取图片后回写）
    	•	availability (text)
    	•	best_sellers_rank (jsonb) — 可保存多个分类的 BSR
    	•	raw_html_snapshot_id (uuid, FK nullable) — 指向快照表
    	•	status (text, enum: fresh, stale, failed, pending)
    	•	etag (text) — 内容 hash/指纹，用于幂等与变更检测
    	•	last_scraped_at (timestamptz)
    	•	created_at/updated_at
	•	amazon_product_bullets（五点描述）
    	•	id (uuid, PK)
    	•	product_id (uuid, FK -> amazon_products.id)
    	•	position (smallint)
    	•	text (text)
	•	amazon_product_images（图片表）
    	•	id (uuid, PK)
    	•	product_id (uuid, FK)
    	•	role (text enum: hero, gallery)
    	•	original_url (text)
    	•	storage_path (text nullable)
    	•	width/height (int nullable)
    	•	position (smallint)
	•	amazon_product_attributes（KV 结构保存 Tech Details / Product information）（产品属性）
    	•	id (uuid, PK)
    	•	product_id (uuid, FK)
    	•	name (text)   — e.g., “Brand”, “Item model number”
    	•	value (text)
    	•	source (text enum: tech_details | product_information)
	•	amazon_html_snapshots（原始快照）
    	•	id (uuid, PK)
    	•	asin (text)
    	•	marketplace (text)
    	•	html (text)  — 可压缩存储；或仅存关键 DOM 片段
    	•	created_at/updated_at
	•	scrape_tasks（抓取任务表）
    	•	id (uuid, PK)
    	•	asin / marketplace
    	•	status (enum: queued, running, success, failed)
    	•	error (text nullable)
    	•	requested_by (text nullable)
    	•	created_at / updated_at

索引与约束
	•	unique(asin, marketplace) on amazon_products
	•	BTREE 索引：last_scraped_at、status
	•	GIN 索引：best_sellers_rank（jsonb）
	•	外键级联删除：product_id 级联到 bullets/images/attributes

Storage
	•	Bucket：amazon-assets
	•	路径模式：{marketplace}/{asin}/hero_{etag}.jpg、gallery_{idx}_{etag}.jpg

RLS（按需）
	•	仅服务角色可写；匿名只读（或完全禁止）；若多租户，增加 owner_org_id 字段并按行级策略隔离。

## 4. 抓取策略与反爬应对

基本策略
	•	Playwright：chromium、stealth-like 配置、userAgent & locale 与站点匹配；context 级别隔离 Cookie；wait_for_load_state('domcontentloaded') + 显式等待需要的选择器。
	•	限速与退避：每域并发（如 <= 3），全局 Semaphore，指数退避对 429/503；重试 2–3 次。
	•	CAPTCHA/Robot 检测：若检测到（典型有 /errors/validateCaptcha 或相关节点），立即标记任务失败并降低该域并发/限速；可引入人工或外部解码通道（非 MVP）。
	•	区域化选择器：不同站点 DOM 差异（#productTitle、#feature-bullets、#corePriceDisplay_*、twister、imgTagWrapperId 等），抽象「解析器接口」按 marketplace 注册处理器。
	•	内容指纹（etag）：对关键字段序列化后 hash，判断是否变更，减少不必要写入。
	•	合规提示：遵循目标站点服务条款与法律法规，尊重 robots.txt（虽然 Playwright 执行 JS），仅用于合法合规目的；必要时取得授权或采用官方 API/联盟数据源。

## 5. 并发与执行模型
	•	进程：单服务进程即可（MVP），后续可作多副本水平扩展（K8s HPA）。
	•	Playwright 浏览器：1 个 browser + N 个 context + 每 context 1–2 个 page（稳妥）；或按任务起止创建/销毁以降低痕迹。
	•	协程：asyncio 原生；图片下载用 aiohttp。
	•	多线程：仅在图片本地裁剪/压缩（可选）或阻塞 I/O 时，用 ThreadPoolExecutor(max_workers=4)。
	•	任务调度：API 将请求放入 asyncio.Queue，后台 worker 消费；支持 ?async=true 异步返回任务 ID；?force=true 跳过缓存。

## 6. 解析清单（以 .com 为例，按需切换）
	•	标题：#productTitle
	•	评分：#acrPopover（title 或 aria-label 文本解析为 float）
	•	评价数：#acrCustomerReviewText
	•	价格：#corePrice_feature_div, .a-price .a-offscreen
	•	主图：#imgTagWrapperId img 的 data-old-hires 或 src；或从 ImageBlockATF JSON 抽取大图
	•	橱窗/轮播：#altImages 下 img 的 src（注意 _SS40_→替换为更高分版本）
	•	五点要点：#feature-bullets ul li span（去噪）
	•	产品信息/Tech Details：#productDetails_techSpec_section_1, #productDetails_detailBullets_sections1，或 #detailBullets_feature_div 列表项解析为键值
	•	可选：BSR、品牌、型号、发货与库存（availability）

需要为每类字段编写 健壮的解析函数，容忍节点缺失和 A/B 结构；所有选择器读取失败不应整体失败，而是标记为空并记录原因。

## 7. API 设计（FastAPI）

路由
	•	GET /asin/{asin}
	•	Query：marketplace（默认 amazon.com），force（bool），async（bool）
	•	行为：
	1.	查 amazon_products（如 last_scraped_at < TTL 视为过期）
	2.	若 force 或过期则入队抓取；
	3.	async=false：可选择同步等待抓取完成（设置上限超时，默认 20–30s）；
	4.	返回整合后的 JSON（含 bullets/images/attributes）。
	•	POST /asin/scrape
	•	body: { items: [{asin, marketplace?}, ...], async?: true }
	•	行为：批量入队；返回任务列表。
	•	GET /tasks/{id}：查询任务状态/错误。

```json
{
  "asin": "B00XXXX",
  "marketplace": "amazon.com",
  "title": "...",
  "rating": 4.6,
  "ratings_count": 1234,
  "price": {"amount": 19.99, "currency": "USD"},
  "hero_image": {"url": "...", "storage_path": "amazon-assets/..."},
  "gallery": [{"url": "...", "storage_path": "...", "position": 1}],
  "bullets": ["...", "..."],
  "attributes": [{"name": "Brand", "value": "..."}, ...],
  "last_scraped_at": "2025-09-23T00:00:00Z",
  "status": "fresh",
  "etag": "..."
}
```
## 8. 关键实现要点（代码骨架）

下列为MVP 示意，真实项目请拆分模块与完善异常处理/日志。

### 8.1 环境变量
```md
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SCRAPER_CONCURRENCY_PER_DOMAIN=3
SCRAPER_GLOBAL_CONCURRENCY=6
SCRAPER_TTL_SECONDS=86400
```

### 8.2 FastAPI & 队列（示意）
```python
# app/main.py
import asyncio
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from .scraper import ensure_fresh_product
from .store import get_product_from_db

app = FastAPI()
queue = asyncio.Queue()

class ScrapeItem(BaseModel):
    asin: str
    marketplace: Optional[str] = "amazon.com"

@app.on_event("startup")
async def startup():
    # 启动 N 个后台 worker
    from .workers import start_workers
    start_workers(queue, num_workers=3)

@app.get("/asin/{asin}")
async def get_asin(
    asin: str,
    marketplace: str = "amazon.com",
    force: bool = False,
    wait: bool = False
):
    # 命中缓存？
    prod = await get_product_from_db(asin, marketplace)
    stale = await ensure_fresh_product(asin, marketplace, force, queue, wait)
    # 读取最新
    prod = await get_product_from_db(asin, marketplace)
    if not prod:
        raise HTTPException(404, "Not found or scraping in progress")
    return prod
```

### 8.3 Worker（Playwright 抓取协程）
```python
# app/workers.py
import asyncio
from playwright.async_api import async_playwright
from .parser import parse_product
from .store import upsert_product_bundle
from .net import fetch_images_to_storage

async def worker(queue: asyncio.Queue, browser):
    while True:
        asin, marketplace = await queue.get()
        try:
            context = await browser.new_context(
                locale="en-US", user_agent="Mozilla/5.0 ..."
            )
            page = await context.new_page()
            url = f"https://{marketplace}/dp/{asin}"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            data = await parse_product(page, asin, marketplace)
            await upsert_product_bundle(data)  # 写入产品 + bullets + attrs + images
            await fetch_images_to_storage(data)  # 可异步拉图入 Storage
        except Exception as e:
            # 写任务失败 & 降低并发/退避等
            ...
        finally:
            queue.task_done()

def start_workers(queue: asyncio.Queue, num_workers: int = 3):
    async def _run():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            tasks = [asyncio.create_task(worker(queue, browser)) for _ in range(num_workers)]
            await asyncio.gather(*tasks)
    asyncio.create_task(_run())
```

### 8.4 解析器（简化示意）

```python
# app/parser.py
from playwright.async_api import Page

async def safe_text(page: Page, selector: str):
    el = await page.query_selector(selector)
    if not el: return None
    t = (await el.text_content()) or ""
    return " ".join(t.split())

async def parse_product(page: Page, asin: str, marketplace: str) -> dict:
    title = await safe_text(page, "#productTitle")
    # 评分
    rating_label = await safe_text(page, "#acrPopover")
    rating = None
    if rating_label:
        # e.g., "4.6 out of 5 stars"
        try:
            rating = float(rating_label.split(" ")[0])
        except: pass
    # 价格
    price_text = await safe_text(page, ".a-price .a-offscreen") or await safe_text(page, "#corePrice_feature_div .a-offscreen")
    amount, currency = None, None
    if price_text:
        # 基于站点格式做健壮解析
        ...

    # 主图与轮播（可再做高清替换）
    hero_src = await page.get_attribute("#imgTagWrapperId img", "data-old-hires") \
            or await page.get_attribute("#imgTagWrapperId img", "src")

    bullets = []
    for idx, li in enumerate(await page.query_selector_all("#feature-bullets ul li span")):
        txt = (await li.text_content()) or ""
        txt = " ".join(txt.split())
        if txt: bullets.append({"position": idx+1, "text": txt})

    # Attributes（多区块合并）
    attributes = []
    # 解析 detailBullets / tech specs 两套结构
    ...

    return {
        "asin": asin,
        "marketplace": marketplace,
        "title": title,
        "rating": rating,
        "price": {"amount": amount, "currency": currency},
        "hero_image": {"url": hero_src},
        "gallery": [],  # 另行解析 altImages
        "bullets": bullets,
        "attributes": attributes
    }
```

### 8.5 Supabase 存取（示意）

```python
# app/store.py
from supabase import create_client
import os, datetime

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

async def get_product_from_db(asin, marketplace):
    # 查询产品 + 关联（可分多次查询或用视图）
    res = supabase.table("amazon_products").select("*").eq("asin", asin).eq("marketplace", marketplace).execute()
    if not res.data: return None
    product = res.data[0]
    # 追加 bullets / images / attributes
    ...
    return product

async def upsert_product_bundle(data: dict):
    # 计算 etag（对核心字段 hash）
    # upsert products; delete+insert children or upsert by composite keys
    ...
```

## 9. 缓存与更新策略
	•	TTL：例如 24h；GET /asin/{asin} 默认返回最近一次抓取结果；force=true 强制刷新。
	•	ETag/指纹：若页面结构无变化则仅更新 last_scraped_at，减少写放大。
	•	增量拉取：定时任务（如 CRON）根据 stale 标记批量刷新热门 ASIN。

## 10. 可观测与告警
	•	指标：抓取耗时 p50/p95、成功率、429 比例、验证码命中率、DOM 解析失败率、存储写入耗时。
	•	日志：结构化 JSON（包含 asin、marketplace、重试次数、最终状态）。
	•	告警：连续失败阈值、异常峰值（如 429 暴涨）触发告警并自动降并发。

## 11. 安全与合规
	•	遵循目标网站条款与法律法规；非授权商业用途前务必评估合规性。
	•	严控并发与频率，避免对对方造成负载影响。
	•	所有请求添加恰当的 Accept-Language 与 User-Agent；禁止采集个人敏感信息。
	•	Supabase：启用 RLS，仅服务角色可写，API 层只暴露必要字段。

## 12. 部署与交付
	•	容器化：Dockerfile 安装 playwright 与浏览器依赖（playwright install --with-deps chromium）。
	•	配置：通过 ENV 注入 Supabase 凭据与并发阈值。
	•	运行：uvicorn app.main:app --host 0.0.0.0 --port 8000；K8s 部署配合 HPA 以“任务队列深度/CPU/自定义指标”伸缩。
	•	持久化：无状态服务，数据库与 Storage 由 Supabase 托管。

## 13. MVP 与里程碑

MVP（1–2 周量级）
	1.	FastAPI 两条路由（单 ASIN 查询 + 批量入队）。
	2.	Playwright 抓取 .com 站点最常见 DOM：title/rating/price/bullets/hero/gallery/attributes。
	3.	Supabase 三张表最小集：amazon_products、amazon_product_bullets、amazon_product_images；attributes 可延后。
	4.	Storage 落主图与 3 张轮播图（可选，或先仅存 URL）。
	5.	并发控制 + 重试 + 基础日志。

v1.1：多站点适配（.co.jp/.de 等）、属性解析增强、BSR。
v1.2：验证码与 429 自适应限流、更多图片规格、A+ 内容提取。
v1.3：任务优先级队列、幂等/去重优化、Prometheus/Grafana 仪表盘。

## 14. 测试方案（要点）
	•	解析回归：准备 20+ 站点/类目的页面快照（HTML fixtures），离线解析单测。
	•	抗变性测试：对选择器做“缺失/变更”容错单测。
	•	并发稳定性：模拟 100–300 个 ASIN 入队，验证吞吐/429 率/退避有效性。
	•	API 契约：Pydantic Schema 校验与示例响应。
	•	入库一致性：多次抓取同 ASIN 不产生重复子项（position/role 去重）。



