//go:build windows

package main

import (
	"context"
	"fmt"
	"time"

	// "github.com/chromedp/cdproto/network" // Future use for HAR
	"github.com/chromedp/cdproto/runtime"
	"github.com/chromedp/chromedp"
)

// StartV8Forensics hooks into a running Chrome instance using CDP (Chrome DevTools Protocol).
// Chrome must be started with --remote-debugging-port=9222
func StartV8Forensics() {
	fmt.Println("[V8 FORENSICS] Initializing Native CDP connection for Browser Observability...")

	// Create allocator context to connect to an existing Chrome instance on port 9222
	allocCtx, cancelAlloc := chromedp.NewRemoteAllocator(context.Background(), "ws://127.0.0.1:9222/")
	defer cancelAlloc()

	// Create context
	ctx, cancelCtx := chromedp.NewContext(allocCtx)
	defer cancelCtx()

	// Listen for CDP events
	chromedp.ListenTarget(ctx, func(ev interface{}) {
		switch ev := ev.(type) {
		case *runtime.EventExceptionThrown:
			// Capture Uncaught JavaScript Exceptions with full stack trace
			exceptionDetails := ev.ExceptionDetails
			trace := ""
			if exceptionDetails.StackTrace != nil && len(exceptionDetails.StackTrace.CallFrames) > 0 {
				frame := exceptionDetails.StackTrace.CallFrames[0]
				trace = fmt.Sprintf("Function: %s, URL: %s, Line: %d", frame.FunctionName, frame.URL, frame.LineNumber)
			}
			
			errMsg := ""
			if exceptionDetails.Exception != nil && exceptionDetails.Exception.Description != "" {
				errMsg = exceptionDetails.Exception.Description
			} else {
				errMsg = exceptionDetails.Text
			}

			fmt.Printf("[V8 EXCEPTION] JS Error Detected: %s | Trace: %s\n", errMsg, trace)

			payload := map[string]interface{}{
				"type":        "browser_issue",
				"browser":     "chrome_native",
				"issue":       "JAVASCRIPT_EXCEPTION",
				"severity":    "high",
				"url":         exceptionDetails.URL,
				"description": errMsg,
				"stack_trace": trace,
				"timestamp":   time.Now().Unix(),
				"pc_name":     agentName,
			}
			go sendHTTPEvent("/issues", payload)

		case *runtime.EventConsoleAPICalled:
			// Capture console.error() calls
			if ev.Type == "error" {
				var argsStr []string
				for _, arg := range ev.Args {
					if arg.Value != nil {
						argsStr = append(argsStr, string(arg.Value))
					} else {
						argsStr = append(argsStr, arg.Description)
					}
				}
				
				fmt.Printf("[V8 CONSOLE] Console Error: %v\n", argsStr)
				
				// Ensure we extract the raw text
				errorText := fmt.Sprintf("%v", argsStr)
				
				payload := map[string]interface{}{
					"type":             "browser_issue",
					"browser":          "chrome_native",
					"issue":            "CONSOLE_ERROR",
					"severity":         "medium",
					"description":      errorText,
					"timestamp":        time.Now().Unix(),
					"pc_name":          agentName,
				}
				go sendHTTPEvent("/issues", payload)
			}
		}
	})

	// Keep connection alive and enable runtime domain
	err := chromedp.Run(ctx, runtime.Enable())
	if err != nil {
		fmt.Printf("[V8 FORENSICS WARNING] Could not connect to Chrome Debugging Port 9222: %v\n", err)
		return
	}

	fmt.Println("[V8 FORENSICS] Connected and listening for JS exceptions and console errors.")
	
	// Block forever while listening
	select {}
}
