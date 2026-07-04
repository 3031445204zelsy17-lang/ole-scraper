# OLE Agent

> 跑在你自己电脑上的 HKMU OLE 学习 agent。用自然语言查课程 / 作业 / 课表 / 成绩,下载课件,搜索课程信息。
> **本地优先 + BYO key**:凭证全留本地,只发往 OLE(登录)和你的 LLM API(推理)。

> ⚠️ **非官方工具**:本项目与 HKMU 无关,为个人学习用途开发。使用前请阅读下方[免责声明](#免责声明)。

---

## 它能做什么

打开 `localhost:8000` 聊天框,用自然语言提问:

- 「我这周有什么作业?」→ 待交作业(按截止日期排序,临期标红)
- 「明天几点的课?」→ 即将上课时间表
- 「COMP2090 成绩」→ 进课程页抓取成绩
- 「下载 COMP2090 课件」→ 下载到 `downloads/<课程代码>/`
- 「COMP2090 有哪些材料?」→ 列出可下载清单(不下载)
- 「COMP2090 的 presentation 安排?」→ 从课程页 TileData 搜索
- 「根据课件,Tutorial 6 讲了哪些分布?」→ 从本地讲义 PDF 检索(RAG,标注来源页码)

目录类查询(课程 / 作业 / 课表)走本地 JSON 缓存,快且零 LLM 成本;细节类(成绩 / 下载 / 搜索)才开浏览器实时访问。

---

## 快速开始

### 1. 安装

```bash
git clone <repo-url> ole-agent && cd ole-agent
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. 配置凭证

```bash
cp .env.example .env
```

编辑 `.env` 填入:

```
OLE_USERNAME=你的 HKMU 学生账号
OLE_PASSWORD=你的 OLE 密码
LLM_PROVIDER=deepseek          # deepseek|glm|openai|ollama
LLM_API_KEY=你的 LLM API key
```

### 3. 启动

一键(推荐,含前端构建 + 起):

    ./init.sh

或手动:

    cd frontend && npm install && npm run build && cd ..
    python -m uvicorn app.main:app

浏览器打开 `http://localhost:8000`(后端托管 `frontend/dist`)。首次使用时 scraper 会登录 OLE 并持久化 session(`sessions/`),之后免重复登录。

> 前端开发(热更新):`cd frontend && npm run dev`(5173,proxy `/ws` → 8000),另起 `python -m uvicorn app.main:app`。

**课件内容问答(RAG)**:若要让 agent 回答「课件里怎么说」类问题,先建索引(扫描 `downloads/` 下 PDF,首次下 bge 模型 ~100MB):

    python -m app.rag_index build        # 建索引
    python -m app.rag_index status       # 查看索引状态

之后「根据课件,…?」会从本地讲义检索并标注来源(哪份 PDF + 页码)。

---

## 隐私

- **凭证全本地**:`.env` 和 `sessions/` 只存在你的机器上,已在 `.gitignore`,不会提交或上传。
- **数据流向**:你的输入 → 本地 agent → ① OLE(登录 / 抓数据)② 你的 LLM API(推理)。**不发往任何第三方**。
- **LLM 角色**:只决定调用哪个工具和组织回答,**不直接看 OLE 页面**(页面交互由本地 Playwright 完成)。

---

## 免责声明

- 本项目**非官方**,与 HKMU 无关,为个人学习用途开发。
- 你需对自己的账号和行为负责。请遵守 HKMU OLE 服务条款,**控制访问频率**(建议每天不超过 1–2 次),勿用于批量抓取或任何可能影响系统运行的用途。
- 本项目不提供任何担保,作者不对使用后果承担责任。

---

## 架构 & 路线图

ReAct agent(DeepSeek function-calling)+ 硬编码选择器的 Playwright 爬虫 + JSON 缓存。
架构详见 [`CLAUDE.md`](CLAUDE.md),开发路线图详见 [`ROADMAP.md`](ROADMAP.md)。

当前阶段:**Phase 3 — RAG(课件内容问答)已完成**。

## License

MIT。**注意**:RAG 课件检索使用 [PyMuPDF](https://pymupdf.readthedocs.io/)(AGPL-3.0)——本地自用零义务;若把本项目嵌入闭源产品分发、或作为 SaaS 对外提供服务,需向 Artifex 购买商业许可。
