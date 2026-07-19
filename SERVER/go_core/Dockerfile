FROM golang:1.26-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /app/ingestion_server SERVER/go_core/main.go

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /app
COPY --from=builder /app/ingestion_server .
COPY --from=builder /app/CLIENT_DISTRIBUSI_GO /app/CLIENT_DISTRIBUSI_GO
EXPOSE 18800 18802 19999
CMD ["./ingestion_server"]
