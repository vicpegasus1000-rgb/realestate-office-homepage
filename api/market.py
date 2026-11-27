"""Vercel 함수: GET /api/market → 올림픽파크포레온 실거래가 (국토부 상세 자료)"""
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _core  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 주소 뒤에 ?... 를 붙여 Vercel 저장본(CDN)을 건너뛰는 것 차단 → 국토부 키 호출 한도 보호
        if "?" in self.path:
            self.send_response(301)
            self.send_header("Location", "/api/market")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        data = _core.get_market()
        if data:
            # Vercel 앞단(CDN)이 6시간 저장 → 국토부에는 거의 안 물음
            _core.send_json(self, 200, data, "public, max-age=600, s-maxage=21600, stale-while-revalidate=86400")
        else:
            _core.send_json(self, 503, {"error": "실거래가 자료가 아직 없습니다."})

    do_HEAD = do_GET
