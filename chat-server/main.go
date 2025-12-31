// Project Chimera - Enterprise Chat Server
// High-performance WebSocket server with security, rate limiting, and NATS integration

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/gorilla/websocket"
	"github.com/nats-io/nats.go"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"golang.org/x/time/rate"
)

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

type Config struct {
	Port           string
	NatsURL        string
	RedisURL       string
	MaxConnections int
	RateLimit      float64
	RateBurst      int
}

func LoadConfig() *Config {
	return &Config{
		Port:           getEnv("PORT", "8080"),
		NatsURL:        getEnv("NATS_URL", "nats://localhost:4222"),
		RedisURL:       getEnv("REDIS_URL", "redis://localhost:6379"),
		MaxConnections: 10000,
		RateLimit:      10.0, // 10 requests per second
		RateBurst:      20,
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// ═══════════════════════════════════════════════════════════════
// PROMETHEUS METRICS
// ═══════════════════════════════════════════════════════════════

var (
	connectionsTotal = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "chimera_connections_total",
		Help: "Total active WebSocket connections",
	})
	messagesTotal = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "chimera_messages_total",
		Help: "Total messages processed",
	}, []string{"type", "status"})
	messageLatency = prometheus.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "chimera_message_latency_seconds",
		Help:    "Message processing latency",
		Buckets: prometheus.DefBuckets,
	}, []string{"type"})
	rateLimitHits = prometheus.NewCounter(prometheus.CounterOpts{
		Name: "chimera_rate_limit_hits_total",
		Help: "Total rate limit rejections",
	})
	circuitBreakerState = prometheus.NewGaugeVec(prometheus.GaugeOpts{
		Name: "chimera_circuit_breaker_state",
		Help: "Circuit breaker state (0=closed, 1=open, 2=half-open)",
	}, []string{"service"})
)

func init() {
	prometheus.MustRegister(connectionsTotal)
	prometheus.MustRegister(messagesTotal)
	prometheus.MustRegister(messageLatency)
	prometheus.MustRegister(rateLimitHits)
	prometheus.MustRegister(circuitBreakerState)
}

// ═══════════════════════════════════════════════════════════════
// MESSAGE TYPES
// ═══════════════════════════════════════════════════════════════

type Message struct {
	ID        string    `json:"id"`
	Type      string    `json:"type"`
	UserID    string    `json:"user_id"`
	Username  string    `json:"username"`
	Content   string    `json:"content"`
	Timestamp time.Time `json:"timestamp"`
	Encrypted bool      `json:"encrypted,omitempty"`
	Signature string    `json:"signature,omitempty"`
	Sentiment float64   `json:"sentiment,omitempty"`
}

type UserPresence struct {
	UserID    string    `json:"user_id"`
	Username  string    `json:"username"`
	Status    string    `json:"status"` // online, away, offline
	LastSeen  time.Time `json:"last_seen"`
	ConnCount int       `json:"conn_count"`
}

// ═══════════════════════════════════════════════════════════════
// CLIENT
// ═══════════════════════════════════════════════════════════════

type Client struct {
	hub      *Hub
	conn     *websocket.Conn
	send     chan []byte
	userID   string
	username string
	limiter  *rate.Limiter
	mu       sync.RWMutex
}

func (c *Client) readPump() {
	defer func() {
		c.hub.unregister <- c
		c.conn.Close()
	}()

	c.conn.SetReadLimit(65536) // 64KB max message
	c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

	for {
		_, data, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				log.Printf("Read error: %v", err)
			}
			break
		}

		// Rate limiting
		if !c.limiter.Allow() {
			rateLimitHits.Inc()
			c.send <- []byte(`{"error":"RATE_LIMITED","message":"Too many requests"}`)
			continue
		}

		// Parse and process message
		var msg Message
		if err := json.Unmarshal(data, &msg); err != nil {
			c.send <- []byte(`{"error":"INVALID_JSON"}`)
			continue
		}

		msg.UserID = c.userID
		msg.Username = c.username
		msg.Timestamp = time.Now()

		c.hub.broadcast <- &msg
	}
}

