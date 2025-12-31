#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 🔥 PROJECT CHIMERA - LAUNCH SCRIPT
# ═══════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
cat << 'BANNER'
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ██████╗██╗  ██╗██╗███╗   ███╗███████╗██████╗  █████╗      ║
║  ██╔════╝██║  ██║██║████╗ ████║██╔════╝██╔══██╗██╔══██╗     ║
║  ██║     ███████║██║██╔████╔██║█████╗  ██████╔╝███████║     ║
║  ██║     ██╔══██║██║██║╚██╔╝██║██╔══╝  ██╔══██╗██╔══██║     ║
║  ╚██████╗██║  ██║██║██║ ╚═╝ ██║███████╗██║  ██║██║  ██║     ║
║   ╚═════╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝     ║
║                                                              ║
║        🔥 Enterprise Distributed Chat System v1.0 🔥         ║
╚══════════════════════════════════════════════════════════════╝
BANNER
echo -e "${NC}"

usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start       Start all services with Docker Compose"
    echo "  stop        Stop all services"
    echo "  restart     Restart all services"
    echo "  status      Show service status"
    echo "  logs        Show logs (follow mode)"
    echo "  build       Build all service images"
    echo "  clean       Stop and remove all containers/volumes"
    echo "  k8s         Deploy to Kubernetes"
    echo "  test        Run integration tests"
    echo ""
}

start_services() {
    echo -e "${YELLOW}🚀 Starting Chimera services...${NC}"
    docker-compose up -d
    
    echo -e "\n${GREEN}✅ Services started!${NC}"
    echo ""
    echo "  📡 Chat WebSocket: ws://localhost:80/ws"
    echo "  🔐 Crypto API:     http://localhost:8081"
    echo "  🧠 ML API:         http://localhost:8082"
    echo "  📊 Prometheus:     http://localhost:9090"
    echo "  📈 Grafana:        http://localhost:3000 (admin/chimera)"
    echo "  📨 NATS Monitor:   http://localhost:8222"
    echo ""
}

stop_services() {
    echo -e "${YELLOW}🛑 Stopping Chimera services...${NC}"
    docker-compose down
    echo -e "${GREEN}✅ Services stopped${NC}"
}

show_status() {
    echo -e "${CYAN}📊 Service Status:${NC}"
    docker-compose ps
    echo ""
    
    echo -e "${CYAN}🔍 Health Checks:${NC}"
    
    for service in "chat-server:8080" "crypto-service:8081" "ml-service:8082"; do
        name=$(echo $service | cut -d: -f1)
        port=$(echo $service | cut -d: -f2)
        
        if curl -s "http://localhost:$port/health" > /dev/null 2>&1; then
            echo -e "  ${GREEN}✓${NC} $name"
        else
            echo -e "  ${RED}✗${NC} $name"
        fi
    done
}

show_logs() {
    docker-compose logs -f
}

build_images() {
    echo -e "${YELLOW}🔨 Building Docker images...${NC}"
    docker-compose build --parallel
    echo -e "${GREEN}✅ Build complete${NC}"
}

clean_all() {
    echo -e "${YELLOW}🧹 Cleaning up...${NC}"
    docker-compose down -v --remove-orphans
    docker system prune -f
    echo -e "${GREEN}✅ Cleanup complete${NC}"
}

deploy_k8s() {
    echo -e "${YELLOW}☸️  Deploying to Kubernetes...${NC}"
    kubectl apply -f k8s/
    
    echo -e "\n${GREEN}✅ Deployed to Kubernetes!${NC}"
    echo ""
    kubectl -n chimera get pods
}

run_tests() {
    echo -e "${YELLOW}🧪 Running integration tests...${NC}"
    
    # Test chat server health
    echo -n "  Chat Server: "
    if curl -s http://localhost:8080/health | grep -q "healthy"; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi
    
    # Test crypto service
    echo -n "  Crypto Service: "
    if curl -s http://localhost:8081/health | grep -q "healthy"; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi
    
    # Test ML service
    echo -n "  ML Service: "
    if curl -s http://localhost:8082/health | grep -q "healthy"; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi
    
    # Test sentiment analysis
    echo -n "  Sentiment API: "
    result=$(curl -s -X POST http://localhost:8082/analyze \
        -H "Content-Type: application/json" \
        -d '{"text":"I love this project!"}')
    
    if echo "$result" | grep -q "positive"; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi
    
    # Test crypto signing
    echo -n "  Crypto Sign API: "
    result=$(curl -s -X POST http://localhost:8081/sign \
        -H "Content-Type: application/json" \
        -d '{"user_id":"test","message":"hello"}')
    
    if echo "$result" | grep -q "signature"; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}✅ Integration tests complete${NC}"
}

# Main
case "${1:-}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        start_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    build)
        build_images
        ;;
    clean)
        clean_all
        ;;
    k8s)
        deploy_k8s
        ;;
    test)
        run_tests
        ;;
    *)
        usage
        exit 1
        ;;
esac
