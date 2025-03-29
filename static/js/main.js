// Global variables
let editor;
let currentQuestionId;
let loadedFunction;

// Initialize Monaco Editor
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
    
    editor = monaco.editor.create(document.getElementById('code-editor'), {
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
        bracketPairColorization: {
            enabled: true
        },
        guides: {
            bracketPairs: true,
            indentation: true
        }
    });
});

// Generate Question Button
document.getElementById('generate-btn').addEventListener('click', generateQuestion);

// Submit Solution Button
document.getElementById('submit-btn').addEventListener('click', submitSolution);

// Hero Start Button
document.getElementById('hero-start-btn').addEventListener('click', function() {
    document.getElementById('hero-section').classList.add('hidden');
    document.getElementById('stats-container').classList.remove('hidden');
    generateQuestion();
});

async function generateQuestion() {
    const difficulty = document.getElementById('difficulty').value;
    const topic = document.getElementById('topic').value;
    
    // Hide hero section if visible
    document.getElementById('hero-section').classList.add('hidden');
    
    // Show loading indicator
    document.getElementById('loading').classList.remove('hidden');
    document.getElementById('question-container').classList.add('hidden');
    document.getElementById('editor-container').classList.add('hidden');
    document.getElementById('submit-container').classList.add('hidden');
    document.getElementById('results-container').classList.add('hidden');
    document.getElementById('stats-container').classList.add('hidden');
    
    try {
        const response = await fetch('/api/generate-question', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                difficulty,
                topic: topic || undefined
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            displayQuestion(data);
            // Show stats after success
            document.getElementById('stats-container').classList.remove('hidden');
            
            // Dispatch event for Coding Buddy
            const event = new CustomEvent('questionGenerated', {
                detail: data
            });
            document.dispatchEvent(event);
        } else {
            showError('Failed to generate question: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error:', error);
        showError('An error occurred while generating the question: ' + error.message);
    } finally {
        // Hide loading indicator
        document.getElementById('loading').classList.add('hidden');
    }
}

function showError(message) {
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
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        toast.remove();
    }, 5000);
}

function displayQuestion(data) {
    currentQuestionId = data.question_id;
    const questionInfo = data.question_info;
    
    // Add animation class for fade-in effect
    document.getElementById('question-container').classList.add('animate-fade-in');
    document.getElementById('editor-container').classList.add('animate-fade-in');
    document.getElementById('submit-container').classList.add('animate-fade-in');
    
    // Set question title
    document.getElementById('question-title').textContent = `${questionInfo.function_name}`;
    
    // Set difficulty badge
    const difficultyBadge = document.getElementById('question-difficulty');
    const difficulty = questionInfo.difficulty || 'medium';
    difficultyBadge.textContent = difficulty.charAt(0).toUpperCase() + difficulty.slice(1);
    difficultyBadge.className = `badge difficulty-badge badge-${difficulty}`;
    
    // Set description
    document.getElementById('question-description').innerHTML = `<p>${questionInfo.problem_statement.replace(/\n/g, '<br>')}</p>`;
    
    // Set function signature
    document.getElementById('function-signature').textContent = questionInfo.function_signature;
    
    // Set examples
    const examplesContainer = document.getElementById('examples-container');
    examplesContainer.innerHTML = '';
    
    if (questionInfo.examples && questionInfo.examples.length > 0) {
        questionInfo.examples.forEach((example, index) => {
            const exampleDiv = document.createElement('div');
            exampleDiv.classList.add('example', 'mb-3', 'animate-fade-in');
            exampleDiv.style.animationDelay = `${index * 0.1}s`;
            exampleDiv.innerHTML = `
                <p><strong>Example ${index + 1}:</strong></p>
                <p><code>${example.input_text}</code></p>
                <p><code>${example.output_text}</code></p>
            `;
            examplesContainer.appendChild(exampleDiv);
        });
    }
    
    // Set constraints
    const constraintsList = document.getElementById('constraints-list');
    constraintsList.innerHTML = '';
    
    if (questionInfo.constraints && questionInfo.constraints.length > 0) {
        questionInfo.constraints.forEach((constraint, index) => {
            const li = document.createElement('li');
            li.classList.add('animate-fade-in');
            li.style.animationDelay = `${index * 0.1}s`;
            li.innerHTML = `<code>${constraint}</code>`;
            constraintsList.appendChild(li);
        });
    }
    
    // Update editor with function template
    if (editor) {
        loadedFunction = questionInfo.function_signature;
        editor.setValue(questionInfo.function_signature + '\n    # Write your solution here\n    pass\n');
        
        // Focus on editor and position cursor at a good starting point
        setTimeout(() => {
            editor.focus();
            const lineCount = editor.getModel().getLineCount();
            const lastLineLength = editor.getModel().getLineContent(lineCount).length;
            editor.setPosition({ lineNumber: lineCount - 1, column: 1 });
        }, 500);
    }
    
    // Show question and editor
    document.getElementById('question-container').classList.remove('hidden');
    document.getElementById('editor-container').classList.remove('hidden');
    document.getElementById('submit-container').classList.remove('hidden');
    document.getElementById('results-container').classList.add('hidden');
}

