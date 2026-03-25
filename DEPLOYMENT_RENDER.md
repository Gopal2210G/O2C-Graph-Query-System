# Deployment Guide - Render

This guide walks you through deploying the Order-to-Cash Graph System to Render.

## Prerequisites

1. A Render account (https://render.com)
2. Your GitHub repository with this code
3. All required environment variables ready

## Step 1: Connect Your GitHub Repository

1. Go to https://dashboard.render.com
2. Click "New +" and select "Web Service"
3. Click "Connect" next to your GitHub repository
4. Authorize Render to access your GitHub account
5. Select the repository with this code
6. Click "Connect"

## Step 2: Configure the Web Service

### Basic Settings
- **Name**: `o2c-graph-system` (or your preferred name)
- **Environment**: `Python 3.11`
- **Region**: Select the region closest to your users
- **Branch**: `main` (or your deployment branch)

### Build and Start Commands

**Build Command**:
```bash
pip install -r requirements.txt
```

**Start Command**:
```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Step 3: Set Environment Variables

Add the following environment variables in the Render dashboard:

| Variable | Value | Notes |
|----------|-------|-------|
| `GROQ_API_KEY` | Your Groq API key | Required for LLM functionality. Get from https://console.groq.com/keys |
| `HOST` | `0.0.0.0` | Must be 0.0.0.0 for Render (don't use 127.0.0.1) |
| `PORT` | (auto-configured by Render) | Leave empty; Render sets this automatically |
| `DATA_PATH` | `./sap-o2c-data` | Path to SAP data (must be included in repo) |
| `ENVIRONMENT` | `production` | Optional: Set to production |

## Step 4: Select Plan

- **Plan**: Free tier recommended for testing
- **Auto-deploy**: Enable if you want automatic deploys on every push to your branch

## Step 5: Deploy

1. Click "Create Web Service"
2. Render will automatically start the build process
3. Watch the build logs for any errors
4. Once deployed, you'll see your service URL (e.g., `https://o2c-graph-system.onrender.com`)

## Accessing Your Application

- **Frontend**: Navigate to your service URL (e.g., `https://o2c-graph-system.onrender.com`)
- **API Health**: `https://o2c-graph-system.onrender.com/health`
- **Graph Data**: `https://o2c-graph-system.onrender.com/graph`

## Important Notes for Render Deployment

### 1. Port Configuration
- **DO NOT** hardcode ports in your code
- The `$PORT` environment variable is automatically set by Render
- The app is configured to read `PORT` from environment: `int(os.getenv('PORT', 5555))`

### 2. Host Binding
- **MUST** bind to `0.0.0.0` (not `127.0.0.1`)
- This is configured in `main.py`: `host = os.getenv('HOST', '0.0.0.0')`

### 3. Data Files
- Ensure `sap-o2c-data/` directory is included in your repository
- All JSONL files will be loaded when the service starts

### 4. Build Time
- First build may take 5-10 minutes
- Subsequent builds are faster due to caching
- If build times exceed limits, switch to a paid plan

### 5. Cold Starts
- Free tier instances spin down after 15 minutes of inactivity
- First request after inactivity may take 10-30 seconds
- Paid plans have faster response times

## Troubleshooting

### Build Failed
- Check the build logs in the Render dashboard
- Ensure all dependencies in `requirements.txt` are compatible with Python 3.11
- Verify all environment variables are set

### Application Won't Start
- Check service logs in Render dashboard
- Common issue: `PORT` environment variable not properly read
  - Should be configured as: `int(os.getenv('PORT', 5555))`
- Ensure `HOST` is set to `0.0.0.0`

### Data Not Loading
- Verify `sap-o2c-data/` directory exists in repository
- Ensure JSONL files are present
- Check DATA_PATH environment variable

### API Key Errors
- Verify `GROQ_API_KEY` is correctly set in Render dashboard
- Ensure it's a valid Groq API key (not copied with extra spaces)

### Performance Issues
- Free tier has limited resources; consider upgrading to paid plan
- Optimize data loading if it takes too long during startup
- Check for long-running queries in logs

## Monitoring and Logs

1. Go to your service dashboard in Render
2. Click "Logs" tab to view real-time logs
3. Check for errors and monitor performance
4. Use "Metrics" tab to view CPU, memory, and bandwidth usage

## Redeploy After Changes

### Option 1: Automatic Deploy
- If enabled, simply push to your GitHub branch
- Render will automatically rebuild and deploy

### Option 2: Manual Deploy
1. Go to your service dashboard
2. Click "Manual Deploy"
3. Select the branch to deploy
4. Click "Deploy"

## Cost Information (Free Tier)

- **$0/month** for the first 750 hours (approximately 31 days/month)
- After 750 hours, service is paused until next month
- 512 MB RAM, shared CPU
- 100 GB bandwidth

## Upgrade to Paid Plan

If you need more resources:
1. Go to your service settings in Render dashboard
2. Click "Change Plan"
3. Select desired plan
4. Service will be upgraded immediately with no downtime

## Next Steps

1. Ensure all files are committed to GitHub
2. Follow the deployment steps above
3. Test the deployed application
4. Monitor logs for any issues
5. Share the URL with stakeholders

## Support

- Render Documentation: https://render.com/docs
- Render Support: https://render.com/support
- FastAPI Documentation: https://fastapi.tiangolo.com/
- Groq Documentation: https://console.groq.com/docs

---

**Deployment Files Included**:
- `render.yaml` - Render deployment configuration
- `Procfile` - Alternative deployment process file
- `requirements.txt` - Python dependencies
- `.env.example` - Environment variables template

**Last Updated**: March 25, 2026
