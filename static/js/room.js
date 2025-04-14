// Room-specific JavaScript functionality

// Global variables
let editor;
let currentQuestionId = null;
let loadedFunctionSignature = null;
let questionPollingInterval = null;
let editorInitialized = false;
let codingBuddyInstance = null;
let userCodeStorage = {};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Room.js loaded');
    
    // Initialize editor
    initializeEditor();
    
    // Ensure submit button event listener is properly attached
    const submitBtn = document.getElementById('submit-btn');
    if (submitBtn) {
        console.log('Submit button found, attaching event listener');
        submitBtn.addEventListener('click', function(event) {
            console.log('Submit button clicked');
            submitSolution();
        });
    } else {
        console.error('Submit button not found in DOM');
    }
    
    // Attach event listener to generate button if it exists
    const generateBtn = document.getElementById('generate-btn');
    if (generateBtn) {
        console.log('Generate button found, attaching event listener');
        generateBtn.addEventListener('click', function(event) {
            console.log('Generate button clicked');
            generateQuestion();
        });
    }
    
    // Add keyboard shortcut for submission
    document.addEventListener('keydown', function(event) {
        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
            if (currentQuestionId && !document.getElementById('submit-container').classList.contains('hidden')) {
                console.log('Keyboard shortcut detected: Ctrl+Enter');
                submitSolution();
                event.preventDefault();
            }
        }
    });
});

// Initialize Monaco Editor
function initializeEditor() {
    if (editorInitialized) {
        console.log('Editor already initialized');
        return;
    }

    console.log('Initializing Monaco editor');
    require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs' }});
    require(['vs/editor/editor.main'], function() {
        monaco.editor.defineTheme('codeChallenge', {
            base: 'vs',
            inherit: true,
            rules: [
                { token: 'comment', foreground: '6B7280', fontStyle: 'italic' },
                { token: 'keyword', foreground: '8B5CF6', fontStyle: 'bold' },
                { token: 'string', foreground: '10B981' },
                { token: 'number', foreground: 'F59E0B' },
                { token: 'type', foreground: '3B82F6' }
            ],
            colors: {
                'editor.foreground': '#1F2937',
                'editor.background': '#FFFFFF',
                'editorCursor.foreground': '#4F46E5',
                'editor.lineHighlightBackground': '#F3F4F6',
                'editorLineNumber.foreground': '#9CA3AF',
                'editor.selectionBackground': '#DBEAFE',
                'editor.inactiveSelectionBackground': '#E5E7EB'
            }
        });

        const editorElement = document.getElementById('code-editor');
        if (editorElement) {
            console.log('Editor element found, creating Monaco editor');
            editor = monaco.editor.create(editorElement, {
                value: '# Write your solution here\n',
                language: 'python',
                theme: 'codeChallenge',
                automaticLayout: true,
                minimap: { enabled: true },
                fontSize: 14,
                lineHeight: 24,
                fontFamily: "'Fira Code', monospace",
                padding: { top: 20, bottom: 20 },
                scrollBeyondLastLine: false,
                cursorBlinking: 'smooth',
                cursorSmoothCaretAnimation: true,
                formatOnPaste: true,
                formatOnType: true,
                bracketPairColorization: { enabled: true },
                guides: { bracketPairs: true, indentation: true }
            });

            editor.onDidChangeModelContent(() => {
                console.log('Editor content changed');
                if (codingBuddyInstance) {
                    codingBuddyInstance.userSolution = editor.getValue();
                }

                if (currentQuestionId) {
                    userCodeStorage[currentQuestionId] = editor.getValue();
                    saveCodeToLocalStorage();
                }
            });

            editorInitialized = true;
            console.log('Editor initialized successfully');

            if (currentQuestionId) {
                loadQuestion(currentQuestionId);
            } else {
                checkForExistingQuestion();
            }

            loadCodeFromLocalStorage();
        } else {
            console.error('Editor element not found in DOM');
        }
    });
}

// Submit solution
async function submitSolution() {
    console.log('Submit solution function called');
    console.log('Current question ID:', currentQuestionId);
    console.log('Editor initialized:', !!editor);
    
    if (!currentQuestionId) {
        showError('No question is currently active.');
        return;
    }

    if (!editor) {
        showError('Code editor is not initialized.');
        return;
    }

    const code = editor.getValue();
    console.log('Code retrieved from editor');

    if (!code.includes(loadedFunctionSignature)) {
        showError('Please keep the function signature intact.');
        return;
    }

    // Hide previous results before submitting new solution
    const resultsContainer = document.getElementById('results-container');
    if (resultsContainer && !resultsContainer.classList.contains('hidden')) {
        resultsContainer.classList.add('hidden');
    }

    // Show loading indicator
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.classList.remove('hidden');
    }

    const submitBtn = document.getElementById('submit-btn');
    if (submitBtn) {
        submitBtn.disabled = true;
    }

    try {
        console.log('Submitting solution to API endpoint');
        
        // Get the room ID from the URL
        const pathParts = window.location.pathname.split('/');
        const roomCode = pathParts[pathParts.length - 1];
        console.log('Room code from URL:', roomCode);
        
        // Get the room ID from the data attribute if available
        const roomIdElement = document.querySelector('[data-room-id]');
        const roomId = roomIdElement ? roomIdElement.getAttribute('data-room-id') : null;
        console.log('Room ID from data attribute:', roomId);
        
        // Use the appropriate API endpoint
        const apiUrl = roomId 
            ? `/api/room/${roomId}/submit-solution`
            : `/api/room/${roomCode}/submit-solution`;
        console.log('API URL:', apiUrl);

        const requestBody = {
            question_id: currentQuestionId,
            code
        };
        console.log('Request body:', requestBody);

        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        console.log('Response status:', response.status);

        if (!response.ok) {
            console.error(`HTTP error! Status: ${response.status}`);
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Response data:', data);

        if (data.success) {
            console.log('Solution submission successful');
            // Small delay to ensure smooth transition
            setTimeout(() => {
                console.log('Displaying results');
                displayResults(data.results);

                if (codingBuddyInstance) {
                    codingBuddyInstance.lastTestResults = data.results;
                }
            }, 300);
        } else {
            console.error('Failed to submit solution:', data.error || 'Unknown error');
            showError('Failed to submit solution: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error:', error);
        showError('An error occurred while submitting your solution: ' + error.message);
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
        }
        if (loadingIndicator) {
            loadingIndicator.classList.add('hidden');
        }
    }
}

// Show error messages
function showError(message) {
    console.error('Error:', message);
    const toast = document.createElement('div');
    toast.className = 'position-fixed bottom-0 end-0 p-3';
    toast.style.zIndex = '5';
    toast.innerHTML = `
        <div class="toast show" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header bg-danger text-white">
                <i class="fas fa-exclamation-circle me-2"></i>
                <strong class="me-auto">Error</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 5000);
}

// Add a data attribute with the room ID to the page
function addRoomIdDataAttribute() {
    const roomIdMatch = window.location.pathname.match(/\/room\/([^\/]+)/);
    if (roomIdMatch && roomIdMatch[1]) {
        const roomCode = roomIdMatch[1];
        document.body.setAttribute('data-room-code', roomCode);
        
        // Fetch the room ID from the API
        fetch(`/api/room/${roomCode}/status`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.room && data.room.id) {
                    document.body.setAttribute('data-room-id', data.room.id);
                    console.log('Room ID set:', data.room.id);
                }
            })
            .catch(error => {
                console.error('Error fetching room ID:', error);
            });
    }
}

// Call this function when the page loads
document.addEventListener('DOMContentLoaded', addRoomIdDataAttribute);
