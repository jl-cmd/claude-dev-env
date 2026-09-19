from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 47613


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        is_health = self.path == "/health"
        self.send_response(200 if is_health else 404)
        self.end_headers()
        self.wfile.write(b"ok" if is_health else b"not found")


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
