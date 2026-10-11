"""Private, authenticated companion API for native cards and Assist."""

from http.server import BaseHTTPRequestHandler
import json

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
        if self.path not in ("/v1/status", "/v1/dashboard", "/v1/message-options"):
            self.send(404, {"message": "That Assist action is not supported."})
            return
        try:
            if self.path == "/v1/dashboard":
                result = self.assistant.app.dashboard.status()
            elif self.path == "/v1/message-options":
                from copy import deepcopy
                with self.assistant.app.lock:
                    result = deepcopy(self.assistant.app.messages.options)
            else:
                result = self.assistant.status()
            self.send(200, result)
        except (UserError, OSError, ValueError, TypeError, KeyError):
            self.send(503, {"message": "Pi status could not be read.", "action": "Keep the Pi powered and check the app's Setup page."})

    def do_POST(self):
        if not self.allowed():
            return
        if self.path not in ("/v1/request", "/v1/keep-awake", "/v1/dashboard/ready", "/v1/dashboard/action"):
            self.send(404, {"message": "That Assist action is not supported."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= 4096 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError()
            self.connection.settimeout(5)
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError()
            if self.path == "/v1/dashboard/ready":
                result = self.assistant.app.dashboard.ready(value)
            elif self.path == "/v1/dashboard/action":
                if set(value) != {"action", "payload"} or not isinstance(value["action"], str):
                    raise ValueError()
                result = self.assistant.app.dashboard.action(value["action"], value["payload"])
            else:
                result = self.assistant.request(value) if self.path == "/v1/request" else self.assistant.keep_awake(value)
            self.send(200, result)
        except UserError as error:
            self.send(409, {"message": error.message, "action": error.action})
        except (OSError, ValueError, TypeError, KeyError):
            self.send(400, {"message": "The Assist request could not be read.", "action": "Clarify the request and try again."})
