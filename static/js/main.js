// Insurance AI Assistant - Main JavaScript

// Configuration
const CONFIG = {
    API_BASE_URL: '/api/v1',
    AUTH_TOKEN: 'Bearer bf0fde9df23f5a761aac76887c4050fee4b3b2d58a5606237a544280594f6d63'
};

// DOM elements
let elements = {};

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    initializeElements();
    bindEvents();
    loadSystemHealth();
});

function initializeElements() {
    elements = {
        form: document.getElementById('analysisForm'),
        submitBtn: document.getElementById('submitBtn'),
        loadingDiv: document.getElementById('loading'),
        resultsDiv: document.getElementById('results'),
        statusDiv: document.getElementById('status'),
        documentUrl: document.getElementById('documentUrl'),
        questions: document.getElementById('questions')
    };
}

function bindEvents() {
    elements.form.addEventListener('submit', handleFormSubmit);
    
    // Add input validation
    elements.documentUrl.addEventListener('input', validateUrl);
    elements.questions.addEventListener('input', validateQuestions);
}

async function handleFormSubmit(e) {
    e.preventDefault();
    
    const documentUrl = elements.documentUrl.value.trim();
    const questionsText = elements.questions.value.trim();
    
    // Validation
    if (!validateInputs(documentUrl, questionsText)) {
        return;
    }
    
    // Parse questions
    const questions = parseQuestions(questionsText);
    
    if (questions.length === 0) {
        showAlert('Please enter at least one question');
        return;
    }
    
    // Process analysis
    await processAnalysis(documentUrl, questions);
}

function validateInputs(documentUrl, questionsText) {
    if (!documentUrl) {
        showAlert('Please enter a document URL');
        elements.documentUrl.focus();
        return false;
    }
    
    if (!questionsText) {
        showAlert('Please enter at least one question');
        elements.questions.focus();
        return false;
    }
    
    // Basic URL validation
    try {
        new URL(documentUrl);
    } catch {
        showAlert('Please enter a valid URL');
        elements.documentUrl.focus();
        return false;
    }
    
    return true;
}

function parseQuestions(questionsText) {
    return questionsText
        .split('\n')
        .map(q => q.trim())
        .filter(q => q.length > 0);
}

async function processAnalysis(documentUrl, questions) {
    setLoadingState(true);
    clearResults();
    
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/hackrx/run`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': CONFIG.AUTH_TOKEN
            },
            body: JSON.stringify({
                documents: documentUrl,
                questions: questions
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(`HTTP ${response.status}: ${errorData.detail || 'Analysis failed'}`);
        }
        
        const data = await response.json();
        
        if (!data.answers || !Array.isArray(data.answers)) {
            throw new Error('Invalid response format');
        }
        
        displayResults(data.answers, questions);
        
    } catch (error) {
        console.error('Analysis error:', error);
        displayError(error.message);
    } finally {
        setLoadingState(false);
    }
}

function setLoadingState(loading) {
    elements.submitBtn.disabled = loading;
    elements.submitBtn.textContent = loading ? 'Analyzing Policy...' : 'Analyze Policy';
    elements.loadingDiv.style.display = loading ? 'block' : 'none';
}

function clearResults() {
    elements.resultsDiv.innerHTML = '';
}

function displayResults(answers, questions) {
    let html = '<h3>📊 Analysis Results</h3>';
    
    answers.forEach((answer, index) => {
        html += `
            <div class="result-item">
                <div class="question">
                    <strong>Q${index + 1}:</strong> ${escapeHtml(questions[index])}
                </div>
                <div class="answer">
                    <strong>Answer:</strong> ${escapeHtml(answer)}
                </div>
            </div>
        `;
    });
    
    elements.resultsDiv.innerHTML = html;
    
    // Smooth scroll to results
    elements.resultsDiv.scrollIntoView({ 
        behavior: 'smooth', 
        block: 'start' 
    });
}

function displayError(message) {
    elements.resultsDiv.innerHTML = `
        <div class="error">
            <h3>⚠️ Analysis Error</h3>
            <p>Failed to analyze policy: ${escapeHtml(message)}</p>
            <p style="margin-top: 10px; font-size: 14px; opacity: 0.8;">
                Please check your document URL and try again.
            </p>
        </div>
    `;
}

async function loadSystemHealth() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/system/health`, {
            headers: {
                'Authorization': CONFIG.AUTH_TOKEN
            }
        });
        
        if (response.ok) {
            const health = await response.json();
            updateStatus(health.status === 'operational' ? 'operational' : 'degraded');
        } else {
            updateStatus('degraded');
        }
    } catch (error) {
        console.error('Health check failed:', error);
        updateStatus('degraded');
    }
}

function updateStatus(status) {
    const statusDot = elements.statusDiv.querySelector('.status-dot');
    const statusText = elements.statusDiv.querySelector('.status-text');
    
    if (status === 'operational') {
        statusDot.style.backgroundColor = '#10b981';
        statusText.textContent = '✅ System Operational';
    } else {
        statusDot.style.backgroundColor = '#ef4444';
        statusText.textContent = '⚠️ System Degraded';
    }
}

function validateUrl(e) {
    const url = e.target.value.trim();
    const urlInput = e.target;
    
    if (url && !isValidUrl(url)) {
        urlInput.style.borderColor = '#ef4444';
        urlInput.style.boxShadow = '0 0 0 3px rgba(239, 68, 68, 0.1)';
    } else {
        urlInput.style.borderColor = '#e5e7eb';
        urlInput.style.boxShadow = 'none';
    }
}

function validateQuestions(e) {
    const questions = parseQuestions(e.target.value);
    const questionsInput = e.target;
    
    // Visual feedback for question count
    if (questions.length === 0 && e.target.value.trim()) {
        questionsInput.style.borderColor = '#f59e0b';
    } else {
        questionsInput.style.borderColor = '#e5e7eb';
    }
}

// Utility functions
function isValidUrl(string) {
    try {
        new URL(string);
        return true;
    } catch {
        return false;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showAlert(message) {
    alert(message); // You can replace with a custom modal later
}

// Export for potential testing
window.InsuranceAI = {
    processAnalysis,
    loadSystemHealth,
    CONFIG
};
