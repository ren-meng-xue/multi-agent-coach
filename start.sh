#!/usr/bin/env bash
# start.sh
# 🚀 Multi-Agent Coach 统一启动入口 (最小闭环)

C_GREEN="\033[32m"
C_CYAN="\033[36m"
C_YELLOW="\033[33m"
C_RED="\033[31m"
C_RESET="\033[0m"

echo -e "${C_CYAN}🚀 正在初始化 Multi-Agent Coach 环境...${C_RESET}"

# 1. 确保日志文件存在
mkdir -p logs
touch logs/backend.log logs/celery.log logs/frontend.log logs/bus.log

cleanup() {
    echo -e "\n${C_YELLOW}🛑 正在关闭所有服务...${C_RESET}"
    # 使用 pkill 匹配进程名，确保清理干净
    pkill -f "uvicorn app.main:app" 2>/dev/null
    pkill -f "celery.*worker" 2>/dev/null
    pkill -f "next-dev" 2>/dev/null
    pkill -f "pnpm dev" 2>/dev/null
    pkill -f ".ai/bus/bin/watch.sh" 2>/dev/null
    echo -e "${C_GREEN}✅ 环境已清理。${C_RESET}"
    exit
}
trap cleanup SIGINT

# 2. 启动基础设施
echo -e "${C_GREEN}📦 [Docker] 启动基础服务...${C_RESET}"
docker compose up -d postgres redis >/dev/null 2>&1

# 3. 启动应用服务 (后台)
echo -e "${C_GREEN}📡 [Backend] 启动中...${C_RESET}"
(cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 > ../logs/backend.log 2>&1) &

echo -e "${C_GREEN}👷 [Celery] 启动中...${C_RESET}"
(cd backend && uv run celery -A app.tasks:celery_app worker --loglevel=info > ../logs/celery.log 2>&1) &

echo -e "${C_GREEN}🎨 [Frontend] 启动中...${C_RESET}"
(cd frontend && pnpm dev --port 3000 > ../logs/frontend.log 2>&1) &

# 4. 启动 Agent OS 总线
AGENT_OS_DIR=""
if [ -d ".ai" ]; then
    AGENT_OS_DIR=".ai"
elif [ -d "ai" ]; then
    AGENT_OS_DIR="ai"
fi

if [ -n "$AGENT_OS_DIR" ] && [ -f "$AGENT_OS_DIR/bus/bin/watch.sh" ]; then
    echo -e "${C_GREEN}🤖 [Agent OS] 启动总线监听器...${C_RESET}"
    bash "$AGENT_OS_DIR/bus/bin/watch.sh" > logs/bus.log 2>&1 &
else
    echo -e "${C_YELLOW}🤖 [Agent OS] 未找到总线脚本，跳过。${C_RESET}"
fi

echo -e "${C_CYAN}-------------------------------------------------------${C_RESET}"
echo -e "🌐 前端: ${C_YELLOW}http://localhost:3000${C_RESET}"
echo -e "🔧 后端: ${C_YELLOW}http://localhost:8000/docs${C_RESET}"
echo -e "📝 日志目录: ${C_YELLOW}./logs/${C_RESET}"
echo -e "${C_CYAN}-------------------------------------------------------${C_RESET}"
echo -e "💡 正在进入 Cockpit 控制面板 (按 Ctrl+C 停止一切)..."
sleep 2

# 5. 进入监控闭环
while true; do
    clear
    echo -e "${C_CYAN}=== System Health ===${C_RESET}"
    nc -z localhost 8000 && echo -e "Backend:  ${C_GREEN}ONLINE${C_RESET}" || echo -e "Backend:  ${C_RED}OFFLINE${C_RESET}"
    nc -z localhost 3000 && echo -e "Frontend: ${C_GREEN}ONLINE${C_RESET}" || echo -e "Frontend: ${C_RED}OFFLINE${C_RESET}"
    nc -z localhost 6379 && echo -e "Redis:    ${C_GREEN}ONLINE${C_RESET}" || echo -e "Redis:    ${C_RED}OFFLINE${C_RESET}"
    nc -z localhost 5432 && echo -e "Postgres: ${C_GREEN}ONLINE${C_RESET}" || echo -e "Postgres: ${C_RED}OFFLINE${C_RESET}"
    
    echo -e "\n${C_CYAN}=== Agent OS Cockpit ===${C_RESET}"
    if [ -n "$AGENT_OS_DIR" ] && [ -f "$AGENT_OS_DIR/dashboard/cockpit_rich.py" ]; then
        python3 "$AGENT_OS_DIR/dashboard/cockpit_rich.py"
    else
        echo -e "${C_YELLOW}Agent OS Cockpit unavailable: missing dashboard script.${C_RESET}"
    fi
    
    echo -e "\n${C_DIM}Tips: 查看日志使用 'tail -f logs/*.log' | 退出按 Ctrl+C${C_RESET}"
    sleep 2
done
