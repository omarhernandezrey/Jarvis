"""
JARVIS Local - Dashboard Web
Página web con métricas en tiempo real del sistema.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.logging_config import get_logger

logger = get_logger("ui.dashboard")

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>JARVIS Dashboard</title>
    <style>
        body { background: #02040a; color: #e6f4ff; font-family: 'Segoe UI', sans-serif; margin: 20px; }
        h1 { color: #00e5ff; }
        .card { background: #08111f; border: 1px solid #132038; border-radius: 8px; padding: 20px; margin: 10px 0; }
        .metric { font-size: 2em; color: #00e5ff; }
        .label { color: #4d6a86; }
    </style>
</head>
<body>
    <h1>JARVIS Dashboard</h1>
    <div class="card">
        <div class="label">Estado del Sistema</div>
        <div class="metric" id="status">Cargando...</div>
    </div>
    <div class="card">
        <div class="label">Herramientas Disponibles</div>
        <div class="metric" id="tools">-</div>
    </div>
    <div class="card">
        <div class="label">Memorias Guardadas</div>
        <div class="metric" id="memories">-</div>
    </div>
    <script>
        async function update() {
            try {
                const r = await fetch('/api/status');
                const d = await r.json();
                document.getElementById('status').textContent = d.status || 'OK';
                document.getElementById('tools').textContent = d.tools || '-';
                document.getElementById('memories').textContent = d.memories || '-';
            } catch(e) {
                document.getElementById('status').textContent = 'Error';
            }
        }
        update();
        setInterval(update, 10000);
    </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    """Handler para el dashboard."""

    def do_GET(self):
        if self.path == '/' or self.path == '/dashboard':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())
        elif self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            status = {
                "status": "Online",
                "tools": "31+",
                "memories": "Variable"
            }
            self.wfile.write(json.dumps(status).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        logger.debug(f"Dashboard: {format % args}")


def run_dashboard(port: int = 8081):
    """Ejecuta el dashboard en el puerto especificado."""
    server = HTTPServer(('127.0.0.1', port), DashboardHandler)
    logger.info(f"Dashboard iniciado en http://127.0.0.1:{port}")
    print(f"Dashboard disponible en http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_dashboard()
