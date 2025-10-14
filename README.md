# Chat VRD Backend - LiveKit Voice Agent

Backend implementation for Kijko Voice Agent using LiveKit, Cartesia (STT/TTS), and Gemini (LLM).

## Architecture

This backend consists of two separate services:

1. **API Service** (`api.py`) - FastAPI server for room creation and token generation
2. **Agent Worker** (`agent.py`) - LiveKit agent that handles voice conversations

## Setup

### Prerequisites

- Python 3.11+
- LiveKit Cloud account (or self-hosted LiveKit server)
- Cartesia API key
- Gemini API key

### Environment Variables

Set these in Railway dashboard for each service:

#### API Service & Agent Worker (Both need these):

```
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
CARTESIA_API_KEY=your_cartesia_key
CARTESIA_VOICE_ID=694f9389-aac1-45b6-b726-9d9369183238
GEMINI_API_KEY=your_gemini_key
```

#### API Service Only:

```
PORT=8000  # Railway sets this automatically
```

## Railway Deployment

### Service 1: API Server

1. Create new Railway service
2. Select "Deploy from GitHub repo"
3. Choose this repository
4. Set **Dockerfile Path**: `Dockerfile.api`
5. Add environment variables (see above)
6. Deploy

### Service 2: Agent Worker

1. Create another Railway service (same project)
2. Select "Deploy from GitHub repo"
3. Choose this repository
4. Set **Dockerfile Path**: `Dockerfile.agent`
5. Add environment variables (see above)
6. Deploy

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run API server
python api.py

# Run agent worker (in separate terminal)
python agent.py start
```

## API Endpoints

### `GET /health`
Health check endpoint

### `POST /connect`
Create LiveKit room and return connection token

Request:
```json
{
  "language": "en",
  "session_id": "optional-custom-id"
}
```

Response:
```json
{
  "room_name": "vrd-session-abc123",
  "token": "eyJhbGc...",
  "server_url": "wss://..."
}
```

### `GET /rooms`
List active rooms (debugging)

## How It Works

1. Frontend calls `/connect` endpoint
2. API creates LiveKit room and returns token
3. Frontend connects to LiveKit room using token
4. Agent worker automatically joins room
5. Agent uses Cartesia for STT/TTS and Gemini for conversation
6. Transcripts automatically stream to frontend via LiveKit events

## Environment Variable Access in Python

Railway injects environment variables at runtime. Access them with:

```python
import os

# Railway automatically provides PORT
port = os.getenv("PORT", 8000)

# Your custom variables
livekit_url = os.getenv("LIVEKIT_URL")
gemini_key = os.getenv("GEMINI_API_KEY")
```

## Troubleshooting

### Agent not connecting
- Check `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- Ensure agent worker service is running
- Check Railway logs for errors

### No transcripts appearing
- Verify `sync_transcription=True` in agent.py
- Check frontend is subscribed to `TranscriptionReceived` events

### Audio not playing
- Check `CARTESIA_API_KEY` and `CARTESIA_VOICE_ID`
- Verify Cartesia voice ID is valid

## References

- [LiveKit Agents Documentation](https://docs.livekit.io/agents/build/)
- [Cartesia Plugin](https://docs.livekit.io/agents/models/tts/plugins/cartesia/)
- [Railway Environment Variables](https://docs.railway.app/guides/variables)
