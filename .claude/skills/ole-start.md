# OLE Session Start - 开发会话启动

每次新开 Claude Code 对话时使用。

## 执行步骤

### 1. 确认位置
```bash
pwd
```
如果不在 ole-scraper 目录，提醒用户 `cd ~/Desktop/ole-scraper`。

### 2. 读上次进度
```bash
git log --oneline -5
```

### 3. 读功能清单
读取 `feature_list.json`，统计完成数，找到第一个 `passes: false` 的条目。

### 4. 识别功能类型
从 feature id 判断：
- F01-F03: 基础设施
- F04a-F05: 信息检索（只读，安全）
- F06: 操作功能（有副作用，需用户确认）
- F07-F13: 增强功能

### 5. 输出状态报告
```
📋 项目状态：
- 上次完成: [git log 最近一条]
- 整体进度: X/15 完成
- 下一个任务: F0X - [功能描述]（信息检索/操作功能）

建议本次实现 F0X，计划：
[简要描述实现方案]

确认后我开始。
```

### 6. 等待用户确认后再动手
