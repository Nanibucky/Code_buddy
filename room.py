import os
import time
import uuid
import random
import string
import json
import sqlite3
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime

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

def get_auth_db():
    """Get a connection to the auth database"""
    auth_db_path = os.path.join(os.getcwd(), 'database', 'users.db')
    # Check if the file exists and initialize if it doesn't
    if not os.path.exists(auth_db_path):
        os.makedirs(os.path.dirname(auth_db_path), exist_ok=True)
        import auth
        auth.init_db()
    conn = sqlite3.connect(auth_db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_room_db():
    """Initialize the database tables for rooms"""
    try:
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
            is_active BOOLEAN DEFAULT 1
        )
        ''')
        
        # Create room_members table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS room_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_creator BOOLEAN DEFAULT 0,
            UNIQUE(room_id, user_id)
        )
        ''')
        
        # Create other tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS room_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            code TEXT NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            passing_ratio REAL,
            passed_tests INTEGER,
            total_tests INTEGER
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS code_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            question_id TEXT NOT NULL,
            code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(room_id, user_id, question_id)
        )
        ''')
        
        conn.commit()
        logger.info("Room database tables initialized successfully")
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        logger.error(f"Error initializing room database: {str(e)}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()

def generate_room_code(length=6):
    """Generate a unique room code"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Generate a random code
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
            cursor.execute("SELECT id FROM rooms WHERE room_code = ?", (code,))
            if not cursor.fetchone():
                return code
        
    except Exception as e:
        logger.error(f"Error generating room code: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def create_room(creator_id: str, name: str, difficulty: str = None, topic: str = None) -> Dict[str, Any]:
    """Create a new room with improved database handling"""
    room_conn = None
    auth_conn = None
    try:
        logger.info(f"Starting room creation for user {creator_id}")
        
        # Initialize databases if they don't exist
        try:
            import auth
            auth.init_db()
            init_room_db()
            logger.info("Ensured databases are initialized")
        except Exception as e:
            logger.warning(f"Database initialization warning: {str(e)}")
        
        # Connect to room database
        room_conn = get_db()
        room_cursor = room_conn.cursor()
        
        # Check if the rooms table exists
        room_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rooms'")
        if not room_cursor.fetchone():
            logger.info("Creating rooms table as it doesn't exist")
            init_room_db()
        
        # Connect to auth database
        auth_db_path = os.path.join(os.getcwd(), 'database', 'users.db')
        if not os.path.exists(auth_db_path):
            logger.warning("Auth database not found, initializing it")
            import auth
            auth.init_db()
            
        auth_conn = sqlite3.connect(auth_db_path)
        auth_conn.row_factory = sqlite3.Row
        auth_cursor = auth_conn.cursor()
        
        # Verify users table exists
        auth_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not auth_cursor.fetchone():
            logger.warning("Users table not found, initializing auth database")
            import auth
            auth.init_db()
            auth_conn.close()
            auth_conn = sqlite3.connect(auth_db_path)
            auth_conn.row_factory = sqlite3.Row
            auth_cursor = auth_conn.cursor()
        
        # Verify user exists in auth database
        logger.info("Verifying user in auth database")
        auth_cursor.execute("SELECT username FROM users WHERE id = ?", (creator_id,))
        user_data = auth_cursor.fetchone()
        creator_name = user_data['username'] if user_data else f"User-{creator_id[:8]}"
        
        # Generate unique room code
        logger.info("Generating room code")
        room_code = generate_room_code()
        
        # Create room
        room_id = str(uuid.uuid4())
        room_cursor.execute(
            """
            INSERT INTO rooms (id, room_code, creator_id, name, difficulty, topic)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (room_id, room_code, creator_id, name, difficulty, topic)
        )
        
        # Add creator as first member
        room_cursor.execute(
            "INSERT INTO room_members (room_id, user_id, is_creator) VALUES (?, ?, 1)",
            (room_id, creator_id)
        )
        
        room_conn.commit()
        logger.info("Room created successfully")
        
        return {
            'id': room_id,
            'room_code': room_code,
            'creator_id': creator_id,
            'creator_name': creator_name,
            'name': name,
            'difficulty': difficulty,
            'topic': topic,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'member_count': 1,
            'is_active': True
        }
        
    except Exception as e:
        logger.error(f"Error creating room: {str(e)}")
        if room_conn:
            room_conn.rollback()
        raise
    finally:
        if room_conn:
            room_conn.close()
        if auth_conn:
            auth_conn.close()

def join_room(room_code: str, user_id: str) -> Dict[str, Any]:
    """Join an existing room"""
    conn = None
    auth_conn = None
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
                "INSERT INTO room_members (room_id, user_id, is_creator) VALUES (?, ?, 0)",
                (room['id'], user_id)
            )
            conn.commit()
        
        # Connect to auth database to get usernames
        auth_conn = get_auth_db()
        auth_cursor = auth_conn.cursor()
        
        # Get all room members with their usernames
        cursor.execute(
            "SELECT user_id, is_creator FROM room_members WHERE room_id = ? ORDER BY is_creator DESC, joined_at ASC",
            (room['id'],)
        )
        members_data = cursor.fetchall()
        
        members = []
        for member in members_data:
            auth_cursor.execute("SELECT username FROM users WHERE id = ?", (member['user_id'],))
            user_data = auth_cursor.fetchone()
            username = user_data['username'] if user_data else f"User-{member['user_id'][:8]}"
            
            members.append({
                'user_id': member['user_id'],
                'username': username,
                'is_creator': bool(member['is_creator'])
            })
        
        # Get creator info
        auth_cursor.execute("SELECT username FROM users WHERE id = ?", (room['creator_id'],))
        creator = auth_cursor.fetchone()
        creator_name = creator['username'] if creator else f"User-{room['creator_id'][:8]}"
        
        # Get submissions with usernames
        submissions = []
        if room['question_id']:
            cursor.execute(
                "SELECT user_id, passing_ratio, passed_tests, total_tests, submitted_at FROM room_submissions WHERE room_id = ? ORDER BY passing_ratio DESC, submitted_at ASC",
                (room['id'],)
            )
            submissions_data = cursor.fetchall()
            
            for submission in submissions_data:
                auth_cursor.execute("SELECT username FROM users WHERE id = ?", (submission['user_id'],))
                user_data = auth_cursor.fetchone()
                username = user_data['username'] if user_data else f"User-{submission['user_id'][:8]}"
                
                submissions.append({
                    'user_id': submission['user_id'],
                    'username': username,
                    'passing_ratio': submission['passing_ratio'],
                    'passed_tests': submission['passed_tests'],
                    'total_tests': submission['total_tests'],
                    'submitted_at': submission['submitted_at']
                })
        
        # Format the response
        return {
            'id': room['id'],
            'room_code': room['room_code'],
            'creator_id': room['creator_id'],
            'creator_name': creator_name,
            'name': room['name'],
            'question_id': room['question_id'],
            'difficulty': room['difficulty'],
            'topic': room['topic'],
            'created_at': room['created_at'],
            'is_active': bool(room['is_active']),
            'members': members,
            'submissions': submissions
        }
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error joining room: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()
        if auth_conn:
            auth_conn.close()


def get_room_by_code(room_code: str) -> Optional[Dict[str, Any]]:
    """Get room details by room code"""
    conn = None
    auth_conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Ensure tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rooms'")
        if not cursor.fetchone():
            init_room_db()
            conn.close()
            return None
            
        # Get the room by code
        cursor.execute(
            "SELECT * FROM rooms WHERE room_code = ?",
            (room_code,)
        )
        room = cursor.fetchone()
        
        if not room:
            conn.close()
            return None
        
        # Connect to auth database
        auth_conn = get_auth_db()
        auth_cursor = auth_conn.cursor()
            
        # Get room members with usernames
        cursor.execute(
            "SELECT user_id, is_creator FROM room_members WHERE room_id = ? ORDER BY is_creator DESC, joined_at ASC",
            (room['id'],)
        )
        members_data = cursor.fetchall()
        
        members_list = []
        for member in members_data:
            auth_cursor.execute("SELECT username FROM users WHERE id = ?", (member['user_id'],))
            user_data = auth_cursor.fetchone()
            username = user_data['username'] if user_data else f"User-{member['user_id'][:8]}"
            
            members_list.append({
                'user_id': member['user_id'],
                'username': username,
                'is_creator': bool(member['is_creator'])
            })
        
        # Get creator info
        auth_cursor.execute("SELECT username FROM users WHERE id = ?", (room['creator_id'],))
        creator = auth_cursor.fetchone()
        creator_name = creator['username'] if creator else f"User-{room['creator_id'][:8]}"
        
        # Get submissions with usernames
        submissions_list = []
        if room['question_id']:
            cursor.execute(
                "SELECT user_id, passing_ratio, passed_tests, total_tests, submitted_at FROM room_submissions WHERE room_id = ? ORDER BY passing_ratio DESC, submitted_at ASC",
                (room['id'],)
            )
            submissions_data = cursor.fetchall()
            
            for submission in submissions_data:
                auth_cursor.execute("SELECT username FROM users WHERE id = ?", (submission['user_id'],))
                user_data = auth_cursor.fetchone()
                username = user_data['username'] if user_data else f"User-{submission['user_id'][:8]}"
                
                submissions_list.append({
                    'user_id': submission['user_id'],
                    'username': username,
                    'passing_ratio': submission['passing_ratio'],
                    'passed_tests': submission['passed_tests'],
                    'total_tests': submission['total_tests'],
                    'submitted_at': submission['submitted_at']
                })
        
        conn.close()
        auth_conn.close()
        
        # Return the formatted room data
        return {
            'id': room['id'],
            'room_code': room['room_code'],
            'creator_id': room['creator_id'],
            'creator_name': creator_name,
            'name': room['name'],
            'question_id': room['question_id'],
            'difficulty': room['difficulty'],
            'topic': room['topic'],
            'created_at': room['created_at'],
            'is_active': bool(room['is_active']),
            'members': members_list,
            'submissions': submissions_list
        }
        
    except Exception as e:
        if conn:
            conn.close()
        if auth_conn:
            auth_conn.close()
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
    conn = None
    auth_conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # First check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rooms'")
        if not cursor.fetchone():
            logger.warning("Rooms table not found, initializing database")
            init_room_db()
            
            # Return empty list if we just initialized the DB
            conn.close()
            return []
        
        # Connect to auth database
        auth_conn = get_auth_db()
        auth_cursor = auth_conn.cursor()
        
        # Get all rooms the user is a member of
        cursor.execute(
            """
            SELECT r.*, 
                  (SELECT COUNT(*) FROM room_members WHERE room_id = r.id) as member_count
            FROM rooms r
            JOIN room_members rm ON r.id = rm.room_id
            WHERE rm.user_id = ? AND r.is_active = 1
            ORDER BY r.created_at DESC
            """,
            (user_id,)
        )
        rooms_data = cursor.fetchall()
        
        result = []
        for room in rooms_data:
            # Get creator username
            auth_cursor.execute("SELECT username FROM users WHERE id = ?", (room['creator_id'],))
            creator = auth_cursor.fetchone()
            creator_name = creator['username'] if creator else f"User-{room['creator_id'][:8]}"
            
            room_dict = {
                'id': room['id'],
                'room_code': room['room_code'],
                'creator_id': room['creator_id'],
                'creator_name': creator_name,
                'name': room['name'],
                'has_question': bool(room['question_id']),
                'difficulty': room['difficulty'],
                'topic': room['topic'],
                'created_at': room['created_at'],
                'member_count': room['member_count']
            }
            result.append(room_dict)
            
        conn.close()
        auth_conn.close()
        return result
        
    except Exception as e:
        if conn:
            conn.close()
        if auth_conn:
            auth_conn.close()
        logger.error(f"Error getting user rooms: {str(e)}")
        return []
    

def save_code_draft(room_id: str, user_id: str, question_id: str, code: str) -> bool:
    """Save a user's code draft for a specific question in a room"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # First check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='code_drafts'")
        if not cursor.fetchone():
            logger.warning("Code drafts table not found, initializing database")
            init_room_db()
            
        # Use INSERT OR REPLACE to handle the unique constraint
        cursor.execute(
            """
            INSERT OR REPLACE INTO code_drafts 
            (room_id, user_id, question_id, code, updated_at) 
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (room_id, user_id, question_id, code)
        )
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        logger.error(f"Error saving code draft: {str(e)}")
        return False

def get_code_draft(room_id: str, user_id: str, question_id: str) -> Optional[str]:
    """Get a user's saved code draft"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # First check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='code_drafts'")
        if not cursor.fetchone():
            logger.warning("Code drafts table not found, initializing database")
            init_room_db()
            conn.close()
            return None
        
        cursor.execute(
            """
            SELECT code FROM code_drafts 
            WHERE room_id = ? AND user_id = ? AND question_id = ?
            """,
            (room_id, user_id, question_id)
        )
        draft = cursor.fetchone()
        
        conn.close()
        
        if draft:
            return draft['code']
        return None
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        logger.error(f"Error getting code draft: {str(e)}")
        return None

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
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if we have access to the users table for username lookup
        has_users_table = True
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cursor.fetchone():
                # Try to check the auth database
                auth_conn = get_auth_db()
                auth_cursor = auth_conn.cursor()
                auth_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
                has_users_table = bool(auth_cursor.fetchone())
                auth_conn.close()
        except:
            has_users_table = False
        
        if has_users_table:
            try:
                cursor.execute(
                    """
                    SELECT 
                        rs.user_id, 
                        (SELECT username FROM users WHERE id = rs.user_id) as username, 
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
                    WHERE rs.room_id = ?
                    ORDER BY rs.passing_ratio DESC, rs.submitted_at ASC
                    """,
                    (room_id,)
                )
                submissions = cursor.fetchall()
            except sqlite3.OperationalError:
                has_users_table = False
                
        if not has_users_table:
            # Fallback without username lookup
            cursor.execute(
                """
                SELECT 
                    rs.user_id, 
                    'User-' || substr(rs.user_id, 1, 4) as username, 
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
            'username': submission['username'] or f"User-{submission['user_id'][:4]}",
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