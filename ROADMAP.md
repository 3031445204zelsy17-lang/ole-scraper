# OLE Agent — v2 路线图

> 状态:**已确认(2026-06-25)**。本文是项目唯一策略准绳。
> 取代 `DEV_PLAN.md` 与 `feature_list.json`(二者已退役,见 §7)。
> 最后更新:2026-07-03(Phase 2 完成)

---

## 1. 定位(North Star)

把 OLE Agent 从"我个人的 OLE 脚本"升级为**可分发的、面向 HKMU 学生的本地学习 agent**:

- **本地优先**:跑在用户自己电脑上,凭证(OLE 登录 + LLM API key)全留本地,只发往 OLE(登录)和 LLM API(推理)。
- **BYO-key**:像主流 agent 一样,用户填自己的 AI API key 即可用。
- **能问答**:不仅能查作业/课表/成绩(目录),还能回答"这门课考核占比/某周讲什么"等**内容类问题**(靠 RAG)。

**目标体验**:`git clone → 一条命令启动 → 首次填 key + 学校账号 → 自动登 OLE 抓数据 → 开聊`。

---

## 2. 架构定论(已核实)

> 运行时是**硬编码选择器的 Playwright 爬虫 + LLM 编排**,不是"LLM 实时探索浏览器"。
> 2026-06-25 已逐项核实:`app/` 文件、ReAct loop(`agent_loop.py`,MAX_TURNS=8)、9 工具(3 缓存 + 3 浏览器 + 3 skill)、ScraperPool + cache 均吻合。

```
Playwright 爬虫(src/,硬编码选择器) → 登录 + 抓数据 → ole-data/current/*.json(缓存)
                                                                  ↓
ReAct agent(app/agent_loop.py,DeepSeek) → 路由选工具 + 组织回答 ← 不感知页面
```

- **目录类**(courses/assignments/classes):读 JSON 缓存,不开浏览器,零 LLM 成本。
- **细节类**(grades/files/download/browse/search):走 ScraperPool → 实时 Playwright。
- **LLM 角色**:决定调哪个工具 + 组织回答,**不看页面**。

**为什么保持这个架构**:快、便宜、确定,适合 BYO-key 分发。**明确排除**"LLM 实时探索浏览器"路线(贵、慢、烧用户额度、不可靠)。

---

## 3. 不做什么(防 scope 蔓延)

- ❌ 不做"代登录服务"——不运营一个替别人登 OLE 的线上服务(合规红线)。
- ❌ 不做"LLM 实时探索浏览器"作为主路径(最多作为未来兜底,非本期)。
- ❌ 不在本期做多租户 / 多用户并发(本地单用户已足够)。
- ❌ 不过早通用化——先 HKMU 跑通,LMS 动作已收敛在 `src/actions/`,以后扩 Moodle 成本可控。

---

## 4. 现状差距(已用代码核实)

| 级别 | 差距 | 证据 |
|---|---|---|
| 🔴 | 系统提示写死个人桌面路径 | `agent_loop.py:41` + `tools.py:138`(两处,同一字面量) |
| 🔴 | 爬虫脆:硬编码选择器 + `section_map` + 多次 fix-download | `tool_executor.py:158` / git log |
| 🔴 | `sessions/` 登录 cookie 未 gitignore | `.gitignore` 仅 4 行,缺 sessions/downloads/logs/ole-data/current |
| 🔴 | 无 RAG,答不了内容类问题 | 无嵌入/检索代码 |
| 🔴 | LLM 写死 DeepSeek(URL + model) | `agent_loop.py:12,94` |
| 🟠 | 无流式输出,用户干等整句 | `agent_loop.py:89` + `main.py:96` |
| 🟠 | 上下文粗暴截断(6 轮)、刷新即丢 | `conversation.py:3` / `main.py:61` |
| 🟠 | 工具参数 JSON 解析失败静默当空参,无校验/重试 | `agent_loop.py:129-131` |
| 🟠 | loop 内手写 `file_type` 补丁(技术债) | `agent_loop.py:133-145` |
| 🟠 | 错误处理单层,无退避重试 | `agent_loop.py:102` |
| 🟡 | 多 session / 历史持久化 / 前端编辑 / trace / 测试 | — |

---

## 5. 策略原则(设计判断)

本次优化遵循四条原则:

