/**
 * Motivational Quotes System for Login Page
 * Displays random coding and programming quotes
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize quotes system
    initQuotesSystem();
});

/**
 * Initialize the motivational quotes system
 */
function initQuotesSystem() {
    // Create quotes container
    createQuotesContainer();
    
    // Display initial quote
    displayRandomQuote();
    
    // Set interval to change quotes
    setInterval(displayRandomQuote, 8000);
}

/**
 * Create the quotes container in the DOM
 */
function createQuotesContainer() {
    // Create quotes container
    const quotesContainer = document.createElement('div');
    quotesContainer.className = 'quotes-container';
    
    // Create quote text element
    const quoteText = document.createElement('p');
    quoteText.className = 'quote-text';
    
    // Create quote author element
    const quoteAuthor = document.createElement('p');
    quoteAuthor.className = 'quote-author';
    
    // Add elements to container
    quotesContainer.appendChild(quoteText);
    quotesContainer.appendChild(quoteAuthor);
    
    // Add to the login container
    const loginContainer = document.querySelector('.login-container');
    const signupLink = document.querySelector('.signup-link');
    
    if (loginContainer && signupLink) {
        loginContainer.insertBefore(quotesContainer, signupLink.nextSibling);
    }
}

/**
 * Display a random quote
 */
function displayRandomQuote() {
    const quoteText = document.querySelector('.quote-text');
    const quoteAuthor = document.querySelector('.quote-author');
    
    if (!quoteText || !quoteAuthor) return;
    
    // Get random quote
    const quote = getRandomQuote();
    
    // Fade out current quote
    quoteText.style.opacity = 0;
    quoteAuthor.style.opacity = 0;
    
    // Update and fade in new quote after a short delay
    setTimeout(() => {
        quoteText.textContent = `"${quote.text}"`;
        quoteAuthor.textContent = `— ${quote.author}`;
        
        quoteText.style.opacity = 1;
        quoteAuthor.style.opacity = 1;
    }, 500);
}

/**
 * Get a random quote from the collection
 * @returns {Object} A random quote object
 */
function getRandomQuote() {
    // Collection of programming and coding quotes
    const quotes = [
        {
            text: "Code is like humor. When you have to explain it, it's bad.",
            author: "Cory House"
        },
        {
            text: "Programming isn't about what you know; it's about what you can figure out.",
            author: "Chris Pine"
        },
        {
            text: "The best error message is the one that never shows up.",
            author: "Thomas Fuchs"
        },
        {
            text: "First, solve the problem. Then, write the code.",
            author: "John Johnson"
        },
        {
            text: "Any fool can write code that a computer can understand. Good programmers write code that humans can understand.",
            author: "Martin Fowler"
        },
        {
            text: "Experience is the name everyone gives to their mistakes.",
            author: "Oscar Wilde"
        },
        {
            text: "It's not a bug – it's an undocumented feature.",
            author: "Anonymous"
        },
        {
            text: "Software and cathedrals are much the same – first we build them, then we pray.",
            author: "Sam Redwine"
        },
        {
            text: "The most disastrous thing that you can ever learn is your first programming language.",
            author: "Alan Kay"
        },
        {
            text: "The function of good software is to make the complex appear to be simple.",
            author: "Grady Booch"
        },
        {
            text: "Your time is limited, don't waste it living someone else's life.",
            author: "Steve Jobs"
        },
        {
            text: "Simplicity is the soul of efficiency.",
            author: "Austin Freeman"
        }
    ];
    
    // Return a random quote
    return quotes[Math.floor(Math.random() * quotes.length)];
}