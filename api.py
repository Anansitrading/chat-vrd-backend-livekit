from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
from pydantic import BaseModel
import os
import uuid
from loguru import logger

app = FastAPI(title="Kijko Voice Agent API")

# CORS for Vercel frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://chat-vrd-livekit.vercel.app",  # New frontend
        "https://chat-vrd.vercel.app",          # Old frontend for comparison
        "http://localhost:3000",
        "http://localhost:5173"
    ],
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
        try:
            await livekit_api.room.create_dispatch(
                api.CreateRoomDispatchRequest(
                    room=room_name,
                    agent_name="kijko_vrd_assistant"  # Must match agent.py WorkerOptions
                )
            )
            logger.info(f"Agent dispatched to room: {room_name}")
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
            "server_url": os.getenv("LIVEKIT_URL")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
