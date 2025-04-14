/**
 * Screen Sharing Module for CodeChallenge Rooms
 * Handles all WebRTC and screen sharing functionality
 */
class ScreenSharing {
    constructor(options) {
        // Required options
        this.roomCode = options.roomCode;
        this.userId = options.userId;
        this.username = options.username;
        this.socket = options.socket;
        
        // Optional callbacks
        this.onUserStartSharing = options.onUserStartSharing || function() {};
        this.onUserStopSharing = options.onUserStopSharing || function() {};
        
        // UI Elements
        this.shareBtn = document.getElementById(options.shareBtnId || 'shareScreenBtn');
        this.videosContainer = document.getElementById(options.videosContainerId || 'videosContainer');
        this.localVideoElem = document.getElementById(options.localVideoId || 'localScreenVideo');
        
        // State
        this.localStream = null;
        this.peerConnections = {};
        this.isSharing = false;
        this.remoteStreams = {};
        
        // Initialize
        this.init();
    }
    
    init() {
        // Check if required elements exist
        if (!this.shareBtn || !this.videosContainer || !this.localVideoElem) {
            console.error('Screen sharing elements not found');
            return;
        }
        
        // Hide videos container initially
        this.videosContainer.style.display = 'none';
        
        // Add event listener to share button
        this.shareBtn.addEventListener('click', () => {
            if (this.isSharing) {
                this.stopScreenShare();
            } else {
                this.startScreenShare();
            }
        });
        
        // Join the screen sharing room
        this.socket.emit('join_screen_room', { room: this.roomCode });
        
        // Set up socket event listeners
        this.setupSocketListeners();
        
        // Clean up on page unload
        window.addEventListener('beforeunload', () => {
            this.stopScreenShare();
            this.socket.emit('leave_screen_room', { room: this.roomCode });
        });
    }
    
    setupSocketListeners() {
        // When a peer sends an offer
        this.socket.on('screen_share_offer', async (data) => {
            if (data.to === this.userId) {
                console.log('Received screen share offer from', data.from);
                await this.handleOffer(data);
            }
        });
        
        // When a peer sends an answer to our offer
        this.socket.on('screen_share_answer', async (data) => {
            if (data.to === this.userId) {
                console.log('Received screen share answer from', data.from);
                await this.handleAnswer(data);
            }
        });
        
        // When a peer sends an ICE candidate
        this.socket.on('ice_candidate', async (data) => {
            if (data.to === this.userId) {
                console.log('Received ICE candidate from', data.from);
                await this.handleIceCandidate(data);
            }
        });
        
        // When a new user joins the room
        this.socket.on('screen_user_joined', (data) => {
            console.log('User joined screen room:', data.user);
            
            // If we're sharing, send them an offer
            if (this.isSharing && this.localStream && data.user !== this.userId) {
                this.createPeerConnection(data.user);
            }
        });
        
        // When a user starts sharing their screen
        this.socket.on('screen_share_started', (data) => {
            console.log('User started sharing:', data.user);
            
            // Callback for UI updates
            if (data.user !== this.userId) {
                this.onUserStartSharing(data);
            }
        });
        
        // When a user stops sharing their screen
        this.socket.on('screen_share_stopped', (data) => {
            console.log('User stopped sharing:', data.user);
            
            // Callback for UI updates
            if (data.user !== this.userId) {
                this.onUserStopSharing(data);
            }
            
            // Remove any videos from this user
            this.removeRemoteVideo(data.user);
        });
    }
    
    async startScreenShare() {
        try {
            // Get screen capture stream
            const stream = await navigator.mediaDevices.getDisplayMedia({
                video: {
                    cursor: 'always',
                    displaySurface: 'monitor', 
                    logicalSurface: true,
                    frameRate: { ideal: 30, max: 60 }
                },
                audio: false
            });
            
            // Save stream and update UI
            this.localStream = stream;
            this.isSharing = true;
            this.localVideoElem.srcObject = stream;
            this.localVideoElem.style.display = 'block';
            this.videosContainer.style.display = 'block';
            
            this.shareBtn.innerHTML = '<i class="fas fa-stop me-2"></i>Stop Sharing';
            this.shareBtn.classList.add('btn-danger');
            this.shareBtn.classList.remove('btn-outline-secondary');
            
            // Handle stream end event (user clicks "Stop sharing" in browser UI)
            stream.getVideoTracks()[0].addEventListener('ended', () => {
                console.log('User ended screen share via browser UI');
                this.stopScreenShare();
            });
            
            // Notify other users that we've started sharing
            this.socket.emit('screen_share_started', { 
                room: this.roomCode,
                username: this.username
            });
            
            // Create peer connections with all users in the room
            // This requires knowing who's in the room
            this.fetchRoomMembers().then(members => {
                members.forEach(member => {
                    if (member.user_id !== this.userId) {
                        this.createPeerConnection(member.user_id);
                    }
                });
            });
            
        } catch (error) {
            console.error('Error starting screen share:', error);
            
            if (error.name === 'NotAllowedError') {
                alert('Screen sharing permission denied. Please allow screen sharing and try again.');
            } else {
                alert('Failed to start screen sharing: ' + error.message);
            }
            
            this.resetShareButton();
        }
    }
    
