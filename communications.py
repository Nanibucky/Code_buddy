# screen.py
import logging
from flask import session
from flask_socketio import SocketIO, join_room, leave_room, emit

# Create a SocketIO instance
socketio = SocketIO()

@socketio.on('join_comm_room')
def on_join_comm_room(data):
    room = data.get('room')
    if room:
        join_room(room)
        user_id = session.get('user_id', 'anonymous')
        logging.info(f"User {user_id} joined communication room: {room} (Socket ID: {id(socketio)})")
        emit('user_joined', {'user': user_id}, room=room, include_self=True)
    else:
        logging.warning("Received 'join_comm_room' event without a room specified.")

@socketio.on('leave_comm_room')
def on_leave_comm_room(data):
    try:
        room = data.get('room')
        if room:
            leave_room(room)
            user_id = session.get('user_id', 'anonymous')
            logging.info(f"User {user_id} left communication room: {room} (Socket ID: {id(socketio)})")
            emit('user_left', {'user': user_id}, room=room, include_self=False)
        else:
            logging.warning("Received 'leave_comm_room' event without a room specified.")
    except Exception as e:
        logging.error(f"Error handling 'leave_comm_room' event: {e}")

@socketio.on('webrtc_offer')
def on_webrtc_offer(data):
    try:
        room = data.get('room')
        to_user = data.get('to')
        from_user = session.get('user_id', 'anonymous')
        offer = data.get('offer')

        if room and offer and from_user and to_user:
            logging.info(f"WebRTC offer from {from_user} to {to_user} in room {room} (Socket ID: {id(socketio)})")
            emit('webrtc_offer', {
                'offer': offer,
                'from': from_user,
                'to': to_user
            }, room=room)
        else:
            logging.warning(f"Received incomplete WebRTC offer data: {data}")
    except Exception as e:
        logging.error(f"Error handling 'webrtc_offer' event: {e}")

@socketio.on('webrtc_answer')
def on_webrtc_answer(data):
    try:
        room = data.get('room')
        to_user = data.get('to')
        from_user = session.get('user_id', 'anonymous')
        answer = data.get('answer')

        if room and answer and from_user and to_user:
            logging.info(f"WebRTC answer from {from_user} to {to_user} in room {room} (Socket ID: {id(socketio)})")
            emit('webrtc_answer', {
                'answer': answer,
                'from': from_user,
                'to': to_user
            }, room=room)
        else:
            logging.warning(f"Received incomplete WebRTC answer data: {data}")
    except Exception as e:
        logging.error(f"Error handling 'webrtc_answer' event: {e}")

@socketio.on('ice_candidate')
def on_ice_candidate(data):
    try:
        room = data.get('room')
        to_user = data.get('to')
        from_user = session.get('user_id', 'anonymous')
        candidate = data.get('candidate')

        if room and candidate and from_user and to_user:
            logging.info(f"ICE candidate from {from_user} to {to_user} in room {room} (Socket ID: {id(socketio)})")
            emit('ice_candidate', {
                'candidate': candidate,
                'from': from_user,
                'to': to_user
            }, room=room)
        else:
            logging.warning(f"Received incomplete ICE candidate data: {data}")
    except Exception as e:
        logging.error(f"Error handling 'ice_candidate' event: {e}")

@socketio.on('media_started')
def on_media_started(data):
    room = data.get('room')
    user_id = session.get('user_id', 'anonymous')
    media_type = data.get('type', 'media')
    logging.info(f"User {user_id} started {media_type} in room: {room}")
    emit('media_started', {'user': user_id, 'type': media_type}, room=room, include_self=False)

@socketio.on('media_stopped')
def on_media_stopped(data):
    room = data.get('room')
    user_id = session.get('user_id', 'anonymous')
    media_type = data.get('type', 'media')
    logging.info(f"User {user_id} stopped {media_type} in room: {room}")
    emit('media_stopped', {'user': user_id, 'type': media_type}, room=room, include_self=False)