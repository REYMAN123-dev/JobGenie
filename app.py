import os
import json
from flask import Flask, request, jsonify, send_from_directory, render_template_string
from flask_cors import CORS
import google.generativeai as genai
import PyPDF2
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
import uuid

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
MODEL_NAME = os.getenv('GEMINI_MODEL', 'gemini-pro')  # Default to gemini-pro (most widely available)

model = None
available_models = []

def initialize_model():
    """Initialize Gemini model with fallback options"""
    global model, MODEL_NAME, available_models
    
    if not GEMINI_API_KEY:
        print("Warning: GEMINI_API_KEY not found in environment variables")
        return False
    
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Try to list available models
        model_names = []
        try:
            all_models = genai.list_models()
            for m in all_models:
                if 'generateContent' in m.supported_generation_methods:
                    # Extract model name (remove 'models/' prefix if present)
                    model_name = m.name.replace('models/', '')
                    model_names.append(model_name)
            available_models = model_names
            if available_models:
                print(f"✓ Found {len(available_models)} available model(s)")
                print(f"  Available models: {', '.join(available_models[:5])}{'...' if len(available_models) > 5 else ''}")
        except Exception as e:
            print(f"⚠ Could not list models: {e}")
            available_models = []
        
        # List of models to try in order of preference
        models_to_try = []
        
        # If user specified a model, try it first
        if MODEL_NAME and MODEL_NAME != 'gemini-pro':
            models_to_try.append(MODEL_NAME)
            # Also try with 'models/' prefix if available_models has it
            if available_models:
                for avail_model in available_models:
                    if MODEL_NAME in avail_model or avail_model.endswith(MODEL_NAME):
                        if avail_model not in models_to_try:
                            models_to_try.insert(0, avail_model)
        
        # If we have available models, use those first
        if available_models:
            # Add available models that match common names
            preferred_order = ['gemini-pro', 'gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.0-flash-exp', 'gemini-2.5-pro']
            for preferred in preferred_order:
                for avail in available_models:
                    if preferred in avail.lower() and avail not in models_to_try:
                        models_to_try.append(avail)
            # Add any remaining available models
            for avail in available_models:
                if avail not in models_to_try:
                    models_to_try.append(avail)
        else:
            # Fallback: try common model names if we couldn't list models
            models_to_try.extend([
                'gemini-pro',  # Most widely available
                'gemini-1.5-pro',
                'gemini-1.5-flash',
                'gemini-2.0-flash-exp',
                'gemini-2.5-pro',
            ])
        
        # Remove duplicates while preserving order
        models_to_try = list(dict.fromkeys(models_to_try))
        
        # Try each model until one works
        print(f"Attempting to initialize model (trying {len(models_to_try)} option(s))...")
        for model_name in models_to_try:
            try:
                # Extract just the model name part (remove 'models/' prefix if present)
                clean_name = model_name.replace('models/', '')
                test_model = genai.GenerativeModel(clean_name)
                
                # If we get here without exception, the model is valid
                model = test_model
                MODEL_NAME = clean_name
                print(f"✓ Successfully initialized Gemini model: {MODEL_NAME}")
                return True
            except Exception as e:
                error_msg = str(e)
                # Only show errors that aren't simple "not found" errors to reduce noise
                if '404' not in error_msg and 'not found' not in error_msg.lower():
                    print(f"✗ Failed to initialize {model_name}: {error_msg[:80]}")
                continue
        
        print("ERROR: Could not initialize any Gemini model. Please check your API key and model availability.")
        return False
        
    except Exception as e:
        print(f"ERROR: Failed to configure Gemini API: {str(e)}")
        return False

# Initialize the model
if not initialize_model():
    model = None

# Store resume data and conversation history per session
resume_data = {}
conversation_history = {}
interview_start_times = {}  # Track when each interview started
INTERVIEW_DURATION_MINUTES = 5  # 5 minutes interview duration

