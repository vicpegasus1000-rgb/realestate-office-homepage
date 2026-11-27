"""홈페이지 공용 처리: 상담 문의(텔레그램), 실거래가(국토부). 로컬 server.py 와 Vercel 함수(api/*.py)가 같이 씀.
비밀(봇 토큰·인증키)은 환경변수로. 로컬에서는 프로젝트 폴더의 telegram_config.json / market_config.json 도 읽음.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ON_VERCEL = bool(os.environ.get("VERCEL"))


def kst():
    """한국 시간 (Vercel 서버는 UTC 라서)"""
    return time.gmtime(time.time() + 9 * 3600)
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
# 환경변수가 없으면 같은 폴더의 telegram_config.json 을 읽음 (화면으로는 절대 내보내지 않음)
_CFG = ROOT / "telegram_config.json"
if (not TOKEN or not CHAT_ID) and _CFG.exists():
    try:
        _c = json.loads(_CFG.read_text(encoding="utf-8"))
        TOKEN = TOKEN or str(_c.get("token") or _c.get("bot_token") or "")
        CHAT_ID = CHAT_ID or str(_c.get("chat_id") or "")
    except (OSError, ValueError):
        pass
# ── 실거래가 (국토교통부 아파트 매매 실거래가, 공공데이터포털 data.go.kr) ──
# 키: 환경변수 DATA_GO_KR_KEY, 없으면 같은 폴더 market_config.json 의 "service_key" (화면으로는 절대 내보내지 않음)
MARKET_KEY = os.environ.get("DATA_GO_KR_KEY", "")
_MCFG = ROOT / "market_config.json"
if not MARKET_KEY and _MCFG.exists():
    try:
        MARKET_KEY = str(json.loads(_MCFG.read_text(encoding="utf-8")).get("service_key") or "")
    except (OSError, ValueError):
        pass
MARKET_KEY = urllib.parse.unquote(MARKET_KEY.strip())  # 인코딩 키·디코딩 키 둘 다 받기
MARKET_URL = os.environ.get("MARKET_API_URL", "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev")  # 상세 자료 API (받은 키가 이쪽용)
# ★ 관리 단지 목록 (국토부 자료의 단지 이름 그대로, 시군구 코드). 늘리려면 여기에 한 줄 추가
COMPLEXES = [
    {"apt": "올림픽파크포레온", "lawd": "11740"},   # 서울 강동구
    {"apt": "신림현대", "lawd": "11620"},           # 서울 관악구 (신림현대성우·신림2차현대와 구분: 이름이 정확히 같은 것만)
]
MARKET_APT = COMPLEXES[0]["apt"]
MARKET_MONTHS = 12
MARKET_TTL = 6 * 3600            # 6시간마다 새로 가져옴
SNAPSHOT = Path(__file__).with_name("_snapshot.json")  # 실제 거래 저장본 (공개 자료). 키가 없거나 국토부 장애 때 보여 줌
MARKET_CACHE = (Path("/tmp") if ON_VERCEL else ROOT) / "market_cache.json"
_market = {"at": 0.0, "data": None, "fail_at": 0.0}
MARKET_BACKOFF = 15 * 60          # 국토부 조회가 실패하면 15분 동안 다시 묻지 않음 (키 호출 한도 보호)
_market_lock = threading.Lock()

MAX_BODY = 4096
LIMITS = {"name": 20, "phone": 20, "kind": 20, "message": 1000}
KINDS = {"아파트", "빌라·다가구", "상가·사무실", "토지", "매도·임대 의뢰", "기타"}
PHONE_RE = re.compile(r"^0\d{1,2}-?\d{3,4}-?\d{4}$")
RATE_N, RATE_SEC = 5, 600
_hits = defaultdict(deque)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def too_many(ip):
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > RATE_SEC:
        q.popleft()
    if len(q) >= RATE_N:
        return True
    q.append(now)
    return False


def clean(s):
    # 제어문자 제거 (줄바꿈은 message 에서만 허용)
    return re.sub(r"[\x00-\x09\x0b-\x1f\x7f]", "", s).strip()


def send_telegram(text):
    if not TOKEN or not CHAT_ID:
        if ON_VERCEL:  # 인터넷에서는 설정이 없으면 실패로 알려 줌 (문의가 사라지지 않게)
            print("[오류] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 환경변수가 없습니다.", flush=True)
            return False
        print("[알림] 텔레그램 설정이 없어 화면에만 출력합니다:\n" + text, flush=True)
        return True
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
    url = "https://api.telegram.org/bot" + TOKEN + "/sendMessage"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10) as r:
            return r.status == 200
    except Exception as e:  # 토큰이 로그에 찍히지 않도록 오류 종류만 출력
        print("[오류] 텔레그램 전송 실패:", type(e).__name__, flush=True)
        return False


def _recent_months(n):
    y, m = kst().tm_year, kst().tm_mon
    out = []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return out[::-1]  # 오래된 달 → 최근 달


def _fetch_month(job):
    """(시군구, 달) 한 묶음 → {단지 이름: [거래...]} (관리 단지만, 해제 거래 제외)"""
    lawd, ymd, names = job
    out, page = {n: [] for n in names}, 1
    while True:
        q = urllib.parse.urlencode({"serviceKey": MARKET_KEY, "LAWD_CD": lawd, "DEAL_YMD": ymd,
                                    "pageNo": page, "numOfRows": 1000})
        for attempt in range(3):  # 국토부 서버가 가끔 503 을 내므로 잠깐 쉬고 다시
            try:
                with urllib.request.urlopen(MARKET_URL + "?" + q, timeout=30) as r:
                    body = r.read(5_000_000)
                break
            except urllib.error.HTTPError as e:
                if e.code < 500 or attempt == 2:
                    raise
                time.sleep(1.5 * (attempt + 1))
        # 기본 파이썬만 쓰므로 defusedxml 대신: DOCTYPE/ENTITY 가 있으면 파싱하지 않음 (XXE·billion laughs 차단)
        if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
            raise ValueError("unsafe xml")
        root = ET.fromstring(body)
        code = (root.findtext(".//resultCode") or "").strip()
        if code not in ("000", "00"):  # 국토부 오류 응답 (예: 04 HTTP 에러, 22 하루 호출 한도 초과)
            raise ValueError("api " + (code or (root.findtext(".//returnReasonCode") or "").strip() + " " + (root.findtext(".//returnAuthMsg") or "").strip()))
        items = root.findall(".//item")
        for it in items:
            g = lambda k: (it.findtext(k) or "").strip()
            name = g("aptNm").replace(" ", "")
            if name not in out or g("cdealType") == "O":  # O = 해제된 거래
                continue
            try:
                out[name].append({
                    "date": f"{int(g('dealYear'))}-{int(g('dealMonth')):02d}-{int(g('dealDay')):02d}",
                    "area": round(float(g("excluUseAr")), 2),
                    "floor": int(g("floor") or 0),
                    "price": int(g("dealAmount").replace(",", "")),  # 만원
                })
            except ValueError:
                continue
        total = int(root.findtext(".//totalCount") or 0)
        if page * 1000 >= total or not items:
            return out
        page += 1


SOURCE = "국토교통부 아파트 매매 실거래가(상세)"


def _summarize(apt, deals, months, updated):
    """한 단지 거래 → 면적별 월 평균·월별 거래·최근 거래"""
    groups = {}
    for d in deals:
        groups.setdefault(f"{int(d['area'])}㎡", []).append(d)  # 전용 84.99 → 84㎡
    out = {}
    for name, ds in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        avg, by_month = [], []
        ds.sort(key=lambda d: d["date"], reverse=True)
        for ymd in months:
            md = [d for d in ds if d["date"].replace("-", "")[:6] == ymd]
            avg.append(round(sum(d["price"] for d in md) / len(md)) if md else None)
            by_month.append([[d["date"], f"{d['area']}㎡ · {d['floor']}층", d["price"]] for d in md])
        out[name] = {"count": len(ds), "months": avg, "byMonth": by_month,
                     "trades": [[d["date"], f"{d['area']}㎡ · {d['floor']}층", d["price"]] for d in ds[:10]]}
    return {"apt": apt, "labels": [f"{int(m[4:])}월" for m in months],
            "fullLabels": [f"{m[:4]}년 {int(m[4:])}월" for m in months], "areas": out,
            "updated": updated, "source": SOURCE}


def _build_market():
    months = _recent_months(MARKET_MONTHS)
    by_lawd = {}
    for c in COMPLEXES:
        by_lawd.setdefault(c["lawd"], []).append(c["apt"].replace(" ", ""))
    jobs = [(lawd, ymd, names) for lawd, names in by_lawd.items() for ymd in months]
    deals = {c["apt"].replace(" ", ""): [] for c in COMPLEXES}
    with ThreadPoolExecutor(max_workers=6) as ex:  # 시군구×12달을 동시에 (Vercel 함수 시간 안에 끝나게)
        for res in ex.map(_fetch_month, jobs):
            for name, rows in res.items():
                deals[name] += rows
    updated = time.strftime("%Y-%m-%d %H:%M", kst())
    return {"complexes": [_summarize(c["apt"], deals[c["apt"].replace(" ", "")], months, updated) for c in COMPLEXES],
            "updated": updated, "source": SOURCE}


def _load(path):
    """저장 파일 읽기 (예전 한 단지 모양도 받아 줌)"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if "complexes" not in data:
        data = {"complexes": [data], "updated": data.get("updated"), "source": data.get("source"), "snapshot": data.get("snapshot")}
    return data


