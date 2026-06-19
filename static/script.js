const API_BASE_URL = 'http://localhost:5000';
let sessionId = 'session_' + Date.now();
let resumeUploaded = false;
let interviewTimer = null;
let statusCheckInterval = null;

// Speech Recognition and Text-to-Speech
let recognition = null;
let isListening = false;
let userStream = null;
let synth = window.speechSynthesis;
let currentUtterance = null;

// Initialize Speech Recognition
function initSpeechRecognition() {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';
        
        recognition.onresult = function(event) {
            let interimTranscript = '';
            let finalTranscript = '';
            
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript + ' ';
                } else {
                    interimTranscript += transcript;
                }
            }
            
            // Update input field with interim results
            const chatInput = document.getElementById('chatInput');
            if (interimTranscript) {
                chatInput.value = interimTranscript;
            }
            
            // If we have final transcript, send it
            if (finalTranscript.trim()) {
                chatInput.value = finalTranscript.trim();
                sendMessage();
            }
        };
        
        recognition.onerror = function(event) {
            console.error('Speech recognition error:', event.error);
            if (event.error === 'no-speech') {
                // Restart recognition if no speech detected
                if (isListening) {
                    recognition.start();
                }
            }
        };
        
        recognition.onend = function() {
            if (isListening) {
                recognition.start();
            }
        };
    } else {
        console.warn('Speech recognition not supported in this browser');
    }
}

// Initialize on page load
initSpeechRecognition();

// File input change handler
document.getElementById('resumeInput').addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (file) {
        document.getElementById('fileName').textContent = `Selected: ${file.name}`;
        document.getElementById('submitBtn').disabled = false;
    }
});

// Upload resume function
async function uploadResume() {
    const fileInput = document.getElementById('resumeInput');
    const file = fileInput.files[0];
    
    if (!file) {
        showStatus('Please select a file first', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('resume', file);
    formData.append('session_id', sessionId);
    
    const submitBtn = document.getElementById('submitBtn');
    const statusDiv = document.getElementById('uploadStatus');
    
    submitBtn.disabled = true;
    showStatus('Uploading and processing resume...', 'loading');
    
    try {
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showStatus('Resume uploaded successfully!', 'success');
            resumeUploaded = true;
            
            // Hide upload section and show chat section
            setTimeout(() => {
                document.getElementById('uploadSection').style.display = 'none';
                document.getElementById('chatSection').style.display = 'flex';
                
                // Add initial question to chat
                addMessage('assistant', data.initial_question);
                
                // Speak the initial question
                speakText(data.initial_question);
                
                // Start timer and status checking
                startInterviewTimer();
                
                // Request camera and microphone permissions
                requestMediaPermissions();
            }, 1000);
        } else {
            showStatus(data.error || 'Error uploading resume', 'error');
            submitBtn.disabled = false;
        }
    } catch (error) {
        showStatus('Error connecting to server: ' + error.message, 'error');
        submitBtn.disabled = false;
    }
}

// Send message function
async function sendMessage() {
    const chatInput = document.getElementById('chatInput');
    const message = chatInput.value.trim();
    
    if (!message) return;
    
    if (!resumeUploaded) {
        alert('Please upload your resume first');
        return;
    }
    
    // Add user message to chat
    addMessage('user', message);
    chatInput.value = '';
    
    // Show typing indicator
    const typingId = showTypingIndicator();
    
    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            })
        });
        
        const data = await response.json();
        
        // Remove typing indicator
        removeTypingIndicator(typingId);
        
        if (response.ok && data.success) {
            addMessage('assistant', data.response);
            // Speak the response
            speakText(data.response);
        } else {
            addMessage('assistant', 'Error: ' + (data.error || 'Failed to get response'));
        }
    } catch (error) {
        removeTypingIndicator(typingId);
        addMessage('assistant', 'Error connecting to server: ' + error.message);
    }
}

