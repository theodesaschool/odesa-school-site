"""Локальный сервер для просмотра сайта: python3 serve.py → http://localhost:8400"""
import functools
import http.server
import os
import socketserver

DIRECTORY = os.path.dirname(os.path.abspath(__file__))  # папка, где лежит этот файл
PORT = 8400

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=DIRECTORY)
socketserver.TCPServer.allow_reuse_address = True

with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
    print(f"Сайт открыт на http://localhost:{PORT} (остановить: Ctrl+C)")
    httpd.serve_forever()
