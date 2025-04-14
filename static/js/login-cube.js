/**
 * 3D Cube Animation for Login Page
 * Creates an interactive 3D cube that rotates based on mouse movement
 */

document.addEventListener('DOMContentLoaded', function() {
    // Create and initialize the 3D cube
    initCube();
});

/**
 * Initialize the 3D cube in the login container
 */
function initCube() {
    // Create cube container
    const cubeContainer = document.createElement('div');
    cubeContainer.className = 'cube-container';
    
    // Create the cube
    const cube = document.createElement('div');
    cube.className = 'cube';
    
    // Create cube faces
    const faces = ['front', 'back', 'right', 'left', 'top', 'bottom'];
    const icons = [
        'fa-code', // front
        'fa-terminal', // back
        'fa-laptop-code', // right
        'fa-keyboard', // left
        'fa-bug', // top
        'fa-coffee' // bottom
    ];
    
    // Create each face with an icon
    faces.forEach((face, index) => {
        const cubeFace = document.createElement('div');
        cubeFace.className = `cube-face cube-face-${face}`;
        
        // Add icon to the face
        const icon = document.createElement('i');
        icon.className = `fas ${icons[index]}`;
        cubeFace.appendChild(icon);
        
        cube.appendChild(cubeFace);
    });
    
    // Add cube to container
    cubeContainer.appendChild(cube);
    
    // Add container before the login form
    const loginContainer = document.querySelector('.login-container');
    loginContainer.insertBefore(cubeContainer, loginContainer.firstChild);
    
    // Add mouse movement event listener for rotation
    document.addEventListener('mousemove', rotateCube);
}

/**
 * Rotate the cube based on mouse position
 * @param {Event} e - Mouse event
 */
function rotateCube(e) {
    const cube = document.querySelector('.cube');
    if (!cube) return;
    
    // Calculate rotation based on mouse position
    const x = e.clientX / window.innerWidth;
    const y = e.clientY / window.innerHeight;
    
    // Apply rotation transformation
    const rotateY = (x * 360 - 180).toFixed(2);
    const rotateX = (y * 360 - 180).toFixed(2);
    
    cube.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
}