#!/bin/bash

echo "Starting Delogo Dev Server..."

# Kill background jobs on exit
trap "exit" INT TERM
trap "kill 0" EXIT

# Start Backend
echo "Starting FastAPI backend..."
cd backend
python3 -m venv venv
if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi
pip install -r requirements.txt
python main.py &
cd ..

# Start Frontend
echo "Starting Electron/Vue frontend..."
cd frontend
npm install
npm run dev
