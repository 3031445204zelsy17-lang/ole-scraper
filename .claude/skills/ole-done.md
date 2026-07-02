# OLE Feature Done - 功能完成提交

每完成一个功能后使用。

## 执行步骤

### 1. 确认测试通过
```bash
# 根据功能类型选择验证方式
python -c "from app.xxx import yyy; print('OK')"  # 验证导入
curl http://localhost:8000/api/health              # 验证服务
```

### 2. 查看改动范围
```bash
git diff --stat
```
确认只改了该功能相关的文件。

### 3. 提交代码
```bash
git add [具体文件，不用 add -A]
git commit -m "feat: F0X - 功能描述"
```

### 4. 更新功能清单
编辑 `feature_list.json`，将对应功能的 `passes` 改为 `true`。

```bash
git add feature_list.json
git commit -m "update: F0X passes"
```

### 5. 输出完成报告
```
✅ F0X 完成
改动文件: [列出]
功能清单进度: X/15

下一个任务是 F0Y - [描述]
下次对话输入 /ole-start 继续
```
