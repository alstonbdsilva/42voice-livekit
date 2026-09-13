#!/usr/bin/env font
#!/bin/bash
set -e

echo "=== 42Voice Container Entrypoint ==="
echo "Mode: ${1:-backend}"

if [ "$1" = "backend" ]; then
    echo "[Backend] Running database migration & initialization against Supabase..."
    python api/init_db.py || {
        echo "[Backend Warning] Database initialization returned code $?. Continuing startup..."
    }
    
    echo "[Backend] Starting FastAPI Server on port 8000..."
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${FASTAPI_WORKERS:-2}

elif [ "$1" = "worker" ]; then
    echo "[Worker] Starting LiveKit Voice Agent Worker..."
    exec python agent.py dev

else
    exec "$@"
fi
