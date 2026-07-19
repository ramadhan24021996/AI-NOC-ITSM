package logger

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"time"

	"go_incident_analysis/SERVER/go_core/security"
)

// LogLevel defines log severity
type LogLevel string

const (
	LevelDebug LogLevel = "DEBUG"
	LevelInfo  LogLevel = "INFO"
	LevelWarn  LogLevel = "WARN"
	LevelError LogLevel = "ERROR"
)

// LogEntry represents a single JSON structured log
type LogEntry struct {
	Timestamp string                 `json:"timestamp"`
	Level     LogLevel               `json:"level"`
	Caller    string                 `json:"caller"`
	Message   string                 `json:"message"`
	Fields    map[string]interface{} `json:"fields,omitempty"`
}

// Logger encapsulates output writers
type Logger struct {
	writer io.Writer
}

var defaultLogger *Logger

// InitLogger initializes logging output to console and file
func InitLogger() (*Logger, error) {
	if defaultLogger != nil {
		return defaultLogger, nil
	}

	// Determine log file location dynamically
	_, filename, _, _ := runtime.Caller(0)
	projectRoot := filepath.Dir(filepath.Dir(filepath.Dir(filename)))
	logDir := filepath.Join(projectRoot, "logs")
	_ = os.MkdirAll(logDir, 0755)

	logFilePath := filepath.Join(logDir, "go_system.log")
	logFile, err := os.OpenFile(logFilePath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
	if err != nil {
		return nil, fmt.Errorf("failed to open log file %s: %w", logFilePath, err)
	}

	// Write to both console and file
	multiWriter := io.MultiWriter(os.Stdout, logFile)
	defaultLogger = &Logger{writer: multiWriter}

	return defaultLogger, nil
}

// Log writes structured log after PII redaction
func (l *Logger) Log(level LogLevel, message string, fields map[string]interface{}) {
	masker := security.Masker()

	// Mask PII in message and text fields
	maskedMsg := masker.Redact(message)
	maskedFields := make(map[string]interface{})
	for k, v := range fields {
		if strVal, ok := v.(string); ok {
			maskedFields[k] = masker.Redact(strVal)
		} else {
			maskedFields[k] = v
		}
	}

	// Get caller file/line info
	callerStr := "unknown"
	if _, file, line, ok := runtime.Caller(2); ok {
		callerStr = fmt.Sprintf("%s:%d", filepath.Base(file), line)
	}

	entry := LogEntry{
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Level:     level,
		Caller:    callerStr,
		Message:   maskedMsg,
		Fields:    maskedFields,
	}

	jsonBytes, err := json.Marshal(entry)
	if err != nil {
		// Fallback simple format if json marshaling fails
		_, _ = fmt.Fprintf(l.writer, "[%s] [%s] [%s] %s\n", entry.Timestamp, level, callerStr, maskedMsg)
		return
	}

	_, _ = l.writer.Write(append(jsonBytes, '\n'))
}

// Debug logs a debug message
func (l *Logger) Debug(message string, fields map[string]interface{}) {
	l.Log(LevelDebug, message, fields)
}

// Info logs an informational message
func (l *Logger) Info(message string, fields map[string]interface{}) {
	l.Log(LevelInfo, message, fields)
}

// Warn logs a warning message
func (l *Logger) Warn(message string, fields map[string]interface{}) {
	l.Log(LevelWarn, message, fields)
}

// Error logs an error message
func (l *Logger) Error(message string, fields map[string]interface{}) {
	l.Log(LevelError, message, fields)
}

// Global logger helper functions for easy logging without explicit instance
func Debug(message string, fields map[string]interface{}) {
	if defaultLogger == nil {
		_, _ = InitLogger()
	}
	defaultLogger.Debug(message, fields)
}

func Info(message string, fields map[string]interface{}) {
	if defaultLogger == nil {
		_, _ = InitLogger()
	}
	defaultLogger.Info(message, fields)
}

func Warn(message string, fields map[string]interface{}) {
	if defaultLogger == nil {
		_, _ = InitLogger()
	}
	defaultLogger.Warn(message, fields)
}

func Error(message string, fields map[string]interface{}) {
	if defaultLogger == nil {
		_, _ = InitLogger()
	}
	defaultLogger.Error(message, fields)
}