func (c *Client) writePump() {
	ticker := time.NewTicker(30 * time.Second)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()

	for {
		select {
		case message, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if !ok {
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			w, err := c.conn.NextWriter(websocket.TextMessage)
			if err != nil {
				return
			}
			w.Write(message)
			w.Close()

		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

// ═══════════════════════════════════════════════════════════════
// HUB (CONNECTION MANAGER)
// ═══════════════════════════════════════════════════════════════

type Hub struct {
	clients    map[*Client]bool
	broadcast  chan *Message
	register   chan *Client
	unregister chan *Client
	nats       *nats.Conn
	history    []*Message
	historyMu  sync.RWMutex
	config     *Config
	mu         sync.RWMutex
}

func NewHub(config *Config) *Hub {
	return &Hub{
		clients:    make(map[*Client]bool),
		broadcast:  make(chan *Message, 256),
		register:   make(chan *Client),
		unregister: make(chan *Client),
		history:    make([]*Message, 0, 100),
		config:     config,
	}
}

func (h *Hub) ConnectNATS() error {
	nc, err := nats.Connect(h.config.NatsURL,
		nats.RetryOnFailedConnect(true),
		nats.MaxReconnects(10),
		nats.ReconnectWait(time.Second),
	)
	if err != nil {
		return fmt.Errorf("NATS connection failed: %w", err)
	}
	h.nats = nc
	log.Printf("✅ Connected to NATS: %s", h.config.NatsURL)

	// Subscribe to broadcast channel
	nc.Subscribe("chimera.broadcast", func(m *nats.Msg) {
		var msg Message
		if err := json.Unmarshal(m.Data, &msg); err == nil {
			h.broadcastToClients(&msg)
		}
	})

	return nil
}

func (h *Hub) Run() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = true
			h.mu.Unlock()

			connectionsTotal.Set(float64(len(h.clients)))
			log.Printf("Client connected: %s (total: %d)", client.username, len(h.clients))

			// Send history
			h.historyMu.RLock()
			for _, msg := range h.history {
				data, _ := json.Marshal(msg)
				client.send <- data
			}
			h.historyMu.RUnlock()

		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send)
			}
			h.mu.Unlock()

			connectionsTotal.Set(float64(len(h.clients)))
			log.Printf("Client disconnected: %s (total: %d)", client.username, len(h.clients))

		case msg := <-h.broadcast:
			start := time.Now()

			// Store in history
			h.historyMu.Lock()
			if len(h.history) >= 100 {
				h.history = h.history[1:]
			}
			h.history = append(h.history, msg)
			h.historyMu.Unlock()

			// Publish to NATS for cross-server broadcast
			if h.nats != nil {
				data, _ := json.Marshal(msg)
				h.nats.Publish("chimera.broadcast", data)
				h.nats.Publish("chimera.sentiment", data) // For ML service
			}

			h.broadcastToClients(msg)

			messagesTotal.WithLabelValues(msg.Type, "success").Inc()
			messageLatency.WithLabelValues(msg.Type).Observe(time.Since(start).Seconds())

		case <-ticker.C:
			// Health maintenance
			h.mu.RLock()
			count := len(h.clients)
			h.mu.RUnlock()
			log.Printf("Health: %d active connections", count)
		}
	}
}

func (h *Hub) broadcastToClients(msg *Message) {
	data, err := json.Marshal(msg)
	if err != nil {
		return
	}

	h.mu.RLock()
	defer h.mu.RUnlock()

	for client := range h.clients {
		select {
		case client.send <- data:
		default:
			close(client.send)
			delete(h.clients, client)
		}
	}
}

// ═══════════════════════════════════════════════════════════════
// HTTP HANDLERS
// ═══════════════════════════════════════════════════════════════

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		// TODO: Implement proper CORS checking
		return true
	},
}

func serveWs(hub *Hub, w http.ResponseWriter, r *http.Request) {
	// Check connection limit
	hub.mu.RLock()
	if len(hub.clients) >= hub.config.MaxConnections {
		hub.mu.RUnlock()
		http.Error(w, "Connection limit reached", http.StatusServiceUnavailable)
		return
	}
	hub.mu.RUnlock()

	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("Upgrade error: %v", err)
		return
	}

	// Extract user info from query params (in prod, use JWT)
	userID := r.URL.Query().Get("user_id")
	username := r.URL.Query().Get("username")
	if userID == "" {
		userID = fmt.Sprintf("anon_%d", time.Now().UnixNano())
	}
	if username == "" {
		username = "Anonymous"
	}

	client := &Client{
		hub:      hub,
		conn:     conn,
		send:     make(chan []byte, 256),
		userID:   userID,
		username: username,
		limiter:  rate.NewLimiter(rate.Limit(hub.config.RateLimit), hub.config.RateBurst),
	}

	hub.register <- client

	go client.writePump()
	go client.readPump()
}

func healthHandler(hub *Hub) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		hub.mu.RLock()
		count := len(hub.clients)
		hub.mu.RUnlock()

		status := map[string]interface{}{
			"status":      "healthy",
			"connections": count,
			"timestamp":   time.Now().UTC(),
			"nats":        hub.nats != nil && hub.nats.IsConnected(),
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(status)
	}
}

func statsHandler(hub *Hub) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		hub.mu.RLock()
		count := len(hub.clients)
		hub.mu.RUnlock()

		hub.historyMu.RLock()
		historyLen := len(hub.history)
		hub.historyMu.RUnlock()

		stats := map[string]interface{}{
			"active_connections": count,
			"max_connections":    hub.config.MaxConnections,
			"message_history":    historyLen,
			"nats_connected":     hub.nats != nil && hub.nats.IsConnected(),
			"uptime":             time.Since(startTime).String(),
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(stats)
	}
}

var startTime = time.Now()

// ═══════════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════════

func main() {
	config := LoadConfig()

	log.Println("═══════════════════════════════════════════════════")
	log.Println("  🔥 PROJECT CHIMERA - Chat Server v1.0")
	log.Println("═══════════════════════════════════════════════════")

	hub := NewHub(config)

	// Connect to NATS (non-blocking)
	go func() {
		for i := 0; i < 5; i++ {
			if err := hub.ConnectNATS(); err != nil {
				log.Printf("NATS connection attempt %d failed: %v", i+1, err)
				time.Sleep(2 * time.Second)
				continue
			}
			break
		}
	}()

	go hub.Run()

	// HTTP routes
	http.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		serveWs(hub, w, r)
	})
	http.HandleFunc("/health", healthHandler(hub))
	http.HandleFunc("/stats", statsHandler(hub))
	http.Handle("/metrics", promhttp.Handler())

	// Graceful shutdown
	server := &http.Server{
		Addr:         ":" + config.Port,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	go func() {
		log.Printf("🚀 Server starting on :%s", config.Port)
		log.Printf("   WebSocket: ws://localhost:%s/ws", config.Port)
		log.Printf("   Metrics:   http://localhost:%s/metrics", config.Port)
		log.Printf("   Health:    http://localhost:%s/health", config.Port)

		if err := server.ListenAndServe(); err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	// Wait for shutdown signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if hub.nats != nil {
		hub.nats.Close()
	}

	server.Shutdown(ctx)
	log.Println("Server stopped")
}