    stopScreenShare() {
        if (this.localStream) {
            // Stop all tracks
            this.localStream.getTracks().forEach(track => track.stop());
            this.localStream = null;
            this.isSharing = false;
            
            // Clear local video
            this.localVideoElem.srcObject = null;
            this.localVideoElem.style.display = 'none';
            
            // Close all peer connections
            Object.values(this.peerConnections).forEach(pc => {
                if (pc) pc.close();
            });
            this.peerConnections = {};
            
            // Reset the share button
            this.resetShareButton();
            
            // Check if there are any remote videos still visible
            const remoteVideos = document.querySelectorAll('.remote-video');
            if (remoteVideos.length === 0) {
                this.videosContainer.style.display = 'none';
            }
            
            // Notify other users that we've stopped sharing
            this.socket.emit('screen_share_stopped', { 
                room: this.roomCode,
                username: this.username
            });
        }
    }
    
    resetShareButton() {
        this.shareBtn.innerHTML = '<i class="fas fa-desktop me-2"></i>Share Screen';
        this.shareBtn.classList.remove('btn-danger');
        this.shareBtn.classList.add('btn-outline-secondary');
    }
    
    createPeerConnection(peerId) {
        if (this.peerConnections[peerId]) {
            // Close existing connection
            this.peerConnections[peerId].close();
            delete this.peerConnections[peerId];
        }
        
        // Create new RTCPeerConnection with STUN servers
        const peerConnection = new RTCPeerConnection({
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' },
                { urls: 'stun:stun2.l.google.com:19302' },
                { urls: 'stun:stun3.l.google.com:19302' },
                { urls: 'stun:stun4.l.google.com:19302' }
            ],
            iceCandidatePoolSize: 10
        });
        
        this.peerConnections[peerId] = peerConnection;
        
        // Add local stream tracks to the peer connection
        if (this.localStream) {
            this.localStream.getTracks().forEach(track => {
                peerConnection.addTrack(track, this.localStream);
            });
        }
        
        // Handle ICE candidates
        peerConnection.onicecandidate = (event) => {
            if (event.candidate) {
                this.socket.emit('ice_candidate', {
                    candidate: event.candidate,
                    room: this.roomCode,
                    from: this.userId,
                    to: peerId
                });
            }
        };
        
        // Monitor connection state
        peerConnection.oniceconnectionstatechange = () => {
            console.log(`ICE connection state with ${peerId}:`, peerConnection.iceConnectionState);
        };
        
        // Create and send offer
        peerConnection.createOffer()
            .then(offer => peerConnection.setLocalDescription(offer))
            .then(() => {
                console.log('Sending offer to', peerId);
                this.socket.emit('screen_share_offer', {
                    offer: peerConnection.localDescription,
                    room: this.roomCode,
                    from: this.userId,
                    to: peerId
                });
            })
            .catch(error => {
                console.error('Error creating offer:', error);
            });
            
