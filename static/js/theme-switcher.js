/**
 * Theme Switcher for Login Page
 * Allows users to switch between different visual themes
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize theme switcher
    initThemeSwitcher();
});

/**
 * Initialize the theme switcher component
 */
function initThemeSwitcher() {
    // Create theme switcher container
    const themeContainer = document.createElement('div');
    themeContainer.className = 'theme-switcher';
    
    // Create theme switcher button
    const themeButton = document.createElement('button');
    themeButton.className = 'theme-toggle-btn';
    themeButton.innerHTML = '<i class="fas fa-palette"></i>';
    themeButton.setAttribute('aria-label', 'Change theme');
    themeButton.setAttribute('title', 'Change theme');
    
    // Create theme options container
    const themeOptions = document.createElement('div');
    themeOptions.className = 'theme-options';
    
    // Define available themes
    const themes = [
        { name: 'default', label: 'Default', primary: '#4f46e5', secondary: '#06b6d4' },
        { name: 'sunset', label: 'Sunset', primary: '#f97316', secondary: '#ec4899' },
        { name: 'forest', label: 'Forest', primary: '#10b981', secondary: '#3b82f6' },
        { name: 'midnight', label: 'Midnight', primary: '#6d28d9', secondary: '#2563eb' },
        { name: 'coffee', label: 'Coffee', primary: '#92400e', secondary: '#b45309' }
    ];
    
    // Create theme option buttons
    themes.forEach(theme => {
        const themeOption = document.createElement('button');
        themeOption.className = 'theme-option';
        themeOption.setAttribute('data-theme', theme.name);
        themeOption.setAttribute('title', theme.label);
        themeOption.style.background = `linear-gradient(135deg, ${theme.primary} 0%, ${theme.secondary} 100%)`;
        
        // Add click event to apply theme
        themeOption.addEventListener('click', () => applyTheme(theme));
        
        themeOptions.appendChild(themeOption);
    });
    
    // Toggle theme options visibility
    themeButton.addEventListener('click', () => {
        themeOptions.classList.toggle('show');
    });
    
    // Close theme options when clicking outside
    document.addEventListener('click', (e) => {
        if (!themeContainer.contains(e.target)) {
            themeOptions.classList.remove('show');
        }
    });
    
    // Add components to the DOM
    themeContainer.appendChild(themeButton);
    themeContainer.appendChild(themeOptions);
    
    // Add to the login container
    const loginContainer = document.querySelector('.login-container');
    loginContainer.appendChild(themeContainer);
}

/**
 * Apply the selected theme
 * @param {Object} theme - The theme to apply
 */
function applyTheme(theme) {
    // Get root element to update CSS variables
    const root = document.documentElement;
    
    // Update CSS variables with theme colors
    root.style.setProperty('--primary', theme.primary);
    root.style.setProperty('--secondary', theme.secondary);
    
    // Calculate light and dark variants
    const primaryLight = adjustColorBrightness(theme.primary, 20);
    const primaryDark = adjustColorBrightness(theme.primary, -20);
    
    root.style.setProperty('--primary-light', primaryLight);
    root.style.setProperty('--primary-dark', primaryDark);
    
    // Add animation effect when changing theme
    const loginContainer = document.querySelector('.login-container');
    loginContainer.classList.add('theme-transition');
    
    // Remove animation class after transition completes
    setTimeout(() => {
        loginContainer.classList.remove('theme-transition');
    }, 1000);
    
    // Save theme preference to localStorage
    localStorage.setItem('loginTheme', theme.name);
}

/**
 * Adjust color brightness
 * @param {string} color - Hex color code
 * @param {number} percent - Percentage to adjust brightness
 * @returns {string} - Adjusted hex color
 */
function adjustColorBrightness(color, percent) {
    // Convert hex to RGB
    let r = parseInt(color.substring(1, 3), 16);
    let g = parseInt(color.substring(3, 5), 16);
    let b = parseInt(color.substring(5, 7), 16);
    
    // Adjust brightness
    r = Math.max(0, Math.min(255, r + (r * percent / 100)));
    g = Math.max(0, Math.min(255, g + (g * percent / 100)));
    b = Math.max(0, Math.min(255, b + (b * percent / 100)));
    
    // Convert back to hex
    return `#${Math.round(r).toString(16).padStart(2, '0')}${Math.round(g).toString(16).padStart(2, '0')}${Math.round(b).toString(16).padStart(2, '0')}`;
}

/**
 * Load saved theme preference
 */
function loadSavedTheme() {
    const savedTheme = localStorage.getItem('loginTheme');
    if (savedTheme) {
        const themeOption = document.querySelector(`[data-theme="${savedTheme}"]`);
        if (themeOption) {
            themeOption.click();
        }
    }
}