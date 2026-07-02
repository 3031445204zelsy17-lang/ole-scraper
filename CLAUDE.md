# OLE Agent — HKMU OLE 本地学习 Agent

**项目名称**: OLE Agent(原 OLE Scraper)
**定位**: 可分发的、面向 HKMU 学生的本地学习 agent(BYO LLM key,凭证全留本地)
**策略准绳**: `ROADMAP.md`(取代已退役的 `DEV_PLAN.md` / `feature_list.json`,见 `archive/`)
**当前阶段**: Phase 0 — 清场(去你化,仓库可公开)

---

## 架构(ReAct + 硬编码选择器爬虫)

```
浏览器 localhost:8000 ──WebSocket──→ app/main.py
                                       ↓ run_agent_loop()
                  app/agent_loop.py   ReAct 循环(DeepSeek function-calling, MAX_TURNS=8)
                        │   LLM 只决定「调哪个工具 + 组织回答」,不看页面
                        ↓
                  app/tool_executor.py   9 个 handler,双数据源:
                        ├─【缓存·快】courses/assignments/classes
                        │              → app/cache.py → ole-data/current/*.json(过期自动刷新)
                        └─【实时·浏览器】files/grades/browse/download/materials/search
                                       → app/scraper_pool.py → src/scraper.py → Playwright → OLE
```

- **目录类**查询走 JSON 缓存(零 LLM 成本、零浏览器);过期由 `cache.py` 起新 scraper 抓。
- **细节类**查询走 `ScraperPool` 复用的 Playwright 实例实时访问 OLE。
- **明确排除**「LLM 实时探索浏览器」路线(贵、慢、不可靠,见 ROADMAP §2)。

---

## 目录结构

```
ole-scraper/
├── app/                    应用层(ReAct agent)
│   ├── main.py             FastAPI + WebSocket 入口
│   ├── agent_loop.py       ReAct 循环 + 系统提示词
│   ├── tools.py            9 工具 function-calling schema
│   ├── tool_executor.py    工具执行(缓存/浏览器双路径)
│   ├── scraper_pool.py     Playwright 实例池(连接级复用)
│   ├── cache.py            JSON 缓存 + TTL 过期刷新
│   ├── conversation.py     对话历史(内存,最近 6 轮)
│   ├── config.py           配置入口(DEEPSEEK_KEY)
│   └── static/index.html   聊天前端(内嵌 CSS+JS)
├── src/                    核心引擎(硬编码选择器,勿改)
│   ├── scraper.py          OLEScraper(组合 5 个 action)
│   ├── auth.py             登录 + session 持久化(sessions/)
│   └── actions/            courses / assignments / grades / calendar / downloads
├── ole-data/
│   ├── current/            运行时缓存(gitignored,首次运行生成)
│   └── example/            缓存格式脱敏示例
├── ole-config/             选择器 / 系统配置
├── archive/                退役文档(DEV_PLAN.md / feature_list.json)
├── ROADMAP.md              ★ 唯一策略准绳
├── CLAUDE.md               本文件(项目指令)
└── README.md               面向用户
```

---

## 权限规则

| 允许 | 禁止 |
|------|------|
| ✅ 读取 OLE 页面 | ❌ 修改 OLE 页面内容 |
| ✅ 下载课件 | ❌ 上传文件到 OLE |
| ✅ 查询成绩/作业 | ❌ 提交作业(通过 scraper) |
| ✅ 登录认证 | ❌ 删除 OLE 内容 |

每次从 OLE 获取数据后,标注信息源 URL。

---

## 开发规范

- **一次一阶段**:按 `ROADMAP.md` 推进,做完验收再进下一阶段(ROADMAP §9)。
- **外科手术式改动**:不破坏 `src/` 已有工作代码;改动小、可验证。
- **每个任务有验收**:能跑 / 能 grep / 能演示,才算完成。
- **改完即提交**:`feat/fix/chore: PhaseX - 描述`,并同步 ROADMAP checkbox。

---

## 技术栈

- **后端**: FastAPI + uvicorn + websockets
- **前端**: 单 HTML(内嵌 CSS + JS)
- **引擎**: Python + Playwright(硬编码选择器)
- **LLM**: DeepSeek(function-calling);Phase 1 将抽象为多 provider
- **数据**: JSON 文件缓存(`ole-data/current/`)

---

## 数据格式

见 `ole-data/example/`(脱敏示例)。运行时由 scraper 写入 `ole-data/current/`(gitignored)。
