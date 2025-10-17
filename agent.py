import os
import asyncio
from livekit import agents
from livekit.agents import Agent, AgentSession, JobContext
from livekit.agents.voice import RoomInputOptions, RoomOutputOptions
from livekit.plugins import google, cartesia
from google.genai import types
from prompts import get_vrd_system_prompt
from loguru import logger

async def entrypoint(ctx: JobContext):
    """
    Main agent entrypoint - spawned for each new LiveKit room via WebRTC.
    Flow: Gemini Live (audio/text in, LLM, Google Search) → TEXT → Cartesia TTS → audio out
    Supports both audio and text input from users
    """
    logger.info(f"Agent connecting to room: {ctx.room.name}")
    await ctx.connect()
    
    # Configure AgentSession: Gemini Live for audio/text input + TEXT output, Cartesia for TTS
    session = AgentSession(
        # Gemini Live 2.5: Audio/Text IN, TEXT OUT (Gemini Live DOES support text input!)
        llm=google.beta.realtime.RealtimeModel(
            model="gemini-2.5-flash-live-preview",
            modalities=[types.Modality.TEXT],  # TEXT output (Cartesia handles TTS)
            temperature=0.7,
            api_key=os.getenv("GEMINI_API_KEY"),
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
    
    # Start session with text and audio input enabled
    await session.start(
        agent=agent,
        room=ctx.room,
        # Enable both text and audio input
        room_input_options=RoomInputOptions(
            text_enabled=True,  # Enable text input via lk.chat topic
            audio_enabled=True,  # Keep audio input enabled too
        ),
        # Enable text transcription output
        room_output_options=RoomOutputOptions(
            transcription_enabled=True,  # Send transcriptions to frontend
            audio_enabled=True,  # Keep audio output enabled
        ),
    )
    
    # The session automatically monitors 'lk.chat' text stream topic when text_enabled=True
    # No need for manual data_received handler - it's handled internally by AgentSession
    
    # Optional: Add conversation item listener to log text interactions
    @session.on("conversation_item_added")
    def on_conversation_item(item):
        if hasattr(item, 'content'):
            logger.info(f"💬 Conversation item added: {item.content[:100]}...")
    
    # Generate initial greeting
    await session.generate_reply(
        instructions="Greet the user warmly and ask about their video project. Let them know they can speak or type their responses."
    )
    
    logger.info("Agent started: Gemini Live (audio+text→LLM+search) → Cartesia TTS (text→audio)")
    logger.info("✅ Text input enabled via lk.chat topic - users can type or speak!")


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="kijko_vrd_assistant"
        )
    )
