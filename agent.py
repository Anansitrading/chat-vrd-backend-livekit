import sentry_sdk
import os
import asyncio
import json
from livekit import agents
from livekit.agents import Agent, AgentSession, JobContext, RoomInputOptions, RoomOutputOptions
from livekit.plugins import deepgram, cartesia
from prompts import get_vrd_system_prompt
from loguru import logger
from langgraph_client import call_langgraph
from voices import LANGUAGE_TO_VOICE, DEFAULT_LANGUAGE, DEFAULT_VOICE_ID


class LangGraphAdapterAgent(Agent):
    def __init__(self, session_id: str) -> None:
        super().__init__(instructions=get_vrd_system_prompt())
        self.session_id = session_id
        self.language_code: str | None = None

    async def _process_and_respond(
        self,
        user_text: str,
        language: str | None,
        session: AgentSession,
        input_type: str,
    ) -> None:
        lang = language or self.language_code or DEFAULT_LANGUAGE
        self.language_code = lang

        room = session.room
        local_participant = room.local_participant

        user_payload = json.dumps(
            {"text": user_text, "speaker": "user", "language": lang}
        ).encode("utf-8")
        await local_participant.publish_data(
            payload=user_payload,
            reliable=True,
            topic="lk.transcription",
        )

        reply_text = await call_langgraph(
            message=user_text,
            session_id=self.session_id,
            language=lang,
            input_type=input_type,
        )

        agent_payload = json.dumps(
            {"text": reply_text, "speaker": "agent", "language": lang}
        ).encode("utf-8")
        await local_participant.publish_data(
            payload=agent_payload,
            reliable=True,
            topic="lk.transcription",
        )

        voice_id = LANGUAGE_TO_VOICE.get(lang, DEFAULT_VOICE_ID)
        tts = session.tts
        if tts is not None and hasattr(tts, "update_options"):
            tts.update_options(voice=voice_id, language=lang)

        session.say(
            reply_text,
            allow_interruptions=True,
            add_to_chat_ctx=True,
        )

    async def on_turn(self, turn, session: AgentSession) -> None:
        text = getattr(turn, "transcript", "") or getattr(turn, "text", "")
        if not text:
            return
        language = getattr(turn, "language", None)
        await self._process_and_respond(
            user_text=text,
            language=language,
            session=session,
            input_type="voice",
        )

    async def handle_chat_message(self, text: str, session: AgentSession) -> None:
        language = self.language_code or DEFAULT_LANGUAGE
        await self._process_and_respond(
            user_text=text,
            language=language,
            session=session,
            input_type="text",
        )


async def entrypoint(ctx: JobContext):
    """
    Main agent entrypoint - spawned for each new LiveKit room via WebRTC.
    Flow: Gemini Live (audio/text in, LLM, Google Search) → TEXT → Cartesia TTS → audio out
    Supports both audio and text input from users
    """
    # Initialize Sentry INSIDE async function (critical for asyncio compatibility)
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        environment=os.getenv("RAILWAY_ENVIRONMENT", "production"),
        release=os.getenv("RAILWAY_GIT_COMMIT_SHA"),
    )
    
    # Set Sentry context tags
    sentry_sdk.set_tag("room_name", ctx.room.name)
    sentry_sdk.set_context("livekit", {
        "room": ctx.room.name,
        "agent": "kijko_vrd_assistant"
    })
    
    try:
        logger.info(f"Agent connecting to room: {ctx.room.name}")
        await ctx.connect()
        
        # Configure AgentSession: Gemini Live for audio/text input + TEXT output, Cartesia for TTS
        session = AgentSession(
            stt=deepgram.STT(
                model="nova-3",
                language="multi",
            ),
            tts=cartesia.TTS(
                api_key=os.getenv("CARTESIA_API_KEY"),
                model="sonic-2",
                voice=DEFAULT_VOICE_ID,
                language="en",
            ),
            llm=None,
        )
        
        # Create Agent with instructions
        agent = LangGraphAdapterAgent(session_id=ctx.room.name)
        
        # Add handler for text messages - must manually call generate_reply
        @ctx.room.on("data_received")
        def on_data_received(packet):
            logger.info(f"📥 RAW DATA RECEIVED - Packet: {packet}")
            try:
                topic = packet.topic if hasattr(packet, 'topic') else 'unknown'
                participant = packet.participant if hasattr(packet, 'participant') else 'unknown'
                data = packet.data
                logger.info(f"📥 Topic: {topic}, From: {participant}, Data: {data[:100]}")
                
                if topic == 'lk.chat':
                    text = data.decode('utf-8')
                    logger.info(f"💬 TEXT MESSAGE DECODED: {text}")
                    logger.info("🤖 Routing text input through LangGraph adapter...")
                    
                    # CRITICAL: Must manually trigger reply for text input
                    asyncio.create_task(agent.handle_chat_message(text, session))
                    
            except Exception as e:
                logger.error(f"Failed to process data packet: {e}")
                sentry_sdk.capture_exception(e)
        
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
        
        logger.info("📡 Session started - listening for text on lk.chat topic")
        
        # Optional: Add conversation item listener to log text interactions
        @session.on("conversation_item_added")
        def on_conversation_item(item):
            logger.info(f"🔔 CONVERSATION ITEM ADDED EVENT")
            if hasattr(item, 'content'):
                logger.info(f"💬 Content: {item.content[:100]}...")
        
        # Generate initial greeting
        logger.info(
            "Initial greeting will be generated by LangGraph on first user input."
        )
        
        logger.info("Agent started: Deepgram STT → LangGraph → Cartesia TTS")
        logger.info("✅ Text input enabled via lk.chat topic - users can type or speak!")
        
    except Exception as e:
        logger.error(f"Agent error: {e}")
        sentry_sdk.capture_exception(e)
        raise


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="kijko_vrd_assistant"
        )
    )
