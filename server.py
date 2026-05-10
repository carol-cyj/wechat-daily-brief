#!/usr/bin/env python3
"""
Web Server - Serve brief HTML files and audio for mobile access

Usage:
    python server.py              # Start on port 8080
    python server.py --port 9000  # Custom port
"""

import sys
import os
import socket
import logging
import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)

# Default output directory
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


class BriefHTTPHandler(SimpleHTTPRequestHandler):
    """Custom handler that serves from the output directory"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=OUTPUT_DIR, **kwargs)
    
    def do_GET(self):
        # Default: redirect to latest brief
        if self.path == "/" or self.path == "":
            self.path = self._find_latest_brief()
            if not self.path:
                self.send_error(404, "No briefs found. Run main.py first.")
                return
        
        # Add CORS headers for mobile access
        self.send_header("Access-Control-Allow-Origin", "*")
        super().do_GET()
    
    def _find_latest_brief(self):
        """Find the most recent HTML brief file"""
        output_path = Path(OUTPUT_DIR)
        if not output_path.exists():
            return None
        
        html_files = sorted(output_path.glob("*.html"), key=lambda f: f.stat().st_mtime, reverse=True)
        if html_files:
            return f"/{html_files[0].name}"
        return None
    
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()
    
    def log_message(self, format, *args):
        logger.info(f"[HTTP] {args[0]}")


def get_local_ip():
    """Get the local IP address for LAN access"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def start_server(port=8080):
    """Start the web server"""
    # Ensure output directory exists
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    
    local_ip = get_local_ip()
    
    server = HTTPServer(("0.0.0.0", port), BriefHTTPHandler)
    
    print()
    print("=" * 50)
    print("  Daily Brief Web Server")
    print("=" * 50)
    print()
    print(f"  Local:   http://localhost:{port}")
    print(f"  LAN:     http://{local_ip}:{port}")
    print(f"  Output:  {OUTPUT_DIR}")
    print()
    print("  Phone access: connect to same WiFi,")
    print(f"  open http://{local_ip}:{port}")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    print()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily Brief Web Server")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port number (default: 8080)")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    start_server(args.port)
