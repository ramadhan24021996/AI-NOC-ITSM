"""
Enterprise AI OS — REST API Server (api/rest_api_server.py)

HTTP REST API Server for External System Integration.
Exposes AI Core features over REST API with Zero-Trust AuthGuard headers.
"""

import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional

from routers.api_router import ApiRouter

logger = logging.getLogger("AI_REST_SERVER")

_global_router = ApiRouter()


class RestApiHTTPHandler(BaseHTTPRequestHandler):
    """
    Standard HTTP Request Handler interfacing with ApiRouter.
    """

    def log_message(self, format, *args):
        # Suppress standard HTTP server stdout logging in favor of python logger
        logger.debug(f"[HTTP] {self.address_string()} - {format % args}")

    def _do_process(self, method: str):
        content_len = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_len) if content_len > 0 else b""

        # Convert headers to simple dict
        headers_dict = {k: v for k, v in self.headers.items()}

        code, resp_headers, resp_data = _global_router.dispatch(
            method=method,
            path=self.path,
            headers=headers_dict,
            body_bytes=body_bytes
        )

        self.send_response(code)
        for h_k, h_v in resp_headers.items():
            self.send_header(h_k, h_v)
        self.end_headers()

        self.wfile.write(json.dumps(resp_data).encode("utf-8"))

    def do_GET(self):
        self._do_process("GET")

    def do_POST(self):
        self._do_process("POST")

    def do_PUT(self):
        self._do_process("PUT")

    def do_DELETE(self):
        self._do_process("DELETE")


class RestApiServer:
    """
    HTTP REST API Server instance runner.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8088):
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        logger.info(f"[REST_SERVER] Initialized for {self.host}:{self.port}")

    def start_background(self):
        """Starts HTTP REST server in a background daemon thread."""
        self.server = HTTPServer((self.host, self.port), RestApiHTTPHandler)
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()
        logger.info(f"[REST_SERVER] Server started in background on http://{self.host}:{self.port}")

    def stop(self):
        """Stops HTTP REST server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("[REST_SERVER] Server stopped.")
