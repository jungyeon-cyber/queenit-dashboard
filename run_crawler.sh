#!/bin/bash
# ──────────────────────────────────────────────────────────────
# run_crawler.sh
# cron이 이 파일을 매일 실행합니다.
# ──────────────────────────────────────────────────────────────

# 스크립트 위치 기준으로 절대경로 설정 (cron은 경로를 모름)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/logs/crawler.log"

# 로그 디렉토리 생성
mkdir -p "$SCRIPT_DIR/logs"

echo "──────────────────────────────" >> "$LOG_FILE"
echo "실행 시작: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"

# Python 경로 자동 탐지 (brew / pyenv / 시스템 순서)
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
    echo "❌ Python3를 찾을 수 없습니다" >> "$LOG_FILE"
    exit 1
fi

echo "Python: $PYTHON" >> "$LOG_FILE"

# 크롤러 실행
cd "$SCRIPT_DIR"
"$PYTHON" crawler.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 완료" >> "$LOG_FILE"
    # 최신 리포트를 브라우저로 자동 오픈 (원하지 않으면 아래 줄 주석처리)
    LATEST_REPORT=$(ls -t "$SCRIPT_DIR/reports/"*.html 2>/dev/null | head -1)
    [ -n "$LATEST_REPORT" ] && open "$LATEST_REPORT"
else
    echo "❌ 오류 발생 (exit $EXIT_CODE)" >> "$LOG_FILE"
fi

echo "실행 종료: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
