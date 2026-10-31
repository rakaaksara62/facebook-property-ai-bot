#!/usr/bin/env bash
# ==============================================================================
# RUNNER & AUTO-RESTART WATCHDOG SCRIPT FOR LINUX / AWS EC2
# ==============================================================================
# Script ini berguna untuk menjalankan bot di background dan otomatis me-restart
# jika proses Python berhenti atau keluar secara tak terduga.
# Sangat cocok untuk instance EC2 minimal atau tanpa systemd.
#
# Cara Penggunaan:
#   chmod +x run_bot.sh
#   nohup ./run_bot.sh > bot.log 2>&1 &
# ==============================================================================

# Pastikan script berjalan dari direktori tempat script ini berada
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Deteksi executable Python dari virtualenv
if [ -f "venv/bin/python" ]; then
    PYTHON_EXEC="venv/bin/python"
elif [ -f ".venv/bin/python" ]; then
    PYTHON_EXEC=".venv/bin/python"
else
    PYTHON_EXEC="python3"
fi

echo "=================================================="
echo "🚀 Memulai Facebook Property Bot Runner"
echo "🕒 Waktu Mulai: $(date)"
echo "🐍 Python: $PYTHON_EXEC"
echo "=================================================="

RESTART_DELAY=10

while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Memulai proses bot utama (main_bot.py)..."
    $PYTHON_EXEC main_bot.py
    EXIT_CODE=$?

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Bot berhenti dengan kode keluar: $EXIT_CODE"

    # Jika bot dihentikan secara normal (kode 0 atau SIGINT 130)
    if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 130 ]; then
        echo "🛑 Penghentian normal terdeteksi. Script runner selesai."
        break
    fi

    echo "⚠️ Bot crash/berhenti tak terduga. Auto-restart dalam ${RESTART_DELAY} detik..."
    sleep $RESTART_DELAY
done

