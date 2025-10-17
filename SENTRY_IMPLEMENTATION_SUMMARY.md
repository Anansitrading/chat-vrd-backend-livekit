# Sentry Implementation Summary

## Changes Made

### 1. Dependencies (`requirements.txt`)
- ✅ Added `sentry-sdk[fastapi]==2.18.0`

### 2. API Service (`api.py`)
- ✅ Imported `sentry_sdk` at the top
- ✅ Initialized Sentry **before** creating FastAPI app with:
  - Performance monitoring (`traces_sample_rate=1.0`)
  - Log integration (`enable_logs=True`)
  - Session profiling (`profiles_sample_rate=1.0`)
  - PII tracking for debugging (`send_default_pii=True`)
  - Environment tagging (production/development)
  - Release tracking via Railway git commit SHA
- ✅ Added `/sentry-debug` endpoint for testing

### 3. Agent Worker (`agent.py`)
- ✅ Imported `sentry_sdk` at the top
- ✅ Initialized Sentry with same configuration as API
- ✅ Enabled continuous profiling for agent sessions
- ✅ Wrapped `entrypoint` function with Sentry scope containing:
  - Room name tag
  - LiveKit context (room + agent name)
  - Exception capture with automatic error reporting
- ✅ All agent errors now automatically reported to Sentry

### 4. Environment Configuration (`.env.example`)
- ✅ Added `SENTRY_DSN` variable
- ✅ Documented Railway auto-variables (`RAILWAY_ENVIRONMENT`, `RAILWAY_GIT_COMMIT_SHA`)

### 5. Documentation
- ✅ Created `SENTRY_SETUP_GUIDE.md` with:
  - Quick start instructions
  - Railway deployment steps
  - Testing procedures
  - Production best practices
  - Troubleshooting guide

## Next Steps

### 1. Create Sentry Project (5 minutes)
1. Go to [sentry.io](https://sentry.io)
2. Create account (free tier available)
3. Create new Python/FastAPI project
4. Copy your DSN (looks like: `https://abc123@o123456.ingest.sentry.io/789`)

### 2. Configure Railway (2 minutes)
Add to **BOTH** Railway services (API Service + Agent Worker):

```bash
SENTRY_DSN=https://your-key@o0.ingest.sentry.io/your-project-id
RAILWAY_ENVIRONMENT=production
```

### 3. Deploy & Test (5 minutes)
```bash
# Commit and push
git add .
git commit -m "Add Sentry monitoring"
git push

# Test error tracking (after deployment)
curl https://your-api.railway.app/sentry-debug

# Check Sentry dashboard within 30 seconds
```

## What You Get

### Real-Time Monitoring
- **API Performance**: Response times, throughput, error rates by endpoint
- **Agent Health**: Room connection success/failure, model latency
- **Error Tracking**: Stack traces, breadcrumbs, user impact analysis
- **Release Tracking**: Which Git commit introduced bugs

### Automatic Alerts
- Configure email/Slack alerts for:
  - Error spikes (> 5/minute)
  - Performance degradation (P95 > 2s)
  - Agent connection failures

### Debug Context
Every error includes:
- Full Python stack trace
- Request metadata (headers, IP, user agent)
- LiveKit room context (room name, agent ID)
- Logger breadcrumbs (what happened before the error)
- Environment info (Railway deployment SHA)

## Production Optimization (Optional)

Once you have traffic, reduce sample rates to save costs:

```python
# In api.py and agent.py
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    traces_sample_rate=0.1,  # 10% sampling instead of 100%
    profiles_sample_rate=0.1,
)
```

This reduces Sentry usage by 90% while still catching errors.

## Files Modified

```
chat-vrd-backend-livekit/
├── requirements.txt          # Added sentry-sdk[fastapi]
├── api.py                    # Sentry init + debug endpoint
├── agent.py                  # Sentry init + error capture
├── .env.example              # Added SENTRY_DSN
├── SENTRY_SETUP_GUIDE.md     # NEW: Comprehensive guide
└── SENTRY_IMPLEMENTATION_SUMMARY.md  # NEW: This file
```

## Testing Checklist

- [ ] Create Sentry account and project
- [ ] Add SENTRY_DSN to Railway (both services)
- [ ] Deploy to Railway
- [ ] Test `/sentry-debug` endpoint
- [ ] Verify error appears in Sentry dashboard
- [ ] Test agent room connection (should log to Sentry)
- [ ] Set up error rate alert (> 5/min)
- [ ] Set up performance alert (P95 > 2s)

## Cost Estimate

**Sentry Free Tier:**
- 5,000 errors/month
- 10,000 performance events/month
- $0/month

**Sentry Team Tier** (if you exceed free tier):
- 50,000 errors/month
- 100,000 performance events/month
- $26/month

With `traces_sample_rate=0.1` (10% sampling), you can handle ~500,000 requests/month on the free tier.

## Support

Questions? Check:
1. `SENTRY_SETUP_GUIDE.md` - Full setup instructions
2. Railway logs - Verify environment variables
3. Sentry dashboard - Check project settings
4. `/sentry-debug` endpoint - Test integration

---

**Status:** ✅ Implementation complete - Ready for deployment
