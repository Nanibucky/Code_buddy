// Simplified Coding Buddy implementation
class CodingBuddy {
    constructor() {
        this.currentQuestion = null;
        this.userSolution = null;
        this.lastTestResults = null;
        this.messages = [];
        this.isOpen = false;
        
        // Initialize UI elements
        this.elements = {
            container: document.getElementById('coding-buddy-container'),
            messages: document.getElementById('buddy-messages'),
            input: document.getElementById('buddy-message-input'),
            send: document.getElementById('buddy-send-button'),
            toggle: document.getElementById('coding-buddy-toggle'),
            close: document.getElementById('buddy-close'),
            minimize: document.getElementById('buddy-minimize')
        };

        // Verify all elements exist
        if (!this.validateElements()) {
            console.error('Some coding buddy elements are missing');
            return;
        }

        this.bindEvents();
        
        // Add initial welcome message immediately after construction
        this.initializeChat();
    }

    validateElements() {
        return Object.values(this.elements).every(element => element !== null);
    }

    initializeChat() {
        // Clear existing messages
        if (this.elements.messages) {
            this.elements.messages.innerHTML = '';
        }
        
        // Add welcome message
        this.addBuddyMessage(`Hi! 👋 I'm your coding buddy. I can help you with:
- Understanding the current problem
- Debugging your code
- Providing hints when you're stuck
- Explaining programming concepts

What would you like help with?`);

        // Store welcome message in messages array
        this.messages = [{
            type: 'buddy',
            content: this.welcomeMessage
        }];
    }
    
    bindEvents() {
        if (!this.validateElements()) return;
        
        this.elements.toggle.addEventListener('click', () => {
            this.isOpen = !this.isOpen;
            if (this.isOpen) {
                this.elements.container.classList.add('open');
                // Always ensure messages container has content
                if (this.elements.messages.children.length === 0) {
                    this.initializeChat();
                }
                setTimeout(() => {
                    this.elements.input.focus();
                    this.scrollToBottom();
                }, 300);
            } else {
                this.elements.container.classList.remove('open');
            }
        });
        
        // Close and minimize buttons
        this.elements.close.addEventListener('click', () => this.closeChat());
        this.elements.minimize.addEventListener('click', () => this.closeChat());
        
        // Send message handlers
        this.elements.send.addEventListener('click', () => this.sendUserMessage());
        this.elements.input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendUserMessage();
            }
        });
        
        // Listen for question and code events
        document.addEventListener('questionGenerated', (e) => {
            this.currentQuestion = e.detail.question_info;
        });
        
        document.addEventListener('codeSolution', (e) => {
            this.userSolution = e.detail.code;
        });
        
        document.addEventListener('testResults', (e) => {
            this.lastTestResults = e.detail;
        });
    }
    
    closeChat() {
        this.isOpen = false;
        this.elements.container.classList.remove('open');
    }
    
    async sendUserMessage() {
        const inputEl = document.getElementById('buddy-message-input');
        const message = inputEl.value.trim();
        
        if (message) {
            // Add user message to chat
            this.addUserMessage(message);
            
            // Clear input
            inputEl.value = '';
            
            // Process user message with the API
            await this.processUserMessageWithAPI(message);
        }
    }
    
    // Update the processUserMessageWithAPI function in coding-buddy.js

async processUserMessageWithAPI(message) {
    // Show typing indicator
    this.showTypingIndicator();
    
    try {
        console.log("Sending message to API:", message.substring(0, 30) + "...");
        
        // Call the backend API
        const response = await fetch('/api/chat-completion', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_message: message,
                question_info: this.currentQuestion,
                code_solution: this.userSolution,
                test_results: this.lastTestResults
            })
        });
        
        console.log("Response status:", response.status);
        
        // Handle non-200 responses
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({
                error: `Server error: ${response.status} ${response.statusText}`
            }));
            
            console.error("API error:", errorData);
            
            this.hideTypingIndicator();
            this.addBuddyMessage(`Error: ${errorData.message || errorData.error || 'Something went wrong with the request. Please try again later.'}`);
            return;
        }
        
        const data = await response.json();
        console.log("Response data received:", data.success);
        
        // Hide typing indicator
        this.hideTypingIndicator();
        
        // Display the response
        if (data.success) {
            this.addBuddyMessage(data.message);
        } else {
            throw new Error(data.error || data.message || "Unknown error");
        }
    } catch (error) {
        console.error("Error processing message with API:", error);
        this.hideTypingIndicator();
        this.addBuddyMessage(`Sorry, I encountered an error: ${error.message}. Please check the browser console for more details or try again later.`);
    }
}
    
    addBuddyMessage(message) {
        if (!this.elements.messages) return;

        const messageEl = document.createElement('div');
        messageEl.className = 'coding-buddy-message buddy-message';
        
        // Process markdown-like formatting
        let formattedMessage = message
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
        
        messageEl.innerHTML = formattedMessage;
        this.elements.messages.appendChild(messageEl);
        this.scrollToBottom();
    }
    
    addUserMessage(message) {
        const messagesContainer = document.getElementById('buddy-messages');
        const messageEl = document.createElement('div');
        messageEl.className = 'coding-buddy-message user-message';
        messageEl.textContent = message;
        messagesContainer.appendChild(messageEl);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        // Add to messages array
        this.messages.push({
            type: 'user',
            content: message
        });
    }
    
    showTypingIndicator() {
        const messagesContainer = document.getElementById('buddy-messages');
        const typingIndicator = document.createElement('div');
        typingIndicator.id = 'typing-indicator';
        typingIndicator.className = 'buddy-typing';
        
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('div');
            dot.className = 'typing-dot';
            typingIndicator.appendChild(dot);
        }
        
        messagesContainer.appendChild(typingIndicator);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    hideTypingIndicator() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    // Add method to scroll chat to bottom
    scrollToBottom() {
        if (this.elements.messages) {
            this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
        }
    }
}

// Initialize the coding buddy when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    const codingBuddy = new CodingBuddy();
    // Make it available globally
    window.codingBuddy = codingBuddy;
});
