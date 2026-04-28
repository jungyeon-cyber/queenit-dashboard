# 퀸잇 경쟁사 크롤러 — 설치 & 사용 가이드

## 📁 파일 구성

```
queenit_crawler/
├── crawler.py          ← 메인 크롤러 (수집 + 리포트 생성)
├── run_crawler.sh      ← cron이 매일 실행하는 쉘 스크립트
├── setup_mac.sh        ← 최초 1회 실행하는 설치 스크립트
├── data/
│   ├── latest.json     ← 최신 수집 데이터 (항상 덮어씀)
│   └── YYYY-MM-DD.json ← 날짜별 백업
├── reports/
│   └── YYYY-MM-DD.html ← 일간 HTML 리포트
└── logs/
    └── crawler.log     ← 실행 로그
```

---

## 🚀 최초 설치 (Mac)

### Step 1 — 폴더를 원하는 위치에 저장
파인더에서 이 폴더를 원하는 위치로 이동하세요.
예: `~/Documents/queenit_crawler/`

### Step 2 — 터미널 열기
`Cmd + Space` → "터미널" 검색 → 실행

### Step 3 — 설치 스크립트 실행
```bash
cd ~/Documents/queenit_crawler
bash setup_mac.sh
```

설치 스크립트가 자동으로:
1. Python3 설치 여부 확인
2. 필수 패키지 설치 (requests, beautifulsoup4)
3. 테스트 크롤링 1회 실행
4. 매일 자동 실행 cron 등록

---

## ▶️ 수동 실행

```bash
cd ~/Documents/queenit_crawler
python3 crawler.py
```

실행 후 `reports/` 폴더에 오늘 날짜의 HTML 리포트가 생성됩니다.

---

## 📊 수집 항목

| 대상 | 수집 내용 | 방법 |
|------|-----------|------|
| 포스티 | iOS 최신 리뷰 5건, Android 업데이트 날짜 | 앱스토어 RSS + 구글플레이 |
| 에이블리 | iOS 최신 리뷰 5건, 기획전 목록 | 앱스토어 RSS + 공개 웹 |
| 지그재그 | iOS 최신 리뷰 5건, Android 업데이트 | 앱스토어 RSS + 구글플레이 |
| 29CM | 기획전 목록 + 링크 | 공개 웹페이지 |

---

## ⏰ 자동 실행 관리

### 현재 등록된 cron 확인
```bash
crontab -l
```

### 실행 시간 변경 (예: 오전 8시로 변경)
```bash
# 기존 cron 제거 후 재등록
crontab -l | grep -v run_crawler | crontab -
(crontab -l; echo "0 8 * * * ~/Documents/queenit_crawler/run_crawler.sh") | crontab -
```

### 자동 실행 중단
```bash
crontab -l | grep -v run_crawler | crontab -
```

---

## ❗ 주의 사항

- **포스티·에이블리**는 앱 전용 서비스라 웹 크롤링에 제한이 있습니다.
  앱스토어 리뷰와 공개 웹 기획전 페이지 기반으로 수집합니다.
- 크롤러 실행 중 Mac이 잠자기 상태이면 cron이 실행되지 않습니다.
  → 시스템 환경설정 > 배터리 > "잠자기 방지" 설정 권장
- 수집 간격은 사이트 과부하 방지를 위해 요청 사이 1.5초 딜레이가 적용되어 있습니다.

---

## 🔄 업데이트 방법

Claude에게 "크롤러 업데이트해줘"라고 요청하면  
`crawler.py` 파일을 새 버전으로 교체해 드립니다.
`run_crawler.sh`와 `setup_mac.sh`는 재설치 불필요합니다.
