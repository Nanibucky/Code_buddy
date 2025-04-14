/**
 * Fingerprint Animation for Login Button
 * Creates an interactive fingerprint scanning effect when clicking the login button
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize fingerprint animation
    initFingerprintAnimation();
});

/**
 * Initialize the fingerprint animation on the login button
 */
function initFingerprintAnimation() {
    // Get the login button
    const loginButton = document.querySelector('.btn-login');
    if (!loginButton) return;
    
    // Create fingerprint icon
    const fingerprintIcon = document.createElement('i');
    fingerprintIcon.className = 'fas fa-fingerprint fingerprint-icon';
    
    // Create scanning effect element
    const scanEffect = document.createElement('div');
    scanEffect.className = 'scan-effect';
    
    // Create fingerprint container
    const fingerprintContainer = document.createElement('div');
    fingerprintContainer.className = 'fingerprint-container';
    fingerprintContainer.appendChild(fingerprintIcon);
    fingerprintContainer.appendChild(scanEffect);
    
    // Replace the existing icon in the login button
    const existingIcon = loginButton.querySelector('i');
    if (existingIcon) {
        loginButton.replaceChild(fingerprintContainer, existingIcon);
    } else {
        // If no icon exists, add it at the beginning of the button
        loginButton.insertBefore(fingerprintContainer, loginButton.firstChild);
    }
    
    // Add space after the icon
    fingerprintContainer.insertAdjacentHTML('afterend', ' ');
    
    // Add event listeners for animation
    loginButton.addEventListener('click', animateFingerprint);
    loginButton.addEventListener('mouseenter', () => {
        fingerprintIcon.classList.add('pulse');
    });
    loginButton.addEventListener('mouseleave', () => {
        fingerprintIcon.classList.remove('pulse');
    });
}

/**
 * Animate the fingerprint scanning effect
 * @param {Event} e - Click event
 */
function animateFingerprint(e) {
    // Don't prevent form submission, just add the animation
    const fingerprintIcon = document.querySelector('.fingerprint-icon');
    const scanEffect = document.querySelector('.scan-effect');
    
    if (!fingerprintIcon || !scanEffect) return;
    
    // Start scanning animation
    fingerprintIcon.classList.add('scanning');
    scanEffect.classList.add('scanning');
    
    // Add success class after a delay (simulating authentication)
    setTimeout(() => {
        fingerprintIcon.classList.remove('scanning');
        fingerprintIcon.classList.add('success');
        scanEffect.classList.remove('scanning');
    }, 1500);
}