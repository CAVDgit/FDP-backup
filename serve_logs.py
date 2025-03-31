import os
import time
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, unquote
from collections import defaultdict
from croniter import croniter
from datetime import datetime

BACKUP_DIR = os.environ.get("LOG_SERVER_DIR", "/app/backup")
CRON_FILE = "/etc/cron.d/fdp-cron"
FDP_FILE = "/app/config/fdp_urls.txt"
PORT = int(os.environ.get("LOG_SERVER_PORT", 8080))

TEMPLATE_PATH = "/app/dashboard.html"

last_backup_status = ""

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.render_dashboard()
        elif self.path.endswith(".zip") or self.path.endswith(".log"):
            self.serve_file(self.path.lstrip("/"))
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        global last_backup_status

        length = int(self.headers.get('Content-Length'))
        body = self.rfile.read(length).decode('utf-8')
        data = parse_qs(body)

        if self.path == "/add-fdp":
            new_url = data.get("new_url", [""])[0].strip()
            if new_url:
                with open(FDP_FILE, "a") as f:
                    f.write(new_url + "\n")

        elif self.path == "/delete-fdp":
            delete_url = data.get("delete_url", [""])[0].strip()
            if delete_url:
                with open(FDP_FILE, "r") as f:
                    lines = f.readlines()
                with open(FDP_FILE, "w") as f:
                    for line in lines:
                        if line.strip() != delete_url:
                            f.write(line)

        elif self.path == "/add-cron":
            expr = data.get("cron_expr", [""])[0].strip()
            if expr:
                with open(CRON_FILE, "a") as f:
                    f.write(expr + "\n")
                os.system(f"crontab {CRON_FILE}")

        elif self.path == "/delete-cron":
            expr = data.get("cron_expr", [""])[0].strip()
            if expr:
                with open(CRON_FILE, "r") as f:
                    lines = f.readlines()
                with open(CRON_FILE, "w") as f:
                    for line in lines:
                        if line.strip() != expr:
                            f.write(line)
                os.system(f"crontab {CRON_FILE}")

        elif self.path == "/run-backup":
            try:
                output = subprocess.check_output(["python", "/app/fdp_backup.py"], stderr=subprocess.STDOUT)
                last_backup_status = output.decode("utf-8")[-500:]  # Store the last part
            except subprocess.CalledProcessError as e:
                last_backup_status = f"❌ Backup failed:\n{e.output.decode('utf-8')}"

        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

    def render_dashboard(self):
        try:
            with open(TEMPLATE_PATH, "r") as f:
                template = f.read()
        except:
            self.send_error(500, "Template not found")
            return

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        fdp_urls = self.read_lines(FDP_FILE)
        cron_jobs = self.parse_cron()
        logs = self.parse_logs()
        zip_files = sorted(f for f in os.listdir(BACKUP_DIR) if f.endswith(".zip"))

        html = template.replace("{{ timestamp }}", timestamp)

        if last_backup_status:
            html = html.replace("</header>", f"<p><strong>Last Backup Output:</strong><br><pre>{last_backup_status}</pre></p></header>")

        html = html.replace("{% for url in fdp_urls %}\n        <li>{{ url }}\n          <form method=\"post\" action=\"/delete-fdp\" style=\"display:inline\">\n            <input type=\"hidden\" name=\"delete_url\" value=\"{{ url }}\">\n            <button type=\"submit\">Delete</button>\n          </form>\n        </li>\n      {% endfor %}",
                            "\n".join([
                                f"<li>{url} <form method='post' action='/delete-fdp' onsubmit=\"return confirm('Delete {url}?');\" style='display:inline'><input type='hidden' name='delete_url' value='{url}'><button type='submit'>Delete</button></form></li>"
                                for url in fdp_urls]))

        cron_block = "\n".join([
            f"<li>{job['expression']} — Next: {job['next_run']}<form method='post' action='/delete-cron' style='display:inline'>"
            f"<input type='hidden' name='cron_expr' value='{job['expression']}'><button type='submit'>Delete</button></form></li>"
            for job in cron_jobs
        ])
        html = html.replace("{% for job in cron_jobs %}\n        <li>{{ job.expression }} — Next: {{ job.next_run }}", cron_block)

        log_block = "\n".join([
            f"<h3>{fdp}</h3><ul>" + "\n".join([f"<li class='log-success'>{entry}</li>" for entry in entries]) + "</ul>"
            for fdp, entries in logs.items()
        ])
        html = html.replace("{% for fdp, entries in logs.items() %}\n      <h3>{{ fdp }}</h3>\n      <ul>", log_block)

        zip_block = "\n".join([f"<li><a href='/{zipf}'>{zipf}</a></li>" for zipf in zip_files])
        html = html.replace("{% for zipf in zip_files %}\n        <li><a href=\"/{{ zipf }}\">{{ zipf }}</a></li>\n      {% endfor %}", zip_block)

        self._respond(200, html, "text/html")

    def serve_file(self, filename):
        path = os.path.join(BACKUP_DIR, filename)
        if not os.path.exists(path):
            self.send_error(404, "File Not Found")
            return
        with open(path, "rb") as f:
            self._respond(200, f.read(), "application/octet-stream", is_bytes=True)

    def parse_logs(self):
        status_logs = [f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_status") and f.endswith(".log")]
        if not status_logs:
            return {}
        status_logs.sort(reverse=True)
        entries_by_fdp = defaultdict(list)
        with open(os.path.join(BACKUP_DIR, status_logs[0]), "r") as f:
            for line in reversed(f.readlines()):
                parts = line.strip().split(" | ")
                if len(parts) == 3 and parts[1].startswith("✅"):
                    ts, _, fdp_info = parts
                    fdp_host, zip_name = fdp_info.split(" | ")
                    entries_by_fdp[fdp_host].append(f"✅ {ts} – {zip_name}")
        for k in entries_by_fdp:
            entries_by_fdp[k] = entries_by_fdp[k][:5]
        return entries_by_fdp

    def parse_cron(self):
        jobs = []
        now = datetime.now()
        with open(CRON_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    parts = line.split()
                    expr = " ".join(parts[:5])
                    next_run = croniter(expr, now).get_next(datetime).strftime('%Y-%m-%d %H:%M')
                    jobs.append({"expression": line, "next_run": next_run})
                except:
                    continue
        return jobs

    def read_lines(self, filepath):
        if not os.path.exists(filepath):
            return []
        with open(filepath, "r") as f:
            return [line.strip() for line in f if line.strip()]

    def _respond(self, code, content, content_type="text/html", is_bytes=False):
        self.send_response(code)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if not is_bytes else ""))
        self.end_headers()
        self.wfile.write(content if is_bytes else content.encode("utf-8"))

if __name__ == "__main__":
    print(f"🚀 Serving dashboard on http://0.0.0.0:{PORT}")
    HTTPServer(("", PORT), DashboardHandler).serve_forever()
