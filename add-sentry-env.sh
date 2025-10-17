#!/bin/bash
# Script to add SENTRY_DSN to Railway services

SENTRY_DSN="https://6718b4e0d8c439e111218f7c369e5eb9@o4510192357474304.ingest.de.sentry.io/4510192993566800"

echo "Adding SENTRY_DSN to Railway services..."

# Add to API Service
echo "Configuring API Service..."
railway variables set SENTRY_DSN="$SENTRY_DSN" --service api

# Add to Agent Worker
echo "Configuring Agent Worker..."
railway variables set SENTRY_DSN="$SENTRY_DSN" --service agent

echo "✅ SENTRY_DSN added to both services"
echo "🚀 Railway will automatically redeploy both services"