1. **价值递进**:先「可公开」→「可分发(BYO key)」→「像产品」→「能问答(RAG)」→「别人能跑」。每步都让仓库更接近北极星一步,不回头改。
2. **agent_loop 解耦主线**:`agent_loop.py` 三处技术债(硬编码 DeepSeek / `file_type` 补丁 / JSON 解析静默)是**同一根因**(把 LLM 怪癖硬编码进 loop)。抽成一条单独追踪线**横穿 Phase 1–2**,避免改一处又添新补丁。
3. **每 Phase 一个可演示验收**:能 grep / 能跑通 / 能给陌生人演示,才算过。
4. **决策前置**:分发方式在 Phase 0→1 之间敲定(反向约束 README 与 wizard),不拖到 Phase 4。

---

## 6. 分阶段路线图

每个阶段:**做完 → 按"验收"验证 → git commit → 进下一阶段**。一次只推进一个阶段。

### Phase 0 — 清场(去你化 + 仓库能见人)
**目标**:仓库可以安全公开,不含任何个人数据。
- [x] 补 `.gitignore`:`sessions/` `downloads/` `logs/` `ole-data/current/` + `ole-downloads/` `ole-session/`(cf6a625)
- [x] 去硬编码:`agent_loop.py:41` + `tools.py:138` 的 `/Users/<个人>/Desktop` → 默认 `downloads/<course>/`(cf6a625)
- [x] 移除个人数据:`ole-data/current/*.json` + 课件 PDF → 换成 `example/` 示例(cf6a625,本地保留)
- [x] 排查硬编码课程码:`app/` 仅 `main.py` 帮助文本的 COMP2090(示例,非泄漏,保留)
- [x] 归档退役文件:`DEV_PLAN.md` / `feature_list.json` → `archive/`(cf6a625)
- [x] 重写 `CLAUDE.md` 架构段(脱节)+ `README`(定位 + 隐私 + 免责)(cf6a625)
- [x] 补项(原 §4 已列但 §6 漏排):`.env.example` 真实凭证脱敏;删 3 处死代码 `retriever.py`/`schemas.py`/`agent.py` → 建 `config.py`(cf6a625)
- **验收**:代码/配置无个人绝对路径或真实凭证(grep `/Users/` 与凭证关键词零命中);clone 后仓库不含 cookie/PDF/真实课表。✅ 已达(2026-07-02)
> Phase 0 全部 squash 进 initial commit `cf6a625`(原 `bd9f76c`/`82f7f83`/`c00cb8b`/`7cc0f35` 已随仓库重置失效)。

### Phase 0.5 — 决策点(已过)
✅ 分发方式已定:Python 直装。

### Phase 1 — 让别人"填 key 就能用"
**目标**:换一家 LLM provider 也能跑,首启引导填信息。(依赖:Phase 0.5 分发方式)
- [x] 多 provider 抽象:OpenAI 兼容接口,支持 DeepSeek / GLM / OpenAI / Ollama(provider + base_url + key + model 可配)(aedf0e2)
- [x] 去掉 `agent_loop.py` 里 hardcode 的 `DEEPSEEK_URL` / `"deepseek-chat"` ← **agent_loop 主线**(aedf0e2)
- [x] 首启 wizard:首次运行收 `LLM_API_KEY` + HKMU 凭证 → 写本地 `.env`(ec04ded;登录 session 留首次 scraper)
- [x] `.env.example` 更新为多 provider 模板(aedf0e2)
- **验收**:DeepSeek 真实调用 + 应用全链路(WS → agent → `call_llm` → DeepSeek → final)已实测 ✅(2026-07-03);GLM/OpenAI/Ollama 配置解析过、真实调用待对应 key;OLE 实时抓数据待用户真实跑覆盖

### Phase 2 — 成熟度补课(用户体验)
**目标**:用起来像主流 agent,不像脚本。(依赖:Phase 1)
- [x] 流式输出:backend 改 stream → frontend 逐字渲染(3f9f1c5;35 delta 逐字 + final 一致已实测)
- [x] 上下文管理:历史持久化到本地(localStorage,刷新不丢)+ 窗口 6→12(7280286);**摘要缓做**(轻量版:对话短 + 事实已在缓存,按升级阶梯后续可加)
- [x] 工具调用健壮性:参数 schema 校验 + JSON 解析失败反馈重试;**删掉** `file_type` 手写补丁 ← **agent_loop 主线**(4441fe9)
- [x] 错误处理:网络错误退避重试(`call_llm`/`call_llm_stream` 连接级重试,4441fe9/3f9f1c5)
- **验收**:工具参数错误有恢复而非静默 ✅;回答逐字出现 ✅;长会话上下文:窗口内(≤12 轮)+ 刷新不丢 ✅,>12 轮摘要待升级(2026-07-03)