# Additional data stores
user_profiles = {}  # Store user profiles and preferences
job_listings = []  # Store job listings
interview_history = {}  # Store interview history per user
resume_templates = []  # Store resume templates
analytics_data = {}  # Store analytics data
candidate_info_store = {}  # Store candidate details per session

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def limit_response_lines(text, max_lines=5):
    """Limit text response to a maximum number of lines"""
    if not text:
        return text
    lines = text.strip().split('\n')
    # Filter out empty lines and take first max_lines non-empty lines
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    limited_lines = non_empty_lines[:max_lines]
    return '\n'.join(limited_lines)

def extract_text_from_pdf(pdf_file):
    """Extract text content from PDF file"""
    import io
    
    try:
        # Reset file pointer to beginning in case it was read before
        file_to_read = pdf_file
        try:
            pdf_file.seek(0)
        except (AttributeError, IOError, OSError):
            # If seek is not available, read the file into a BytesIO object
            try:
                file_content = pdf_file.read()
                file_to_read = io.BytesIO(file_content)
            except Exception as read_error:
                raise Exception(f"Cannot read file: {str(read_error)}")
        
        # Read the file content
        pdf_reader = PyPDF2.PdfReader(file_to_read)
        
        # Check if PDF has pages
        if len(pdf_reader.pages) == 0:
            raise Exception("PDF contains no pages")
        
        # Check if PDF is encrypted
        if pdf_reader.is_encrypted:
            # Try to decrypt with empty password (some PDFs have empty password)
            try:
                # In newer PyPDF2 versions, decrypt() returns a boolean
                # In older versions, it might not return anything
                decrypt_result = pdf_reader.decrypt("")
                if decrypt_result is False:
                    raise Exception("PDF is encrypted and cannot be decrypted. Please provide an unencrypted PDF.")
            except Exception as decrypt_error:
                # If decrypt raises an exception, the PDF is encrypted
                error_msg = str(decrypt_error)
                if "password" in error_msg.lower() or "encrypted" in error_msg.lower():
                    raise Exception("PDF is encrypted and cannot be read. Please provide an unencrypted PDF.")
                raise Exception(f"PDF decryption error: {error_msg}")
        
        text = ""
        for page_num, page in enumerate(pdf_reader.pages, 1):
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            except Exception as page_error:
                # Log but continue with other pages
                print(f"Warning: Could not extract text from page {page_num}: {str(page_error)}")
                continue
        
        if not text.strip():
            raise Exception("No text could be extracted from the PDF. The PDF may be image-based or corrupted.")
        
        return text.strip()
    except Exception as e:
        error_msg = str(e)
        # Check if it's a PyPDF2 specific error
        if 'PdfReadError' in str(type(e)) or 'pdf' in error_msg.lower():
            raise Exception(f"Invalid PDF format: {error_msg}")
        raise Exception(f"Error reading PDF: {error_msg}")

def generate_initial_interview_prompt(resume_text, candidate_info=None):
    """Generate the initial prompt for Gemini to start the interview"""
    candidate_context = ""
    if candidate_info:
        candidate_context = f"""
Candidate Information:
- Name: {candidate_info.get('firstName', '')} {candidate_info.get('lastName', '')}
- Email: {candidate_info.get('email', '')}
- Phone: {candidate_info.get('phone', 'N/A')}
- Experience: {candidate_info.get('experience', 'N/A')} years
- Position Applying For: {candidate_info.get('position', 'N/A')}
- Key Skills: {candidate_info.get('skills', 'N/A')}
- Additional Info: {candidate_info.get('additionalInfo', 'None')}

"""
    
    prompt = f"""You are JobGenie, a professional AI interviewer conducting a technical and behavioral interview. You are conducting an interview based on the following resume:

{resume_text}

{candidate_context}Your role as JobGenie:
- Introduce yourself as JobGenie at the start
- Ask direct, professional questions without phrases like "follow-up question" or "next question"
- Be professional, courteous, and focused
- Ask relevant questions about their experience, projects, skills, or background
- Keep questions clear and direct
- Personalize questions based on the candidate's information and the position they're applying for
- IMPORTANT: Keep your response to a MAXIMUM of 5 lines. Be concise and to the point.

Start the interview by introducing yourself as JobGenie, then immediately ask your first question based on their resume and candidate information. Be professional and direct. Remember: Maximum 5 lines."""
    
    return prompt

