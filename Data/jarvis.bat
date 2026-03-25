@echo off
cd /d C:\jarvis

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Running main.py...
python main.py
pause