// Add message to chat
function addMessage(role, content) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const label = role === 'user' ? 'You' : 'JobGenie';
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    
    const labelDiv = document.createElement('div');
    labelDiv.className = 'message-label';
    labelDiv.textContent = label;
    
    const contentDiv = document.createElement('div');
    contentDiv.textContent = content;
    
    messageContent.appendChild(labelDiv);
    messageContent.appendChild(contentDiv);
    messageDiv.appendChild(messageContent);
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Show typing indicator
function showTypingIndicator() {
    const chatMessages = document.getElementById('chatMessages');
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message assistant';
    typingDiv.id = 'typing-indicator';
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    
    const labelDiv = document.createElement('div');
    labelDiv.className = 'message-label';
    labelDiv.textContent = 'JobGenie';
    
    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'typing-indicator';
    typingIndicator.innerHTML = '<span></span><span></span><span></span>';
    
    messageContent.appendChild(labelDiv);
    messageContent.appendChild(typingIndicator);
    typingDiv.appendChild(messageContent);
    
    chatMessages.appendChild(typingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return 'typing-indicator';
}

// Remove typing indicator
function removeTypingIndicator(id) {
    const indicator = document.getElementById(id);
    if (indicator) {
        indicator.remove();
    }
}

// Handle Enter key press
function handleKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

// Show status message
function showStatus(message, type) {
    const statusDiv = document.getElementById('uploadStatus');
    statusDiv.textContent = message;
    statusDiv.className = `status-message ${type}`;
}

// Start interview timer
function startInterviewTimer() {
    // Clear any existing intervals
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }
    
    // Check status every second
    statusCheckInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/interview/status?session_id=${sessionId}`);
            const data = await response.json();
            
            if (data.started) {
                const minutes = Math.floor(data.remaining_seconds / 60);
                const seconds = data.remaining_seconds % 60;
                const timerDisplay = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
                document.getElementById('timer').textContent = timerDisplay;
                
                // Change color when time is running out
                const timerEl = document.getElementById('timer');
                if (data.remaining_seconds < 60) {
                    timerEl.style.color = '#ff4444';
                } else if (data.remaining_seconds < 120) {
                    timerEl.style.color = '#ffaa00';
                } else {
                    timerEl.style.color = '#fff';
                }
                
                // Auto-end interview when time is up
                if (data.is_complete) {
                    clearInterval(statusCheckInterval);
                    endInterview();
                }
            }
        } catch (error) {
            console.error('Error checking interview status:', error);
        }
    }, 1000);
}

// End interview and get feedback
async function endInterview() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }
    
    // Stop media streams
    stopMediaStreams();
    
    // Disable chat input
    document.getElementById('chatInput').disabled = true;
    const sendBtn = document.querySelector('.send-btn');
    if (sendBtn) sendBtn.disabled = true;
    
    // Show loading message
    addMessage('assistant', 'Interview completed. Generating your feedback...');
    
    try {
        const response = await fetch(`${API_BASE_URL}/interview/feedback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: sessionId
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            displayFeedback(data.feedback);
        } else {
            addMessage('assistant', 'Error generating feedback: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        addMessage('assistant', 'Error connecting to server: ' + error.message);
    }
}

// Display feedback
function displayFeedback(feedback) {
    const feedbackSection = document.getElementById('feedbackSection');
    const chatMessages = document.getElementById('chatMessages');
    
    // Hide chat and show feedback
    chatMessages.style.display = 'none';
    const inputContainer = document.querySelector('.transcript-input-container') || document.querySelector('.chat-input-container');
    if (inputContainer) inputContainer.style.display = 'none';
    feedbackSection.style.display = 'block';
    
    feedbackSection.innerHTML = `
        <div class="feedback-container">
            <h2>Interview Feedback</h2>
            <div class="feedback-header">
                <div class="score-circle">
                    <div class="score-value">${feedback.total_score}</div>
                    <div class="score-label">/ 100</div>
                </div>
                <div class="interview-info">
                    <p><strong>Duration:</strong> ${feedback.interview_duration_minutes} minutes</p>
                </div>
            </div>
            
            <div class="feedback-section-item">
                <h3>Overall Feedback</h3>
                <p>${feedback.overall_feedback || 'No overall feedback available.'}</p>
            </div>
            
            <div class="feedback-grid">
                <div class="feedback-section-item">
                    <h3>Strengths</h3>
                    <ul>
                        ${feedback.strengths ? feedback.strengths.map(s => `<li>${s}</li>`).join('') : '<li>No strengths listed</li>'}
                    </ul>
                </div>
                
                <div class="feedback-section-item">
                    <h3>Weaknesses</h3>
                    <ul>
                        ${feedback.weaknesses ? feedback.weaknesses.map(w => `<li>${w}</li>`).join('') : '<li>No weaknesses listed</li>'}
                    </ul>
                </div>
            </div>
            
            <div class="feedback-section-item">
                <h3>Areas of Improvement</h3>
                <ul>
                    ${feedback.areas_of_improvement ? feedback.areas_of_improvement.map(a => `<li>${a}</li>`).join('') : '<li>No areas listed</li>'}
                </ul>
            </div>
            
            <div class="feedback-grid">
                <div class="feedback-section-item">
                    <h3>Technical Assessment</h3>
                    <p>${feedback.technical_assessment || 'No technical assessment available.'}</p>
                </div>
                
                <div class="feedback-section-item">
                    <h3>Communication Assessment</h3>
                    <p>${feedback.communication_assessment || 'No communication assessment available.'}</p>
                </div>
            </div>
        </div>
    `;
}

// Reset interview
function resetInterview() {
    if (confirm('Are you sure you want to start a new interview? This will clear the current session.')) {
        if (statusCheckInterval) {
            clearInterval(statusCheckInterval);
        }
        sessionId = 'session_' + Date.now();
        resumeUploaded = false;
        document.getElementById('chatMessages').innerHTML = '';
        document.getElementById('resumeInput').value = '';
        document.getElementById('fileName').textContent = '';
        document.getElementById('submitBtn').disabled = true;
        document.getElementById('uploadStatus').textContent = '';
        document.getElementById('uploadStatus').className = 'status-message';
        document.getElementById('chatSection').style.display = 'none';
        document.getElementById('uploadSection').style.display = 'block';
        document.getElementById('feedbackSection').style.display = 'none';
        document.getElementById('chatMessages').style.display = 'block';
        const inputContainer = document.querySelector('.transcript-input-container') || document.querySelector('.chat-input-container');
        if (inputContainer) inputContainer.style.display = 'flex';
        document.getElementById('chatInput').disabled = false;
        document.querySelector('.send-btn').disabled = false;
        document.getElementById('timer').textContent = '05:00';
        document.getElementById('timer').style.color = '#fff';
        
        // Stop media streams
        stopMediaStreams();
    }
}

