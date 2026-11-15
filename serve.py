import functools
import http.server
import socketserver

DIRECTORY = "/Users/vasilenkonataliia/Desktop/my-site"
PORT = 8400

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=DIRECTORY)
socketserver.TCPServer.allow_reuse_address = True

with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
    httpd.serve_forever()
