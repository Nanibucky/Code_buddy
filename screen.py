# screen.py
import logging
from flask import session
from flask_socketio import SocketIO, join_room, leave_room, emit

# Create a SocketIO instance
socketio = SocketIO()

@socketio.on('join_screen_room')
def on_join_screen_room(data):
    room = data.get('room')
    if room:
        join_room(room)
        user_id = session.get('user_id', 'anonymous')
        logging.info(f"User {user_id} joined screen sharing room: {room}")
        emit('screen_user_joined', {'user': user_id}, room=room)
    else:
        logging.warning("Received 'join_screen_room' event without a room specified.")

@socketio.on('leave_screen_room')
def on_leave_screen_room(data):
    room = data.get('room')
    if room:
        leave_room(room)
        user_id = session.get('user_id', 'anonymous')
        logging.info(f"User {user_id} left screen sharing room: {room}")
        emit('screen_user_left', {'user': user_id}, room=room)
    else:
        logging.warning("Received 'leave_screen_room' event without a room specified.")

@socketio.on('screen_share_offer')
def on_screen_share_offer(data):
    room = data.get('room')
    to_user = data.get('to')
    from_user = session.get('user_id', 'anonymous')
    offer = data.get('offer')

    if room and offer and to_user:
        logging.info(f"Screen share offer from {from_user} to {to_user} in room {room}")
        emit('screen_share_offer', {
            'offer': offer,
            'from': from_user,
            'to': to_user,
            'room': room
        }, room=room)
    else:
        logging.warning(f"Received incomplete screen share offer data: {data}")

@socketio.on('screen_share_answer')
def on_screen_share_answer(data):
    room = data.get('room')
    to_user = data.get('to')
    from_user = session.get('user_id', 'anonymous')
    answer = data.get('answer')

    if room and answer and to_user:
        logging.info(f"Screen share answer from {from_user} to {to_user} in room {room}")
        emit('screen_share_answer', {
            'answer': answer,
            'from': from_user,
            'to': to_user,
            'room': room
        }, room=room)
    else:
        logging.warning(f"Received incomplete screen share answer data: {data}")

@socketio.on('ice_candidate')
def on_ice_candidate(data):
    room = data.get('room')
    to_user = data.get('to')
    from_user = session.get('user_id', 'anonymous')
    candidate = data.get('candidate')

    if room and candidate and to_user:
        logging.info(f"ICE candidate from {from_user} to {to_user} in room {room}")
        emit('ice_candidate', {
            'candidate': candidate,
            'from': from_user,
            'to': to_user,
            'room': room
        }, room=room)
    else:
        logging.warning(f"Received incomplete ICE candidate data: {data}")

@socketio.on('screen_share_started')
def on_screen_share_started(data):
    room = data.get('room')
    user_id = session.get('user_id', 'anonymous')
    username = session.get('username', 'Anonymous User')
    logging.info(f"User {user_id} started screen sharing in room: {room}")
    
    # Send more detailed information about who is sharing
    emit('screen_share_started', {
        'user': user_id,
        'username': username
    }, room=room)

@socketio.on('screen_share_stopped')
def on_screen_share_stopped(data):
    room = data.get('room')
    user_id = session.get('user_id', 'anonymous')
    username = session.get('username', 'Anonymous User')
    logging.info(f"User {user_id} stopped screen sharing in room: {room}")
    
    emit('screen_share_stopped', {
        'user': user_id,
        'username': username
    }, room=room)