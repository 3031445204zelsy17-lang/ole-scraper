"""ReAct Agent 循环 — LLM 推理 → 工具调用 → 观察 → 重复/回答"""
import json
import asyncio
import logging

from .tools import TOOL_DEFINITIONS
from .config import LLM_CONFIG
from .llm import call_llm_stream

log = logging.getLogger("ole-agent")

MAX_TURNS = 8
RETRIEVE_CAP = 3  # 每次循环 retrieve_* 类工具最多调用次数(防 LLM 空转撑满轮次)
_RETRIEVE_TOOLS = {"retrieve_course_content", "retrieve_public_info"}


def _validate_tool_args(fn_name: str, fn_args: dict) -> tuple[bool, str]:
    """按 TOOL_DEFINITIONS 校验参数:required 缺失 / enum 非法。

    返回 (ok, error_msg);ok=True 时 error_msg 为空。
    取代旧的 file_type 手写补丁 —— 用通用 schema 校验 + 让 LLM 自纠正。
    """
    for td in TOOL_DEFINITIONS:
        if td["function"]["name"] != fn_name:
            continue
        schema = td["function"].get("parameters", {})
        for req in schema.get("required", []):
            if not fn_args.get(req):
                return False, f"缺少必填参数「{req}」"
        for prop, spec in schema.get("properties", {}).items():
            if prop in fn_args and "enum" in spec and fn_args[prop] not in spec["enum"]:
                return False, f"参数「{prop}」={fn_args[prop]!r} 不合法,可选 {spec['enum']}"
        return True, ""
    return True, ""  # 未登记的工具,交由 executor 处理

AGENT_SYSTEM_PROMPT = """你是 OLE Agent，帮助学生查询 HKMU OLE 学习系统信息。

可用工具分四类：
1. 缓存工具（快）：get_courses, get_assignments, get_upcoming_classes
2. 浏览器查询工具（实时访问 OLE 页面）：
   - list_course_files: 列出课程可下载的文件（课件、辅导材料等）
   - get_grades: 查看课程成绩
   - browse_course_page: 访问课程页面提取内容（用于查询 Presentation 安排、公告、Class Activities 等）
3. Skill 工具（预编排的多步操作，自动完成登录、导航、提取）：
   - download_course_files: 下载课程文件到本地（需传 course_code）
   - get_course_materials: 列出课程所有可下载材料清单（含分类统计，不执行下载）
   - search_course_info: 从课程 TileData 搜索特定信息（日程安排、presentation、group project、exam 等）
4. RAG 检索工具（本地索引，需先建索引）：
   - retrieve_course_content: 从已下载的课件 PDF 回答「考核占比/评分标准/某 unit 讲什么/某概念定义」(需 `python -m app.rag_index build`)
   - retrieve_public_info: 从 HKMU 官网公开页面回答「招生/专业介绍/课程结构/培养方案/某专业学什么或有哪些课/学费/奖学金/新闻/校历/图书馆服务」(需 `python -m app.public_rag crawl && build`)

使用工具的时机：
- 用户要「下载」课件 → 先用 get_courses 确认课程代码（如果用户没给完整的），再调用 download_course_files
- 用户要「列出/看看有什么材料」→ get_course_materials（不下载）
- 用户要查成绩 → get_grades
- 用户要查作业 → get_assignments
- 用户要查课程安排（presentation日期、分组、考试时间等）→ search_course_info（传 course_code + query 关键词）
- search_course_info 比 browse_course_page 更快更可靠，优先使用
- 用户问「课件里怎么说」「考核占比/评分标准」「某 unit 讲什么」「某概念定义」→ retrieve_course_content（传 query 关键词，从本地讲义 PDF 检索）
- retrieve_course_content 返回片段后,务必基于片段总结回答并标注来源(pdf + 页码);若片段不相关,如实告知「课件中未找到」,不要返回空回答
- 标注来源时,直接复用片段里的 source 字段(已是 markdown 链接 [📄 文件名 p页](/source?...),前端可点击打开 PDF),不要自己重写文件名
- 区分两类「课程」问题:「我的/我这学期注册的课」→ 个人数据(get_courses,需 OLE 登录);「某专业/programme 的课程结构、培养方案、某专业学什么/有哪些课」→ 官网公开信息(retrieve_public_info)。后者即使用户没说「官网」也走 retrieve_public_info。
- 用户问 HKMU 官网公开信息(招生/专业/课程结构/学费/奖学金/新闻/校历/图书馆等),或 OLE 返回空但问题其实属于公开信息 → retrieve_public_info(传 query 关键词,英文+中文皆可)
- retrieve_public_info 返回片段后,复用片段 source 字段(已是 [🔗 标题](url) 外链,前端可点击打开官网原文);只摘录要点 + 标注来源,不要全文搬运官网页面;查不到如实告知

下载策略：
- 用户指定文件名（如「下载 Unit 1」）→ 传 file_name="Unit 1"
- 用户要下载某类文件（如「全部 tutorial」「全部课件」）→ 传 file_type="tutorial"/"lecture" 和 max_files=50
- 用户要下载全部 → 传 max_files=50，不传 file_name
- 用户没指定具体文件 → 先用 get_course_materials 列出文件让用户选择
- 下载默认保存到 downloads/<课程代码>/,无需传 output_dir;仅当用户明确指定其他目录时才传 output_dir(绝对路径)

重要规则：
- 回答简洁，直接给出关键信息
- 用户提到具体课程时务必传 course_code 参数
- 如果工具返回空数据，直接告知用户，不要猜测或编造
- 【严禁编造具体事实】绝不可凭训练记忆杜撰:课程代码/课程名/学分/学费金额/截止日期/电话/政策条款等。这些只能来自工具结果;工具查不到就如实说「未查到」,并建议查 OLE 或官网。若 OLE 课表为空、但问题其实是「某专业的课程结构」(公开信息),**必须先调 retrieve_public_info 再回答**,不可凭印象列课。
- 【检索收敛】对同一问题,retrieve_* 类工具最多调用 2-3 次(每次换不同关键词,如中文/英文/专业代码各一次);之后**必须基于已有片段综合回答并标注来源**,不可反复检索撑满轮次。若返回片段明显不相关或不足以回答,如实告知「官网索引里没查到详细内容」+ 给出最相关的来源链接供用户自查,不要硬凑。
- 不要反复调用相同工具
- 下载时只调用 download_course_files，不要同时调用 get_grades 或其他无关工具
- 当前日期：{date}
"""


