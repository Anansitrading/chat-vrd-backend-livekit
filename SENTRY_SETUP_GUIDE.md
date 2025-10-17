# Sentry Setup Guide for LiveKit Voice Agent Backend

## Overview

Sentry is now integrated into your LiveKit voice agent backend to track:
- **API Service** (api.py): HTTP requests, performance, errors
- **Agent Worker** (agent.py): Room operations, model interactions, agent lifecycle

## Quick Start

### 1. Create Sentry Account & Project

1. Go to [sentry.io](https://sentry.io) and create a free account
2. Create a new project:
   - Platform: **Python**
   - Integration: **FastAPI**
3. Copy your **DSN** (looks like: `https://abc123@o123456.ingest.sentry.io/789`)

### 2. Configure Railway Environment Variables

Add the following to **BOTH** Railway services (API + Agent Worker):

```bash
SENTRY_DSN=https://your-key@o0.ingest.sentry.io/your-project-id
RAILWAY_ENVIRONMENT=production
```

**Note:** `RAILWAY_GIT_COMMIT_SHA` is automatically set by Railway for release tracking.

### 3. Deploy to Railway

After adding the environment variable:

```bash
# Commit your changes
git add .
git commit -m "Add Sentry monitoring"
git push

# Railway will automatically deploy both services
```

### 4. Test Sentry Integration

Once deployed, test error tracking:

```bash
# Visit the debug endpoint (replace with your Railway API URL)
curl https://your-api.railway.app/sentry-debug
```

Within 30 seconds, you should see the error in your Sentry dashboard.

## What Gets Tracked

### API Service (api.py)
- ✅ All HTTP requests (endpoint, method, status code, duration)
- ✅ Middleware performance (CORS, auth, routing)
- ✅ LiveKit room operations (creation, token generation)
- ✅ Unhandled exceptions (5xx errors)
- ✅ Request metadata (IP, user agent, headers)

### Agent Worker (agent.py)
- ✅ Agent lifecycle events (connect, disconnect, errors)
- ✅ LiveKit room context (room name, agent identity)
- ✅ Gemini API interactions (latency, errors)
- ✅ Cartesia TTS requests (duration, failures)
- ✅ All logger.error() calls via loguru integration
- ✅ Text input processing errors

## Viewing Data in Sentry

### Performance Dashboard
1. Go to **Performance** tab
2. View:
   - API endpoint response times (P50, P75, P95, P99)
   - Throughput (requests/minute)
   - Error rates by endpoint
   - Slowest transactions

### Issues Dashboard
1. Go to **Issues** tab
2. See:
   - **Grouped errors**: Similar errors combined automatically
   - **Stack traces**: Full Python traceback
   - **Breadcrumbs**: Logger calls before the error
   - **User impact**: How many users affected
   - **Room context**: Which LiveKit room caused the error

### Releases
1. Go to **Releases** tab
2. Track which Railway deployment caused issues
3. Compare performance across Git commits

## Production Best Practices

### Adjust Sample Rates (Recommended for High Traffic)

Once you have significant traffic, reduce sample rates to save costs:

**In api.py:**
```python
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    traces_sample_rate=0.1,  # Sample 10% of transactions
    profiles_sample_rate=0.1,  # Profile 10% of sessions
)
```

**In agent.py:**
```python
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    traces_sample_rate=0.1,  # Sample 10% of agent sessions
    profiles_sample_rate=0.1,
)
```

### Filter Sensitive Data

If you need to exclude PII (personally identifiable information):

```python
def filter_sensitive_data(event, hint):
    # Remove sensitive fields
    if 'request' in event:
        if 'headers' in event['request']:
            event['request']['headers'].pop('Authorization', None)
            event['request']['headers'].pop('Cookie', None)
    return event

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    send_default_pii=False,  # Don't send IP addresses, headers
    before_send=filter_sensitive_data,
)
```

### Set Up Alerts

In Sentry dashboard:

1. Go to **Project Settings → Alerts**
2. Create alerts for:
   - **Error Rate**: `> 5 errors/minute`
   - **Performance**: `P95 response time > 2 seconds`
   - **Agent Failures**: `Failed agent connections > 3/hour`

Sentry will send email/Slack notifications when thresholds are exceeded.

## Monitoring Agent-Specific Events

The agent worker includes LiveKit-specific context in Sentry errors:

- **Room Name**: `ctx.room.name`
- **Agent Name**: `kijko_vrd_assistant`

This appears in Sentry under **Additional Data → livekit** for each error.

## Common Issues

### Sentry not tracking errors

1. **Check DSN is set**: `echo $SENTRY_DSN` in Railway logs
2. **Verify deployment**: Check Railway build logs for sentry-sdk installation
3. **Test endpoint**: Visit `/sentry-debug` to trigger a test error
4. **Check Sentry project**: Ensure you're viewing the correct Sentry project

### High data usage

1. **Reduce sample rates**: Set `traces_sample_rate=0.1` (10%)
2. **Filter noisy errors**: Use `before_send` to ignore expected errors
3. **Disable profiling**: Set `profiles_sample_rate=0`

### Missing agent errors

1. **Check agent worker logs**: Agent worker is a separate Railway service
2. **Verify SENTRY_DSN**: Must be set on **both** API and Agent Worker services
3. **Check agent startup**: Look for Sentry initialization in Railway logs

## Local Development

To use Sentry locally:

```bash
# Create .env file with your Sentry DSN
echo "SENTRY_DSN=https://your-key@o0.ingest.sentry.io/your-project-id" >> .env
echo "RAILWAY_ENVIRONMENT=development" >> .env

# Run API service
python api.py

# Run agent worker (in separate terminal)
python agent.py
```

Errors will appear in your Sentry project tagged as `environment: development`.

## Cost Management

Sentry free tier includes:
- **5,000 errors/month**
- **10,000 performance events/month**
- **500 MB attachments**

To stay within limits:
- Use `traces_sample_rate=0.1` (10% sampling)
- Filter out noisy errors
- Disable profiling if not needed

## Resources

- [Sentry Python Docs](https://docs.sentry.io/platforms/python/)
- [Sentry FastAPI Integration](https://docs.sentry.io/platforms/python/integrations/fastapi/)
- [Sentry Agent Monitoring](https://blog.sentry.io/sentrys-updated-agent-monitoring/)
- [Railway Environment Variables](https://docs.railway.app/deploy/variables)

## Support

If you encounter issues:
1. Check Sentry dashboard for error details
2. Review Railway logs for both services
3. Test with `/sentry-debug` endpoint
4. Verify environment variables are set correctly
