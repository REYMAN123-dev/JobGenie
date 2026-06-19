# AI Resume Interview System

An intelligent interview system powered by Google's Gemini 2.5 Pro that conducts back-and-forth interviews based on user-uploaded resumes in PDF format.

## Features

- 📄 **PDF Resume Parsing**: Upload and extract text from PDF resumes
- 🤖 **AI-Powered Interviews**: Conducts intelligent interviews using Gemini 2.5 Pro
- 💬 **Interactive Chat**: Real-time back-and-forth conversation interface
- 🎨 **Modern UI**: Beautiful and responsive web interface
- 🔒 **Session Management**: Maintains conversation context throughout the interview

## Prerequisites

- Python 3.8 or higher
- Google Gemini API key ([Get one here](https://makersuite.google.com/app/apikey))

## Installation

1. **Clone or download this repository**

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   - Create a `.env` file in the project root (you can use `env_template.txt` as reference)
   - Add your Gemini API key:
     ```
     GEMINI_API_KEY=your_actual_api_key_here
     GEMINI_MODEL=gemini-pro
     ```
   - **Note**: Available models include:
     - `gemini-pro` (default, most widely available and stable)
     - `gemini-1.5-pro` (more powerful, if available with your API key)
     - `gemini-1.5-flash` (faster, good for quick responses)
     - `gemini-2.0-flash-exp` (experimental, faster)
     - `gemini-2.5-pro` (if available with your API key)
     - The application will automatically try different models if your specified model is not available
     - Check [Google AI Studio](https://aistudio.google.com/) for the latest available models
     - Visit `/health` endpoint after starting the server to see available models

## Usage

1. **Start the Flask server**:
   
   **Windows:**
   ```bash
   python app.py
   ```
   Or double-click `start_server.bat`
   
   **Linux/Mac:**
   ```bash
   python3 app.py
   ```
   Or run `./start_server.sh` (make sure it's executable: `chmod +x start_server.sh`)

2. **Open your web browser** and navigate to:
   ```
   http://localhost:5000
   ```

3. **Upload your resume**:
   - Click "Choose PDF File" and select your resume
   - Click "Start Interview"

4. **Conduct the interview**:
   - The AI will ask you questions based on your resume
   - Answer the questions in the chat interface
   - Continue the conversation naturally

5. **Start a new interview**:
   - Click "New Interview" to reset and upload a different resume

## Project Structure

```
.
├── app.py                 # Flask backend server
├── requirements.txt       # Python dependencies
├── .env                  # Environment variables (API key)
├── .env.example          # Example environment file
├── README.md             # This file
├── static/
│   ├── index.html        # Frontend HTML
│   ├── style.css         # Styling
│   └── script.js         # Frontend JavaScript
└── uploads/              # Uploaded resume storage (created automatically)
```

## API Endpoints

- `GET /` - Serves the main web page
- `POST /upload` - Upload and process resume PDF
- `POST /chat` - Send chat messages and get AI responses
- `GET /health` - Health check endpoint

## Configuration

### Changing the Gemini Model

You can change the model in the `.env` file:

```env
GEMINI_MODEL=gemini-1.5-pro
```

Or modify `MODEL_NAME` in `app.py`. Available models:
- `gemini-1.5-pro` (recommended, most powerful)
- `gemini-1.5-flash` (faster, good for quick responses)
- `gemini-pro` (older model)

Check [Google AI Studio](https://aistudio.google.com/) for the latest available models and their names.

### File Upload Limits

Default maximum file size is 16MB. To change it, modify `MAX_FILE_SIZE` in `app.py`.

## Troubleshooting

### "Gemini API key not configured" error
- Make sure you've created a `.env` file with your API key
- Verify the API key is correct and has proper permissions

### PDF parsing issues
- Ensure your PDF contains selectable text (not just scanned images)
- Try a different PDF file if extraction fails

### Connection errors
- Make sure the Flask server is running on port 5000
- Check if port 5000 is available or change the port in `app.py`

## Security Notes

- Never commit your `.env` file to version control
- The `.env` file is already in `.gitignore`
- Keep your API key secure and don't share it

## License

This project is open source and available for personal and commercial use.

## Support

For issues or questions, please check:
- [Google Gemini API Documentation](https://ai.google.dev/docs)
- [Flask Documentation](https://flask.palletsprojects.com/)

