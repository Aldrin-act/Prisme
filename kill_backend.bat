@echo off
echo Arret de tous les serveurs Python/uvicorn...
taskkill /IM python.exe /F
timeout /t 2
echo Serveurs arretes.