def generate_chat_prompt(resume_text, conversation_history_list, user_message, candidate_info=None):
    """Generate prompt for continuing the conversation"""
    candidate_context = ""
    if candidate_info:
        candidate_context = f"""
Candidate Information:
- Name: {candidate_info.get('firstName', '')} {candidate_info.get('lastName', '')}
- Position Applying For: {candidate_info.get('position', 'N/A')}
- Experience: {candidate_info.get('experience', 'N/A')} years
- Key Skills: {candidate_info.get('skills', 'N/A')}

"""
    
    context = f"""You are JobGenie, a professional AI interviewer. You are conducting an interview based on this resume:

{resume_text}

{candidate_context}Previous conversation:
"""
    for msg in conversation_history_list:
        if msg['role'] == 'user':
            context += f"Candidate: {msg['content']}\n"
        else:
            context += f"JobGenie: {msg['content']}\n"
    
    context += f"\nCandidate's latest response: {user_message}\n\n"
    context += """As JobGenie, respond professionally and directly.

Focus on:
- Asking relevant technical or behavioral questions based on their resume and previous answers
- Being professional, clear, and direct
- Maintaining a professional interview tone
- Asking one clear question at a time
- IMPORTANT: Keep your response to a MAXIMUM of 5 lines. Be concise and to the point.

Ask your question now (maximum 5 lines):"""
    
    return context

def generate_feedback_prompt(resume_text, conversation_history_list):
    """Generate prompt for interview feedback"""
    full_conversation = ""
    for msg in conversation_history_list:
        if msg['role'] == 'user':
            full_conversation += f"Candidate: {msg['content']}\n\n"
        else:
            full_conversation += f"JobGenie: {msg['content']}\n\n"
    
    prompt = f"""You are JobGenie, a professional AI interviewer. Analyze the following interview and provide comprehensive feedback.

Resume:
{resume_text}

Complete Interview Conversation:
{full_conversation}

Provide detailed feedback in the following JSON format (respond ONLY with valid JSON, no additional text):
{{
    "total_score": <number between 0-100>,
    "strengths": [
        "<strength 1>",
        "<strength 2>",
        "<strength 3>"
    ],
    "weaknesses": [
        "<weakness 1>",
        "<weakness 2>",
        "<weakness 3>"
    ],
    "areas_of_improvement": [
        "<area 1>",
        "<area 2>",
        "<area 3>"
    ],
    "overall_feedback": "<comprehensive feedback paragraph>",
    "technical_assessment": "<technical skills assessment>",
    "communication_assessment": "<communication skills assessment>"
}}

Be specific, constructive, and professional in your feedback. Base your assessment on:
- Quality of answers
- Technical knowledge demonstrated
- Communication clarity
- Relevance to the role
- Problem-solving approach
- Professionalism"""
    
    return prompt

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/about')
def about():
    return send_from_directory('static', 'about.html')

@app.route('/features')
def features():
    return send_from_directory('static', 'features.html')

@app.route('/pricing')
def pricing():
    return send_from_directory('static', 'pricing.html')

@app.route('/contact')
def contact():
    return send_from_directory('static', 'contact.html')

@app.route('/dashboard')
def dashboard():
    return send_from_directory('static', 'dashboard.html')

@app.route('/candidate-details')
def candidate_details():
    return send_from_directory('static', 'candidate-details.html')