async def run_agent_loop(
    user_message: str,
    history: list[dict],
    executor,
    on_thinking=None,
    on_delta=None,
    cancel_event: asyncio.Event | None = None,
) -> str:
    """运行 ReAct 循环。

    Args:
        user_message: 用户原始消息
        history: 对话历史
        executor: ToolExecutor 实例
        on_thinking: async callback(str) 用于向前端推送中间状态

    Returns:
        最终回复文本
    """
    from datetime import datetime

    system_msg = {
        "role": "system",
        "content": AGENT_SYSTEM_PROMPT.format(date=datetime.now().strftime("%Y-%m-%d")),
    }
    messages = [system_msg] + history + [{"role": "user", "content": user_message}]

    retrieve_used = 0  # 本轮 retrieve_* 调用计数(硬上限见 RETRIEVE_CAP)

    for turn in range(MAX_TURNS):
        log.info("Agent turn %d", turn + 1)

        # 检查取消信号
        if cancel_event and cancel_event.is_set():
            return "已停止生成。"

        try:
            assistant_msg, finish_reason = await call_llm_stream(
                LLM_CONFIG,
                messages,
                tools=TOOL_DEFINITIONS,
                temperature=0.1,
                on_delta=on_delta,
            )
        except Exception as e:
            log.error("LLM stream error [%s]: %s", LLM_CONFIG.describe(), e)
            return f"Agent 推理失败: {e.__class__.__name__}。请稍后重试,或检查 LLM 配置({LLM_CONFIG.describe()})。"

        if finish_reason == "tool_calls":
            # LLM 要调用工具
            messages.append(assistant_msg)

            # 推送思考内容
            if on_thinking and assistant_msg.get("content"):
                await on_thinking(assistant_msg["content"])

            tool_calls = assistant_msg.get("tool_calls", [])
            for tc in tool_calls:
                # 每次工具调用前检查取消
                if cancel_event and cancel_event.is_set():
                    return "已停止生成。"
                fn_name = tc["function"]["name"]
                fn_args_str = tc["function"]["arguments"]

                if on_thinking:
                    await on_thinking(f"[调用] {fn_name}({fn_args_str})")

                # 1. 参数 JSON 解析:失败不静默,反馈给 LLM 让它重新生成
                try:
                    fn_args = json.loads(fn_args_str)
                except json.JSONDecodeError as e:
                    log.warning("工具参数 JSON 解析失败 [%s]: %s", fn_name, e)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": f"arguments 不是合法 JSON({e})。请重新调用 {fn_name} 并输出合法 JSON。",
                    })
                    continue

                # 2. 参数 schema 校验:缺必填 / enum 非法 → 反馈纠正(取代旧 file_type 手写补丁)
                ok, err = _validate_tool_args(fn_name, fn_args)
                if not ok:
                    log.warning("工具参数校验失败 [%s]: %s", fn_name, err)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": f"参数错误:{err}。请修正后重新调用 {fn_name}。",
                    })
                    continue

                # 3. 执行(retrieve_* 类有硬次数上限,防 LLM 空转撑满 MAX_TURNS)
                if fn_name in _RETRIEVE_TOOLS:
                    retrieve_used += 1
                    if retrieve_used > RETRIEVE_CAP:
                        result = json.dumps({"note": f"已检索 {RETRIEVE_CAP} 次达上限。请直接基于以上已检索到的内容综合回答并标注来源,不要再调用任何 retrieve 工具。"}, ensure_ascii=False)
                        if on_thinking:
                            await on_thinking("[检索上限] 强制综合回答")
                        messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                        continue
                result = await executor.execute(fn_name, fn_args)

                if on_thinking:
                    preview = result[:150] + "..." if len(result) > 150 else result
                    await on_thinking(f"[结果] {preview}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
            continue

        elif finish_reason == "stop":
            return assistant_msg.get("content") or "（agent 未能生成回答。可能检索结果不足或推理中断,请换个问法,或确认已运行 python -m app.rag_index build 建索引。）"

        else:
            log.warning("Unexpected finish_reason: %s", finish_reason)
            return assistant_msg.get("content", "处理过程中出现问题，请换个说法再试。")

    return "这个问题比较复杂，我已尝试多步但仍未完全解决。请尝试更具体地描述你的需求。"
