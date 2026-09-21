#!/usr/bin/env python3
"""
PDF Workspace - Online Web Server Application
Run fully online in any browser with Google Lens OCR, visual search highlighting, and data export.
"""
import sys
import os
import argparse
import webbrowser
import threading
import time

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.web.server import create_app


def main():
    parser = argparse.ArgumentParser(description="PDF Workspace - Online Web Server Application")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--data-dir", default=None, help="Custom directory for workspace projects")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open web browser")
    args = parser.parse_args()

    app = create_app(data_dir=args.data_dir)

    url = f"http://localhost:{args.port}"
    print("\n" + "=" * 64)
    print("  📄  PDF Workspace — Fully Online Web Application")
    print("=" * 64)
    print(f"  ⚡ Web Server URL:    {url}")
    print(f"  ⚡ Network Access:    http://0.0.0.0:{args.port}")
    print(f"  ⚡ OCR Engine:        Google Lens (Online High Precision)")
    print(f"  ⚡ Data Directory:   {args.data_dir or 'Default'}")
    print("=" * 64 + "\n")

    if not args.no_browser:
        def _open():
            time.sleep(1.2)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
