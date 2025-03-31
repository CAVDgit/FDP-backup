import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote
import time

LOG_DIR = os.environ.get("LOG_SERVER_DIR", "/app/backup")
PORT = int(os.environ.get("LOG_SERVER_PORT", 8080))

class LogViewerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = unquote(self.path)
        if path == "/" or path == "/index.html":
            self._serve_index()
        elif path.endswith(".log") or path.endswith(".zip"):
            self._serve_file(path.lstrip("/"))
        else:
            self.send_error(404, "File Not Found")

    def _serve_index(self):
        files = os.listdir(LOG_DIR)
        log_files = sorted(f for f in files if f.endswith(".log"))
        zip_files = sorted(f for f in files if f.endswith(".zip"))

        html = "<html><head><title>FDP Backups</title>"
        html += '<meta http-equiv="refresh" content="10">'  # Auto-refresh every 10s
        html += "</head><body>"
        html += "<h1>📦 FDP Backup Viewer</h1>"

        html += "<h2>📝 Logs</h2><ul>"
        for log in log_files:
            html += f'<li><a href="/{log}">{log}</a></li>'
        html += "</ul>"

        html += "<h2>🗜️ Backup Archives</h2><ul>"
        for zipf in zip_files:
            html += f'<li><a href="/{zipf}">{zipf}</a></li>'
        html += "</ul>"

        html += f"<p>Last refreshed: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>"
        html += "</body></html>"

        self._respond(200, html, content_type="text/html")

    def _serve_file(self, filename):
        file_path = os.path.join(LOG_DIR, filename)
        if not os.path.exists(file_path):
            self.send_error(404, "File Not Found")
            return

        content_type = "application/octet-stream"
        if filename.endswith(".log"):
            content_type = "text/plain"

        with open(file_path, "rb") as f:
            content = f.read()
            self._respond(200, content, content_type=content_type, is_bytes=True)

    def _respond(self, status_code, content, content_type="text/html", is_bytes=False):
        self.send_response(status_code)
        if not is_bytes and content_type == "text/html":
            content_type += "; charset=utf-8"
        self.send_header("Content-Type", content_type)
        self.end_headers()
        if is_bytes:
            self.wfile.write(content)
        else:
            self.wfile.write(content.encode("utf-8"))


# Start the server
if __name__ == "__main__":
    print(f"📡 Log server running at http://localhost:{PORT}")
    server = HTTPServer(("", PORT), LogViewerHandler)
    server.serve_forever()
