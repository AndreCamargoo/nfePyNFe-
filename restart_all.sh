#!/bin/bash

echo "========================================="
echo "Reiniciando todos os serviços do AllNube"
echo "========================================="

./stop_all.sh
sleep 2
./start_all.sh
