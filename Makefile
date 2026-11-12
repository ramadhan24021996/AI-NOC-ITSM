.PHONY: all setup build build-server build-agents up down test clean

BINARY_DIR := build/bin

all: build

setup:
	@chmod +x scripts/bootstrap.sh
	@./scripts/bootstrap.sh

build: build-server

build-server:
	@mkdir -p $(BINARY_DIR)
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o $(BINARY_DIR)/ingestion_server ./SERVER/go_core
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o $(BINARY_DIR)/portal ./portal
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o $(BINARY_DIR)/secure_relay ./portal/relay

build-agents:
	@mkdir -p $(BINARY_DIR)
	CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o $(BINARY_DIR)/agent.exe ./CLIENT_DISTRIBUSI_GO/agent
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o $(BINARY_DIR)/osi-agent ./CLIENT_DISTRIBUSI_GO/linux_agent

up: build-server
	docker compose up -d

down:
	docker compose down

test:
	PYTHONPATH=.:SERVER/python_ai_core pytest tests/unit/ -v
	PYTHONPATH=SERVER/python_ai_core python3 SERVER/python_ai_core/tests/test_phase40b_event_loop_wrapper.py

clean:
	rm -rf $(BINARY_DIR)/*
