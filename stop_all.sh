#!/bin/bash

echo "========================================="
echo "Parando serviços do AllNube"
echo "========================================="

# Parar Celery Worker
echo -n "🔄 Parando Celery Worker... "
if [ -f celery_worker.pid ]; then
    kill -TERM $(cat celery_worker.pid) 2>/dev/null
    rm celery_worker.pid
    echo "✅"
else
    echo "⚠️  Não estava rodando"
fi

# Parar Celery Beat
echo -n "⏰ Parando Celery Beat... "
if [ -f celery_beat.pid ]; then
    kill -TERM $(cat celery_beat.pid) 2>/dev/null
    rm celery_beat.pid
    echo "✅"
else
    echo "⚠️  Não estava rodando"
fi

# Parar Flower
echo -n "🌼 Parando Flower... "
if [ -f flower.pid ]; then
    kill -TERM $(cat flower.pid) 2>/dev/null
    rm flower.pid
    echo "✅"
else
    echo "⚠️  Não estava rodando"
fi

# Matar processos remanescentes
pkill -f "celery.*worker" 2>/dev/null
pkill -f "celery.*beat" 2>/dev/null
pkill -f "celery.*flower" 2>/dev/null

echo ""
echo "✅ Todos os serviços foram parados!"