// Text-to-Speech function
function speakText(text) {
    // Stop any current speech
    if (currentUtterance) {
        synth.cancel();
    }
    
    // Remove JobGenie's greeting/introduction from speech if present
    let speechText = text;
    if (speechText.toLowerCase().includes('jobgenie')) {
        // Extract just the question part
        const parts = speechText.split(/[.!?]/);
        speechText = parts.filter(p => !p.toLowerCase().includes('jobgenie')).join('. ').trim();
        if (!speechText) {
            speechText = text; // Fallback to full text
        }
    }
    
    const utterance = new SpeechSynthesisUtterance(speechText);
    utterance.rate = 0.9;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    
    // Show speaking indicator
    const speakingIndicator = document.getElementById('speakingIndicator');
    speakingIndicator.style.display = 'flex';
    document.getElementById('jobgenieAvatar').classList.add('speaking');
    
    utterance.onend = function() {
        speakingIndicator.style.display = 'none';
        document.getElementById('jobgenieAvatar').classList.remove('speaking');
        currentUtterance = null;
    };
    
    utterance.onerror = function() {
        speakingIndicator.style.display = 'none';
        document.getElementById('jobgenieAvatar').classList.remove('speaking');
        currentUtterance = null;
    };
    
    currentUtterance = utterance;
    synth.speak(utterance);
}

// Toggle Microphone
function toggleMicrophone() {
    if (!recognition) {
        alert('Speech recognition is not supported in your browser. Please use Chrome or Edge.');
        return;
    }
    
    const micBtn = document.getElementById('micBtn');
    const micStatus = document.getElementById('micStatus');
    
    if (isListening) {
        // Stop listening
        recognition.stop();
        isListening = false;
        micBtn.classList.remove('active');
        micStatus.textContent = 'Mic Off';
        micStatus.style.color = '#999';
    } else {
        // Start listening
        try {
            recognition.start();
            isListening = true;
            micBtn.classList.add('active');
            micStatus.textContent = 'Mic On';
            micStatus.style.color = '#4caf50';
        } catch (error) {
            console.error('Error starting recognition:', error);
            alert('Error starting microphone. Please check permissions.');
        }
    }
}

// Toggle Camera
async function toggleCamera() {
    const cameraBtn = document.getElementById('cameraBtn');
    const cameraStatus = document.getElementById('cameraStatus');
    const userCameraContainer = document.getElementById('userCameraContainer');
    const userVideo = document.getElementById('userVideo');
    
    if (userStream) {
        // Turn off camera
        userStream.getTracks().forEach(track => track.stop());
        userStream = null;
        userCameraContainer.style.display = 'none';
        cameraBtn.classList.remove('active');
        cameraStatus.textContent = 'Camera Off';
        cameraStatus.style.color = '#999';
    } else {
        // Turn on camera
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ 
                video: true, 
                audio: false 
            });
            userStream = stream;
            userVideo.srcObject = stream;
            userCameraContainer.style.display = 'block';
            cameraBtn.classList.add('active');
            cameraStatus.textContent = 'Camera On';
            cameraStatus.style.color = '#4caf50';
        } catch (error) {
            console.error('Error accessing camera:', error);
            alert('Error accessing camera. Please check permissions.');
        }
    }
}

// Request Media Permissions
async function requestMediaPermissions() {
    try {
        // Request microphone permission
        await navigator.mediaDevices.getUserMedia({ audio: true });
        // Request camera permission (optional)
        // await navigator.mediaDevices.getUserMedia({ video: true });
    } catch (error) {
        console.log('Media permissions not granted:', error);
    }
}

// Stop all media streams
function stopMediaStreams() {
    // Stop speech recognition
    if (recognition && isListening) {
        recognition.stop();
        isListening = false;
    }
    
    // Stop text-to-speech
    if (synth.speaking) {
        synth.cancel();
    }
    
    // Stop camera
    if (userStream) {
        userStream.getTracks().forEach(track => track.stop());
        userStream = null;
    }
    
    // Reset UI
    document.getElementById('micBtn').classList.remove('active');
    document.getElementById('micStatus').textContent = 'Mic Off';
    document.getElementById('micStatus').style.color = '#999';
    document.getElementById('cameraBtn').classList.remove('active');
    document.getElementById('cameraStatus').textContent = 'Camera Off';
    document.getElementById('cameraStatus').style.color = '#999';
    document.getElementById('userCameraContainer').style.display = 'none';
    document.getElementById('speakingIndicator').style.display = 'none';
    document.getElementById('jobgenieAvatar').classList.remove('speaking');
}

