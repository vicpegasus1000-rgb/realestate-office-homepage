"""내 PC 에서 홈페이지 띄우기 (인터넷 공개는 Vercel: api/*.py 함수가 같은 일을 함).

실행:
    PowerShell 에서
        $env:TELEGRAM_BOT_TOKEN = "봇 토큰"
        $env:TELEGRAM_CHAT_ID   = "받을 채팅 ID"
        $env:DATA_GO_KR_KEY     = "공공데이터포털 인증키"   (올림픽파크포레온 실거래가 자동 갱신)
        python server.py
    → 브라우저에서 http://127.0.0.1:8000
    환경변수 대신 같은 폴더에 telegram_config.json {"token","chat_id"} / market_config.json {"service_key"} 를 둬도 됨.

실제 처리(문의 검사·텔레그램 전송·실거래가 조회)는 api/_core.py 에 있음.

보안 메모
- 봇 토큰·인증키는 환경변수(또는 위 config 파일)로만. 화면이나 코드에 적지 않기
- index.html 과 fonts/ 글꼴만 보여 주고, 다른 파일(이 파일, config, CLAUDE.md 등)은 보여 주지 않음
- 문의는 4KB 이하, 칸마다 길이 제한, 같은 IP 10분에 5번까지, 다른 사이트에서 보낸 요청 차단
- 기본은 이 PC 에서만 접속(127.0.0.1)
"""
import os
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "api"))
import _core  # noqa: E402

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
INDEX = Path(__file__).with_name("index.html")
FONTS = Path(__file__).with_name("fonts")
FONT_RE = re.compile(r"^/fonts/([A-Za-z0-9-]+\.woff2?)$")


class Handler(BaseHTTPRequestHandler):
    server_version = "web"
    sys_version = ""

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in _core.SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        font = FONT_RE.match(path)
        if path in ("/", "/index.html"):
            self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/market":
            data = _core.get_market()
            if data:
                _core.send_json(self, 200, data)
            else:
                _core.send_json(self, 503, {"error": "실거래가 자료가 아직 없습니다."})
        elif font and (FONTS / font.group(1)).is_file():
            # 글꼴 폴더의 .woff/.woff2 파일만 (이름에 영문·숫자·- 만 허용 → 다른 폴더로 못 빠져나감)
            ctype = "font/woff2" if font.group(1).endswith(".woff2") else "font/woff"
            self._send(200, (FONTS / font.group(1)).read_bytes(), ctype)
        else:
            self._send(404, "없는 페이지입니다".encode(), "text/plain; charset=utf-8")

    do_HEAD = do_GET

    def do_POST(self):
        if urllib.parse.urlsplit(self.path).path != "/api/inquiry":
            return _core.send_json(self, 404, {"error": "없는 주소입니다."})
        code, obj = _core.handle_inquiry(self.headers, self.rfile.read, self.client_address[0])
        _core.send_json(self, code, obj)

    def log_message(self, fmt, *args):
        # 접속 기록에 개인정보가 남지 않도록 주소와 결과만 출력
        sys.stderr.write("%s %s\n" % (self.command, args[1] if len(args) > 1 else ""))


if __name__ == "__main__":
    if not _core.TOKEN or not _core.CHAT_ID:
        print("텔레그램 환경변수가 없어 문의는 이 창에만 출력됩니다.")
    if not _core.MARKET_KEY:
        print("실거래가 인증키(DATA_GO_KR_KEY)가 없어 시세는 저장본 또는 예시로 보입니다.")
    print(f"http://{HOST}:{PORT} 에서 열렸습니다. 끄려면 Ctrl+C")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
