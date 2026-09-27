$ cd ~/Desktop/Vs_code_projects/Channels/tg-analyzer
source channels_env/Scripts/activate
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000
ngrok http 8000