def _complete(data):
    """관리 단지가 빠져 있으면 저장본으로 채우고, 그래도 없으면 '준비 중' 표시"""
    have = {c.get("apt") for c in data["complexes"]}
    snap = _load(SNAPSHOT) if SNAPSHOT.exists() else None
    snap_map = {c.get("apt"): c for c in (snap or {}).get("complexes", [])}
    out = []
    for c in COMPLEXES:
        found = next((x for x in data["complexes"] if x.get("apt") == c["apt"]), None)
        if found is None and c["apt"] in snap_map:
            found = dict(snap_map[c["apt"]], snapshot=True)
        if found is None:
            found = {"apt": c["apt"], "areas": {}, "pending": True}
        out.append(found)
    return dict(data, complexes=out)


def get_market():
    """캐시(6시간) → 새로 조회 → 실패하면 마지막 저장 → 공개 저장본. 항상 관리 단지 전체를 돌려줌."""
    with _market_lock:
        if _market["data"] and time.time() - _market["at"] < MARKET_TTL:
            return _market["data"]
        if MARKET_KEY and time.time() - _market["fail_at"] > MARKET_BACKOFF:
            try:
                data = _build_market()
                _market.update(at=time.time(), data=data)
                try:
                    MARKET_CACHE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                except OSError:
                    pass
                return data
            except Exception as e:  # 키가 로그에 찍히지 않도록 오류 종류만
                why = str(e)[:60] if isinstance(e, ValueError) else ""
                if isinstance(e, urllib.error.HTTPError):
                    why = f"{e.code} (403 이면 키가 아직 등록 중이거나 이 API 활용신청이 안 됨)"
                _market["fail_at"] = time.time()
                print("[오류] 실거래가 조회 실패:", type(e).__name__, why, flush=True)
        for path in (MARKET_CACHE, SNAPSHOT):
            data = _load(path) if path.exists() else None
            if data:
                data = _complete(data)
                if path == SNAPSHOT:
                    data["snapshot"] = True
                _market.update(at=time.time() - MARKET_TTL + 600, data=data)  # 10분 뒤 다시 시도
                return data
        return None




