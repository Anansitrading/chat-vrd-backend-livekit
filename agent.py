import os
from livekit import agents
from livekit.agents import AgentSession, JobContext
from livekit.plugins import cartesia, google
from prompts import get_vrd_system_prompt
from loguru import logger

async def entrypoint(ctx: JobContext):
    """
    Main agent entrypoint - spawned for each new LiveKit room.
    Flow: Cartesia STT → Gemini 2.5 Flash (text) + Google Search → Cartesia TTS
    """
    logger.info(f"Agent connecting to room: {ctx.room.name}")
    await ctx.connect()
    
    # Configure AgentSession with Cartesia STT/TTS + Gemini 2.5 Flash text LLM
    session = AgentSession(
        # Cartesia STT (Speech-to-Text)
        stt=cartesia.STT(
            model="ink-whisper",
            language="en"
        ),
        
        # Gemini 2.5 Flash LLM (text-only) with Google Search grounding
        llm=google.LLM(
            model="gemini-2.5-flash",
            temperature=0.7,
            google_search_tool=True,  # Enable Google Search grounding
        ),
        
        # Cartesia TTS (Text-to-Speech)
        tts=cartesia.TTS(
            model="sonic-2",
            voice=os.getenv("CARTESIA_VOICE_ID", "694f9389-aac1-45b6-b726-9d9369183238"),
            language="en"
        ),
    )
    
    # Start session with mobile-optimized settings
    await session.start(
        room=ctx.room,
        participant_identity="kijko_assistant",
    )
    
    # Send initial greeting with system prompt
    await session.generate_reply(
        instructions=get_vrd_system_prompt()
    )
    
    logger.info("Agent session started: Cartesia STT → Gemini 2.5 Flash + Search → Cartesia TTS")


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="kijko_vrd_assistant"
        )
    )
