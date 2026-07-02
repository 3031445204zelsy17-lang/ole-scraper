# OLE Download Lectures Skill

自动下载 OLE 课程 lecture 文件的技能。

## 触发条件

用户请求下载课程的 lecture/课件 文件，例如：
- "下载 COMP 课程的 lecture"
- "下载 IT1030 的课件"
- "获取 xxx 课程的 lec 文件"

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

### Step 4: 筛选 Lecture 文件

从 TileData JSON 中筛选包含以下关键词的文件：
- `lec` (lecture)
- `Lecture`
- `lec_note`

提取每个文件的：
- `lbl`: 文件名
- `link`: 相对路径（如 `./0/XXX/$FILE/filename.pdf`）

### Step 5: 构建下载 URL

```
Base URL: https://ole.hkmu.edu.hk/course2600/{COURSE_CODE}.nsf
Full URL: {Base URL}{相对路径去掉开头的./}

例如:
./0/959387ED94982EE948258D800033B108/$FILE/lec_note_1.pdf
→ https://ole.hkmu.edu.hk/course2600/COMP2090SEF.nsf/0/959387ED94982EE948258D800033B108/$FILE/lec_note_1.pdf
```

### Step 6: 下载文件

```bash
# 创建目录
mkdir -p ~/Desktop/{COURSE_CODE}_lectures

# 使用 cookies 下载
curl -L -b "LtpaToken={TOKEN}; oleuser={USER}" \
  -o "filename.pdf" "https://ole.hkmu.edu.hk/course2600/{COURSE_CODE}.nsf/0/{DOC_ID}/\$FILE/{FILENAME}"
```

### Step 7: 验证并打开

```bash
# 验证文件
file ~/Desktop/{COURSE_CODE}_lectures/*.pdf

# 打开文件夹
open ~/Desktop/{COURSE_CODE}_lectures/
```

## 常用课程代码

| 课程 | 代码 |
|------|------|
| Data Structures, Algorithms And Problem Solving | COMP2090SEF |
| Introduction To Internet Application Development | IT1030SEF |
| Probability And Distributions | STAT1510SEF |
| Data Analytics With Applications | STAT2610SEF |
| University English: Listening And Speaking | ENGL1202EEF |

## 注意事项

1. **Session 有效期**: LtpaToken 有效期约 24 小时，过期需重新登录
2. **URL 编码**: 文件名中的空格和特殊字符需要 URL 编码
3. **Frameset 结构**: 课程页面使用 frameset，browser_snapshot 返回空，必须用 browser_evaluate 访问 frame 内容
4. **去重**: TileData 中同一文件可能出现在多个 tile 中，下载时需去重

## 示例调用

```
用户: 下载 COMP2090SEF 的 lecture 文件

执行:
1. 登录 OLE → 获取 cookies
2. 打开 COMP2090SEF 课程页面
3. 提取 TileData，筛选 lec_note_*.pdf
4. 下载 6 个文件到 ~/Desktop/COMP2090SEF_lectures/
5. 验证并打开文件夹
```

## Token 消耗参考

- 单次下载（6-7个文件）: ~35-40K tokens
- 主要消耗: TileData 提取、页面导航、多次 curl 下载
