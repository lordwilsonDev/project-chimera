# 🔥 PROJECT CHIMERA - Enterprise Distributed Chat System

## Quick Start

```bash
# Start everything
~/chimera start

# Check status
~/chimera status

# View logs
~/chimera logs

# Stop
~/chimera stop
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      NGINX (Port 80)                        │
│           Load Balancing + Rate Limiting + CORS             │
└────────────────┬──────────────┬──────────────┬──────────────┘
                 │              │              │
    ┌────────────▼──────┐ ┌─────▼─────┐ ┌──────▼──────┐
    │ Chat Server (Go)  │ │ Crypto    │ │ ML Service  │
    │ WebSocket :8080   │ │ (Rust)    │ │ (Python)    │
    │ 10k connections   │ │ :8081     │ │ :8082       │
    │ Rate limiting     │ │ Ed25519   │ │ VADER       │
    │ Circuit breaker   │ │ ChaCha20  │ │ TextBlob    │
    │ Prometheus        │ │ Argon2    │ │ FastAPI     │
    └────────┬──────────┘ └───────────┘ └─────────────┘
             │
    ┌────────▼─────────────────────────────────────────┐
    │               NATS (Port 4222)                   │
    │           JetStream Message Bus                  │
    └────────┬─────────────────────────────────────────┘
             │
    ┌────────▼──────────┐     ┌──────────────────────┐
    │ Redis (6379)      │     │ Prometheus + Grafana │
    │ Caching + Pub/Sub │     │ 50+ metrics          │
    └───────────────────┘     └──────────────────────┘
```

## Services

| Service | Port | Language | Purpose |
|---------|------|----------|---------|
| chat-server | 8080 | Go | WebSocket chat with rate limiting |
| crypto-service | 8081 | Rust | Ed25519, ChaCha20, Argon2 |
| ml-service | 8082 | Python | Sentiment analysis |
| nats | 4222 | - | Message bus |
| redis | 6379 | - | Caching |
| prometheus | 9090 | - | Metrics |
| grafana | 3000 | - | Dashboards |
| nginx | 80 | - | Load balancer |

## APIs

### WebSocket
```javascript
ws://localhost:80/ws?user_id=123&username=wilson
```

### Sentiment Analysis
```bash
curl -X POST http://localhost:8082/analyze \
  -H "Content-Type: application/json" \
  -d '{"text":"I love this!"}'
```

### Crypto Sign
```bash
curl -X POST http://localhost:8081/sign \
  -H "Content-Type: application/json" \
  -d '{"user_id":"wilson","message":"hello"}'
```

## Deploy to Kubernetes

```bash
~/chimera k8s
kubectl -n chimera get pods
```

## Integration with Sovereign Trinity

```bash
python scripts/sovereign_bridge.py "test message"
```
