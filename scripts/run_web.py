"""Serve the static MindBridge Chess web level selector."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    handler = partial(SimpleHTTPRequestHandler, directory=str(repo_root))
    server = ThreadingHTTPServer(("127.0.0.1", 8000), handler)
    print("Serving MindBridge web UI at http://127.0.0.1:8000/web/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web server.")


if __name__ == "__main__":
    main()
