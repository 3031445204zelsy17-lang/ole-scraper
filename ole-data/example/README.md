# ole-data/example — 缓存数据格式示例

本目录是 OLE 缓存数据的**脱敏示例**,仅用于展示格式,供开发/参考。

## 运行时数据在哪

真实数据由 scraper 写入 `ole-data/current/`(见 `app/cache.py`):

- `courses.json`
- `assignments.json`
- `classes.json`

`ole-data/current/` 已在 `.gitignore` 中,**不会被提交**(含真实课表/作业,属个人数据)。
首次运行时由 scraper 登录 OLE 后自动抓取生成。

## 字段说明

| 文件 | 顶层键 | 条目字段 |
|---|---|---|
| `courses.json` | `courses` | `code`, `name`, `url` |
| `assignments.json` | `assignments` | `course`, `title`, `deadline`(ISO) |
| `classes.json` | `upcoming_classes` | `course`, `type`, `time`(ISO), `location` |

每个文件还含 `fetch_time`(抓取时间,`app/cache.py` 据此判 TTL 过期)与 `source`(来源 URL)。
