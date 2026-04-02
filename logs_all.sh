#!/bin/bash

echo "========================================="
echo "Logs dos Serviços AllNube"
echo "========================================="
echo ""
echo "1) Celery Worker logs"
echo "2) Celery Beat logs"
echo "3) Flower logs"
echo "4) Todos (multitail)"
echo "5) Sair"
echo ""
read -p "Escolha uma opção: " option

case $option in
    1)
        echo ""
        echo "=== Celery Worker Logs ==="
        echo "Pressione Ctrl+C para sair"
        sleep 2
        tail -f logs/celery_worker.log
        ;;
    2)
        echo ""
        echo "=== Celery Beat Logs ==="
        echo "Pressione Ctrl+C para sair"
        sleep 2
        tail -f logs/celery_beat.log
        ;;
    3)
        echo ""
        echo "=== Flower Logs ==="
        echo "Pressione Ctrl+C para sair"
        sleep 2
        tail -f logs/flower.log
        ;;
    4)
        echo ""
        echo "=== Todos os Logs ==="
        echo "Pressione Ctrl+C para sair"
        sleep 2
        # Verificar se multitail está instalado
        if command -v multitail &> /dev/null; then
            multitail logs/celery_worker.log logs/celery_beat.log logs/flower.log
        else
            echo "multitail não instalado. Instale com: sudo apt install multitail"
            echo "Exibindo apenas worker logs..."
            tail -f logs/celery_worker.log
        fi
        ;;
    5)
        exit 0
        ;;
    *)
        echo "Opção inválida"
        ;;
esac
