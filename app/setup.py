"""首启配置向导 — 交互式收集 LLM 与 OLE 凭证,写入 .env。

用法:python -m app.setup
首次运行(无 .env)时由 init.sh 自动触发,也可随时手动运行重配。
所有输入只写入本地 .env(gitignored),不上传任何地方。
"""
import sys
from pathlib import Path

from .llm import _PROVIDERS

ENV_PATH = Path(__file__).parent.parent / ".env"

# 可选 provider = 预设 + custom
PROVIDERS = list(_PROVIDERS.keys()) + ["custom"]


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    return input(f"{prompt}{suffix}: ").strip() or default


def _secret(prompt: str) -> str:
    import getpass
    return getpass.getpass(f"{prompt}: ").strip()


def main() -> int:
    print("=" * 60)
    print("  OLE Agent 首启配置")
    print("  凭证只写入本地 .env(gitignored),不上传任何地方。")
    print("=" * 60)

    if ENV_PATH.exists():
        print(f"\n⚠️  已检测到 {ENV_PATH.name}")
        if _ask("覆盖重写? (y/N)", "N").lower() != "y":
            print("保留现有 .env,退出。")
            return 0

    # 1. LLM provider
    print(f"\n支持的 LLM provider:{PROVIDERS}")
    provider = _ask("选择 LLM provider", "deepseek").lower()
    if provider not in PROVIDERS:
        print(f"❌ 未知 provider:{provider}")
        return 1

    base_url = model = ""
    if provider == "custom":
        base_url = _ask("LLM_BASE_URL(OpenAI 兼容,含 /v1)")
        model = _ask("LLM_MODEL")
        if not base_url or not model:
            print("❌ custom provider 需提供 base_url 和 model")
            return 1

    # 2. API key(ollama 本地可空)
    if provider == "ollama":
        key = _ask("LLM_API_KEY(本地 ollama 通常无需,回车跳过)", "")
    else:
        key = _secret(f"LLM_API_KEY({provider})")
        if not key:
            print("❌ API key 不能为空")
            return 1

    # 3. OLE 凭证
    print("\n— HKMU OLE 登录凭证 —")
    username = _ask("OLE_USERNAME(学生账号)")
    if not username:
        print("❌ 学号不能为空")
        return 1
    password = _secret("OLE_PASSWORD")
    if not password:
        print("❌ 密码不能为空")
        return 1

    # 4. 写 .env
    lines = [
        "# OLE Agent 凭证(由 app/setup.py 生成)",
        "# HKMU OLE 登录",
        f"OLE_USERNAME={username}",
        f"OLE_PASSWORD={password}",
        "",
        "# LLM(OpenAI 兼容)",
        f"LLM_PROVIDER={provider}",
        f"LLM_API_KEY={key}",
    ]
    if base_url:
        lines.append(f"LLM_BASE_URL={base_url}")
    if model:
        lines.append(f"LLM_MODEL={model}")
    lines.append("")

    ENV_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ 已写入 {ENV_PATH.name}")
    print("下一步:启动应用")
    print("  python -m uvicorn app.main:app")
    print("(首次 scraper 调用时会自动登录 OLE 并持久化 session)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\n已取消。")
        sys.exit(1)
