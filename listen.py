import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
load_dotenv()


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Rank Tracker Bot is running!")

    def log_message(self, format, *args):
        pass  # suppress access logs


def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


if __name__ == "__main__":
    # Start health check server in background thread
    thread = threading.Thread(target=run_health_server, daemon=True)
    thread.start()
    print(f"✅ Health server running on port {os.environ.get('PORT', 8080)}")

    # Start bot (blocks main thread)
    from src.bot_listener import run_bot
    run_bot()