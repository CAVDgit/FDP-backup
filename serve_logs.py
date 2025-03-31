import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote
import time
from collections import defaultdict

LOG_DIR = os.environ.get("LOG_SERVER_DIR", "/app/backup")
PORT = int(os.environ.get("LOG_SERVER_PORT", 8080))

STATUS_LOG_FILE = None
for fname in sorted(os.listdir(LOG_DIR), reverse=True):
    if fname.startswith("backup_status") and fname.endswith(".log"):
        STATUS_LOG_FILE = fname
        break

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
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        logs = parse_status_log(os.path.join(LOG_DIR, STATUS_LOG_FILE)) if STATUS_LOG_FILE else {}
        zip_files = sorted(f for f in os.listdir(LOG_DIR) if f.endswith(".zip"))

        html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <title>FDP Backup Viewer</title>
  <meta http-equiv=\"refresh\" content=\"30\">
  <style>
    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f9f9f9; color: #333; margin: 0; padding: 2rem; }}
    header {{ border-bottom: 2px solid #ddd; margin-bottom: 2rem; }}
    h1 {{ margin: 0; font-size: 2rem; color: #2c3e50; }}
    h2, h3 {{ color: #34495e; }}
    ul {{ list-style-type: none; padding-left: 0; }}
    li {{ background: #fff; margin-bottom: 0.5rem; padding: 0.5rem 1rem; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
    .log-success {{ color: #27ae60; }}
    .log-error {{ color: #c0392b; }}
    .section {{ margin-bottom: 2rem; }}
    .timestamp {{ font-size: 0.9rem; color: #7f8c8d; }}
    footer {{ border-top: 1px solid #ddd; padding-top: 1rem; font-size: 0.8rem; color: #999; }}
    a {{ text-decoration: none; color: #2980b9; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <header>
    <h1>📦 FDP Backup Viewer</h1>
    <p class=\"timestamp\">Last refreshed: {timestamp}</p>
  </header>
  <section class=\"section\">
    <h2>📝 Latest Logs</h2>
"""
        if logs:
            for fdp, entries in logs.items():
                html += f"<div class=\"log-block\"><h3>{fdp}</h3><ul>"
                for entry in entries:
                    html += f"<li class=\"log-success\">{entry}</li>"
                html += "</ul></div>"
        else:
            html += "<p>No logs found.</p>"

        html += "<h2>🗜️ Backup Archives</h2><ul>"
        for zipf in zip_files:
            html += f'<li><a href="/{zipf}">{zipf}</a></li>'
        html += f"</ul><footer>FDP Backup Viewer | Auto-refreshes every 30 seconds</footer></section></body></html>"

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

def parse_status_log(log_path):
    entries_by_fdp = defaultdict(list)
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
        for line in reversed(lines):
            parts = line.strip().split(" | ")
            if len(parts) == 3 and parts[1].startswith("✅"):
                timestamp, status, fdp_info = parts
                fdp_host, zip_name = fdp_info.split(" | ")
                entries_by_fdp[fdp_host].append(f"✅ {timestamp} – {zip_name}")
        for k in entries_by_fdp:
            entries_by_fdp[k] = entries_by_fdp[k][:5]
    except Exception as e:
        print(f"Error parsing status log: {e}")
    return entries_by_fdp

if __name__ == "__main__":
    print(f"📡 Log server running at http://0.0.0.0:{PORT}")
    server = HTTPServer(("", PORT), LogViewerHandler)
    server.serve_forever()
