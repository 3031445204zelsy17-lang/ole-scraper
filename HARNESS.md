# OLE Agent - Claude Code Harness（精简版）

> 基于你的流程框架 + Anthropic 文章，裁剪到 ole-scraper 的实际规模

---

## 三个阶段，每个阶段 = 一次 Claude Code 对话

```
阶段1: 规划（Plan Mode）
  └─ 读现状 → 定目标 → 写 feature_list.json → 人审
阶段2: 执行（Act Mode）← 重复 N 次，每次一个功能
  └─ 读快照 → 写代码 → 测试 → commit → 更新 feature_list
阶段3: 验收（Review）
  └─ 全量测试 → 人审 diff → 清理上下文 → 更新记忆
```

---

## 阶段1: 规划（首次对话）

### 你做什么
在 Claude Code 中执行：

```
读取 ole-scraper 项目的 CLAUDE.md、src/ 目录结构、
ole-data/current/ 下的数据，和 DEV_PLAN.md。

然后帮我做三件事：

1. 初始化 git（如果还没有的话），.gitignore 排除 .env、__pycache__、.DS_Store
2. 创建 feature_list.json，把 DEV_PLAN.md 里的 15 个功能全部标为 false
3. 提交首次 commit

输出：当前项目状态摘要 + feature_list 全景
```

### 你审查什么
- feature_list.json 的 15 条是否覆盖你想做的所有功能
- 有没有遗漏的？有就加进去
- 确认后说「确认，进入执行」

---

## 阶段2: 执行（每个功能一次对话）

### 每次对话的开场白（固定模板）

```
继续开发 ole-scraper 项目。

执行启动流程：
1. pwd 确认目录
2. git log --oneline -3 看上次进度
3. 读 feature_list.json，选第一个 passes=false 的功能
4. 开始实现

实现前先告诉我你选了哪个功能、计划怎么做，等我确认再动手。
```

### Claude Code 做什么（固定流程）

```
┌─ 读快照（Recovery Load）
│  git log → 看上次做了什么
│  feature_list.json → 看该做什么
│
├─ 原子操作（Atomic Act）
│  只改一个功能相关的文件
│  不动其他已完成的代码
│
├─ 验证（Verify）
│  运行 python -c "from app.xxx import yyy" 确认无语法错误
│  如果有 API 端点：curl 测试
│  如果有前端：打开浏览器确认
│
├─ HITL 检查点
│  展示改动内容，等你说「继续」或「改一下 xxx」
│
└─ 提交（Commit）
   git add 具体文件（不 add -A）
   git commit -m "feat: F0X - 功能描述"
   更新 feature_list.json 中对应条目为 true
   git commit -m "update: F0X passes"
```

### 你审查什么（每个功能）

| 检查 | 怎么做 |
|------|--------|
| 代码能跑 | 看终端输出有没有报错 |
| 改动范围对不对 | `git diff HEAD~1` 看只改了该改的文件 |
| 功能正确 | 手动测试一次（输入指令看回复） |

**如果出 bug**：
```
刚才 F05 的作业查询返回了空列表，修一下。
提示：assignments.json 的路径可能有问题。
```
→ Claude Code 修复 → 重新验证 → amend commit 或新 commit

---

## 阶段3: 验收（全部功能完成后）

### 你在 Claude Code 中执行

```
ole-scraper 项目所有功能开发完毕，做验收：

1. 读 feature_list.json，确认所有条目都是 true
2. 启动应用（uvicorn app.main:app），逐个测试每个功能
3. 发现问题列出来，逐个修复
4. 全部通过后，输出最终项目摘要
```

### 你做什么
- `bash init.sh` 启动应用
- 打开浏览器，逐个输入：课程、作业、课表、成绩、help、下载
- 每个都正常 → 验收通过
- 有问题 → 回到阶段2修复

---

## 上下文管理（对话中）

### 对话变长时（token 接近上限）

在对话中输入：
```
总结当前进度：
1. 已完成哪些 feature（标 true 的）
2. 当前正在做什么
3. 下一步该做什么

然后清理对话历史，保留这个总结。
```

### 跨对话时（新 session）

用开场白模板（阶段2的那个），它会自动读 git log + feature_list 恢复状态。

---

## 一页速查

```
╔══════════════════════════════════════════╗
║  每个 Claude Code 对话的固定节奏          ║
╠══════════════════════════════════════════╣
║                                          ║
║  1. pwd + git log     → 我在哪           ║
║  2. feature_list.json → 我该做什么       ║
║  3. 说计划，等人确认   → 人审（HITL）     ║
║  4. 写代码 + 测试     → 原子操作         ║
║  5. 展示改动，等人确认 → 人审（HITL）     ║
║  6. git commit        → 提交             ║
║  7. 更新 feature_list → 记录进度         ║
║                                          ║
╚══════════════════════════════════════════╝

功能执行顺序（建议）：
  F01 API启动 → F02 聊天界面 → F03 WebSocket
  → F04 课程 → F05 作业 → F06 课表
  → F07 下载 → F08 全部 → F09 格式化
  → F10 缓存 → F11 成绩 → F12 init.sh
  → F13 错误处理 → F14 帮助 → F15 截止提醒
```
