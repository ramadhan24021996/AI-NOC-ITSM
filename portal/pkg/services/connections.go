// Package services menyediakan shared connection management untuk
// Database (GORM), Redis, dan NATS yang digunakan oleh portal handlers.
// Memisahkan connection lifecycle dari business logic.
package services

import (
	"context"
	"fmt"
	"os"
	"sync"
	"time"

	"github.com/go-redis/redis/v8"
	nats "github.com/nats-io/nats.go"
	"gorm.io/gorm"

	"go_incident_analysis/SERVER/go_core/config"
	"go_incident_analysis/SERVER/go_core/database"
)

// PortalServices menyimpan semua shared connection untuk portal.
type PortalServices struct {
	DB    *gorm.DB
	Redis *redis.Client
	NATS  *nats.Conn
	Cfg   *config.Config
	Ctx   context.Context
	mu    sync.RWMutex
}

var (
	instance *PortalServices
	once     sync.Once
)

// Init menginisialisasi semua service connections.
// Dipanggil sekali di main() dan hasilnya dishare ke seluruh handler.
func Init() (*PortalServices, error) {
	var initErr error
	once.Do(func() {
		cfg, err := config.GetConfig()
		if err != nil {
			initErr = fmt.Errorf("[SERVICES] config load failed: %w", err)
			return
		}

		dbConn, err := database.InitDatabase()
		if err != nil {
			initErr = fmt.Errorf("[SERVICES] database init failed: %w", err)
			return
		}

		redisHost := os.Getenv("REDIS_HOST")
		if redisHost == "" {
			redisHost = "redis"
		}
		redisPort := os.Getenv("REDIS_PORT")
		if redisPort == "" {
			redisPort = "6379"
		}

		rc := redis.NewClient(&redis.Options{
			Addr:     redisHost + ":" + redisPort,
			Password: cfg.RedisPass,
		})

		instance = &PortalServices{
			DB:    dbConn,
			Redis: rc,
			Cfg:   cfg,
			Ctx:   context.Background(),
		}
		fmt.Println("[SERVICES] DB, Redis initialized OK")
	})

	if initErr != nil {
		return nil, initErr
	}
	return instance, nil
}

// Get mengembalikan instance PortalServices yang sudah diinisialisasi.
// Panic jika Init() belum dipanggil.
func Get() *PortalServices {
	if instance == nil {
		panic("[SERVICES] Init() belum dipanggil sebelum Get()")
	}
	return instance
}

// ConnectNATS menghubungkan portal ke NATS server dan menyimpan koneksi.
func (s *PortalServices) ConnectNATS(natsURL, token string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	opts := []nats.Option{
		nats.Token(token),
		nats.Timeout(10 * time.Second),
		nats.ReconnectWait(5 * time.Second),
		nats.MaxReconnects(-1),
		nats.DisconnectErrHandler(func(nc *nats.Conn, err error) {
			fmt.Printf("[NATS] Disconnected: %v\n", err)
		}),
		nats.ReconnectHandler(func(nc *nats.Conn) {
			fmt.Printf("[NATS] Reconnected to %s\n", nc.ConnectedUrl())
		}),
	}

	nc, err := nats.Connect(natsURL, opts...)
	if err != nil {
		return fmt.Errorf("[SERVICES] NATS connect failed: %w", err)
	}

	s.NATS = nc
	fmt.Printf("[SERVICES] NATS connected: %s\n", natsURL)
	return nil
}

// HealthCheck memverifikasi status semua koneksi.
func (s *PortalServices) HealthCheck() map[string]string {
	status := map[string]string{}

	// DB check
	sqlDB, err := s.DB.DB()
	if err == nil && sqlDB.Ping() == nil {
		status["database"] = "ok"
	} else {
		status["database"] = "error"
	}

	// Redis check
	if _, err := s.Redis.Ping(s.Ctx).Result(); err == nil {
		status["redis"] = "ok"
	} else {
		status["redis"] = "error"
	}

	// NATS check
	if s.NATS != nil && s.NATS.IsConnected() {
		status["nats"] = "ok"
	} else {
		status["nats"] = "disconnected"
	}

	return status
}
