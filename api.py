import sentry_sdk
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
from pydantic import BaseModel
import uuid
from loguru import logger

# Initialize Sentry FIRST - before creating FastAPI app
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    
    # Performance monitoring
    traces_sample_rate=1.0,  # Capture 100% of transactions (adjust in production: 0.1 = 10%)
    
    # Enable logs
    enable_logs=True,
    
    # Session tracking
    profiles_sample_rate=1.0,  # Profile performance
    
    # Send user info (IP, headers) for better debugging
    send_default_pii=True,
    
    # Environment tag
    environment=os.getenv("RAILWAY_ENVIRONMENT", "production"),
    
    # Release tracking (optional)
    release=os.getenv("RAILWAY_GIT_COMMIT_SHA"),
)

app = FastAPI(title="Kijko Voice Agent API")

# CORS for Vercel frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://chat-vrd-livekit.vercel.app",  # Production frontend
        "https://chat-vrd.vercel.app",          # Old frontend for comparison
        "http://localhost:3000",
        "http://localhost:5173"
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",  # Allow all Vercel preview deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize LiveKit API client
livekit_api = api.LiveKitAPI(
    url=os.getenv("LIVEKIT_URL"),
    api_key=os.getenv("LIVEKIT_API_KEY"),
    api_secret=os.getenv("LIVEKIT_API_SECRET"),
)


class ConnectRequest(BaseModel):
    language: str = "en"
    session_id: str | None = None


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "kijko-voice-agent-api",
        "livekit_url": os.getenv("LIVEKIT_URL") is not None,
    }


@app.post("/connect")
async def connect(request: ConnectRequest):
    """
    Create LiveKit room and return client token for WebRTC connection.
    This is called by the frontend when user clicks the mic button.
    """
    
    # Generate unique room name
    room_name = request.session_id or f"vrd-session-{uuid.uuid4().hex[:8]}"
    
    logger.info(f"Creating LiveKit room: {room_name}")
    
    try:
        # Create room with auto-cleanup settings
        room = await livekit_api.room.create_room(
            api.CreateRoomRequest(
                name=room_name,
                empty_timeout=300,  # Auto-close after 5min empty
                max_participants=2   # User + agent only
            )
        )
        
        logger.info(f"Room created: {room.name} (SID: {room.sid})")
        
        # Dispatch agent to this room
        agent_identity = None  # Will be set by LiveKit as 'agent-{random_id}'
        try:
            dispatch = await livekit_api.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    room=room_name,
                    agent_name="kijko_vrd_assistant"  # Must match agent.py WorkerOptions
                )
            )
            # Note: LiveKit auto-generates agent identity as 'agent-{random_id}'
            # We'll return the pattern to frontend for reliable identification
            agent_identity = f"agent-"  # Prefix that frontend can match against
            logger.info(f"Agent dispatched to room: {room_name} (Dispatch ID: {dispatch.id})")
        except Exception as dispatch_error:
            logger.error(f"Failed to dispatch agent: {dispatch_error}")
            # Continue anyway - room is created
        
        # Generate client token for the user
        token = api.AccessToken(
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET")
        )
        token.with_identity("user").with_name("User").with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True
            )
        )
        
        return {
            "room_name": room.name,
            "token": token.to_jwt(),
            "server_url": os.getenv("LIVEKIT_URL"),
            "agent_identity_prefix": agent_identity  # Frontend uses this to identify agent
        }
        
    except Exception as e:
        logger.error(f"Error creating room: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rooms")
async def list_rooms():
    """List active rooms (for debugging/monitoring)"""
    try:
        rooms = await livekit_api.room.list_rooms(api.ListRoomsRequest())
        return {
            "rooms": [
                {
                    "name": room.name,
                    "sid": room.sid,
                    "num_participants": room.num_participants,
                    "creation_time": room.creation_time
                }
                for room in rooms
            ]
        }
    except Exception as e:
        logger.error(f"Error listing rooms: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sentry-debug")
async def trigger_error():
    """
    Debug endpoint to test Sentry error tracking.
    Visit: https://your-api.railway.app/sentry-debug
    Check Sentry dashboard within ~30 seconds to see the error.
    """
    division_by_zero = 1 / 0


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
