#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 🔥 NANO-RAG LAUNCHER
# ═══════════════════════════════════════════════════════════════
# 
# Axiom Inversion Applied:
# - Two agents, one brain
# - Files as neurons
# - RAG as long-term memory
# - 40KB context + infinite disk = unlimited intelligence

set -e

SCRIPT_DIR="$HOME/project-chimera/scripts"
NANO_DIR="$HOME/nano_memory"
VENV_DIR="$HOME/.sovereign_trinity_app/venv"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
cat << 'BANNER'
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ███╗   ██╗ █████╗ ███╗   ██╗ ██████╗     ██████╗  █████╗   ║
║   ████╗  ██║██╔══██╗████╗  ██║██╔═══██╗    ██╔══██╗██╔══██╗  ║
║   ██╔██╗ ██║███████║██╔██╗ ██║██║   ██║    ██████╔╝███████║  ║
║   ██║╚██╗██║██╔══██║██║╚██╗██║██║   ██║    ██╔══██╗██╔══██║  ║
║   ██║ ╚████║██║  ██║██║ ╚████║╚██████╔╝    ██║  ██║██║  ██║  ║
║   ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝     ╚═╝  ╚═╝╚═╝  ╚═╝  ║
║                                                              ║
║     🔥 File-Based AI with Infinite Memory 🔥                 ║
╚══════════════════════════════════════════════════════════════╝
BANNER
echo -e "${NC}"

usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  agent     Start the RAG agent (background processor)"
    echo "  chat      Start the UI agent (interactive chat)"
    echo "  ask       One-shot query: $0 ask 'your question'"
    echo "  status    Show system status"
    echo "  clean     Clear nano memory"
    echo ""
}

check_deps() {
    # Install watchdog if needed
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
        pip install watchdog -q 2>/dev/null || true
    fi
}

start_agent() {
    echo -e "${GREEN}🤖 Starting RAG Agent...${NC}"
    check_deps
    
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
    fi
    
    python3 "$SCRIPT_DIR/nano_rag_agent.py"
}

start_chat() {
    echo -e "${GREEN}💬 Starting UI Agent...${NC}"
    
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
    fi
    
    python3 "$SCRIPT_DIR/nano_ui_agent.py"
}

ask_query() {
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
    fi
    
    python3 "$SCRIPT_DIR/nano_ui_agent.py" "$@"
}

show_status() {
    echo -e "${CYAN}📊 Nano-RAG Status${NC}"
    echo ""
    
    # Check directories
    echo "Directories:"
    for dir in "$NANO_DIR/inbox" "$NANO_DIR/outbox" "$NANO_DIR/archive"; do
        if [ -d "$dir" ]; then
            count=$(ls -1 "$dir"/*.nano 2>/dev/null | wc -l)
            echo -e "  ${GREEN}✓${NC} $dir ($count files)"
        else
            echo -e "  ${RED}✗${NC} $dir (missing)"
        fi
    done
    
    # Check index
    if [ -f "$NANO_DIR/index.jsonl" ]; then
        lines=$(wc -l < "$NANO_DIR/index.jsonl")
        echo -e "  ${GREEN}✓${NC} Memory index: $lines entries"
    else
        echo -e "  ${RED}✗${NC} Memory index: empty"
    fi
    
    # Check Ollama
    echo ""
    echo "Services:"
    if curl -s http://localhost:11434/api/version >/dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Ollama running"
    else
        echo -e "  ${RED}✗${NC} Ollama not running"
    fi
}

clean_memory() {
    echo -e "${RED}🧹 Cleaning nano memory...${NC}"
    rm -rf "$NANO_DIR/inbox"/*.nano 2>/dev/null
    rm -rf "$NANO_DIR/outbox"/*.nano 2>/dev/null
    rm -rf "$NANO_DIR/archive"/*.nano 2>/dev/null
    rm -f "$NANO_DIR/index.jsonl"
    echo "Done."
}

case "${1:-}" in
    agent)
        start_agent
        ;;
    chat)
        start_chat
        ;;
    ask)
        shift
        ask_query "$@"
        ;;
    status)
        show_status
        ;;
    clean)
        clean_memory
        ;;
    *)
        usage
        ;;
esac
