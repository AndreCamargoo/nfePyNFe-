#!/bin/bash

echo "========================================="
echo "Status dos Serviços AllNube"
echo "========================================="
echo ""

# Redis
echo -n "🐘 Redis: "
if sudo systemctl is-active --quiet redis-server; then
    echo "✅ Rodando"
else
    echo "❌ Parado"
fi

# Celery Worker
echo -n "🔄 Celery Worker: "
if [ -f celery_worker.pid ] && kill -0 $(cat celery_worker.pid) 2>/dev/null; then
    echo "✅ Rodando (PID: $(cat celery_worker.pid))"
else
    echo "❌ Parado"
fi

# Celery Beat
echo -n "⏰ Celery Beat: "
if [ -f celery_beat.pid ] && kill -0 $(cat celery_beat.pid) 2>/dev/null; then
    echo "✅ Rodando (PID: $(cat celery_beat.pid))"
else
    echo "❌ Parado"
fi

# Flower
echo -n "🌼 Flower: "
if [ -f flower.pid ] && kill -0 $(cat flower.pid) 2>/dev/null; then
    echo "✅ Rodando (PID: $(cat flower.pid))"
    echo "   📊 http://localhost:5555"
else
    echo "⚠️  Não rodando (opcional)"
fi

echo ""
echo "========================================="
echo "Tasks Registradas no Celery:"
echo "========================================="

if [ -f celery_worker.pid ] && kill -0 $(cat celery_worker.pid) 2>/dev/null; then
    celery -A app inspect registered 2>/dev/null | grep -E "(leads_api|nfe|debug_task)" || echo "   Nenhuma task encontrada"
else
    echo "   Celery Worker não está rodando"
fi

echo ""
echo "========================================="
echo "Tasks Agendadas (Celery Beat):"
echo "========================================="

if [ -f celery_beat.pid ] && kill -0 $(cat celery_beat.pid) 2>/dev/null; then
    echo "   📅 automação NFe: 00:00 às 07:00 (a cada 30 min)"
else
    echo "   Celery Beat não está rodando"
fi

echo ""
echo "========================================="
echo "Logs:"
echo "   tail -f logs/celery_worker.log"
echo "   tail -f logs/celery_beat.log"
echo "========================================="
