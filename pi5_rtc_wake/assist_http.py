"""Private, authenticated companion API; it has no approval or firmware endpoints."""

from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlsplit

from state import UserError


class AssistHandler(BaseHTTPRequestHandler):
    assistant = None

    def log_message(self, *args):
        pass

    def send(self, status, value):
        body = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def allowed(self):
        if not self.assistant.authenticate(self.headers.get("Authorization")):
            self.send(401, {"message": "Reconnect the discovered Pi Wake & Sleep integration."})
            return False
        return True

    def do_GET(self):
        if not self.allowed():
            return
        if self.path != "/v1/status":
            self.send(404, {"message": "That Assist action is not supported."})
            return
        self.send(200, self.assistant.status())

    def do_POST(self):
        if not self.allowed():
            return
        if self.path not in ("/v1/request", "/v1/keep-awake"):
            self.send(404, {"message": "That Assist action is not supported."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= 2048 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError()
            self.connection.settimeout(5)
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError()
            result = self.assistant.request(value) if self.path == "/v1/request" else self.assistant.keep_awake(value)
            self.send(200, result)
        except UserError as error:
            self.send(409, {"message": error.message, "action": error.action})
        except (OSError, ValueError, TypeError, KeyError):
            self.send(400, {"message": "The Assist request could not be read.", "action": "Clarify the request and try again."})
