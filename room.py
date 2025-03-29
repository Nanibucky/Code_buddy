import os
import time
import uuid
import random
import string
import json
import sqlite3
from typing import Dict, List, Any, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database initialization
DB_PATH = os.path.join(os.getcwd(), 'database', 'codechallenge.db')

def get_db():
    """Get a database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_room_db():
    """Initialize the database tables for rooms"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Create rooms table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS rooms (
        id TEXT PRIMARY KEY,
        room_code TEXT UNIQUE NOT NULL,
        creator_id TEXT NOT NULL,
        name TEXT NOT NULL,
        question_id TEXT,
        difficulty TEXT,
        topic TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1,
        FOREIGN KEY (creator_id) REFERENCES users (id)
    )
    ''')
    
    # Create room_members table to track participants
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS room_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_creator BOOLEAN DEFAULT 0,
        FOREIGN KEY (room_id) REFERENCES rooms (id),
        FOREIGN KEY (user_id) REFERENCES users (id),
        UNIQUE(room_id, user_id)
    )
    ''')
    
    # Create room_submissions table to track participant solutions
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS room_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        code TEXT NOT NULL,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        passing_ratio REAL,
        passed_tests INTEGER,
        total_tests INTEGER,
        FOREIGN KEY (room_id) REFERENCES rooms (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    conn.commit()
    conn.close()
    
    logger.info("Room database tables initialized successfully")

def generate_room_code(length=6):
    """Generate a unique room code"""
    # Generate a random code
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    
    # Check if code already exists
    conn = get_db()
    cursor = conn.cursor()
    
    while True:
        cursor.execute("SELECT id FROM rooms WHERE room_code = ?", (code,))
        if not cursor.fetchone():
            break
        # Generate a new code if this one exists
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    
    conn.close()
    return code

def create_room(creator_id: str, name: str, difficulty: str = None, topic: str = None) -> Dict[str, Any]:
    """
    Create a new coding room
    
    Args:
        creator_id: User ID of the room creator
        name: Room name
        difficulty: Optional difficulty setting
        topic: Optional topic setting
        
    Returns:
        Room details including room_code
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Generate a unique room ID and code
        room_id = str(uuid.uuid4())
        room_code = generate_room_code()
        
        # Insert room record
        cursor.execute(
            "INSERT INTO rooms (id, room_code, creator_id, name, difficulty, topic) VALUES (?, ?, ?, ?, ?, ?)",
            (room_id, room_code, creator_id, name, difficulty, topic)
        )
        
        # Add creator as a room member
        cursor.execute(
            "INSERT INTO room_members (room_id, user_id, is_creator) VALUES (?, ?, 1)",
            (room_id, creator_id)
        )
        
        conn.commit()
        
        # Retrieve the room details
        cursor.execute(
            "SELECT * FROM rooms WHERE id = ?",
            (room_id,)
        )
        room = cursor.fetchone()
        
        conn.close()
        
        # Convert to dict for return
        room_dict = {
            'id': room['id'],
            'room_code': room['room_code'],
            'creator_id': room['creator_id'],
            'name': room['name'],
            'question_id': room['question_id'],
            'difficulty': room['difficulty'],
            'topic': room['topic'],
            'created_at': room['created_at'],
            'is_active': bool(room['is_active'])
        }
        
        logger.info(f"Room created: {room_code} by user {creator_id}")
        return room_dict
        
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        logger.error(f"Error creating room: {str(e)}")
        raise

def join_room(room_code: str, user_id: str) -> Dict[str, Any]:
    """
    Join an existing room by room code
    
    Args:
        room_code: The unique code for the room
        user_id: The ID of the user joining
        
    Returns:
        Room details
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if room exists and is active
        cursor.execute(
            "SELECT * FROM rooms WHERE room_code = ? AND is_active = 1",
            (room_code,)
        )
        room = cursor.fetchone()
        
        if not room:
            conn.close()
            raise ValueError(f"Room with code {room_code} not found or is inactive")
        
        # Check if user is already in the room
        cursor.execute(
            "SELECT id FROM room_members WHERE room_id = ? AND user_id = ?",
            (room['id'], user_id)
        )
        existing_member = cursor.fetchone()
        
        if not existing_member:
            # Add user to room members
            cursor.execute(
                "INSERT INTO room_members (room_id, user_id) VALUES (?, ?)",
                (room['id'], user_id)
            )
            conn.commit()
        
        # Get room members
        cursor.execute(
            """
            SELECT u.username, rm.is_creator, u.id as user_id
            FROM room_members rm
            JOIN users u ON rm.user_id = u.id
            WHERE rm.room_id = ?
            ORDER BY rm.is_creator DESC, rm.joined_at ASC
            """,
            (room['id'],)
        )
        members = cursor.fetchall()
        
        # Get creator username
        cursor.execute(
            "SELECT username FROM users WHERE id = ?",
            (room['creator_id'],)
        )
        creator = cursor.fetchone()
        
        # Get any submissions if question is assigned
        submissions = []
        if room['question_id']:
            cursor.execute(
                """
                SELECT rs.user_id, u.username, rs.passing_ratio, rs.passed_tests, rs.total_tests, rs.submitted_at
                FROM room_submissions rs
                JOIN users u ON rs.user_id = u.id
                WHERE rs.room_id = ?
                ORDER BY rs.passing_ratio DESC, rs.submitted_at ASC
                """,
                (room['id'],)
            )
            submissions = cursor.fetchall()
        
        conn.close()
        
        # Convert to dict for return
        room_dict = {
            'id': room['id'],
            'room_code': room['room_code'],
            'creator_id': room['creator_id'],
            'creator_name': creator['username'] if creator else "Unknown",
            'name': room['name'],
            'question_id': room['question_id'],
            'difficulty': room['difficulty'],
            'topic': room['topic'],
            'created_at': room['created_at'],
            'is_active': bool(room['is_active']),
            'members': [{'username': m['username'], 'user_id': m['user_id'], 'is_creator': bool(m['is_creator'])} for m in members],
            'submissions': [{
                'user_id': s['user_id'],
                'username': s['username'],
                'passing_ratio': s['passing_ratio'],
                'passed_tests': s['passed_tests'],
                'total_tests': s['total_tests'],
                'submitted_at': s['submitted_at']
            } for s in submissions] if submissions else []
        }
        
        logger.info(f"User {user_id} joined room {room_code}")
        return room_dict
        
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        logger.error(f"Error joining room: {str(e)}")
        raise

def get_room_by_code(room_code: str) -> Optional[Dict[str, Any]]:
    """Get room details by room code"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM rooms WHERE room_code = ?",
            (room_code,)
        )
        room = cursor.fetchone()
        
        if not room:
            conn.close()
            return None
        
        # Get room members
        cursor.execute(
            """
            SELECT u.username, rm.is_creator, u.id as user_id
            FROM room_members rm
            JOIN users u ON rm.user_id = u.id
            WHERE rm.room_id = ?
            ORDER BY rm.is_creator DESC, rm.joined_at ASC
            """,
            (room['id'],)
        )
        members = cursor.fetchall()
        
        # Get creator username
        cursor.execute(
            "SELECT username FROM users WHERE id = ?",
            (room['creator_id'],)
        )
        creator = cursor.fetchone()
        
        # Get any submissions if question is assigned
        submissions = []
        if room['question_id']:
            cursor.execute(
                """
                SELECT rs.user_id, u.username, rs.passing_ratio, rs.passed_tests, rs.total_tests, rs.submitted_at
                FROM room_submissions rs
                JOIN users u ON rs.user_id = u.id
                WHERE rs.room_id = ?
                ORDER BY rs.passing_ratio DESC, rs.submitted_at ASC
                """,
                (room['id'],)
            )
            submissions = cursor.fetchall()
        
        conn.close()
        
        # Convert to dict for return
        room_dict = {
            'id': room['id'],
            'room_code': room['room_code'],
            'creator_id': room['creator_id'],
            'creator_name': creator['username'] if creator else "Unknown",
            'name': room['name'],
            'question_id': room['question_id'],
            'difficulty': room['difficulty'],
            'topic': room['topic'],
            'created_at': room['created_at'],
            'is_active': bool(room['is_active']),
            'members': [{'username': m['username'], 'user_id': m['user_id'], 'is_creator': bool(m['is_creator'])} for m in members],
            'submissions': [{
                'user_id': s['user_id'],
                'username': s['username'],
                'passing_ratio': s['passing_ratio'],
                'passed_tests': s['passed_tests'],
                'total_tests': s['total_tests'],
                'submitted_at': s['submitted_at']
            } for s in submissions] if submissions else []
        }
        
        return room_dict
        
    except Exception as e:
        if conn:
            conn.close()
        logger.error(f"Error getting room: {str(e)}")
        return None

def assign_question_to_room(room_id: str, question_id: str, creator_id: str) -> bool:
    """
    Assign a coding question to a room
    
    Args:
        room_id: Room ID
        question_id: Question ID
        creator_id: Creator's user ID (for verification)
        
    Returns:
        Success status
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Verify room exists and user is creator
        cursor.execute(
            "SELECT creator_id FROM rooms WHERE id = ? AND is_active = 1",
            (room_id,)
        )
        room = cursor.fetchone()
        
        if not room:
            conn.close()
            raise ValueError(f"Room {room_id} not found or is inactive")
        
        if room['creator_id'] != creator_id:
            conn.close()
            raise ValueError("Only the room creator can assign questions")
        
        # Assign question to room
        cursor.execute(
            "UPDATE rooms SET question_id = ? WHERE id = ?",
            (question_id, room_id)
        )
        
        conn.commit()
        conn.close()
        
        logger.info(f"Question {question_id} assigned to room {room_id}")
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        logger.error(f"Error assigning question: {str(e)}")
        return False

def record_submission(room_id: str, user_id: str, code: str, results: Dict[str, Any]) -> bool:
    """
    Record a user's code submission in a room
    
    Args:
        room_id: Room ID
        user_id: User ID
        code: The submitted code
        results: Test results
        
    Returns:
        Success status
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Verify user is a member of the room
        cursor.execute(
            "SELECT id FROM room_members WHERE room_id = ? AND user_id = ?",
            (room_id, user_id)
        )
        if not cursor.fetchone():
            conn.close()
            raise ValueError("User is not a member of this room")
        
        # Record submission
        cursor.execute(
            """
            INSERT INTO room_submissions 
            (room_id, user_id, code, passing_ratio, passed_tests, total_tests) 
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                room_id, 
                user_id, 
                code, 
                results.get('passing_ratio', 0),
                results.get('passed_tests', 0),
                results.get('total_tests', 0)
            )
        )
        
        conn.commit()
        conn.close()
        
        logger.info(f"Submission recorded for user {user_id} in room {room_id}")
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        logger.error(f"Error recording submission: {str(e)}")
        return False

