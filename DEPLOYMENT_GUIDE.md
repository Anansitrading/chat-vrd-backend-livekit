# Deployment Guide - LiveKit Voice Agent Backend

## Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `chat-vrd-backend-livekit`
3. Description: "LiveKit voice agent backend for Kijko VRD Assistant"
4. Set to Public or Private
5. **DO NOT** initialize with README, .gitignore, or license (we already have these)
6. Click "Create repository"

## Step 2: Push Code to GitHub

```bash
cd /home/david/Projects/chat-vrd-backend-livekit

# Add remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/chat-vrd-backend-livekit.git

# Rename branch to main (if needed)
git branch -M main

# Push code
git push -u origin main
```

## Step 3: Set Up LiveKit Cloud

1. Go to https://cloud.livekit.io
2. Create account or sign in
3. Create a new project (e.g., "kijko-voice-agent")
4. Copy these credentials:
   - **WebSocket URL**: `wss://your-project.livekit.cloud`
   - **API Key**: `APIxxxxxxxxxxxxxxx`
   - **API Secret**: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Step 4: Set Up Cartesia

1. Go to https://cartesia.ai
2. Create account or sign in
3. Get API key from dashboard
4. Browse voice library and copy a voice ID (or use default: `694f9389-aac1-45b6-b726-9d9369183238`)

## Step 5: Get Gemini API Key

1. Go to https://ai.google.dev
2. Sign in with Google account
3. Click "Get API Key"
4. Create new key or use existing
5. Copy API key

## Step 6: Deploy to Railway (Service 1: API Server)

1. Go to https://railway.app
2. Click "New Project" → "Deploy from GitHub repo"
3. Connect GitHub and select `chat-vrd-backend-livekit`
4. Railway will detect the repository

### Configure API Service:

1. In Railway dashboard, click on your service
2. Go to "Settings" tab:
   - **Service Name**: `kijko-voice-api`
   - **Dockerfile Path**: `Dockerfile.api`
   - **Port**: Railway auto-detects from `PORT` env var
   
3. Go to "Variables" tab and add:
   ```
   LIVEKIT_URL=wss://your-project.livekit.cloud
   LIVEKIT_API_KEY=your_livekit_api_key
   LIVEKIT_API_SECRET=your_livekit_api_secret
   CARTESIA_API_KEY=your_cartesia_key
   CARTESIA_VOICE_ID=694f9389-aac1-45b6-b726-9d9369183238
   GEMINI_API_KEY=your_gemini_key
   ```
   
   **Note**: Railway automatically provides `PORT` variable.

4. Click "Deploy"
5. Once deployed, copy the public URL (e.g., `https://kijko-voice-api.railway.app`)

## Step 7: Deploy to Railway (Service 2: Agent Worker)

1. In the same Railway project, click "+ New"
2. Select "GitHub Repo" again
3. Choose `chat-vrd-backend-livekit` (same repo)
4. This creates a second service

### Configure Agent Service:

1. Click on the new service
2. Go to "Settings" tab:
   - **Service Name**: `kijko-voice-agent`
   - **Dockerfile Path**: `Dockerfile.agent`
   - **No port needed** (agent doesn't expose HTTP)
   
3. Go to "Variables" tab and add (same as API service):
   ```
   LIVEKIT_URL=wss://your-project.livekit.cloud
   LIVEKIT_API_KEY=your_livekit_api_key
   LIVEKIT_API_SECRET=your_livekit_api_secret
   CARTESIA_API_KEY=your_cartesia_key
   CARTESIA_VOICE_ID=694f9389-aac1-45b6-b726-9d9369183238
   GEMINI_API_KEY=your_gemini_key
   ```

4. Click "Deploy"

## Step 8: Verify Deployment

### Test API Service:

```bash
# Replace with your Railway URL
curl https://kijko-voice-api.railway.app/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "kijko-voice-agent-api",
  "livekit_url": true
}
```

### Check Logs:

1. **API Service Logs**:
   - Go to Railway dashboard → API service
   - Click "Deployments" → Latest deployment → "View Logs"
   - Should see: "Application startup complete"

2. **Agent Service Logs**:
   - Go to Railway dashboard → Agent service
   - Click "Deployments" → Latest deployment → "View Logs"
   - Should see: "Agent worker started" or similar

## Step 9: Update Frontend

Copy the API service URL and add it to your frontend's Vercel environment variables:

```
VITE_BACKEND_URL=https://kijko-voice-api.railway.app
```

(See frontend deployment guide for details)

## Troubleshooting

### API Service Issues

**Problem**: Health check returns 404
- **Solution**: Check Dockerfile.api path in Railway settings
- **Verify**: PORT environment variable is set

**Problem**: CORS errors
- **Solution**: Update `allow_origins` in api.py to include your frontend URL
- Redeploy after changes

### Agent Service Issues

**Problem**: Agent not joining rooms
- **Solution**: Check LIVEKIT_URL, API_KEY, API_SECRET are correct
- **Verify**: All three values match your LiveKit Cloud credentials

**Problem**: No audio output
- **Solution**: Verify CARTESIA_API_KEY is valid
- **Check**: Voice ID exists in Cartesia dashboard

**Problem**: No responses from LLM
- **Solution**: Check GEMINI_API_KEY is valid
- **Verify**: API key has permissions for Gemini 2.0

### Logs to Check

```bash
# View API logs
railway logs --service kijko-voice-api

# View Agent logs
railway logs --service kijko-voice-agent
```

## Updating Deployment

```bash
# Make changes locally
git add .
git commit -m "Update: description of changes"
git push

# Railway auto-deploys on push
```

## Environment Variable Management in Railway

Railway stores environment variables securely and injects them at runtime. Access them in Python with:

```python
import os

value = os.getenv("VARIABLE_NAME")
# OR with default
value = os.getenv("VARIABLE_NAME", "default_value")
```

**Important**: Railway provides these special variables automatically:
- `PORT` - The port your service should listen on
- `RAILWAY_ENVIRONMENT` - Current environment (production/staging)
- `RAILWAY_SERVICE_NAME` - Name of the service

## Cost Estimates

- **Railway**: ~$5-20/month depending on usage
- **LiveKit Cloud**: Free tier (50GB/month), then ~$0.5/GB
- **Cartesia**: Pay-per-use, ~$0.03/minute
- **Gemini API**: Free tier generous, then ~$0.05/1K requests

## Security Best Practices

1. ✅ Never commit `.env` files to git
2. ✅ Use Railway's environment variables for secrets
3. ✅ Rotate API keys periodically
4. ✅ Monitor usage in each service dashboard
5. ✅ Set up budget alerts in Railway

## Next Steps

1. Deploy frontend to Vercel (see frontend deployment guide)
2. Test end-to-end voice conversation
3. Monitor logs for errors
4. Set up alerts in Railway dashboard
