import os
from livekit import agents
from livekit.agents import AgentSession, JobContext
from livekit.plugins import google, cartesia
from google.genai import types
from prompts import get_vrd_system_prompt
from loguru import logger

async def entrypoint(ctx: JobContext):
    """
    Main agent entrypoint - spawned for each new LiveKit room via WebRTC.
    Flow: Gemini Live (audio in, STT, LLM, Google Search) → TEXT → Cartesia TTS → audio out
    """
    logger.info(f"Agent connecting to room: {ctx.room.name}")
    await ctx.connect()
    
    # Configure AgentSession: Gemini Live for audio input + TEXT output, Cartesia for TTS
    session = AgentSession(
        # Gemini Live 2.5: Audio IN (STT + language detection), TEXT OUT
        llm=google.beta.realtime.RealtimeModel(
            model="gemini-2.5-flash-preview",
            modalities=[types.Modality.TEXT],  # TEXT output only (no audio from Gemini)
            temperature=0.7,
            instructions=get_vrd_system_prompt(),
            # Enable Google Search grounding
            _gemini_tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
        
        # Cartesia TTS: TEXT IN, Audio OUT
        tts=cartesia.TTS(
            model="sonic-2",
            voice=os.getenv("CARTESIA_VOICE_ID", "694f9389-aac1-45b6-b726-9d9369183238"),
            language="auto",
        ),
    )
    
    # Start session - connects to LiveKit room via WebRTC
    await session.start(
        room=ctx.room,
        participant_identity="kijko_assistant",
    )
    
    logger.info("Agent started: Gemini Live (audio→text+search) → Cartesia TTS (text→audio)")


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="kijko_vrd_assistant"
        )
    )
