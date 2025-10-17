import sentry_sdk
import os
import asyncio
import json
from livekit import agents
from livekit.agents import Agent, AgentSession, JobContext, RoomInputOptions, RoomOutputOptions
from livekit.plugins import google, cartesia
from google.genai import types
from prompts import get_vrd_system_prompt
from loguru import logger

# VRD State Management
class VRDState:
    """Tracks the current VRD (Video Requirements Document) state for the session"""
    def __init__(self):
        self.project_name = ""
        self.target_audience = ""
        self.video_length = ""
        self.style = ""
        self.tone = ""
        self.budget = ""
        self.timeline = ""
        self.key_messages = []
        self.sections = []
        self.technical_requirements = {}
    
    def to_dict(self):
        """Convert to camelCase for frontend"""
        return {
            "projectInformation": {
                "projectTitle": self.project_name
            },
            "purposeAndBackground": {
                "projectContext": "",
                "currentChallenges": ""
            },
            "targetAudience": {
                "demographics": self.target_audience
            },
            "keyMessageAndCTA": {
                "coreMessage": "",
                "supportingMessages": self.key_messages
            },
            "styleFormAndMoodboard": {
                "videoStyle": [],
                "toneMood": []
            }
        }
    
    def update_from_dict(self, updates: dict):
        """Update VRD state from frontend updates (camelCase → snake_case)"""
        if "projectInformation" in updates and "projectTitle" in updates["projectInformation"]:
            self.project_name = updates["projectInformation"]["projectTitle"]
        if "targetAudience" in updates and "demographics" in updates["targetAudience"]:
            self.target_audience = updates["targetAudience"]["demographics"]
        # Add more field mappings as needed

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
        
        # Initialize VRD state for this session
        vrd_state = VRDState()
        logger.info("📝 VRD state initialized")
        
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
        
        # Helper function to send VRD updates to frontend
        async def send_vrd_update(updates: dict):
            """Send VRD updates to frontend via data channel"""
            try:
                message = json.dumps({
                    "type": "vrd-agent-update",
                    "updates": updates,
                    "timestamp": asyncio.get_event_loop().time()
                })
                
                await ctx.room.local_participant.publish_data(
                    message.encode('utf-8'),
                    reliable=True,
                    topic='vrd-update'
                )
                
                logger.info(f"✅ Sent VRD update to frontend: {updates}")
            except Exception as e:
                logger.error(f"Failed to send VRD update: {e}")
                sentry_sdk.capture_exception(e)
        
        # Add handler for text messages and VRD updates
        @ctx.room.on("data_received")
        def on_data_received(packet):
            logger.info(f"📥 RAW DATA RECEIVED - Packet: {packet}")
            try:
                topic = packet.topic if hasattr(packet, 'topic') else 'unknown'
                participant = packet.participant if hasattr(packet, 'participant') else 'unknown'
                data = packet.data
                logger.info(f"📥 Topic: {topic}, From: {participant}, Data: {data[:100]}")
                
                # Handle VRD updates from user
                if topic == 'vrd-update':
                    message = json.loads(data.decode('utf-8'))
                    
                    if message.get('type') == 'vrd-user-update' and message.get('updates'):
                        logger.info(f"📝 VRD USER UPDATE: {message['updates']}")
                        vrd_state.update_from_dict(message['updates'])
                        
                        # Inform LLM about the update
                        update_fields = ", ".join([str(k) for k in message['updates'].keys()])
                        asyncio.create_task(session.generate_reply(
                            user_input=f"User updated VRD fields: {update_fields}. Acknowledge the update briefly and continue the conversation naturally."
                        ))
                
                # Handle text chat messages
                elif topic == 'lk.chat':
                    text = data.decode('utf-8')
                    logger.info(f"💬 TEXT MESSAGE DECODED: {text}")
                    logger.info(f"🤖 Generating reply for text input...")
                    
                    # CRITICAL: Must manually trigger reply for text input
                    asyncio.create_task(session.generate_reply(user_input=text))
                    
            except Exception as e:
                logger.error(f"Failed to process data packet: {e}")
                sentry_sdk.capture_exception(e)
        
        # Store send_vrd_update function for agent access
        agent._send_vrd_update = send_vrd_update
        agent._vrd_state = vrd_state
        
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
        await session.generate_reply(
            instructions="Greet the user warmly and ask about their video project. Let them know they can speak or type their responses."
        )
        
        logger.info("Agent started: Gemini Live (audio+text→LLM+search) → Cartesia TTS (text→audio)")
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
