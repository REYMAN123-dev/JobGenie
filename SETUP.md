# Quick Setup Guide

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Configure API Key

1. Get your Gemini API key from: https://makersuite.google.com/app/apikey

2. Create a `.env` file in the project root:
   ```
   GEMINI_API_KEY=your_actual_api_key_here
   GEMINI_MODEL=gemini-pro
   ```
   (The application will automatically try other models if this one is not available)

3. **Important**: Replace `your_actual_api_key_here` with your actual API key

## Step 3: Start the Server

**Windows:**
```bash
python app.py
```
Or double-click `start_server.bat`

**Linux/Mac:**
```bash
python3 app.py
```

## Step 4: Open in Browser

Navigate to: http://localhost:5000

## Step 5: Upload Resume and Start Interview

1. Click "Choose PDF File" and select your resume
2. Click "Start Interview"
3. Answer the AI interviewer's questions
4. Continue the conversation naturally

## Troubleshooting

### "Gemini API key not configured" error
- Make sure you created a `.env` file (not `.env.txt`)
- Verify your API key is correct
- Restart the server after creating/modifying `.env`

### PDF parsing issues
- Ensure your PDF contains selectable text (not scanned images)
- Try a different PDF file

### Model errors (404 model not found)
- The application now automatically tries different models if your specified model is not available
- Default model is `gemini-pro` which is most widely available
- To see available models, start the server and visit: `http://localhost:5000/health`
- Update your `.env` file with a model from the available list:
  ```
  GEMINI_MODEL=gemini-pro
  ```
- Common working models:
  - `gemini-pro` (most reliable)
  - `gemini-1.5-pro` (if available with your API key)
  - `gemini-1.5-flash` (faster, if available)
- Visit https://aistudio.google.com/ to see available models for your API key

### Port already in use
- Change the port in `app.py`: `app.run(debug=True, port=5001)`
- Update the API URL in `static/script.js`: `const API_BASE_URL = 'http://localhost:5001';`

## Need Help?

Check the main README.md for more detailed information.