@app.route('/interview')
def interview():
    return send_from_directory('static', 'interview.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

@app.route('/upload', methods=['POST'])
def upload_resume():
    """Handle resume PDF upload and extract text"""
    if 'resume' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['resume']
    session_id = request.form.get('session_id', 'default')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Extract text from PDF
            try:
                resume_text = extract_text_from_pdf(file)
            except Exception as pdf_error:
                error_msg = str(pdf_error)
                return jsonify({
                    'error': f'Failed to parse PDF: {error_msg}',
                    'details': 'Please ensure the PDF is not corrupted, encrypted, or password-protected.'
                }), 400
            
            if not resume_text or len(resume_text.strip()) < 50:
                return jsonify({
                    'error': 'Could not extract sufficient text from PDF. Please ensure the PDF contains readable text.',
                    'details': 'The PDF may be image-based or contain only non-text elements. Try a PDF with selectable text.'
                }), 400
            
            # Extract candidate details from form data
            candidate_info = {
                'firstName': request.form.get('firstName', ''),
                'lastName': request.form.get('lastName', ''),
                'email': request.form.get('email', ''),
                'phone': request.form.get('phone', ''),
                'experience': request.form.get('experience', ''),
                'position': request.form.get('position', ''),
                'skills': request.form.get('skills', ''),
                'additionalInfo': request.form.get('additionalInfo', '')
            }
            
            # Store resume data
            resume_data[session_id] = resume_text
            
            # Store candidate details
            candidate_info_store[session_id] = candidate_info
            
            # Initialize conversation history
            conversation_history[session_id] = []
            
            # Record interview start time
            interview_start_times[session_id] = datetime.now()
            
            # Generate initial interview question
            if not model:
                return jsonify({
                    'error': 'Gemini API key not configured or model initialization failed. Please check your .env file and restart the server.',
                    'hint': 'Visit /health endpoint to see available models'
                }), 500
            
            try:
                initial_prompt = generate_initial_interview_prompt(resume_text, candidate_info)
                response = model.generate_content(initial_prompt)
                interviewer_message = limit_response_lines(response.text, max_lines=5)
            except Exception as model_error:
                error_msg = str(model_error)
                if '404' in error_msg or 'not found' in error_msg.lower():
                    return jsonify({
                        'error': f'Model "{MODEL_NAME}" is not available. Please check available models at /health endpoint and update GEMINI_MODEL in .env file.',
                        'current_model': MODEL_NAME,
                        'hint': 'Try setting GEMINI_MODEL=gemini-pro in your .env file'
                    }), 500
                raise
            conversation_history[session_id].append({
                'role': 'assistant',
                'content': interviewer_message
            })
            
            return jsonify({
                'success': True,
                'message': 'Resume uploaded and processed successfully',
                'initial_question': interviewer_message,
                'session_id': session_id
            })
        except Exception as e:
            error_msg = str(e)
            if 'model' in error_msg.lower() or 'not found' in error_msg.lower():
                return jsonify({'error': f'Model error: {error_msg}. Please check your GEMINI_MODEL in .env file.'}), 500
            return jsonify({'error': f'Error processing resume: {error_msg}'}), 500
    
    return jsonify({'error': 'Invalid file type. Please upload a PDF file.'}), 400

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages for the interview"""
    data = request.json
    user_message = data.get('message', '')
    session_id = data.get('session_id', 'default')
    
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    
    if session_id not in resume_data:
        return jsonify({'error': 'Resume not uploaded. Please upload a resume first.'}), 400
    
    if not model:
        return jsonify({'error': 'Gemini API key not configured'}), 500
    
    try:
        # Add user message to history
        conversation_history[session_id].append({
            'role': 'user',
            'content': user_message
        })
        
        # Generate response
        resume_text = resume_data[session_id]
        candidate_info = candidate_info_store.get(session_id)
        try:
            chat_prompt = generate_chat_prompt(resume_text, conversation_history[session_id][:-1], user_message, candidate_info)
            response = model.generate_content(chat_prompt)
            interviewer_message = limit_response_lines(response.text, max_lines=5)
        except Exception as model_error:
            error_msg = str(model_error)
            if '404' in error_msg or 'not found' in error_msg.lower():
                return jsonify({
                    'error': f'Model "{MODEL_NAME}" is not available. Please restart the server with a valid model.',
                    'current_model': MODEL_NAME,
                    'hint': 'Check /health endpoint for available models'
                }), 500
            raise
        
        # Add assistant message to history
        conversation_history[session_id].append({
            'role': 'assistant',
            'content': interviewer_message
        })
        
        return jsonify({
            'success': True,
            'response': interviewer_message
        })
    except Exception as e:
        error_msg = str(e)
        if 'model' in error_msg.lower() or 'not found' in error_msg.lower():
            return jsonify({'error': f'Model error: {error_msg}. Please check your GEMINI_MODEL in .env file.'}), 500
        return jsonify({'error': f'Error generating response: {error_msg}'}), 500

@app.route('/interview/status', methods=['GET'])
def interview_status():
    """Get interview status and time remaining"""
    session_id = request.args.get('session_id', 'default')
    
    if session_id not in interview_start_times:
        return jsonify({
            'error': 'Interview not started',
            'started': False
        }), 404
    
    start_time = interview_start_times[session_id]
    elapsed = datetime.now() - start_time
    elapsed_seconds = int(elapsed.total_seconds())
    remaining_seconds = max(0, (INTERVIEW_DURATION_MINUTES * 60) - elapsed_seconds)
    is_complete = remaining_seconds == 0
    
    # Get initial question if available
    initial_question = None
    if session_id in conversation_history and len(conversation_history[session_id]) > 0:
        first_message = conversation_history[session_id][0]
        if first_message.get('role') == 'assistant':
            initial_question = first_message.get('content')
    
    return jsonify({
        'started': True,
        'start_time': start_time.isoformat(),
        'elapsed_seconds': elapsed_seconds,
        'remaining_seconds': remaining_seconds,
        'duration_minutes': INTERVIEW_DURATION_MINUTES,
        'is_complete': is_complete,
        'initial_question': initial_question
    })

@app.route('/interview/feedback', methods=['POST'])
def get_feedback():
    """Generate and return interview feedback"""
    data = request.json
    session_id = data.get('session_id', 'default')
    
    if session_id not in resume_data:
        return jsonify({'error': 'Resume not uploaded. Please upload a resume first.'}), 400
    
    if session_id not in conversation_history:
        return jsonify({'error': 'No interview conversation found.'}), 400
    
    if not model:
        return jsonify({'error': 'Gemini API key not configured'}), 500
    
    try:
        resume_text = resume_data[session_id]
        conversation_list = conversation_history[session_id]
        
        if len(conversation_list) < 2:
            return jsonify({'error': 'Interview too short. Need at least one question and answer.'}), 400
        
        # Generate feedback
        feedback_prompt = generate_feedback_prompt(resume_text, conversation_list)
        response = model.generate_content(feedback_prompt)
        feedback_text = response.text
        
        # Try to parse JSON from response
        try:
            # Remove markdown code blocks if present
            feedback_clean = feedback_text.strip()
            if feedback_clean.startswith('```json'):
                feedback_clean = feedback_clean[7:]
            if feedback_clean.startswith('```'):
                feedback_clean = feedback_clean[3:]
            if feedback_clean.endswith('```'):
                feedback_clean = feedback_clean[:-3]
            feedback_clean = feedback_clean.strip()
            
            feedback_data = json.loads(feedback_clean)
        except json.JSONDecodeError:
            # If JSON parsing fails, return structured text response
            feedback_data = {
                'total_score': 75,
                'strengths': ['Good communication', 'Relevant experience'],
                'weaknesses': ['Could provide more detail'],
                'areas_of_improvement': ['Expand on technical details'],
                'overall_feedback': feedback_text,
                'technical_assessment': 'See overall feedback',
                'communication_assessment': 'See overall feedback'
            }
        
        # Calculate interview duration
        duration_seconds = 0
        if session_id in interview_start_times:
            start_time = interview_start_times[session_id]
            elapsed = datetime.now() - start_time
            duration_seconds = int(elapsed.total_seconds())
        
        feedback_data['interview_duration_seconds'] = duration_seconds
        feedback_data['interview_duration_minutes'] = round(duration_seconds / 60, 2)
        
        return jsonify({
            'success': True,
            'feedback': feedback_data
        })
    except Exception as e:
        return jsonify({'error': f'Error generating feedback: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'gemini_configured': model is not None,
        'model_name': MODEL_NAME if model else None,
        'available_models': available_models[:10] if available_models else []  # Limit to first 10
    })

# New endpoints for enhanced functionality

@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    """Get job listings"""
    try:
        # Return sample job listings or from database
        jobs = [
            {
                'id': str(uuid.uuid4()),
                'title': 'Senior Software Engineer',
                'company': 'Tech Corp',
                'location': 'Remote',
                'type': 'Full-time',
                'description': 'Looking for an experienced software engineer...',
                'posted_date': datetime.now().isoformat()
            }
        ]
        return jsonify({'success': True, 'jobs': jobs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/jobs/match', methods=['POST'])
def match_jobs():
    """Match jobs based on resume"""
    try:
        data = request.json
        session_id = data.get('session_id', 'default')
        
        if session_id not in resume_data:
            return jsonify({'error': 'Resume not uploaded'}), 400
        
        if not model:
            return jsonify({'error': 'Gemini API not configured'}), 500
        
        resume_text = resume_data[session_id]
        
        # Generate job matching using AI
        prompt = f"""Based on this resume, suggest 5 matching job positions with titles, required skills, and match percentage:

{resume_text}

Return JSON format:
{{
    "matches": [
        {{
            "title": "Job Title",
            "company": "Company Name",
            "match_percentage": 85,
            "required_skills": ["skill1", "skill2"],
            "description": "Job description"
        }}
    ]
}}"""
        
        response = model.generate_content(prompt)
        matches_text = response.text
        
        # Try to parse JSON
        try:
            if matches_text.startswith('```json'):
                matches_text = matches_text[7:]
            if matches_text.startswith('```'):
                matches_text = matches_text[3:]
            if matches_text.endswith('```'):
                matches_text = matches_text[:-3]
            matches_data = json.loads(matches_text.strip())
            return jsonify({'success': True, 'matches': matches_data.get('matches', [])})
        except:
            return jsonify({'success': True, 'matches': [], 'raw_response': matches_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/resume/generate', methods=['POST'])
def generate_resume():
    """Generate resume using AI"""
    try:
        data = request.json
        user_info = data.get('user_info', {})
        
        if not model:
            return jsonify({'error': 'Gemini API not configured'}), 500
        
        prompt = f"""Create a professional resume based on the following information:

Name: {user_info.get('name', 'John Doe')}
Email: {user_info.get('email', 'john@example.com')}
Phone: {user_info.get('phone', '')}
Experience: {user_info.get('experience', '')}
Education: {user_info.get('education', '')}
Skills: {user_info.get('skills', '')}
Objective: {user_info.get('objective', '')}

Generate a well-formatted resume in markdown format."""
        
        response = model.generate_content(prompt)
        resume_content = response.text
        
        return jsonify({
            'success': True,
            'resume': resume_content
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Get user analytics"""
    try:
        session_id = request.args.get('session_id', 'default')
        
        analytics = {
            'total_interviews': len([k for k in interview_start_times.keys()]),
            'average_score': 75,
            'improvement_trend': 'up',
            'strengths': ['Communication', 'Technical Knowledge'],
            'weaknesses': ['Time Management', 'Confidence']
        }
        
        if session_id in interview_history:
            analytics['user_interviews'] = len(interview_history[session_id])
        
        return jsonify({'success': True, 'analytics': analytics})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/profile', methods=['POST'])
def save_profile():
    """Save user profile"""
    try:
        data = request.json
        session_id = data.get('session_id', 'default')
        profile = data.get('profile', {})
        
        user_profiles[session_id] = {
            **profile,
            'updated_at': datetime.now().isoformat()
        }
        
        return jsonify({'success': True, 'profile': user_profiles[session_id]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/profile', methods=['GET'])
def get_profile():
    """Get user profile"""
    try:
        session_id = request.args.get('session_id', 'default')
        
        if session_id in user_profiles:
            return jsonify({'success': True, 'profile': user_profiles[session_id]})
        else:
            return jsonify({'success': True, 'profile': None})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/interview/history', methods=['GET'])
def get_interview_history():
    """Get interview history for a user"""
    try:
        session_id = request.args.get('session_id', 'default')
        
        history = []
        if session_id in interview_history:
            history = interview_history[session_id]
        
        return jsonify({'success': True, 'history': history})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/interview/save', methods=['POST'])
def save_interview():
    """Save interview to history"""
    try:
        data = request.json
        session_id = data.get('session_id', 'default')
        interview_data = data.get('interview_data', {})
        
        if session_id not in interview_history:
            interview_history[session_id] = []
        
        interview_record = {
            'id': str(uuid.uuid4()),
            'date': datetime.now().isoformat(),
            'score': interview_data.get('score', 0),
            'feedback': interview_data.get('feedback', {}),
            'duration': interview_data.get('duration', 0)
        }
        
        interview_history[session_id].append(interview_record)
        
        return jsonify({'success': True, 'interview': interview_record})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)