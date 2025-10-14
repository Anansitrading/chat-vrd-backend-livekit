import os
from livekit import agents, rtc
from livekit.agents import AgentSession, JobContext
from livekit.plugins import cartesia
from prompts import get_vrd_system_prompt
from loguru import logger

async def entrypoint(ctx: JobContext):
    """
    Main agent entrypoint - spawned for each new LiveKit room.
    Follows livekit-examples/cartesia-voice-agent pattern.
    """
    logger.info(f"Agent connecting to room: {ctx.room.name}")
    await ctx.connect()
    
    # Configure AgentSession with Cartesia STT/TTS + Gemini LLM
    session = AgentSession(
        # Cartesia STT (Speech-to-Text)
        stt=cartesia.STT(
            model="ink-whisper",
            language="en"  # Default language - Gemini will handle multilingual
        ),
        
        # Cartesia TTS (Text-to-Speech)
        tts=cartesia.TTS(
            model="sonic-2",
            voice=os.getenv("CARTESIA_VOICE_ID", "694f9389-aac1-45b6-b726-9d9369183238"),  # Default to a neutral voice
            language="en"
        ),
        
        # Gemini LLM via OpenAI-compatible API
        llm=agents.llm.LLM.with_openai(
            model="gemini-2.0-flash-exp",
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            temperature=0.7,
        ),
    )
    
    # Start session with mobile-optimized settings
    await session.start(
        room=ctx.room,
        participant_identity="kijko_assistant",
        room_output_options=agents.RoomOutputOptions(
            sync_transcription=True,  # Enable real-time transcript streaming
            audio_bitrate=32000,      # Mobile-optimized (lower = better compatibility)
            audio_codec="opus"        # Best mobile browser compatibility
        )
    )
    
    # Send initial greeting
    await session.generate_reply(
        instructions=get_vrd_system_prompt()
    )
    
    logger.info("Agent session started successfully")


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="kijko_vrd_assistant"
        )
    )
