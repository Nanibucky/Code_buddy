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
        logging.info(f"User {user_id} joined screen sharing room: {room} (Socket ID: {id(socketio)})")
        emit('screen_user_joined', {'user': user_id}, room=room, include_self=True)
    else:
        logging.warning("Received 'join_screen_room' event without a room specified.")

@socketio.on('leave_screen_room')
def on_leave_screen_room(data):
    try:
        room = data.get('room')
        if room:
            leave_room(room)
            user_id = session.get('user_id', 'anonymous')
            logging.info(f"User {user_id} left screen sharing room: {room} (Socket ID: {id(socketio)})")
            emit('screen_user_left', {'user': user_id}, room=room, include_self=False)
        else:
            logging.warning("Received 'leave_screen_room' event without a room specified.")
    except Exception as e:
        logging.error(f"Error handling 'leave_screen_room' event: {e}")

@socketio.on('screen_share_offer')
def on_screen_share_offer(data):
    try:
        room = data.get('room')
        to_user = data.get('to')
        from_user = session.get('user_id', 'anonymous')
        offer = data.get('offer')

        if room and offer and from_user and to_user:
            logging.info(f"Screen share offer from {from_user} to {to_user} in room {room} (Socket ID: {id(socketio)})")
            emit('screen_share_offer', {
                'offer': offer,
                'from': from_user,
                'to': to_user
            }, room=room)
        else:
            logging.warning(f"Received incomplete screen share offer data: {data}")
    except Exception as e:
        logging.error(f"Error handling 'screen_share_offer' event: {e}")

@socketio.on('screen_share_answer')
def on_screen_share_answer(data):
    try:
        room = data.get('room')
        to_user = data.get('to')
        from_user = session.get('user_id', 'anonymous')
        answer = data.get('answer')

        if room and answer and from_user and to_user:
            logging.info(f"Screen share answer from {from_user} to {to_user} in room {room} (Socket ID: {id(socketio)})")
            emit('screen_share_answer', {
                'answer': answer,
                'from': from_user,
                'to': to_user
            }, room=room)
        else:
            logging.warning(f"Received incomplete screen share answer data: {data}")
    except Exception as e:
        logging.error(f"Error handling 'screen_share_answer' event: {e}")

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

@socketio.on('screen_share_started')
def on_screen_share_started(data):
    room = data.get('room')
    user_id = session.get('user_id', 'anonymous')
    logging.info(f"User {user_id} started screen sharing in room: {room}")
    emit('screen_share_started', {'user': user_id}, room=room, include_self=False)

@socketio.on('screen_share_stopped')
def on_screen_share_stopped(data):
    room = data.get('room')
    user_id = session.get('user_id', 'anonymous')
    logging.info(f"User {user_id} stopped screen sharing in room: {room}")
    emit('screen_share_stopped', {'user': user_id}, room=room, include_self=False)