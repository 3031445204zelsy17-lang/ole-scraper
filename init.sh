#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; }

# ── 1. Python 版本检查 ──────────────────────────────────────

check_python() {
    if command -v python3 &>/dev/null; then
        PY=python3
    elif command -v python &>/dev/null; then
        PY=python
    else
        error "Python 未安装。请安装 Python 3.10+ 后重试。"
        exit 1
    fi

    VER=$($PY -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    MAJOR=$(echo "$VER" | cut -d. -f1)
    MINOR=$(echo "$VER" | cut -d. -f2)

    if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]; }; then
        error "Python $VER 版本过低，需要 3.10+"
        exit 1
    fi
    info "Python $VER"
}

# ── 2. .env 检查 ─────────────────────────────────────────────

check_env() {
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            warn "已从 .env.example 创建 .env"
            warn "请编辑 .env 填入你的 OLE 凭证后重新运行"
            exit 0
        else
            error "缺少 .env 文件，请参考文档创建"
            exit 1
        fi
    fi
    info ".env 已就绪"
}

# ── 3. 依赖安装 ──────────────────────────────────────────────

install_deps() {
    if $PY -c "import fastapi" 2>/dev/null && $PY -c "import uvicorn" 2>/dev/null; then
        info "Python 依赖已安装"
    else
        info "安装 Python 依赖..."
        $PY -m pip install -r requirements.txt -q
        info "Python 依赖安装完成"
    fi
}

# ── 4. Playwright 浏览器 ─────────────────────────────────────

check_playwright() {
    if ! $PY -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
        info "安装 Playwright..."
        $PY -m pip install playwright -q
    fi

    info "确保 Chromium 已安装..."
    $PY -m playwright install chromium 2>&1 | grep -q "already" && info "Playwright 浏览器已就绪" || info "Chromium 安装完成"
}

# ── 5. 可选：DeepSeek API Key ────────────────────────────────

check_deepseek() {
    if [ -f ".env" ] && grep -q '^DEEPSEEK_API_KEY=.\+' .env 2>/dev/null; then
        info "DeepSeek API Key 已配置"
    else
        warn "未配置 DEEPSEEK_API_KEY，意图解析将使用关键词模式"
    fi
}

# ── 6. 创建必要目录 ──────────────────────────────────────────

ensure_dirs() {
    mkdir -p ole-data/current ole-downloads ole-session
    info "数据目录已就绪"
}

# ── 7. 启动服务器 ────────────────────────────────────────────

start_server() {
    echo ""
    info "启动 OLE Agent..."
    echo -e "  地址: ${GREEN}http://localhost:8000${NC}"
    echo -e "  按 Ctrl+C 停止"
    echo ""

    set -a
    source .env
    set +a

    exec $PY -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
}

# ── 主流程 ───────────────────────────────────────────────────

main() {
    echo -e "${GREEN}OLE Agent 初始化${NC}"
    echo "─────────────────────"

    check_python
    check_env
    install_deps
    check_playwright
    check_deepseek
    ensure_dirs

    echo "─────────────────────"
    start_server
}

main
