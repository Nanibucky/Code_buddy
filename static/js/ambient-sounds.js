/**
 * Ambient Sound Effects for Login and Signup Pages
 * Adds subtle sound effects that respond to user interactions
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize ambient sounds
    initAmbientSounds();
});

/**
 * Initialize ambient sound effects
 */
function initAmbientSounds() {
    // Create sound control button
    createSoundControl();
    
    // Create audio elements
    createAudioElements();
    
    // Add event listeners for interactive sounds
    addSoundEventListeners();
}

/**
 * Create sound control button
 */
function createSoundControl() {
    // Create sound control container
    const soundControl = document.createElement('div');
    soundControl.className = 'sound-control';
    
    // Create sound toggle button
    const soundToggle = document.createElement('button');
    soundToggle.className = 'sound-toggle';
    soundToggle.innerHTML = '<i class="fas fa-volume-mute"></i>';
    soundToggle.setAttribute('aria-label', 'Toggle sound effects');
    soundToggle.setAttribute('title', 'Enable sound effects');
    
    // Create sound wave effect element
    const soundWave = document.createElement('span');
    soundWave.className = 'sound-wave';
    soundToggle.appendChild(soundWave);
    
    // Add click event to toggle sound
    soundToggle.addEventListener('click', toggleSound);
    
    // Add to sound control container
    soundControl.appendChild(soundToggle);
    
    // Add to the login or register container
    const container = document.querySelector('.login-container') || document.querySelector('.register-container');
    if (container) {
        container.appendChild(soundControl);
    }
    
    // Store sound state in local storage for persistence between pages
    if (localStorage.getItem('soundEnabled') === null) {
        localStorage.setItem('soundEnabled', 'false');
    } else if (localStorage.getItem('soundEnabled') === 'true') {
        // If sound was previously enabled, update the button
        soundToggle.innerHTML = '<i class="fas fa-volume-up"></i>';
        soundToggle.classList.add('sound-on');
        soundToggle.setAttribute('title', 'Disable sound effects');
    }
}

/**
 * Create audio elements for different sounds
 */
function createAudioElements() {
    // Create audio container
    const audioContainer = document.createElement('div');
    audioContainer.className = 'audio-container';
    audioContainer.style.display = 'none';
    
    // Define sounds
    const sounds = [
        { id: 'hover-sound', src: 'data:audio/mp3;base64,SUQzAwAAAAAAElRTU0UAAAAKAAAADGF2MDEuMjYuMAD/+5DEAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAACcACD///////////////////////////////////////////8AAAA8TEFNRTMuMTAwAc0AAAAAAAAAABSAJAJAQgAAgAAAAnSOuMKAAAAAAAAAAAAAAAAAAAAA//uQxAAABLQDe7QQAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV' },
        { id: 'click-sound', src: 'data:audio/mp3;base64,SUQzAwAAAAAAElRTU0UAAAAKAAAADGF2MDEuMjYuMAD/+5DEAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAACcACD///////////////////////////////////////////8AAAA8TEFNRTMuMTAwAc0AAAAAAAAAABSAJAJAQgAAgAAAAnSOuMKAAAAAAAAAAAAAAAAAAAAA//uQxAAABLQDe7QQAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV' },
        { id: 'success-sound', src: 'data:audio/mp3;base64,SUQzAwAAAAAAElRTU0UAAAAKAAAADGF2MDEuMjYuMAD/+5DEAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAACcACD///////////////////////////////////////////8AAAA8TEFNRTMuMTAwAc0AAAAAAAAAABSAJAJAQgAAgAAAAnSOuMKAAAAAAAAAAAAAAAAAAAAA//uQxAAABLQDe7QQAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV' }
    ];
    
    // Create audio elements for each sound
    sounds.forEach(sound => {
        const audio = document.createElement('audio');
        audio.id = sound.id;
        audio.src = sound.src;
        audio.preload = 'auto';
        audioContainer.appendChild(audio);
    });
    
    // Add audio container to the document
    document.body.appendChild(audioContainer);
}

/**
 * Toggle sound effects on/off
 */
function toggleSound() {
    // Get current sound state
    const soundEnabled = localStorage.getItem('soundEnabled') === 'true';
    
    // Toggle sound state
    localStorage.setItem('soundEnabled', (!soundEnabled).toString());
    
    // Update button appearance
    const soundToggle = document.querySelector('.sound-toggle');
    if (!soundEnabled) {
        // Enable sounds
        soundToggle.innerHTML = '<i class="fas fa-volume-up"></i>';
        soundToggle.classList.add('sound-on');
        soundToggle.setAttribute('title', 'Disable sound effects');
        
        // Play a subtle sound to indicate sounds are enabled
        playSound('click-sound');
    } else {
        // Disable sounds
        soundToggle.innerHTML = '<i class="fas fa-volume-mute"></i>';
        soundToggle.classList.remove('sound-on');
        soundToggle.setAttribute('title', 'Enable sound effects');
    }
}

/**
 * Play a sound by its ID
 * @param {string} soundId - The ID of the sound to play
 */
function playSound(soundId) {
    // Only play sound if sounds are enabled
    if (localStorage.getItem('soundEnabled') !== 'true') return;
    
    const sound = document.getElementById(soundId);
    if (sound) {
        // Reset sound to beginning if it's already playing
        sound.currentTime = 0;
        sound.play().catch(err => console.log('Error playing sound:', err));
    }
}

/**
 * Add event listeners for interactive sounds
 */
function addSoundEventListeners() {
    // Add hover sound to buttons and links
    const interactiveElements = document.querySelectorAll('.btn, .btn-login, .btn-register, .input-group, a, .form-control, .sound-toggle');
    
    interactiveElements.forEach(element => {
        // Play hover sound on mouse enter
        element.addEventListener('mouseenter', () => {
            playSound('hover-sound');
        });
        
        // Play click sound on mouse click
        element.addEventListener('click', () => {
            playSound('click-sound');
        });
    });
    
    // Add success sound to form submission (both login and register forms)
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', () => {
            playSound('success-sound');
        });
    }
    
    // Add subtle sounds to form interactions
    const formControls = document.querySelectorAll('.form-control');
    formControls.forEach(control => {
        control.addEventListener('focus', () => {
            playSound('hover-sound');
        });
    });
}