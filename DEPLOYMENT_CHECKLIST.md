# Render Deployment Checklist

Use this checklist to ensure everything is ready for deployment to Render.

## Pre-Deployment Tasks

### Code Repository
- [ ] All code is committed to GitHub
- [ ] `.gitignore` includes sensitive files (.env, __pycache__, venv, etc.)
- [ ] README.md is complete and accurate
- [ ] No hardcoded API keys or sensitive data in code

### Requirements and Dependencies
- [ ] `requirements.txt` is up-to-date with all dependencies
- [ ] Python 3.11 compatibility verified (or 3.10)
- [ ] No conflicting package versions in requirements.txt
- [ ] `pip install -r requirements.txt` works locally without errors

### Environment Configuration
- [ ] `.env.example` file exists with all required variables
- [ ] Environment variable names are correctly spelled
- [ ] `GROQ_API_KEY` is valid and accessible
- [ ] `HOST` is set to `0.0.0.0` in main.py (not 127.0.0.1)
- [ ] `PORT` is read from environment variable: `int(os.getenv('PORT', ...))`

### Application Code
- [ ] `main.py` uses `0.0.0.0` as default host
- [ ] Start command uses fixed port: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- [ ] No hardcoded localhost addresses (127.0.0.1)
- [ ] All imports are tested and working
- [ ] Application starts without errors locally

### Data Files
- [ ] `/sap-o2c-data/` directory exists in repository
- [ ] All JSONL files are included in repository
- [ ] `.gitignore` does NOT exclude the data files
- [ ] Data path is correctly configured: `./sap-o2c-data`

### Configuration Files (for Render)
- [ ] `render.yaml` exists and is properly configured
- [ ] `Procfile` exists with correct start command
- [ ] Both files use `$PORT` environment variable
- [ ] Both files bind to `0.0.0.0`

### Frontend Assets
- [ ] `frontend/index.html` exists and is valid
- [ ] All CSS and JavaScript files are embedded or properly served
- [ ] Static files are in `/frontend` directory
- [ ] No references to localhost addresses in frontend code

### API Keys and Secrets
- [ ] `GROQ_API_KEY` ready to add to Render environment
- [ ] No other sensitive keys needed initially
- [ ] All secrets are in `.env` or Render dashboard (not in code)

## Render Dashboard Preparation

### Account Setup
- [ ] Render account created and verified
- [ ] GitHub account connected to Render
- [ ] Repository access granted to Render

### Service Configuration
- [ ] Service name decided (e.g., `o2c-graph-system`)
- [ ] Region selected
- [ ] Python 3.11 selected as environment
- [ ] Build command verified: `pip install -r requirements.txt`
- [ ] Start command verified: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Environment Variables Ready

Before clicking "Deploy", confirm you have:

- [ ] `GROQ_API_KEY` = [your key from https://console.groq.com/keys]
- [ ] `HOST` = `0.0.0.0` (or omitted to use default)
- [ ] `ENVIRONMENT` = `production` (optional)
- [ ] Any other custom variables documented

## Final Checks

- [ ] All 62+ items above are checked
- [ ] Application builds successfully locally with: `pip install -r requirements.txt`
- [ ] Application starts successfully locally
- [ ] Frontend loads at http://localhost:5555
- [ ] API endpoints respond correctly
- [ ] Data loads without errors
- [ ] Deployment files are committed to GitHub

## Deployment Steps

1. [ ] Go to https://dashboard.render.com
2. [ ] Click "New +" → "Web Service"
3. [ ] Connect GitHub repository
4. [ ] Select this repository
5. [ ] Enter service name: `o2c-graph-system`
6. [ ] Confirm build command: `pip install -r requirements.txt`
7. [ ] Confirm start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
8. [ ] Add environment variables:
   - [ ] `GROQ_API_KEY` = [your key]
   - [ ] Any other required variables
9. [ ] Select plan (Free tier recommended for testing)
10. [ ] Enable auto-deploy if desired
11. [ ] Click "Create Web Service"
12. [ ] Monitor build logs for errors
13. [ ] Wait for deployment to complete
14. [ ] Test the deployed application URL

## Post-Deployment Verification

- [ ] Service is running (green status in Render dashboard)
- [ ] Frontend loads at service URL
- [ ] `/health` endpoint returns healthy status
- [ ] `/graph` endpoint returns graph data
- [ ] `/chat` endpoint processes queries
- [ ] Logs show no errors

## Known Issues and Solutions

### Issue: Port binding error
**Solution**: Check that main.py uses `int(os.getenv('PORT', ...))`

### Issue: Data not loading
**Solution**: Verify `/sap-o2c-data/` is in repository root

### Issue: Build fails with dependency errors
**Solution**: Run `pip install -r requirements.txt` locally to verify

### Issue: 502 Bad Gateway errors
**Solution**: Check service logs; likely a startup issue

### Issue: Slow API responses
**Solution**: Normal on free tier; upgrade to paid plan if needed

## Support Resources

- Render Docs: https://render.com/docs
- FastAPI Docs: https://fastapi.tiangolo.com
- GitHub Issues: Check project repository
- Render Support: https://support.render.com

## Deployment Successful!

Once all items are checked and deployment is complete:

1. Note the service URL from Render dashboard
2. Share the URL with stakeholders
3. Document the URL in your README
4. Set up monitoring alerts if needed
5. Plan for maintenance and updates

---

**Last Updated**: March 25, 2026  
**Status**: Ready for Deployment ✓