### Phase 3 — 能力跃升:RAG
**目标**:能回答内容类问题(考核占比、某周讲什么、某概念在哪份讲义)。(嵌入选型 Phase 2 末正式定,默认本地 bge-small)
- [ ] PDF/讲义抽文本(pdfplumber/PyMuPDF)+ 分块
- [ ] 嵌入:**本地嵌入优先**(bge-small,零 API 成本 + 隐私)
- [ ] 轻量向量索引(单学生数据量小,numpy/chromadb 均可)
- [ ] 接入 `agent_loop` 作为新工具 `retrieve_course_content`
- [ ] 引用来源:回答标注来自哪份讲义 + 信息源 URL
- **验收**:"COMP2090 考核占比是多少"这类问题能从课件答出,并标注来源。

### Phase 4 — 分发
**目标**:新同学照 README 能跑起来。(分发方式:Python 直装)
- [ ] 面向他人的 `init.sh` / 启动脚本(处理 `playwright install` 等)
- [ ] `requirements.txt` + 安装文档(Mac/Win)
- **验收**:一个非作者的用户,照 README 从零跑起来并完成一次问答。

### Phase 5 — 打磨(可选,优先级最低)
- [ ] 多 session / 前端重新生成 / 编辑消息 / markdown 渲染
- [ ] agent trace + token 成本统计
- [ ] 单元/集成测试 + CI

---

## 7. 退役清单(不再驱动决策)

| 文件 / 策略 | 处置 | 理由 |
|---|---|---|
| `DEV_PLAN.md` | 🗄 Phase 0 移入 `archive/` | Session 1–9 全完成,不再反映现状 |
| `feature_list.json` | 🗄 Phase 0 移入 `archive/` | F01–F14 全完成(F14 过时标记),不再驱动新工作 |
| `CLAUDE.md` 架构段(retriever/operator、单步意图分类) | ✏️ Phase 0 重写 | 与现状(ReAct + 9 工具)脱节 |
| 旧「意图分类」思路 | 🗑 放弃 | 已被 ReAct 工具编排取代 |

> **从现在起,唯一准绳是本路线图的北极星 + §5 策略原则。** 不再引用 F14、retriever/operator 等旧概念。

---

## 8. 决议记录(原 §6 待定决策)

| # | 决策 | 结论 | 时间 |
|---|---|---|---|
| ① | 分发方式 | **Python 直装** | 2026-06-25 已定 |
| ② | RAG 嵌入选型 | 本地嵌入 bge-small(默认推荐) | Phase 2 末正式确认 |
| ③ | 通用化野心 | 纯 HKMU + 保持 `src/actions/` 动作粒度 | 已采纳 |
| ④ | 分发决策时间点 | 前置到 Phase 0→1 | 已采纳 |
| ⑤ | agent_loop 解耦 | 作为贯穿主线单列(横穿 Phase 1–2) | 已采纳 |

---

## 9. 工作原则

- **一次一阶段**:做完验证再进下一个,不跨阶段并行。
- **外科手术式改动**:不破坏现有 `src/` 工作代码;每个改动尽量小、可验证。
- **每个任务有验收标准**:能跑/能 grep/能演示,才算完成。
- **改完即提交**:`feat/fix: PhaseX - 描述`,并同步本文件的 checkbox。

---

## 10. 下一步

**Phase 2 — 成熟度补课:✅ 已完成(2026-07-03)**,见 §6(`4441fe9` + `3f9f1c5` + `7280286`)。
流式逐字、工具 schema 校验、错误重试、上下文持久化均已实测;>12 轮摘要按升级阶梯缓做。
下一阶段 **Phase 3 — RAG**(PDF 抽文本 + 本地嵌入 bge-small + 向量检索 + `retrieve_course_content` 工具),等用户发令后启动。
