@echo off
echo Updating pip...
python -m pip install --upgrade pip

echo Installing/upgrading sip...
pip install --upgrade sip

echo Installing/upgrading PyQt5...
pip install --upgrade PyQt5

echo Installing requirements from requirements.txt...
pip install -r requirements.txt

echo Launching main.py...
python main.py

pause