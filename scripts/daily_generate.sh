#!/bin/bash
# dlogic-note 日次記事自動生成
# cron: JRA=土日 7:00, NAR=毎日 14:00
#
# Usage:
#   ./daily_generate.sh jra    # JRA記事生成
#   ./daily_generate.sh nar    # NAR記事生成
#   ./daily_generate.sh        # 両方生成

set -e

SCRIPT_DIR="/opt/dlogic/note"
VENV="$SCRIPT_DIR/venv/bin/activate"
LOG_DIR="$SCRIPT_DIR/logs"
DATE=$(date +%Y%m%d)

mkdir -p "$LOG_DIR"

source "$VENV"
cd "$SCRIPT_DIR"

generate() {
    local type=$1
    local log_file="$LOG_DIR/${DATE}_${type}.log"

    echo "[$(date)] Starting $type article generation for $DATE" >> "$log_file"
    python main.py --date "$DATE" --type "$type" >> "$log_file" 2>&1

    if [ $? -eq 0 ]; then
        echo "[$(date)] SUCCESS: $type article generated" >> "$log_file"
    else
        echo "[$(date)] FAILED: $type article generation" >> "$log_file"
    fi
}

case "${1:-both}" in
    jra)
        generate jra
        ;;
    nar)
        generate nar
        ;;
    both)
        generate jra
        generate nar
        ;;
    *)
        echo "Usage: $0 {jra|nar|both}"
        exit 1
        ;;
esac