def handle_inquiry(headers, read_body, ip):
    """상담 문의 처리 → (상태코드, 응답 dict). headers 는 .get() 되는 것, read_body(n) 은 bytes 를 돌려줌."""
    if "application/json" not in (headers.get("Content-Type") or ""):
        return 415, {"error": "잘못된 요청입니다."}
    # 다른 사이트에서 몰래 보내는 요청 차단 (Origin 이 있으면 같은 호스트여야 함)
    origin = headers.get("Origin")
    host = headers.get("X-Forwarded-Host") or headers.get("Host")
    if origin and urllib.parse.urlsplit(origin).netloc != host:
        return 403, {"error": "허용되지 않은 요청입니다."}
    try:
        n = int(headers.get("Content-Length") or 0)
    except ValueError:
        n = -1
    if n <= 0 or n > MAX_BODY:
        return 413, {"error": "문의 내용이 너무 깁니다."}
    if too_many(ip):
        return 429, {"error": "잠시 뒤에 다시 신청해 주세요. 급하시면 전화 주세요."}
    try:
        data = json.loads(read_body(n).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError
    except Exception:
        return 400, {"error": "잘못된 요청입니다."}
    if data.get("website"):  # 숨긴 칸을 채우면 자동 프로그램으로 보고 조용히 무시
        return 200, {"ok": True}
    f = {k: clean(str(data.get(k, ""))) for k in LIMITS}
    if any(len(f[k]) > LIMITS[k] for k in LIMITS):
        return 400, {"error": "입력이 너무 깁니다."}
    if not f["name"] or not f["message"]:
        return 400, {"error": "이름과 문의 내용을 적어 주세요."}
    if not PHONE_RE.match(f["phone"]):
        return 400, {"error": "연락처를 010-1234-5678 처럼 적어 주세요."}
    if f["kind"] not in KINDS:
        f["kind"] = "기타"
    text = (
        "[홈페이지 상담 신청]\n"
        f"이름: {f['name']}\n연락처: {f['phone']}\n관심: {f['kind']}\n"
        f"내용:\n{f['message']}\n"
        f"시각: {time.strftime('%Y-%m-%d %H:%M', kst())}"
    )
    if send_telegram(text):
        return 200, {"ok": True}
    return 502, {"error": "신청을 보내지 못했습니다. 전화 02-1234-5678 으로 연락 주세요."}


def client_ip(headers, fallback):
    """Vercel 에서는 X-Forwarded-For 첫 주소가 실제 방문자"""
    if ON_VERCEL:
        xff = (headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        if xff:
            return xff
    return fallback


def send_json(h, code, obj, cache=None):
    """BaseHTTPRequestHandler 로 JSON 응답 + 보안 헤더"""
    body = json.dumps(obj, ensure_ascii=False).encode()
    h.send_response(code)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(body)))
    h.send_header("Cache-Control", cache or "no-store")
    for k, v in SECURITY_HEADERS.items():
        h.send_header(k, v)
    h.end_headers()
    if h.command != "HEAD":
        h.wfile.write(body)