def get_user_rooms(user_id: str) -> List[Dict[str, Any]]:
    """
    Get all rooms a user is a member of
    
    Args:
        user_id: User ID
        
    Returns:
        List of rooms
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT r.*, u.username as creator_name, 
                  (SELECT COUNT(*) FROM room_members WHERE room_id = r.id) as member_count
            FROM rooms r
            JOIN users u ON r.creator_id = u.id
            JOIN room_members rm ON r.id = rm.room_id
            WHERE rm.user_id = ? AND r.is_active = 1
            ORDER BY r.created_at DESC
            """,
            (user_id,)
        )
        rooms = cursor.fetchall()
        
        conn.close()
        
        return [{
            'id': room['id'],
            'room_code': room['room_code'],
            'creator_id': room['creator_id'],
            'creator_name': room['creator_name'],
            'name': room['name'],
            'has_question': bool(room['question_id']),
            'difficulty': room['difficulty'],
            'topic': room['topic'],
            'created_at': room['created_at'],
            'member_count': room['member_count']
        } for room in rooms]
        
    except Exception as e:
        if conn:
            conn.close()
        logger.error(f"Error getting user rooms: {str(e)}")
        return []

def close_room(room_id: str, creator_id: str) -> bool:
    """
    Mark a room as inactive
    
    Args:
        room_id: Room ID
        creator_id: Creator's user ID (for verification)
        
    Returns:
        Success status
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Verify room exists and user is creator
        cursor.execute(
            "SELECT creator_id FROM rooms WHERE id = ?",
            (room_id,)
        )
        room = cursor.fetchone()
        
        if not room:
            conn.close()
            raise ValueError(f"Room {room_id} not found")
        
        if room['creator_id'] != creator_id:
            conn.close()
            raise ValueError("Only the room creator can close the room")
        
        # Mark room as inactive
        cursor.execute(
            "UPDATE rooms SET is_active = 0 WHERE id = ?",
            (room_id,)
        )
        
        conn.commit()
        conn.close()
        
        logger.info(f"Room {room_id} marked as inactive")
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        logger.error(f"Error closing room: {str(e)}")
        return False

def get_room_leaderboard(room_id: str) -> List[Dict[str, Any]]:
    """
    Get the leaderboard for a room
    
    Args:
        room_id: Room ID
        
    Returns:
        List of submissions sorted by performance
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT 
                rs.user_id, 
                u.username, 
                rs.passing_ratio, 
                rs.passed_tests, 
                rs.total_tests, 
                rs.submitted_at,
                (SELECT COUNT(*) + 1 FROM room_submissions rs2 
                 WHERE rs2.room_id = rs.room_id 
                   AND (rs2.passing_ratio > rs.passing_ratio 
                        OR (rs2.passing_ratio = rs.passing_ratio AND rs2.submitted_at < rs.submitted_at))
                ) as rank
            FROM room_submissions rs
            JOIN users u ON rs.user_id = u.id
            WHERE rs.room_id = ?
            ORDER BY rs.passing_ratio DESC, rs.submitted_at ASC
            """,
            (room_id,)
        )
        submissions = cursor.fetchall()
        
        conn.close()
        
        return [{
            'rank': submission['rank'],
            'user_id': submission['user_id'],
            'username': submission['username'],
            'passing_ratio': submission['passing_ratio'],
            'passed_tests': submission['passed_tests'],
            'total_tests': submission['total_tests'],
            'submitted_at': submission['submitted_at']
        } for submission in submissions]
        
    except Exception as e:
        if conn:
            conn.close()
        logger.error(f"Error getting room leaderboard: {str(e)}")
        return []