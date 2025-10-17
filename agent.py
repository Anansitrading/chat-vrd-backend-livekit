import os
from livekit import agents
from livekit.agents import Agent, AgentSession, JobContext
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
            model="gemini-2.5-flash-live-preview",
            modalities=[types.Modality.TEXT],  # TEXT output only (no audio from Gemini)
            temperature=0.7,
            api_key=os.getenv("GEMINI_API_KEY"),  # Explicitly pass API key
            # Enable Google Search grounding
            _gemini_tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
        
        # Cartesia TTS: TEXT IN, Audio OUT
        tts=cartesia.TTS(
            api_key=os.getenv("CARTESIA_API_KEY"),
            model="sonic-2",
            voice=os.getenv("CARTESIA_VOICE_ID", "694f9389-aac1-45b6-b726-9d9369183238"),
            language="en",
        ),
    )
    
    # Create Agent with instructions
    agent = Agent(instructions=get_vrd_system_prompt())
    
    # Register data channel handler for text messages
    @ctx.room.on("data_received")
    def on_data_received(data: bytes, participant, topic: str):
        if topic == 'lk.chat':
            try:
                text = data.decode('utf-8')
                logger.info(f"📨 Received text from {participant.identity}: {text}")
                
                # Generate reply using text input (correct parameter is user_input, not content)
                import asyncio
                asyncio.create_task(session.generate_reply(user_input=text))
                logger.info(f"✅ Generating reply for text: {text}")
            except Exception as e:
                logger.error(f"Error handling text message: {e}")
    
    # Start session - connects to LiveKit room via WebRTC
    await session.start(
        agent=agent,
        room=ctx.room,
    )
    
    # Generate initial greeting and begin listening for user input
    await session.generate_reply(
        instructions="Greet the user warmly and ask about their video project."
    )
    
    logger.info("Agent started: Gemini Live (audio→text+search) → Cartesia TTS (text→audio) + text input handler")


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="kijko_vrd_assistant"
        )
    )