        return peerConnection;
    }
    
    async handleOffer(data) {
        try {
            // Create a new peer connection
            const peerConnection = new RTCPeerConnection({
                iceServers: [
                    { urls: 'stun:stun.l.google.com:19302' },
                    { urls: 'stun:stun1.l.google.com:19302' },
                    { urls: 'stun:stun2.l.google.com:19302' },
                    { urls: 'stun:stun3.l.google.com:19302' },
                    { urls: 'stun:stun4.l.google.com:19302' }
                ],
                iceCandidatePoolSize: 10
            });
            
            this.peerConnections[data.from] = peerConnection;
            
            // Handle incoming tracks (remote screen)
            peerConnection.ontrack = (event) => {
                console.log('Received remote track from', data.from);
                this.displayRemoteVideo(data.from, event.streams[0]);
            };
            
            // Handle ICE candidates
            peerConnection.onicecandidate = (event) => {
                if (event.candidate) {
                    this.socket.emit('ice_candidate', {
                        candidate: event.candidate,
                        room: this.roomCode,
                        from: this.userId,
                        to: data.from
                    });
                }
            };
            
            // Set remote description and create answer
            await peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
            const answer = await peerConnection.createAnswer();
            await peerConnection.setLocalDescription(answer);
            
            // Send answer back
            this.socket.emit('screen_share_answer', {
                answer: peerConnection.localDescription,
                room: this.roomCode,
                from: this.userId,
                to: data.from
            });
            
        } catch (error) {
            console.error('Error handling offer:', error);
        }
    }
    
    async handleAnswer(data) {
        try {
            const peerConnection = this.peerConnections[data.from];
            
            if (peerConnection) {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
            } else {
                console.warn(`No peer connection found for ${data.from}`);
            }
        } catch (error) {
            console.error('Error handling answer:', error);
        }
    }
    
    async handleIceCandidate(data) {
        try {
            const peerConnection = this.peerConnections[data.from];
            
            if (peerConnection) {
                await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
            } else {
                console.warn(`No peer connection found for ${data.from}`);
            }
        } catch (error) {
            console.error('Error handling ICE candidate:', error);
        }
    }
    
    displayRemoteVideo(userId, stream) {
        // Save the stream reference
        this.remoteStreams[userId] = stream;
        
        // Check if there's already a video element for this user
        const existingVideo = document.getElementById(`remote-video-${userId}`);
        if (existingVideo) {
            existingVideo.srcObject = stream;
            return;
        }
        
        // Create container for the video
        const container = document.createElement('div');
        container.id = `remote-video-container-${userId}`;
        container.className = 'remote-video-container mb-3';
        container.style.position = 'relative';
        
        // Create video element
        const video = document.createElement('video');
        video.id = `remote-video-${userId}`;
        video.className = 'remote-video w-100';
        video.autoplay = true;
        video.playsInline = true;
        video.srcObject = stream;
        video.style.borderRadius = '8px';
        video.style.maxHeight = '400px';
        
        // Create user label
        const label = document.createElement('div');
        label.className = 'remote-video-label';
        label.style.position = 'absolute';
        label.style.bottom = '10px';
        label.style.left = '10px';
        label.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
        label.style.color = 'white';
        label.style.padding = '5px 10px';
        label.style.borderRadius = '4px';
        label.style.fontSize = '0.9rem';
        
        // Try to get username from the DOM if available
        const usernameElem = document.querySelector(`[data-user-id="${userId}"] .member-name span`);
        if (usernameElem) {
            label.textContent = `${usernameElem.textContent}'s screen`;
        } else {
            label.textContent = 'Screen share';
            
            // Try to fetch username
            this.fetchUsername(userId).then(username => {
                if (username) {
                    label.textContent = `${username}'s screen`;
                }
            });
        }
        
        // Add elements to container
        container.appendChild(video);
        container.appendChild(label);
        
        // Add container to videos container
        this.videosContainer.appendChild(container);
        this.videosContainer.style.display = 'block';
    }
    
    removeRemoteVideo(userId) {
        const container = document.getElementById(`remote-video-container-${userId}`);
        if (container) {
            container.remove();
            
            // Delete stream reference
            delete this.remoteStreams[userId];
            
            // Check if there are any videos left
            if (Object.keys(this.remoteStreams).length === 0 && !this.isSharing) {
                this.videosContainer.style.display = 'none';
            }
        }
    }
    
    async fetchRoomMembers() {
        try {
            const response = await fetch(`/api/room/${this.roomCode}/status`);
            const data = await response.json();
            
            if (data.success && data.room && data.room.members) {
                return data.room.members;
            } else {
                return [];
            }
        } catch (error) {
            console.error('Error fetching room members:', error);
            return [];
        }
    }
    
    async fetchUsername(userId) {
        try {
            // First check if we have a members list in localStorage
            const cachedMembers = localStorage.getItem(`room_${this.roomCode}_members`);
            if (cachedMembers) {
                const members = JSON.parse(cachedMembers);
                const member = members.find(m => m.user_id === userId);
                if (member && member.username) {
                    return member.username;
                }
            }
            
            // Fallback to API request
            const response = await fetch(`/api/room/${this.roomCode}/status`);
            const data = await response.json();
            
            if (data.success && data.room && data.room.members) {
                // Cache members list
                localStorage.setItem(`room_${this.roomCode}_members`, JSON.stringify(data.room.members));
                
                // Find member
                const member = data.room.members.find(m => m.user_id === userId);
                if (member) {
                    return member.username;
                }
            }
            
            return null;
        } catch (error) {
            console.error('Error fetching username:', error);
            return null;
        }
    }
}