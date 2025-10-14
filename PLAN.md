# Backend Agent Update Plan

## Goal
Update `agent.py` to use Gemini Live 2.5 Flash for audio input (STT + language detection + Google Search) → TEXT output → Cartesia TTS for audio output.

## Current Issues
1. Current code uses `google.beta.realtime.RealtimeModel` with `types.Modality.TEXT` and `types.Tool`
2. These imports appear to be from `google.genai.types`, not from LiveKit plugins
3. Need to verify the correct LiveKit plugin syntax for Google Gemini integration

## Research Findings

### From LiveKit Documentation (docs.livekit.io/agents/models/realtime/plugins/gemini/)
```python
from livekit.plugins import google
from google.genai import types

session = AgentSession(
    llm=google.beta.realtime.RealtimeModel(
        model="gemini-2.5-flash-native-audio-preview-09-2025",
        modalities=[types.Modality.TEXT],  # TEXT output only
        instructions="...",
        _gemini_tools=[types.Tool(google_search=types.GoogleSearch())],
    ),
)
```

### From Perplexity Research
- Model name: `gemini-2.5-flash-native-audio-preview-09-2025` (confirmed)
- Imports needed:
  - `from livekit.plugins import google`
  - `from google.genai import types`
- Google Search grounding syntax: `_gemini_tools=[types.Tool(google_search=types.GoogleSearch())]`

### From Exa Code Context
- LiveKit docs show `google.beta.realtime.RealtimeModel` exists
- Modality import: `from google.genai import types` then use `types.Modality.TEXT`

## Planned Code Changes

### 1. Imports Section
```python
import os
from livekit import agents
from livekit.agents import AgentSession, JobContext
from livekit.plugins import google, cartesia
from google.genai import types  # For Modality.TEXT and Tool/GoogleSearch
from prompts import get_vrd_system_prompt
from loguru import logger
```

### 2. Agent Configuration
```python
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
            model="gemini-2.5-flash-native-audio-preview-09-2025",
            modalities=[types.Modality.TEXT],  # TEXT output only (no audio from Gemini)
            temperature=0.7,
            instructions=get_vrd_system_prompt(),
            # Enable Google Search grounding
            _gemini_tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
        
        # Cartesia TTS: TEXT IN, Audio OUT
        tts=cartesia.TTS(
            model="sonic-multilingual",
            voice=os.getenv("CARTESIA_VOICE_ID", "694f9389-aac1-45b6-b726-9d9369183238"),
            language="auto",  # Auto-detect language from Gemini's text output
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
        agents.WorkerOptions(entrypoint_fnc=entrypoint, agent_name="kijko_vrd_assistant")
    )
```

### 3. Requirements.txt (Already Updated)
```txt
# Core FastAPI
fastapi==0.115.0
uvicorn[standard]==0.34.0
python-dotenv==1.0.0

# LiveKit with Cartesia and Google plugins
livekit==0.17.0
livekit-agents[cartesia]>=0.9.0
livekit-agents[google]>=1.2.0

# Gemini integration
google-genai>=0.8.0

# Logging
loguru==0.7.2
pydantic==2.10.0
```

## Environment Variables Required (Already Set on Railway)
- `LIVEKIT_URL` - LiveKit server URL
- `LIVEKIT_API_KEY` - LiveKit API key
- `LIVEKIT_API_SECRET` - LiveKit API secret
- `GOOGLE_API_KEY` or `GEMINI_API_KEY` - For Gemini Live API
- `CARTESIA_API_KEY` - For Cartesia TTS
- `CARTESIA_VOICE_ID` - Voice ID for Cartesia

## ✅ VERIFIED Information (User Confirmed)

1. **Model Name**: `gemini-2.5-flash-preview` ✅
   - Accepts audio input, outputs TEXT only (not audio)
   - Use with separate TTS (Cartesia) for audio output
   - Supports Google Search grounding via _gemini_tools

2. **Import Statement**: `from google.genai import types` ✅
   - Confirmed from user-provided example

3. **Google Search Grounding Syntax**: `_gemini_tools=[types.Tool(google_search=types.GoogleSearch())]` ✅
   - Confirmed from user-provided LiveKit implementation example

4. **RealtimeModel accepts `_gemini_tools` parameter**: YES ✅
   - Confirmed in user's example code

## ❓ Remaining Questions to Research

1. **Does Cartesia TTS have a `sonic-multilingual` model?**
   - Need to verify if it should be `sonic-2` with `language="auto"` or if `sonic-multilingual` exists
   - Check Cartesia documentation after September 2025

## Flow Architecture
```
User speaks (audio) 
  ↓ (WebRTC)
LiveKit Room
  ↓
Gemini Live 2.5 Flash (receives audio)
  ↓ (STT + language detection + Google Search grounding)
Gemini outputs TEXT response
  ↓
Cartesia TTS (receives text)
  ↓ (generates audio with language auto-detection)
Audio out
  ↓ (WebRTC)
User hears response
```

## Deployment Steps
1. Verify code with Perplexity
2. Update agent.py
3. Git commit and push
4. Railway auto-deploys
5. Test with frontend mic button

## Risks
- Incorrect import paths could cause runtime errors
- Wrong parameter names for Google Search grounding
- Model name mismatch
- Cartesia model name incorrect
