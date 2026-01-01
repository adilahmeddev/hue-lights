
  1. Install API dependencies:
  pip install -e ".[api]"

  2. Start the daemon + API (in separate terminals):
  # Terminal 1: Start daemon
  python cli.py daemon start

  # Terminal 2: Start API server
  uvicorn api.main:app --host 0.0.0.0 --port 8000

  3. Run Web App:
  cd web
  npm run dev
  Open http://localhost:5173

  4. Run Mobile App:
  cd mobile
  npx expo start
  Scan QR code with Expo Go app on your Android phone.

  Mobile App Settings

  On first launch, tap "Settings" to enter your Raspberry Pi's IP address (e.g., http://192.168.1.100:8000).

