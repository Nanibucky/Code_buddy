// Function to add password toggle functionality to password fields
function initPasswordToggles() {
    // Find all password fields
    const passwordFields = document.querySelectorAll('input[type="password"]');
    
    passwordFields.forEach((passwordField) => {
        // Create container for the field and toggle button
        const container = document.createElement('div');
        container.className = 'password-field-container';
        
        // Get parent element (form-floating)
        const parent = passwordField.parentElement;
        
        // Insert container in place of the password field
        parent.insertBefore(container, passwordField);
        
        // Move password field into container
        container.appendChild(passwordField);
        
        // Create toggle button
        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = 'password-toggle-btn';
        toggleBtn.innerHTML = '<i class="fa-solid fa-eye-slash"></i>';
        toggleBtn.setAttribute('aria-label', 'Show password');
        
        // Add toggle functionality
        toggleBtn.addEventListener('click', () => {
            // Toggle password visibility
            if (passwordField.type === 'password') {
                passwordField.type = 'text';
                toggleBtn.innerHTML = '<i class="fa-solid fa-eye"></i>';
                toggleBtn.setAttribute('aria-label', 'Hide password');
                
                // Add "show" class for animation
                toggleBtn.classList.add('show');
            } else {
                passwordField.type = 'password';
                toggleBtn.innerHTML = '<i class="fa-solid fa-eye-slash"></i>';
                toggleBtn.setAttribute('aria-label', 'Show password');
                
                // Remove "show" class
                toggleBtn.classList.remove('show');
            }
            
            // Focus back on the input
            passwordField.focus();
        });
        
        // Add button to container
        container.appendChild(toggleBtn);
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initPasswordToggles);