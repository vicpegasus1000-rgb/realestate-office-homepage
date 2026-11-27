# 한 줄 요약

공인중개사 사무소 홈페이지 시안 (고급 매거진풍, 청록색): 매물 검색·상세 보기, 올림픽파크포레온 실거래가(국토부 자료 자동 갱신) 그래프, 상담 문의 텔레그램 알림, 오시는 길. 사무소 정보는 가상 값(홍길동·강남구).

## 주요 파일

| 파일 | 하는 일 |
|---|---|
| `index.html` | 홈페이지 전체 (CSS·JS 포함). 표지(이달의 매물) · 움직이는 이름 띠(TechText: React Bits 부품을 React 없이 옮김, 글자에 마우스·누르기·끌기 반응, 설정은 맨 아래 `TechText(...)` 호출) · 매물 검색(검색어·종류·거래·가격) + 상세 창 · 실거래가 그래프·표 · 단지 지도(오픈스트리트맵 그림 조각 + 단지 경계 + 아파트 표시, 누르면 면적별 최근 실거래가. 설정은 `<script>` 의 `APT_MAP`) · 소개 · 상담 폼 · 오시는 길. 휴대폰 대응 |
| `server.py` | 내 PC 에서 띄우는 서버 (index.html·글꼴 제공, `/api/market`, `/api/inquiry`). 실제 처리는 `api/_core.py` |
| `api/_core.py` | 공용 처리: 상담 문의 검사·텔레그램 전송, 국토부 실거래가(상세 자료 API, 강동구 11740 중 `올림픽파크포레온`, 12달 동시 조회, 6시간 캐시, 해제 거래 제외) |
| `api/market.py`, `api/inquiry.py` | Vercel 함수 (인터넷 공개용). `_core` 를 불러 씀 |
| `vercel.json` | Vercel 설정: 보안 헤더(CSP 등), 함수 시간, 글꼴 캐시 |
| `.vercelignore` | Vercel 에 안 올릴 것: server.py, 문서, 비밀 파일, 캐시 |
| `market_cache.json` | 마지막으로 가져온 실거래가 저장본 (서버가 자동 생성, 국토부 조회 실패 시 사용) |
| `fonts/` | 네이버 한글 글꼴(hangeul.naver.com): 마루부리 Regular·SemiBold·Bold(제목), 나눔스퀘어네오 Rg·Bd·Eb(본문). 서버가 이 폴더의 .woff/.woff2 만 내보냄 |
| `index_old.html` | 이전 시안 (보관용) |

## 실행 방법

- 화면만 보기: `index.html` 더블클릭 (상담 폼은 시범 모드, 실제 전송 안 함. 브라우저에 따라 글꼴이 안 나올 수 있으니 서버 주소로 보는 것이 정확함)
- 텔레그램 알림까지: PowerShell 에서
  ```
  $env:TELEGRAM_BOT_TOKEN = "봇 토큰"
  $env:TELEGRAM_CHAT_ID = "채팅 ID"
  $env:DATA_GO_KR_KEY = "공공데이터포털 인증키"
  python server.py
  ```
  → http://127.0.0.1:8000 . 환경변수가 없으면 같은 폴더 `telegram_config.json`(token, chat_id)을 읽음. 둘 다 없으면 문의를 서버 창에만 출력.
- 실거래가 인증키: data.go.kr 에서 "국토교통부_아파트 매매 실거래가 상세 자료" 활용신청 → 마이페이지의 일반 인증키. 환경변수 대신 `market_config.json` `{"service_key": "..."}` 도 됨. 키가 없으면 저장본, 그것도 없으면 예시 숫자가 보임
- 관리 단지 추가: `api/_core.py` 의 `COMPLEXES` (국토부 자료의 단지 이름, 시군구 코드) + `index.html` 의 `APT_MAPS`(지도 위치·경계) + `LISTINGS`(매물 카드, `complex` 에 단지 이름)
- 지금 관리 단지: 올림픽파크포레온(강동구 11740), 신림현대(관악구 11620)

## 인터넷 공개 (Vercel)

- 공개 주소: https://realestate-office-homepage-s79d.vercel.app (Vercel 팀 `tujawoodeungsaeng`, 프로젝트 `realestate-office-homepage-s79d`)
- GitHub 공개 저장소 `vicpegasus1000-rgb/realestate-office-homepage` 와 연결됨 (커밋 메일은 GitHub 가림 메일)
- GitHub 비밀 자동 감시(secret scanning·push protection) 켜짐. 개인 메모(`pegasus_skill_*`)는 .gitignore 로 제외
- Framework Preset: **Other**, Build/Output 설정은 비워 둠
- Environment Variables (Vercel 화면에서 직접 입력): `DATA_GO_KR_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- 이후 GitHub 에 올리면(push) 자동으로 다시 배포됨
- 실거래가 저장본 `api/_snapshot.json` (2026-11-27 22:23, 134건): 키가 없거나 국토부 장애 때 보여 줌. 새로 만들려면 `market_cache.json` 을 복사하고 source 끝에 "저장본", "snapshot": true
- 예전 저장소 `realestate-office-homepage-pegasus` (비공개, 예전 Gmail 기록 있음) — 쓰지 않음, 지워도 됨
- Vercel 에서는 문의 횟수 제한이 함수마다 따로라 느슨함. 실거래가는 Vercel 앞단이 6시간 저장(s-maxage)
- 이 PC 에 Node.js·Vercel CLI 없음 (웹 화면으로 연결)
- 환경변수를 넣거나 바꾼 뒤에는 Vercel 에서 Redeploy 해야 반영됨

## 바꿀 곳 (예시 값 → 실제 정보)

- 사무소 이름 `강남싹쓸이 부동산`, 대표 `홍길동`, 전화 `02-1234-5678`·`010-1234-5678`(tel: 링크 `0212345678` 포함), 주소 `서울특별시 강남구 싹쓸이로 123, 싹쓸이빌딩 1층` (모두 가상 정보), 등록번호·사업자번호 → 찾아 바꾸기
- 매물: `<script>` 의 `LISTINGS` 배열 / 시세: 서버가 자동으로 채움 (`MARKET` 객체는 서버 없이 열 때 보이는 예시)
- 색: `<style>` 맨 위 `:root` (청록 #1f7f81 / 바탕 #e3f1f0)
- 지도: 지금은 가상 약도(SVG 그림: 길·건물·공원·강남역·걷는 길). 실제 주소가 정해지면 `.map` 상자를 카카오맵·네이버지도 코드로 교체. 이때 `<meta http-equiv="Content-Security-Policy">` 에 지도 주소 추가

## 보안 메모

- 지도는 외부 스크립트 없이 tile.openstreetmap.org 그림만 불러옴 (CSP img-src 에 그 주소만 추가). 화면 오른쪽 아래 OpenStreetMap 출처 표시는 지우지 말 것

- 봇 토큰·실거래가 키는 환경변수 또는 config 파일로만. 화면·코드에 적지 않기 (서버는 config 파일을 내보내지 않음)
- 국토부 응답 XML 에 DOCTYPE/ENTITY 가 있으면 읽지 않음 (XXE 차단, 파이썬 기본 기능만 쓰기 때문)
- 서버는 `index.html` 만 보여 줌, 문의 길이 제한·같은 IP 10분 5번 제한·다른 사이트 요청 차단·자동 프로그램 걸러내기(숨은 칸)
- 화면 글자는 모두 textContent 로 넣음 (HTML 끼워 넣기 방지)
- 인터넷 공개 시 HTTPS 뒤에 둘 것

## 자동 실행

없음.
