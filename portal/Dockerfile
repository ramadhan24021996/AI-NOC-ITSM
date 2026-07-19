FROM golang:1.26-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /app/dashboard_server ./portal

FROM alpine:latest
RUN apk --no-cache add ca-certificates tzdata
WORKDIR /app
COPY --from=builder /app/dashboard_server .
COPY portal/templates ./templates
COPY portal/static ./static
COPY portal/remote_settings.json ./remote_settings.json
COPY portal/ai_config.json* ./ai_config.json
EXPOSE 9999
CMD ["./dashboard_server"]