async function submitSolution() {
    if (!currentQuestionId) {
        showError('No question is currently active.');
        return;
    }
    
    const code = editor.getValue();
    
    // Basic validation
    if (!code.includes(loadedFunction)) {
        showError('Please keep the function signature intact.');
        return;
    }
    
    // Show loading state on button
    const submitBtn = document.getElementById('submit-btn');
    const originalText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Running tests...';
    
    try {
        const response = await fetch('/api/submit-solution', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question_id: currentQuestionId,
                code
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            displayResults(data.results);
            
            // Dispatch event for Coding Buddy
            const event = new CustomEvent('testResults', {
                detail: data.results
            });
            document.dispatchEvent(event);
            
        } else {
            showError('Failed to submit solution: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error:', error);
        showError('An error occurred while submitting your solution: ' + error.message);
    } finally {
        // Reset button
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
}

function displayResults(results) {
    const resultsContainer = document.getElementById('results-container');
    const summary = document.getElementById('summary');
    const testCasesContainer = document.getElementById('test-cases');
    
    // Add animation
    resultsContainer.classList.add('animate-fade-in');
    
    // Show results section
    resultsContainer.classList.remove('hidden');
    
    // Update summary
    if (results.success === false) {
        summary.className = 'alert alert-danger';
        summary.innerHTML = `
            <h4><i class="fas fa-times-circle me-2"></i>Execution Error</h4>
            <p>${results.error}</p>
        `;
        testCasesContainer.innerHTML = '';
        return;
    }
    
    // Update summary based on passing ratio
    const passingRatio = results.passing_ratio;
    if (passingRatio === 1) {
        summary.className = 'alert alert-success';
        summary.innerHTML = `
            <div class="d-flex align-items-center">
                <div class="me-3">
                    <i class="fas fa-check-circle fa-3x"></i>
                </div>
                <div>
                    <h4>All Tests Passed!</h4>
                    <p class="mb-0">You passed ${results.passed_tests} out of ${results.total_tests} tests. Great job!</p>
                </div>
            </div>
            <div class="confetti-container" id="confetti"></div>
        `;
        
        // Show confetti animation for passing all tests
        showConfetti();
        
        // Update stats for successful completion
        updateStats();
    } else if (passingRatio >= 0.5) {
        summary.className = 'alert alert-warning';
        summary.innerHTML = `
            <div class="d-flex align-items-center">
                <div class="me-3">
                    <i class="fas fa-exclamation-triangle fa-3x"></i>
                </div>
                <div>
                    <h4>Some Tests Passed</h4>
                    <p class="mb-0">You passed ${results.passed_tests} out of ${results.total_tests} tests. You're getting closer!</p>
                </div>
            </div>
        `;
    } else {
        summary.className = 'alert alert-danger';
        summary.innerHTML = `
            <div class="d-flex align-items-center">
                <div class="me-3">
                    <i class="fas fa-times-circle fa-3x"></i>
                </div>
                <div>
                    <h4>Most Tests Failed</h4>
                    <p class="mb-0">You passed only ${results.passed_tests} out of ${results.total_tests} tests. Keep trying!</p>
                </div>
            </div>
        `;
    }
    
    // Update test cases
    testCasesContainer.innerHTML = '';
    
    // Sort test cases: examples first, then by test_id
    const sortedResults = [...results.results].sort((a, b) => {
        if (a.is_example && !b.is_example) return -1;
        if (!a.is_example && b.is_example) return 1;
        return a.test_id - b.test_id;
    });
    
    sortedResults.forEach((test, index) => {
        const testDiv = document.createElement('div');
        testDiv.classList.add('test-case', 'animate-fade-in');
        testDiv.style.animationDelay = `${index * 0.1}s`;
        
        if (test.error) {
            testDiv.classList.add('failed');
            testDiv.innerHTML = `
                <h5><i class="fas fa-times-circle me-2"></i>Test ${test.test_id} ${test.is_example ? '(Example)' : ''}: Failed with Error</h5>
                <p><strong>Inputs:</strong> <code>${JSON.stringify(test.inputs)}</code></p>
                <p><strong>Expected:</strong> <code>${JSON.stringify(test.expected_output)}</code></p>
                <p><strong>Error:</strong> <code>${test.error}</code></p>
            `;
        } else if (test.passed) {
            testDiv.classList.add('passed');
            testDiv.innerHTML = `
                <h5><i class="fas fa-check-circle me-2"></i>Test ${test.test_id} ${test.is_example ? '(Example)' : ''}: Passed</h5>
                <div class="row">
                    <div class="col-md-4">
                        <p><strong>Inputs:</strong></p>
                        <code>${JSON.stringify(test.inputs)}</code>
                    </div>
                    <div class="col-md-4">
                        <p><strong>Expected:</strong></p>
                        <code>${JSON.stringify(test.expected_output)}</code>
                    </div>
                    <div class="col-md-4">
                        <p><strong>Your Output:</strong></p>
                        <code>${JSON.stringify(test.actual_output)}</code>
                    </div>
                </div>
            `;
        } else {
            testDiv.classList.add('failed');
            testDiv.innerHTML = `
                <h5><i class="fas fa-times-circle me-2"></i>Test ${test.test_id} ${test.is_example ? '(Example)' : ''}: Failed</h5>
                <div class="row">
                    <div class="col-md-4">
                        <p><strong>Inputs:</strong></p>
                        <code>${JSON.stringify(test.inputs)}</code>
                    </div>
                    <div class="col-md-4">
                        <p><strong>Expected:</strong></p>
                        <code>${JSON.stringify(test.expected_output)}</code>
                    </div>
                    <div class="col-md-4">
                        <p><strong>Your Output:</strong></p>
                        <code>${JSON.stringify(test.actual_output)}</code>
                    </div>
                </div>
            `;
        }
        
        testCasesContainer.appendChild(testDiv);
    });
    
    // Scroll to results
    resultsContainer.scrollIntoView({ behavior: 'smooth' });
}

function showConfetti() {
    // Create confetti elements
    const confettiContainer = document.getElementById('confetti');
    const colors = ['#4F46E5', '#10B981', '#F59E0B', '#EF4444', '#06B6D4', '#8B5CF6'];
    
    for (let i = 0; i < 100; i++) {
        const confetti = document.createElement('div');
        confetti.className = 'confetti-piece';
        confetti.style.width = `${Math.random() * 10 + 5}px`;
        confetti.style.height = `${Math.random() * 10 + 5}px`;
        confetti.style.background = colors[Math.floor(Math.random() * colors.length)];
        confetti.style.position = 'absolute';
        confetti.style.top = `-10px`;
        confetti.style.left = `${Math.random() * 100}%`;
        confetti.style.transformOrigin = 'center';
        confetti.style.opacity = Math.random() + 0.5;
        confetti.style.zIndex = '1000';
        confetti.style.borderRadius = Math.random() > 0.5 ? '50%' : '0';
        
        // Add animation
        confetti.style.animation = `
            fall ${Math.random() * 3 + 2}s linear forwards,
            sway ${Math.random() * 2 + 3}s ease-in-out infinite alternate
        `;
        
        confettiContainer.appendChild(confetti);
    }
    
    // Remove confetti after animation
    setTimeout(() => {
        confettiContainer.innerHTML = '';
    }, 5000);
}

function updateStats() {
    // Simple function to update the stats (simulated for now)
    const problemsElement = document.querySelector('#stats-container .stats-card:nth-child(1) h3');
    const streakElement = document.querySelector('#stats-container .stats-card:nth-child(2) h3');
    const pointsElement = document.querySelector('#stats-container .stats-card:nth-child(3) h3');
    
    // Get current values
    let problems = parseInt(problemsElement.textContent.match(/\d+/)[0]);
    let streak = parseInt(streakElement.textContent.match(/\d+/)[0]);
    let points = parseInt(pointsElement.textContent.match(/\d+/)[0]);
    
    // Update values
    problems++;
    streak++;
    points += 10;
    
    // Update UI with animation
    problemsElement.innerHTML = `<i class="fas fa-check-circle text-success me-2"></i>${problems}`;
    streakElement.innerHTML = `<i class="fas fa-fire text-warning me-2"></i>${streak}`;
    pointsElement.innerHTML = `<i class="fas fa-star text-primary me-2"></i>${points}`;
    
    // Flash animation
    const statsCards = document.querySelectorAll('.stats-card');
    statsCards.forEach(card => {
        card.style.transition = 'all 0.3s ease';
        card.style.transform = 'scale(1.05)';
        card.style.boxShadow = '0 15px 30px rgba(79, 70, 229, 0.2)';
        setTimeout(() => {
            card.style.transform = 'scale(1)';
            card.style.boxShadow = '0 10px 15px rgba(0,0,0,0.05)';
        }, 500);
    });
}

// Add keyboard shortcuts
document.addEventListener('keydown', function(event) {
    // Ctrl+Enter or Command+Enter to submit solution
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        if (!document.getElementById('submit-container').classList.contains('hidden')) {
            submitSolution();
            event.preventDefault();
        }
    }
});

// Load a question when the page loads (optional)
window.addEventListener('load', function() {
    // Show hero section by default
    document.getElementById('hero-section').classList.remove('hidden');
    
    // Initialize tooltips if you want to use Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });
    
    // Setup event tracking for editor changes
    if (editor) {
        editor.onDidChangeModelContent(() => {
            const code = editor.getValue();
            // Dispatch event for coding buddy
            const event = new CustomEvent('codeSolution', {
                detail: { code }
            });
            document.dispatchEvent(event);
        });
    }
});