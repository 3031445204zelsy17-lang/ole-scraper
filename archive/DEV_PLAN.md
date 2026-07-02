# OLE Agent App - 开发流程

**目标**: 本地聊天应用，通过文本框交互完成 OLE 操作
**原则**: 每个功能一个 session，做完测试，git commit

---

## 最终形态

```
┌─────────────────────────────────────────┐
│  OLE Agent                    [_][□][×] │
├─────────────────────────────────────────┤
│                                         │
│  你好！有什么需要帮你查的？              │
│                                         │
│  你: 这周有什么作业要交                  │
│                                         │
│  📋 待交作业（信息检索）：                │
│     ⚠️ STAT2610 - Assignment 3          │
│        截止: 3月29日 (还剩2天!)          │
│     📝 COMP2090 - Tutorial #10          │
│        截止: 4月5日                      │
│                                         │
│  你: 帮我下载 COMP2090 的课件            │
│                                         │
│  ⚡ 操作确认：将下载 COMP2090SEF 课件     │
│     到桌面，确认吗？                      │
│                                         │
│  你: 确认                                │
│                                         │
│  ✅ 已下载 6 个文件到 ~/Desktop/          │
│                                         │
├─────────────────────────────────────────┤
│  [输入消息...]                  [发送]   │
└─────────────────────────────────────────┘
```

**两类功能**：
- **信息检索**（只读）: 课程、作业、课表、成绩、全部 → 直接返回结果
- **操作功能**（有副作用）: 下载文件 → 需用户确认后执行

**意图解析**: DeepSeek API（便宜，~100 token/次）

---

## 技术栈

| 层 | 技术 | 用途 |
|----|------|------|
| 后端 | FastAPI + WebSocket | 消息收发 |
| 意图解析 | DeepSeek Chat API | 理解自然语言，分类为检索/操作 |
| 核心引擎 | src/（现有 Playwright 脚本）| 抓取 OLE 数据 |
| 前端 | 单个 HTML 文件 | 聊天界面 |
| 缓存 | JSON 文件 | 避免重复登录 |

---

## 目录结构

```
ole-scraper/
├── app/                          # 应用层
│   ├── main.py                   # FastAPI + WebSocket
│   ├── agent.py                  # DeepSeek 意图解析 + 路由
│   ├── retriever.py              # 信息检索（课程/作业/课表/成绩）
│   ├── operator.py               # 操作功能（下载）- 需确认
│   ├── cache.py                  # 数据缓存
│   ├── static/index.html         # 聊天界面
│   └── schemas.py                # 数据结构
├── src/                          # 核心引擎（已有，不改）
│   ├── scraper.py
│   ├── auth.py
│   ├── actions/
│   └── utils/
├── ole-data/current/             # 缓存数据
├── ole-config/                   # 配置
├── init.sh                       # 一键启动
├── feature_list.json             # 功能清单
├── HARNESS.md                    # 开发流程
└── CLAUDE.md                     # 项目指引
```

---

## 意图解析设计（DeepSeek）

### API 调用

```python
# app/agent.py
import httpx

DEEPSEEK_API = "https://api.deepseek.com/chat/completions"

async def parse_intent(user_input: str) -> dict:
    """用 DeepSeek 解析用户意图"""
    response = await httpx.AsyncClient().post(
        DEEPSEEK_API,
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": INTENT_PROMPT},
                {"role": "user", "content": user_input}
            ],
            "temperature": 0,
            "max_tokens": 100
        }
    )
    return response.json()["choices"][0]["message"]["content"]
```

### System Prompt（意图解析用）

```
你是 OLE Agent 的意图解析器。从用户消息中提取意图，返回 JSON。

意图分类：
- 信息检索类（只读）: courses, assignments, classes, grades, all, help
- 操作类（有副作用）: download

返回格式：
{"intent": "courses|assignments|classes|grades|all|download|help|unknown",
 "course_code": "COMP2090SEF",  // 如能提取到
 "params": {},                   // 其他参数
 "needs_confirm": false}         // 操作类为 true

示例：
"这周有啥作业" → {"intent":"assignments","course_code":null,"params":{},"needs_confirm":false}
"下载COMP2090课件" → {"intent":"download","course_code":"COMP2090SEF","params":{"file_type":"lecture"},"needs_confirm":true}
"明天几点的课" → {"intent":"classes","course_code":null,"params":{},"needs_confirm":false}
```

---

## 消息处理流程

```
用户输入
  ↓
DeepSeek 解析意图
  ↓
┌─ needs_confirm=false → 信息检索路径
│    ↓
│  retriever.py → 读取缓存 or 调用 scraper
│    ↓
│  格式化返回结果
│
└─ needs_confirm=true → 操作确认路径
     ↓
     返回 "确认执行 XXX？"
     ↓
     用户回复"确认"
     ↓
     operator.py → 执行操作
     ↓
     返回操作结果
```

---

## Session 计划

### Session 1: 地基
- git init + .gitignore
- feature_list.json（已有）
- 确认现有 scraper 能跑
- `git commit -m "init: project foundation"`

### Session 2: FastAPI 骨架 (F01)
- app/main.py: FastAPI + /health
- app/schemas.py: 消息数据结构
- `uvicorn app.main:app --port 8000` 能启动
- `curl localhost:8000/health` → `{"status":"ok"}`

### Session 3: 聊天界面 (F02, F03)
- app/static/index.html: 深色聊天 UI
- WebSocket 连接
- 能收发消息（先 echo 回来）

### Session 4: 意图解析 (F09)
- app/agent.py: DeepSeek API 集成
- 关键词 fallback（DeepSeek 挂了也能用）
- .env 加 DEEPSEEK_API_KEY

### Session 5: 信息检索 (F04a-d, F05)
- app/retriever.py: 统一检索入口
- 调用现有 src/ 代码获取数据
- 格式化输出

### Session 6: 数据缓存 (F08)
- app/cache.py: JSON 缓存 + 过期检查
- retriever 先查缓存，过期才调 scraper

### Session 7: 格式化 + 提醒 (F07, F13, F12)
- 作业按截止日期排序
- 标红 N 天内到期
- help 指令

### Session 8: 下载功能 (F06)
- app/operator.py: 操作执行器
- 确认流程: 解析出 download → 先问确认 → 执行
- 调用 src/actions/downloads.py

### Session 9: init.sh + 错误处理 (F10, F11)
- init.sh 一键启动
- OLE 登录失败友好提示

---

## 每个 Session 的固定节奏

```bash
# 开始
pwd && git log --oneline -3
cat feature_list.json | python -c "import sys,json;[print(f'{f[\"id\"]} {\"✅\" if f[\"passes\"] else \"⬜\"} {f[\"desc\"]}') for f in json.load(sys.stdin)]"

# 做完
git add [具体文件]
git commit -m "feat: F0X - 描述"
# 更新 feature_list.json 对应条目
git commit -m "update: F0X passes"
```
