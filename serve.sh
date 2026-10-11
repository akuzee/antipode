#!/bin/sh
# Serve Antipode over HTTPS on your LAN so a phone can use it.
# (iOS Safari and Android Chrome only expose motion sensors + camera on HTTPS.)
# Run it, then open  https://<this-mac's-ip>:8443  on the phone and accept the
# self-signed certificate warning.
#
# Only the site's .html pages are served, from an allowlist built at startup --
# never the whole directory. This machine may sit on a routable address, and a
# directory server would hand out the TLS private key below to anyone who asked.
cd "$(dirname "$0")"

mkdir -p .tls
chmod 700 .tls
if [ ! -f .tls/cert.pem ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -keyout .tls/key.pem -out .tls/cert.pem \
    -days 3650 -subj "/CN=antipode.local" 2>/dev/null
  chmod 600 .tls/key.pem
fi
rm -f .cert.pem .key.pem   # clean up keys from any earlier directory-serving run

IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "<your-ip>")
PORT=${PORT:-8443}
echo ""
echo "  On your phone (same network):  https://$IP:$PORT"
echo "  Accept the certificate warning (self-signed). Ctrl-C to stop."
echo ""

exec python3 -c '
import http.server, ssl, sys, os

PORT = int(os.environ.get("PORT", "8443"))
ROOT = os.path.abspath(".")
PAGES = {}                      # url path -> absolute file path, built once
for dirpath, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if not d.startswith(".")]
    for f in files:
        if not f.endswith(".html"):
            continue
        rel = os.path.relpath(os.path.join(dirpath, f), ROOT).replace(os.sep, "/")
        PAGES["/" + rel] = os.path.join(dirpath, f)
        if f == "index.html":
            base = "/" + rel[: -len("index.html")]
            PAGES[base] = os.path.join(dirpath, f)
            if base != "/":
                PAGES[base.rstrip("/")] = os.path.join(dirpath, f)

class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        page = PAGES.get(path)
        if page is None:
            self.send_error(404)
            return
        try:
            body = open(page, "rb").read()
        except OSError:
            self.send_error(500)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def log_message(self, fmt, *a):
        sys.stderr.write("  %s %s\n" % (self.address_string(), fmt % a))

srv = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), H)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(".tls/cert.pem", ".tls/key.pem")
srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
srv.serve_forever()
'
