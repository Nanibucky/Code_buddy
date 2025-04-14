/**
 * Login Page Animations
 * Enhances the login page with interactive animations and effects
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize animations
    initAnimations();
    
    // Add event listeners for interactive animations
    addInteractiveEffects();
});

/**
 * Initialize all animations when page loads
 */
function initAnimations() {
    // Staggered animation for form elements
    const formElements = document.querySelectorAll('.input-group, .remember-me, .btn-login, .signup-link');
    formElements.forEach((element, index) => {
        // Set initial state (if not already set by CSS)
        if (!element.style.getPropertyValue('--i')) {
            element.style.setProperty('--i', index);
        }
    });
    
    // Animate brand logo with a subtle bounce
    const brandLogo = document.querySelector('.brand h1');
    if (brandLogo) {
        brandLogo.classList.add('animate__animated', 'animate__bounceIn');
    }
    
    // Create floating particles in the background
    createParticles();
}

/**
 * Add interactive effects that respond to user actions
 */
function addInteractiveEffects() {
    // Form field focus effects
    const formControls = document.querySelectorAll('.form-control');
    formControls.forEach(control => {
        control.addEventListener('focus', () => {
            control.closest('.input-group').classList.add('input-focus');
        });
        
        control.addEventListener('blur', () => {
            control.closest('.input-group').classList.remove('input-focus');
        });
    });
    
    // Button hover effect with ripple
    const loginButton = document.querySelector('.btn-login');
    if (loginButton) {
        loginButton.addEventListener('mouseenter', createRippleEffect);
        loginButton.addEventListener('click', createRippleEffect);
    }
    
    // Parallax effect on mouse move
    document.addEventListener('mousemove', (e) => {
        const x = e.clientX / window.innerWidth;
        const y = e.clientY / window.innerHeight;
        
        // Move background slightly
        const background = document.querySelector('.animated-background');
        if (background) {
            background.style.transform = `translate(${x * 15}px, ${y * 15}px)`;
        }
        
        // Subtle movement for the login container
        const container = document.querySelector('.login-container');
        if (container) {
            container.style.transform = `translate(${x * 5}px, ${y * 5}px)`;
        }
    });
}

/**
 * Creates a ripple effect on button click/hover
 * @param {Event} e - The mouse event
 */
function createRippleEffect(e) {
    const button = e.currentTarget;
    
    // Remove any existing ripple
    const existingRipple = button.querySelector('.ripple');
    if (existingRipple) {
        existingRipple.remove();
    }
    
    // Create ripple element
    const ripple = document.createElement('span');
    ripple.classList.add('ripple');
    button.appendChild(ripple);
    
    // Position the ripple
    const rect = button.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    ripple.style.width = ripple.style.height = `${size}px`;
    
    const x = e.clientX - rect.left - size / 2;
    const y = e.clientY - rect.top - size / 2;
    ripple.style.left = `${x}px`;
    ripple.style.top = `${y}px`;
    
    // Remove ripple after animation completes
    setTimeout(() => {
        ripple.remove();
    }, 600);
}

/**
 * Creates floating particles in the background
 */
function createParticles() {
    const background = document.querySelector('.animated-background');
    if (!background) return;
    
    // Create particle container
    const particleContainer = document.createElement('div');
    particleContainer.classList.add('particles');
    background.appendChild(particleContainer);
    
    // Create particles
    for (let i = 0; i < 20; i++) {
        const particle = document.createElement('div');
        particle.classList.add('particle');
        
        // Random position, size and animation delay
        particle.style.left = `${Math.random() * 100}%`;
        particle.style.top = `${Math.random() * 100}%`;
        particle.style.width = particle.style.height = `${Math.random() * 10 + 5}px`;
        particle.style.opacity = Math.random() * 0.5 + 0.1;
        particle.style.animationDelay = `${Math.random() * 5}s`;
        particle.style.animationDuration = `${Math.random() * 10 + 10}s`;
        
        particleContainer.appendChild(particle);
    }
}