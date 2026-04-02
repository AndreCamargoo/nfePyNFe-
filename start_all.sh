#!/bin/bash

echo "========================================="
echo "Iniciando todos os serviços do AllNube"
echo "========================================="

mkdir -p logs

# Ativar virtualenv
if [ -z "$VIRTUAL_ENV" ]; then
    source venv/bin/activate
fi

# Verificar Redis
echo ""
echo "1. Verificando Redis..."
if sudo systemctl is-active --quiet redis-server; then
    echo "   ✅ Redis OK"
else
    sudo systemctl start redis-server
fi

# Parar processos antigos
echo ""
echo "2. Parando processos antigos..."
pkill -f "celery.*worker" 2>/dev/null
pkill -f "celery.*beat" 2>/dev/null
sleep 2

# Iniciar Worker
echo ""
echo "3. Iniciando Celery Worker..."
nohup celery -A app worker --loglevel=info --pool=threads --concurrency=4 \
    --logfile=logs/celery_worker.log --pidfile=celery_worker.pid > /dev/null 2>&1 &

sleep 3
if pgrep -f "celery.*worker" > /dev/null; then
    echo "   ✅ Celery Worker iniciado"
else
    echo "   ❌ Erro ao iniciar Worker"
    tail -5 logs/celery_worker.log
fi

# Iniciar Beat
echo ""
echo "4. Iniciando Celery Beat..."
nohup celery -A app beat --loglevel=info \
    --logfile=logs/celery_beat.log --pidfile=celery_beat.pid > /dev/null 2>&1 &

sleep 2
if pgrep -f "celery.*beat" > /dev/null; then
    echo "   ✅ Celery Beat iniciado"
else
    echo "   ❌ Erro ao iniciar Beat"
fi

echo ""
echo "========================================="
echo "✅ Serviços iniciados!"
echo "========================================="
echo ""
echo "📊 Verificar status: celery -A app status"
echo "📝 Ver logs: tail -f logs/celery_worker.log"
echo "🛑 Parar: pkill -f celery"
echo "========================================="
