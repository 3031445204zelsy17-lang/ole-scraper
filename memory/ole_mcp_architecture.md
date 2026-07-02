---
name: OLE MCP-First Architecture
description: 2026-03-26 重构为 MCP-First 架构
type: project
---

## 架构变更

**从 Python Playwright 重构为 MCP-First 架构**

**Why**: Python 方案存在下载问题和性能瓶颈，且每次操作需要执行脚本不够灵活。用户需要快速、低 token、易于执行的方案。

**How to apply**:
1. 使用 `/ole <action>` 指令直接操作 OLE
2. 配置在 `ole-config/` 目录
3. Session 保存在 `ole-session/state.json`
4. 数据保存在 `ole-data/current/`

## 配置文件

| 文件 | 用途 |
|------|------|
| `ole-config/system.yaml` | URL、Session 配置 |
| `ole-config/selectors.yaml` | 页面选择器 |
| `ole-config/workflows/` | 操作流程 |

## 指令

- `/ole login` - 登录
- `/ole courses` - 课程
- `/ole assignments` - 作业
- `/ole classes` - 即将上课
- `/ole download` - 下载文件
- `/ole all` - 全部数据

## Session 管理

- Session 文件: `ole-session/state.json`
- 有效期: 24 小时
- 验证 URL: Dashboard 页面
