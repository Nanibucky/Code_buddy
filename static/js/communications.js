/**
 * Communications Module for CodeChallenge Rooms
 * Handles all WebRTC and communication functionality
 */
class Communications {
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
        this.startCameraBtn = document.getElementById(options.startCameraBtnId || 'startCameraBtn');
        this.muteBtn = document.getElementById(options.muteBtnId || 'muteBtn');
        
        // State
        this.localStream = null;
        this.localCameraStream = null;
        this.peerConnections = {};
        this.isSharing = false;
        this.isCameraOn = false;
        this.isMuted = true;
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

        // Add event listener to camera button
        this.startCameraBtn.addEventListener('click', () => {
            if (this.isCameraOn) {
                this.stopCamera();
            } else {
                this.startCamera();
            }
        });

        // Add event listener to mute button
        this.muteBtn.addEventListener('click', () => {
            if (this.isMuted) {
                this.unmuteAudio();
            } else {
                this.muteAudio();
            }
        });
        
        // Join the communication room
        this.socket.emit('join_comm_room', { room: this.roomCode });
        
        // Set up socket event listeners
        this.setupSocketListeners();
        
        // Clean up on page unload
        window.addEventListener('beforeunload', () => {
            this.stopScreenShare();
            this.stopCamera();
            this.socket.emit('leave_comm_room', { room: this.roomCode });
        });
    }
    
    setupSocketListeners() {
        // When a peer sends an offer
        this.socket.on('webrtc_offer', async (data) => {
            if (data.to === this.userId) {
                console.log('Received WebRTC offer from', data.from);
                await this.handleOffer(data);
            }
        });
        
        // When a peer sends an answer to our offer
        this.socket.on('webrtc_answer', async (data) => {
            if (data.to === this.userId) {
                console.log('Received WebRTC answer from', data.from);
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
        this.socket.on('user_joined', (data) => {
            console.log('User joined comm room:', data.user);
            
            // If we're sharing, send them an offer
            if ((this.isSharing || this.isCameraOn) && data.user !== this.userId) {
                this.createPeerConnection(data.user);
            }
        });
        
        // When a user starts sharing their screen or camera
        this.socket.on('media_started', (data) => {
            console.log(`User ${data.user} started ${data.type}`);
            
            // Callback for UI updates
            if (data.user !== this.userId) {
                if (data.type === 'screen') {
                    this.onUserStartSharing(data);
                }
            }
        });
        
        // When a user stops sharing their screen or camera
        this.socket.on('media_stopped', (data) => {
            console.log(`User ${data.user} stopped ${data.type}`);
            
            // Callback for UI updates
            if (data.user !== this.userId) {
                if (data.type === 'screen') {
                    this.onUserStopSharing(data);
                }
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
            this.socket.emit('media_started', {
                room: this.roomCode,
                username: this.username,
                type: 'screen'
            });
            
            // Create peer connections with all users in the room
            // This requires knowing who's in the room
            this.fetchRoomMembers().then(members => {
                members.forEach(member => {
                    if (member.user_id !== this.userId) {
                        this.createOrUpdatePeerConnection(member.user_id);
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
            
            // remove tracks from peer connections
            if (this.localStream) {
                this.localStream.getTracks().forEach(track => {
                    Object.values(this.peerConnections).forEach(pc => {
                        const sender = pc.getSenders().find(s => s.track === track);
                        if (sender) {
                            pc.removeTrack(sender);
                        }
                    });
                });
            }
            
            // Reset the share button
            this.resetShareButton();
            
            // Check if there are any remote videos still visible
            const remoteVideos = document.querySelectorAll('.remote-video');
            if (remoteVideos.length === 0) {
                this.videosContainer.style.display = 'none';
            }
            
            // Notify other users that we've stopped sharing
            this.socket.emit('media_stopped', {
                room: this.roomCode,
                username: this.username,
                type: 'screen'
            });
        }
    }
    
    resetShareButton() {
        this.shareBtn.innerHTML = '<i class="fas fa-desktop me-2"></i>Share Screen';
        this.shareBtn.classList.remove('btn-danger');
        this.shareBtn.classList.add('btn-outline-secondary');
    }
    
    createOrUpdatePeerConnection(peerId) {
        let peerConnection = this.peerConnections[peerId];
        if (!peerConnection) {
            peerConnection = new RTCPeerConnection({
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

            peerConnection.oniceconnectionstatechange = () => {
                console.log(`ICE connection state with ${peerId}:`, peerConnection.iceConnectionState);
            };

            peerConnection.ontrack = (event) => {
                console.log('Received remote track from', peerId);
                const stream = event.streams[0];
                const videoTrack = stream.getVideoTracks()[0];
                let streamType = 'camera';
                if (videoTrack && videoTrack.getSettings().displaySurface) {
                    streamType = 'screen';
                }
                this.displayRemoteVideo(peerId, stream, streamType);
            };
        }

        // Add tracks
        if (this.localStream) {
            this.localStream.getTracks().forEach(track => {
                peerConnection.addTrack(track, this.localStream);
            });
        }
        if (this.localCameraStream) {
            this.localCameraStream.getTracks().forEach(track => {
                peerConnection.addTrack(track, this.localCameraStream);
            });
        }

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
                const stream = event.streams[0];
                const videoTrack = stream.getVideoTracks()[0];
                let streamType = 'camera';
                if (videoTrack && videoTrack.getSettings().displaySurface) {
                    streamType = 'screen';
                }
                this.displayRemoteVideo(data.from, stream, streamType);
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
    
    displayRemoteVideo(userId, stream, streamType) {
        if (!this.remoteStreams[userId]) {
            this.remoteStreams[userId] = {};
        }
        this.remoteStreams[userId][streamType] = stream;

        let userContainer = document.getElementById(`user-video-container-${userId}`);
        if (!userContainer) {
            userContainer = document.createElement('div');
            userContainer.id = `user-video-container-${userId}`;
            userContainer.className = 'user-video-container mb-3';
            this.videosContainer.appendChild(userContainer);
        }

        const videoId = `remote-video-${userId}-${streamType}`;
        let videoContainer = document.getElementById(videoId);
        if (videoContainer) {
            const video = videoContainer.querySelector('video');
            video.srcObject = stream;
            return;
        }

        videoContainer = document.createElement('div');
        videoContainer.id = videoId;
        videoContainer.className = 'remote-video-container';
        videoContainer.style.position = 'relative';

        const video = document.createElement('video');
        video.className = 'remote-video w-100';
        video.autoplay = true;
        video.playsInline = true;
        video.srcObject = stream;
        video.style.borderRadius = '8px';
        video.style.maxHeight = '400px';

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

        this.fetchUsername(userId).then(username => {
            label.textContent = `${username}'s ${streamType}`;
        });

        videoContainer.appendChild(video);
        videoContainer.appendChild(label);
        userContainer.appendChild(videoContainer);
        this.videosContainer.style.display = 'block';

        if (stream.getAudioTracks().length > 0) {
            this.handleSpeakingIndicator(userId, stream);
        }
    }

    removeRemoteVideo(userId) {
        const userContainer = document.getElementById(`user-video-container-${userId}`);
        if (userContainer) {
            userContainer.remove();
            delete this.remoteStreams[userId];

            if (Object.keys(this.remoteStreams).length === 0 && !this.isSharing && !this.isCameraOn) {
                this.videosContainer.style.display = 'none';
            }
        }
    }

    async startCamera() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: true,
                audio: true
            });

            this.localCameraStream = stream;
            this.isCameraOn = true;
            this.isMuted = false;

            this.localVideoElem.srcObject = stream;
            this.localVideoElem.style.display = 'block';
            this.videosContainer.style.display = 'block';

            this.startCameraBtn.innerHTML = '<i class="fas fa-video-slash me-2"></i>Stop Camera';
            this.startCameraBtn.classList.add('btn-danger');
            this.startCameraBtn.classList.remove('btn-outline-secondary');

            this.muteBtn.innerHTML = '<i class="fas fa-microphone-slash me-2"></i>Mute';
            this.muteBtn.classList.remove('btn-danger');
            this.muteBtn.classList.add('btn-outline-secondary');

            this.fetchRoomMembers().then(members => {
                members.forEach(member => {
                    if (member.user_id !== this.userId) {
                        this.createOrUpdatePeerConnection(member.user_id);
                    }
                });
            });

            // Notify other users that we've started sharing
            this.socket.emit('media_started', {
                room: this.roomCode,
                username: this.username,
                type: 'camera'
            });

        } catch (error) {
            console.error('Error starting camera:', error);
            alert('Failed to start camera: ' + error.message);
        }
    }

    stopCamera() {
        if (this.localCameraStream) {
            this.localCameraStream.getTracks().forEach(track => track.stop());
            this.localCameraStream = null;
            this.isCameraOn = false;

            this.localVideoElem.srcObject = null;
            this.localVideoElem.style.display = 'none';

            this.startCameraBtn.innerHTML = '<i class="fas fa-video me-2"></i>Start Camera';
            this.startCameraBtn.classList.remove('btn-danger');
            this.startCameraBtn.classList.add('btn-outline-secondary');

            // remove tracks from peer connections
            if (this.localCameraStream) {
                this.localCameraStream.getTracks().forEach(track => {
                    Object.values(this.peerConnections).forEach(pc => {
                        const sender = pc.getSenders().find(s => s.track === track);
                        if (sender) {
                            pc.removeTrack(sender);
                        }
                    });
                });
            }

            if (Object.keys(this.remoteStreams).length === 0 && !this.isSharing) {
                this.videosContainer.style.display = 'none';
            }

            // Notify other users that we've stopped sharing
            this.socket.emit('media_stopped', {
                room: this.roomCode,
                username: this.username,
                type: 'camera'
            });
        }
    }

    muteAudio() {
        if (this.localCameraStream) {
            this.localCameraStream.getAudioTracks().forEach(track => track.enabled = false);
            this.isMuted = true;
            this.muteBtn.innerHTML = '<i class="fas fa-microphone me-2"></i>Unmute';
            this.muteBtn.classList.add('btn-danger');
            this.muteBtn.classList.remove('btn-outline-secondary');
        }
    }

    unmuteAudio() {
        if (this.localCameraStream) {
            this.localCameraStream.getAudioTracks().forEach(track => track.enabled = true);
            this.isMuted = false;
            this.muteBtn.innerHTML = '<i class="fas fa-microphone-slash me-2"></i>Mute';
            this.muteBtn.classList.remove('btn-danger');
            this.muteBtn.classList.add('btn-outline-secondary');
        }
    }

    handleSpeakingIndicator(userId, stream) {
        const audioContext = new AudioContext();
        const source = audioContext.createMediaStreamSource(stream);
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 512;
        analyser.minDecibels = -60;
        analyser.maxDecibels = -10;
        analyser.smoothingTimeConstant = 0.85;
        source.connect(analyser);

        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        const videoContainer = document.getElementById(`user-video-container-${userId}`);

        const checkSpeaking = () => {
            analyser.getByteFrequencyData(dataArray);
            let sum = 0;
            for (const amplitude of dataArray) {
                sum += amplitude * amplitude;
            }
            const volume = Math.sqrt(sum / dataArray.length);
            if (volume > 5) { // Threshold can be adjusted
                videoContainer.classList.add('speaking');
            } else {
                videoContainer.classList.remove('speaking');
            }
            requestAnimationFrame(checkSpeaking);
        };

        checkSpeaking();
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