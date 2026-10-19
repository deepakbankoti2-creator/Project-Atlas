@echo off
title Project Atlas - Report Copilot Server
echo ========================================================
echo  Starting Project Atlas Report Copilot Server
echo  Web Portal: http://localhost:8000/portal
echo  Swagger UI: http://localhost:8000/docs
echo ========================================================
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
pause
