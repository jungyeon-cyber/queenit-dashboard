#!/bin/bash
# ──────────────────────────────────────────────────────────────
# setup_mac.sh  —  Mac 최초 1회 실행하는 설치 스크립트
# 사용법: bash setup_mac.sh
# ──────────────────────────────────────────────────────────────

set -e  # 오류 시 즉시 중단

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   퀸잇 경쟁사 크롤러 — Mac 설치 스크립트   ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Python3 확인 ───────────────────────────────────────────
echo "① Python3 확인 중..."
PYTHON=""
for candidate in \
    "$HOME/.pyenv/shims/python3" \
    "/opt/homebrew/bin/python3" \
    "/usr/local/bin/python3" \
    "/usr/bin/python3"; do
    if [ -x "$candidate" ]; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo "  ❌ Python3가 설치되어 있지 않습니다."
    echo "  아래 명령어로 설치해 주세요:"
    echo ""
    echo "     /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    echo "     brew install python"
    echo ""
    exit 1
fi

PYTHON_VER=$("$PYTHON" --version 2>&1)
echo "  ✅ $PYTHON_VER ($PYTHON)"

# ── 2. pip 패키지 설치 ────────────────────────────────────────
echo ""
echo "② 필수 패키지 설치 중..."
"$PYTHON" -m pip install --upgrade pip --quiet
"$PYTHON" -m pip install requests beautifulsoup4 --quiet

echo "  ✅ requests, beautifulsoup4 설치 완료"

# ── 3. 디렉토리 생성 ──────────────────────────────────────────
echo ""
echo "③ 폴더 구조 생성 중..."
mkdir -p "$SCRIPT_DIR/data"
mkdir -p "$SCRIPT_DIR/reports"
mkdir -p "$SCRIPT_DIR/logs"
echo "  ✅ data / reports / logs 폴더 생성"

# ── 4. 실행 권한 부여 ─────────────────────────────────────────
echo ""
echo "④ 실행 권한 설정 중..."
chmod +x "$SCRIPT_DIR/run_crawler.sh"
chmod +x "$SCRIPT_DIR/crawler.py"
echo "  ✅ 완료"

# ── 5. 테스트 실행 ────────────────────────────────────────────
echo ""
echo "⑤ 테스트 실행 중... (약 30초 소요)"
cd "$SCRIPT_DIR"
"$PYTHON" crawler.py
echo ""

# ── 6. cron 등록 ──────────────────────────────────────────────
echo "⑥ Mac cron 자동 실행 등록 중..."
echo ""
echo "  매일 몇 시에 실행할까요? (0~23, 기본값: 9)"
read -p "  시간 입력 [9]: " HOUR
HOUR=${HOUR:-9}

# 숫자 검증
if ! [[ "$HOUR" =~ ^[0-9]+$ ]] || [ "$HOUR" -lt 0 ] || [ "$HOUR" -gt 23 ]; then
    echo "  ⚠ 잘못된 입력, 기본값 9시로 설정합니다"
    HOUR=9
fi

CRON_JOB="0 $HOUR * * * $SCRIPT_DIR/run_crawler.sh"

# 기존 crontab에서 중복 제거 후 추가
(crontab -l 2>/dev/null | grep -v "run_crawler.sh"; echo "$CRON_JOB") | crontab -

echo "  ✅ cron 등록 완료: 매일 ${HOUR}:00 자동 실행"
echo ""
echo "  현재 등록된 cron 작업:"
crontab -l | grep "run_crawler" | sed 's/^/    /'

# ── 7. 완료 안내 ──────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║              ✅ 설치 완료!               ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  📁 크롤러 위치:   $SCRIPT_DIR"
echo "  📊 리포트 위치:   $SCRIPT_DIR/reports/"
echo "  📋 로그 위치:     $SCRIPT_DIR/logs/crawler.log"
echo "  ⏰ 자동 실행:     매일 ${HOUR}:00"
echo ""
echo "  지금 바로 실행하려면:"
echo "    bash $SCRIPT_DIR/run_crawler.sh"
echo ""
echo "  cron 등록 확인:"
echo "    crontab -l"
echo ""
echo "  cron 등록 취소:"
echo "    crontab -l | grep -v run_crawler | crontab -"
echo ""
