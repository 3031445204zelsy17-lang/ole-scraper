# OLE Retrieve Grading Info Skill

检索 OLE 课程评分/考核要求的技能。

## 触发条件

用户请求检索课程的评分/考核/作业要求，例如：
- "查找 GEN 课程的评分要求"
- "获取 xxx 课程的考核信息"
- "查看课程的成绩构成"

## 前置条件

- `.env` 文件中配置了 `OLE_USERNAME` 和 `OLE_PASSWORD`
- Playwright MCP 可用

## 执行流程

### Step 1: 登录并获取 Cookies

```
1. 导航到 https://ole.hkmu.edu.hk/
2. 填写用户名密码登录
3. 获取 cookies: document.cookie
4. 提取 LtpaToken 和 oleuser
```

### Step 2: 导航到课程页面

```
1. 导航到 Dashboard: https://ole.hkmu.edu.hk/dashboard/index.html
2. 等待课程列表加载
3. 点击目标课程链接（匹配课程代码）
4. 切换到新打开的 tab
```

### Step 3: 提取 TileData

课程页面使用 frameset 结构，需要通过 JavaScript 提取：

```javascript
() => {
  try {
    const navTop = window.frames[0];
    const body = navTop.document.body.innerHTML;
    const match = body.match(/TileData\s*=\s*\[[\s\S]*?\];/);
    return match ? match[0] : 'No TileData found';
  } catch(e) {
    return 'Error: ' + e.message;
  }
}
```

### Step 4: 筛选评分相关文件

从 TileData JSON 中筛选包含以下关键词的文件：
- `assessment` (评估)
- `grading` (评分)
- `mark` (分数)
- `score` (得分)
- `assignment` (作业)
- `exam` (考试)
- `coursework` (课程作业)
- `考核` (中文)
- `评分` (中文)

提取每个文件的：
- `lbl`: 文件名
- `link`: 相对路径（如 `./0/XXX/$FILE/filename.pdf`）

### Step 5: 构建访问 URL

```
Base URL: https://ole.hkmu.edu.hk/course2600/{COURSE_CODE}.nsf
Full URL: {Base URL}{相对路径去掉开头的./}
```

### Step 6: 检索信息

对于找到的评分相关文件：
1. 记录文件名和 URL
2. 如果是 PDF/文档，记录下载链接
3. 如果是网页内容，提取文本信息
4. 汇总评分要求信息

### Step 7: 返回结果

返回格式：
```
## 课程评分要求

**信息源**: {URL}

### 评分构成
- 作业/课程作业: XX%
- 考试: XX%
- 其他: XX%

### 详细要求
{提取的具体内容}
```

## 常用课程代码

| 课程类型 | 代码示例 |
|---------|---------|
| General Education | GEN1234SEF |
| Computing | COMP2090SEF |
| IT | IT1030SEF |
| Statistics | STAT1510SEF |
| English | ENGL1202EEF |

## 注意事项

1. **只读操作**: 只检索信息，不修改任何内容
2. **信息溯源**: 必须标注信息源 URL
3. **Frameset 结构**: 课程页面使用 frameset，browser_snapshot 返回空，必须用 browser_evaluate 访问 frame 内容
4. **文件类型**: 评分信息可能在 PDF、网页或 Word 文档中

## Token 消耗参考

- 单次检索（1-2个课程）: ~30-50K tokens
- 主要消耗: TileData 提取、页面导航、内容提取
