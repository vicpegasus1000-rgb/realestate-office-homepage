"""Vercel 함수: POST /api/inquiry → 상담 문의를 텔레그램으로"""
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        ip = _core.client_ip(self.headers, self.client_address[0] if self.client_address else "")
        code, obj = _core.handle_inquiry(self.headers, self.rfile.read, ip)
        _core.send_json(self, code, obj)

    def do_GET(self):
        _core.send_json(self, 405, {"error": "POST 만 됩니다."})
