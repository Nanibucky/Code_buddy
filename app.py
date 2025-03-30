import os
import sys
import json
import time
import uuid
import signal
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
import re
import random
import openai
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash, g
import logging
from cachetools import TTLCache
from flask import request, jsonify
from dotenv import load_dotenv
import html
import traceback
from werkzeug.middleware.proxy_fix import ProxyFix
from ratelimit import limits, RateLimitException
from datetime import timedelta

# Import authentication module
import auth
from auth import login_required, UserAuth
# Add these imports at the top of your app.py file
import room
from auth import login_required
import os
os.makedirs(os.path.join(os.getcwd(), 'database'), exist_ok=True)

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# In app.py - Replace the @app.before_first_request approach with this

# Remove the @app.before_first_request decorator and function

# Instead, add this code near your app initialization
def initialize_databases():
    """Ensure all database tables are created"""
    # Initialize auth database
    auth.init_db()
    # Initialize room database
    room.init_room_db()
    logger.info("All databases initialized at startup")

# Then call the function immediately after app initialization
app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB max-limit
app.config['MAX_CACHE_SIZE'] = 1000  # 1000 questions in cache
app.config['CACHE_TTL'] = 3600  # 1 hour TTL
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes

# For proper IP handling behind proxies
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Initialize databases
initialize_databases()


# Add to top of app.py
def ensure_db_initialized():
    """Make sure all database tables exist"""
    try:
        # Initialize auth database
        auth.init_db()
        
        # Initialize room database
        room.init_room_db()
        
        logger.info("All databases initialized at startup")
        return True
    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
        return False

# Call this after setting up the app but before any routes
ensure_db_initialized()



# Initialize OpenAI client
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    logger.warning("No OpenAI API key provided. LLM features will be limited.")
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Constants
RATE_LIMIT_MINUTE = 30  # API calls per minute

# Initialize the auth system
auth.init_db()

# Initialize room database
room.init_room_db()


# In app.py

@app.before_request
def check_databases():
    # Verify the database tables exist before each request
    try:
        auth_conn = auth.get_db()
        auth_cursor = auth_conn.cursor()
        auth_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not auth_cursor.fetchone():
            auth.init_db()
            logger.info("Auth database initialized before request")
        auth_conn.close()
        
        room_conn = room.get_db()
        room_cursor = room_conn.cursor()
        room_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rooms'")
        if not room_cursor.fetchone():
            room.init_room_db()
            logger.info("Room database initialized before request")
        room_conn.close()
    except Exception as e:
        logger.error(f"Database check error: {str(e)}")





@app.route('/rooms')
@login_required
def rooms():
    """Show list of user's rooms"""
    user_id = session.get('user_id')
    user_rooms = room.get_user_rooms(user_id)
    return render_template('room.html', rooms=user_rooms)  # Change 'rooms.html' to 'room.html'

# Fix for create_room function in app.py
@app.route('/rooms/create', methods=['GET', 'POST'])
@login_required
def create_room():
    """Create a new coding room"""
    if request.method == 'POST':
        room_name = request.form.get('room_name', '').strip()
        difficulty = request.form.get('difficulty', 'medium')
        topic = request.form.get('topic', '')
        
        if not room_name:
            flash('Room name is required', 'error')
            return render_template('create_room.html')
        
        try:
            user_id = session.get('user_id')
            
            # Create room
            new_room = room.create_room(user_id, room_name, difficulty, topic)
            
            # Add a delay to ensure database writes are complete
            time.sleep(0.5)
            
            # Verify room was created successfully
            verification = room.get_room_by_code(new_room['room_code'])
            if verification:
                flash(f'Room created successfully! Room code: {new_room["room_code"]}', 'success')
                # After creating, redirect to rooms list instead of detail page
                return redirect(url_for('rooms'))
            else:
                flash('Room created but could not be verified. Please try again.', 'error')
                return redirect(url_for('rooms'))
            
        except Exception as e:
            logger.error(f"Error creating room: {str(e)}")
            flash(f'Error creating room: {str(e)}', 'error')
            return render_template('create_room.html')
    
    return render_template('create_room.html')

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
        
        # First check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rooms'")
        if not cursor.fetchone():
            logger.warning("Rooms table not found, initializing database")
            init_room_db()
        
        # Check if users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            logger.warning("Users table not found, initializing auth database")
            import auth
            auth.init_db()
        
        cursor.execute(
            """
            SELECT r.*, 
                  (SELECT username FROM users WHERE id = r.creator_id) as creator_name,
                  (SELECT COUNT(*) FROM room_members WHERE room_id = r.id) as member_count
            FROM rooms r
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
            'creator_name': room['creator_name'] or "Unknown",
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

# Modified room.py join_room function to create user entries if needed
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
        
        # Get room members - modified to handle missing users table
        try:
            cursor.execute(
                """
                SELECT rm.user_id, rm.is_creator, 
                       (SELECT username FROM users WHERE id = rm.user_id) as username
                FROM room_members rm
                WHERE rm.room_id = ?
                ORDER BY rm.is_creator DESC, rm.joined_at ASC
                """,
                (room['id'],)
            )
            members = cursor.fetchall()
        except Exception as e:
            logger.error(f"Error fetching members: {str(e)}")
            # Simplified fallback if users table doesn't exist
            cursor.execute(
                """
                SELECT user_id, is_creator, 'Unknown' as username
                FROM room_members
                WHERE room_id = ?
                ORDER BY is_creator DESC, joined_at ASC
                """,
                (room['id'],)
            )
            members = cursor.fetchall()
        
        # Get creator info
        try:
            cursor.execute(
                "SELECT username FROM users WHERE id = ?",
                (room['creator_id'],)
            )
            creator = cursor.fetchone()
            creator_name = creator['username'] if creator else "Unknown"
        except Exception:
            creator_name = "Unknown"
        
        # Get any submissions if question is assigned
        submissions = []
        if room['question_id']:
            try:
                cursor.execute(
                    """
                    SELECT rs.user_id, 
                           (SELECT username FROM users WHERE id = rs.user_id) as username,
                           rs.passing_ratio, rs.passed_tests, rs.total_tests, rs.submitted_at
                    FROM room_submissions rs
                    WHERE rs.room_id = ?
                    ORDER BY rs.passing_ratio DESC, rs.submitted_at ASC
                    """,
                    (room['id'],)
                )
                submissions = cursor.fetchall()
            except Exception:
                # Simplified fallback if users table is missing
                cursor.execute(
                    """
                    SELECT user_id, 'Unknown' as username, passing_ratio, passed_tests, total_tests, submitted_at
                    FROM room_submissions 
                    WHERE room_id = ?
                    ORDER BY passing_ratio DESC, submitted_at ASC
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
            'creator_name': creator_name,
            'name': room['name'],
            'question_id': room['question_id'],
            'difficulty': room['difficulty'],
            'topic': room['topic'],
            'created_at': room['created_at'],
            'is_active': bool(room['is_active']),
            'members': [{'username': m['username'] or "User"+m['user_id'][:4], 'user_id': m['user_id'], 'is_creator': bool(m['is_creator'])} for m in members],
            'submissions': [{
                'user_id': s['user_id'],
                'username': s['username'] or "User"+s['user_id'][:4],
                'passing_ratio': s['passing_ratio'],
                'passed_tests': s['passed_tests'],
                'total_tests': s['total_tests'],
                'submitted_at': s['submitted_at']
            } for s in submissions] if submissions else []
        }
        
        logger.info(f"User {user_id} joined room {room_code}")
        return room_dict
        
    except Exception as e:
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        logger.error(f"Error joining room: {str(e)}")
        raise


@app.route('/api/room/<room_id>/update-settings', methods=['POST'])
@login_required
def api_update_room_settings(room_id):
    """API endpoint to update room settings"""
    try:
        # Get the request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request data'
            }), 400
            
        # Extract settings
        difficulty = data.get('difficulty')
        topic = data.get('topic')
        
        # Validate difficulty
        if difficulty and difficulty not in ['easy', 'medium', 'hard']:
            return jsonify({
                'success': False,
                'error': 'Invalid difficulty level'
            }), 400
        
        # Get current user ID
        user_id = session.get('user_id')
        
        # Verify the user is the room creator
        conn = room.get_db()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT creator_id FROM rooms WHERE id = ?",
            (room_id,)
        )
        
        room_data = cursor.fetchone()
        
        if not room_data:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Room not found'
            }), 404
            
        if room_data['creator_id'] != user_id:
            conn.close()
            return jsonify({
                'success': False, 
                'error': 'Only the room creator can update settings'
            }), 403
        
        # Update room settings
        cursor.execute(
            "UPDATE rooms SET difficulty = ?, topic = ? WHERE id = ?",
            (difficulty, topic, room_id)
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Room settings updated successfully'
        })
        
    except Exception as e:
        logger.exception("Error updating room settings")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/rooms/join', methods=['GET', 'POST'])
@login_required
def join_room():
    """Join an existing room"""
    if request.method == 'POST':
        room_code = request.form.get('room_code', '').strip().upper()
        
        if not room_code:
            flash('Room code is required', 'error')
            return render_template('join_room.html')
        
        try:
            user_id = session.get('user_id')
            joined_room = room.join_room(room_code, user_id)
            
            flash(f'Successfully joined room: {joined_room["name"]}', 'success')
            return redirect(url_for('room_detail', room_code=room_code))
            
        except Exception as e:
            logger.error(f"Error joining room: {str(e)}")
            flash(f'Error joining room: {str(e)}', 'error')
            return render_template('join_room.html')
    
    # Handle direct access with code in URL
    room_code = request.args.get('code')
    if room_code:
        try:
            user_id = session.get('user_id')
            joined_room = room.join_room(room_code, user_id)
            
            flash(f'Successfully joined room: {joined_room["name"]}', 'success')
            return redirect(url_for('room_detail', room_code=room_code))
        except Exception:
            pass
    
    return render_template('join_room.html')

@app.route('/room/<room_code>')
@login_required
def room_detail(room_code):
    """Show room details and current question"""
    try:
        # Try to get the room and gracefully handle failure
        room_data = room.get_room_by_code(room_code)
        
        if not room_data:
            flash(f'Room with code {room_code} not found. Please check the code and try again.', 'error')
            return redirect(url_for('rooms'))
        
        user_id = session.get('user_id')
        
        # Check if user is a member of this room
        is_member = False
        for member in room_data.get('members', []):
            if member.get('user_id') == user_id:
                is_member = True
                break
        
        if not is_member:
            # Automatically join the room
            try:
                room_data = room.join_room(room_code, user_id)
            except Exception as e:
                logger.error(f"Error joining room: {str(e)}")
                flash(f'Error joining room: {str(e)}', 'error')
                return redirect(url_for('rooms'))
        
        # Check if user is the creator
        is_creator = room_data.get('creator_id') == user_id
        
        # Get user stats
        user_stats = {
            'problems_solved': 0,
            'current_streak': 0,
            'longest_streak': 0,
            'points': 0
        }
        
        # Get question data if assigned
        question_data = None
        if room_data.get('question_id'):
            question_id = room_data['question_id']
            question_data = questions_db.get(question_id)
            
            if question_data:
                question_info = question_data['question_info']
                example_test_cases = [tc for tc in question_data['test_cases'] if tc.get('is_example', False)]
                
                question_data = {
                    'id': question_id,
                    'info': question_info,
                    'example_test_cases': example_test_cases
                }
        
        # Success! Render the template with the data
        return render_template(
            'room_detail.html',
            room=room_data, 
            is_creator=is_creator,
            question=question_data,
            user_stats=user_stats
        )
        
    except Exception as e:
        logger.error(f"Error in room_detail: {str(e)}")
        flash(f'Error accessing room: {str(e)}', 'error')
        return redirect(url_for('rooms'))

@app.route('/api/room/<room_id>/assign-question', methods=['POST'])
@login_required
def api_assign_question(room_id):
    """API endpoint to assign a question to a room"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'Invalid request data'}), 400
            
        difficulty = data.get('difficulty', 'medium')
        topic = data.get('topic')
        
        if difficulty not in ['easy', 'medium', 'hard']:
            return jsonify({'success': False, 'error': 'Invalid difficulty level'}), 400
        
        # Get current user
        user_id = session.get('user_id')
        
        # Verify the user is the room creator
        conn = room.get_db()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT creator_id FROM rooms WHERE id = ?",
            (room_id,)
        )
        
        room_data = cursor.fetchone()
        
        if not room_data:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Room not found'
            }), 404
            
        if room_data['creator_id'] != user_id:
            conn.close()
            return jsonify({
                'success': False, 
                'error': 'Only the room creator can assign questions'
            }), 403
            
        # Update room settings first
        cursor.execute(
            "UPDATE rooms SET difficulty = ?, topic = ? WHERE id = ?",
            (difficulty, topic, room_id)
        )
        conn.commit()
        
        # Generate a question
        question_response = question_generator.generate_question(difficulty, topic)
        
        if not question_response.get('success'):
            conn.close()
            return jsonify({
                'success': False, 
                'error': 'Failed to generate question'
            }), 500
        
        question_info = question_response['question']
        
        # Generate test cases
        test_cases = test_case_generator.generate_test_cases(question_info)
        test_code = test_case_generator.format_test_code(question_info, test_cases)
        
        # Store the question
        question_id = str(uuid.uuid4())
        questions_db[question_id] = {
            'question_info': question_info,
            'test_cases': test_cases,
            'test_code': test_code,
            'created_at': time.time()
        }
        
        # Assign to the room
        cursor.execute(
            "UPDATE rooms SET question_id = ? WHERE id = ?",
            (question_id, room_id)
        )
        conn.commit()
        conn.close()
        
        # Extract example test cases for the response
        example_test_cases = [tc for tc in test_cases if tc.get('is_example', False)]
        
        return jsonify({
            'success': True,
            'question_id': question_id,
            'question_info': question_info,
            'example_test_cases': example_test_cases
        })
        
    except Exception as e:
        logger.exception("Error in room question assignment")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/api/room/<room_id>/submit-solution', methods=['POST'])
@login_required
def api_room_submit_solution(room_id):
    """Submit a solution within a room context"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid request data'}), 400
            
        question_id = data.get('question_id')
        code = data.get('code', '').strip()
        
        # Get the room to verify
        room_data = None
        for r in room.get_user_rooms(session.get('user_id')):
            if r['id'] == room_id:
                room_data = r
                break
                
        if not room_data:
            return jsonify({
                'success': False,
                'error': 'Room not found or you are not a member'
            }), 404
        
        if not code:
            return jsonify({'success': False, 'error': 'No code provided'}), 400
            
        if len(code) > 50000:  # 50KB limit
            return jsonify({'success': False, 'error': 'Code submission too large'}), 400
            
        # Sanitize user code - prevent malicious imports
        if any(pattern in code for pattern in [
            "import os", "import subprocess", "import sys", 
            "from os import", "from subprocess import", "from sys import",
            "__import__('os')", "__import__('subprocess')", 
            "eval(", "exec("
        ]):
            return jsonify({
                'success': False,
                'error': 'Code contains restricted imports or functions'
            }), 403
            
        question_data = questions_db.get(question_id)
        if not question_data:
            return jsonify({
                'success': False,
                'error': 'Question not found or expired'
            }), 404
        
        function_name = question_data['question_info']['function_name']
        test_code = question_data['test_code']
        
        # Execute user code
        results = execute_code_simplified(code, function_name, test_code)
        
        # Record the submission in the room
        if results.get('success'):
            user_id = session.get('user_id')
            room.record_submission(room_id, user_id, code, results)
            
            # Update user stats if all tests passed
            if results.get('passing_ratio') == 1:
                update_user_stats_on_success()
        
        return jsonify({
            'success': True,
            'results': results,
            'room_id': room_id
        })
        
    except Exception as e:
        logger.exception("Error in room submit solution")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/room/<room_id>/leaderboard', methods=['GET'])
@login_required
def api_room_leaderboard(room_id):
    """Get the leaderboard for a room"""
    try:
        # Verify user is a member of the room
        user_id = session.get('user_id')
        user_rooms = room.get_user_rooms(user_id)
        
        if not any(r['id'] == room_id for r in user_rooms):
            return jsonify({
                'success': False,
                'error': 'Room not found or you are not a member'
            }), 404
        
        # Get the leaderboard
        leaderboard = room.get_room_leaderboard(room_id)
        
        return jsonify({
            'success': True,
            'leaderboard': leaderboard
        })
        
    except Exception as e:
        logger.exception("Error getting room leaderboard")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/room/<room_id>/close', methods=['POST'])
@login_required
def api_close_room(room_id):
    """Close a room (mark as inactive)"""
    try:
        user_id = session.get('user_id')
        
        if room.close_room(room_id, user_id):
            return jsonify({
                'success': True,
                'message': 'Room closed successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to close room'
            }), 500
            
    except Exception as e:
        logger.exception("Error closing room")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/room/<room_code>/status', methods=['GET'])
@login_required
def api_room_status(room_code):
    """Get the current status of a room including members and question"""
    try:
        room_data = room.get_room_by_code(room_code)
        
        if not room_data:
            return jsonify({
                'success': False,
                'error': 'Room not found'
            }), 404
        
        # Get question data if assigned
        question_data = None
        if room_data['question_id']:
            question_id = room_data['question_id']
            question_data = questions_db.get(question_id)
            
            if question_data:
                question_info = question_data['question_info']
                
                question_data = {
                    'id': question_id,
                    'info': {
                        'problem_statement': question_info['problem_statement'],
                        'function_name': question_info['function_name'],
                        'difficulty': question_info['difficulty']
                    }
                }
        
        # Format the response
        response_data = {
            'id': room_data['id'],
            'room_code': room_data['room_code'],
            'name': room_data['name'],
            'creator': {
                'id': room_data['creator_id'],
                'username': room_data['creator_name']
            },
            'members': room_data['members'],
            'question': question_data,
            'submissions': len(room_data['submissions']),
            'is_active': room_data['is_active']
        }
        
        return jsonify({
            'success': True,
            'room': response_data
        })
        
    except Exception as e:
        logger.exception("Error getting room status")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500




# This is a conceptual implementation of Pynguine
class Pynguine:
    @staticmethod
    def generate_tests(function_signature: str, description: str, examples: List[Dict] = None, num_tests: int = 5) -> List[Dict[str, Any]]:
        """
        Generate test cases based on function signature, description, and examples.
        
        Args:
            function_signature: The Python function signature
            description: Description of what the function should do
            examples: List of example input/output pairs
            num_tests: Number of test cases to generate
            
        Returns:
            List of test cases with inputs and expected outputs
        """
        # Extract function name and parameters
        # Improved regex to handle multiline signatures and more flexible whitespace
        if "def " in function_signature:
            # For function-based questions
            signature_line = [line for line in function_signature.split('\n') if "def " in line][0]
            match = re.match(r'def\s+(\w+)\s*\((.*?)\)', signature_line)
            
            if not match:
                # Try a more flexible regex as fallback
                match = re.search(r'def\s+(\w+)\s*\((.*?)\)(?:\s*->.*?)?:', function_signature, re.DOTALL)
                
            if not match:
                logger.error(f"Failed to parse function signature: {function_signature}")
                # Default parameters to avoid crashing
                function_name = "solution"
                params = [("input", None)]
            else:
                function_name = match.group(1)
                params_str = match.group(2)
                
                # Parse parameters
                params = []
                if params_str:
                    for param in params_str.split(','):
                        param = param.strip()
                        if not param:
                            continue
                        if ':' in param:
                            name, type_hint = param.split(':', 1)
                            params.append((name.strip(), type_hint.strip()))
                        else:
                            params.append((param, None))
        elif "class " in function_signature:
            # Handle class-based questions
            match = re.match(r'class\s+(\w+)', function_signature)
            if match:
                function_name = match.group(1)
                params = [("self", None)]  # Default parameter for class
            else:
                function_name = "Solution"
                params = [("self", None)]
        else:
            # Fallback for unrecognized formats
            logger.warning(f"Unrecognized function signature format: {function_signature}")
            function_name = "solution"
            params = [("input", None)]
        
        # Start with example test cases if provided
        test_cases = []
        if examples:
            for i, example in enumerate(examples):
                test_cases.append({
                    "test_id": i + 1,
                    "is_example": True,
                    "inputs": example["inputs"],
                    "expected_output": example["output"]
                })
        
        # Generate additional test cases
        for i in range(len(test_cases), num_tests):
            test_case = {
                "test_id": i + 1,
                "is_example": False,
                "inputs": {},
                "expected_output": None
            }
            
            # Generate inputs based on parameter names and types
            for param_name, param_type in params:
                if param_name != 'self':  # Skip 'self' parameter for class methods
                    test_case["inputs"][param_name] = Pynguine._generate_sample_input(param_name, param_type, description)
            
            # Generate expected output based on function name and inputs
            test_case["expected_output"] = Pynguine._generate_expected_output(
                function_name, test_case["inputs"], description
            )
            
            test_cases.append(test_case)
            
        return test_cases
    
    @staticmethod
    def _generate_sample_input(param_name: str, param_type: Optional[str], description: str) -> Any:
        """Generate simpler sample input based on parameter name and type hint"""
        # Check type hint first if available
        if param_type:
            if 'int' in param_type:
                return random.randint(-10, 10)  # Smaller range than before
            elif 'float' in param_type:
                return round(random.uniform(-10, 10), 1)  # Fewer decimal places
            elif 'str' in param_type:
                return f"test_{random.randint(1, 5)}"  # Shorter strings
            elif 'list' in param_type or 'List' in param_type:
                # Try to determine list type, but keep lists shorter
                if 'int' in param_type:
                    return [random.randint(-5, 5) for _ in range(random.randint(2, 4))]
                elif 'str' in param_type:
                    return [f"item_{i}" for i in range(random.randint(2, 3))]
                else:
                    return [random.randint(-5, 5) for _ in range(random.randint(2, 4))]
            elif 'dict' in param_type or 'Dict' in param_type:
                return {f"k{i}": random.randint(1, 5) for i in range(random.randint(1, 3))}
            elif 'bool' in param_type:
                return random.choice([True, False])
        
        # If no type hint or unsupported type, infer from parameter name
        if 'num' in param_name or 'count' in param_name or 'index' in param_name:
            return random.randint(1, 10)  # Smaller numbers
        elif 'name' in param_name or 'text' in param_name or 'str' in param_name:
            return f"sample_{random.randint(1, 3)}"  # Shorter strings
        elif 'list' in param_name or 'array' in param_name:
            return [random.randint(1, 5) for _ in range(random.randint(2, 4))]  # Shorter lists
        elif 'dict' in param_name or 'map' in param_name:
            return {f"k{i}": random.randint(1, 5) for i in range(random.randint(1, 2))}  # Smaller dicts
        elif 'flag' in param_name or 'enable' in param_name:
            return random.choice([True, False])
        else:
            # Default to a simple string
            return f"input_{random.randint(1, 3)}"
    
    @staticmethod
    def _generate_expected_output(function_name: str, inputs: Dict[str, Any], description: str) -> Any:
        """
        Generate expected output based on function name, inputs, and description.
        This implementation includes specific handling for common algorithm types.
        """
        function_name_lower = function_name.lower()
        description_lower = description.lower()
        
        # Handle palindrome functions
        if 'palindrome' in function_name_lower or ('palindrome' in description_lower and 'is_' in function_name_lower):
            for input_val in inputs.values():
                if isinstance(input_val, str):
                    # Clean the string and check if it's a palindrome
                    cleaned = ''.join(char.lower() for char in input_val if char.isalnum())
                    return cleaned == cleaned[::-1]
        
        # Handle anagram functions
        elif 'anagram' in function_name_lower or 'anagram' in description_lower:
            input_values = list(inputs.values())
            if len(input_values) >= 2 and all(isinstance(x, str) for x in input_values[:2]):
                s1, s2 = input_values[0], input_values[1]
                # Check if strings are anagrams (same characters, different order)
                return sorted(s1.lower()) == sorted(s2.lower())
        
        # Sum functions
        elif 'sum' in function_name_lower or 'add' in function_name_lower:
            # If there are numeric inputs, return their sum
            numeric_inputs = [v for v in inputs.values() if isinstance(v, (int, float))]
            if numeric_inputs:
                return sum(numeric_inputs)
            
            # If there's a list of numbers, sum it
            for input_val in inputs.values():
                if isinstance(input_val, list) and all(isinstance(x, (int, float)) for x in input_val):
                    return sum(input_val)
        
        # Average/mean functions
        elif 'average' in function_name_lower or 'mean' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, list) and all(isinstance(x, (int, float)) for x in input_val):
                    return sum(input_val) / len(input_val) if input_val else 0
        
        # Maximum value functions
        elif 'max' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, list) and input_val:
                    try:
                        return max(input_val)
                    except TypeError:
                        pass
        
        # Minimum value functions
        elif 'min' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, list) and input_val:
                    try:
                        return min(input_val)
                    except TypeError:
                        pass
        
        # Count/length functions
        elif any(x in function_name_lower for x in ['count', 'length', 'len']):
            for input_val in inputs.values():
                if isinstance(input_val, (list, str, dict)):
                    return len(input_val)
        
        # Reverse functions
        elif 'reverse' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, list):
                    return input_val[::-1]
                elif isinstance(input_val, str):
                    return input_val[::-1]
        
        # Sort functions
        elif 'sort' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, list):
                    try:
                        return sorted(input_val)
                    except TypeError:
                        pass
        
        # Find missing number
        elif 'find' in function_name_lower and 'missing' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, list) and all(isinstance(x, int) for x in input_val):
                    all_nums = set(range(1, max(input_val) + 2))
                    return min(all_nums - set(input_val))
        
        # Prime number check
        elif 'prime' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, int) and input_val > 1:
                    for i in range(2, int(input_val ** 0.5) + 1):
                        if input_val % i == 0:
                            return False
                    return True
        
        # Fibonacci function
        elif 'fibonacci' in function_name_lower or 'fib' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, int) and input_val >= 0:
                    if input_val <= 1:
                        return input_val
                    a, b = 0, 1
                    for _ in range(2, input_val + 1):
                        a, b = b, a + b
                    return b
        
        # Factorial function
        elif 'factorial' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, int) and input_val >= 0:
                    result = 1
                    for i in range(2, input_val + 1):
                        result *= i
                    return result
        
        # Common types based on description and return type
        if 'boolean' in description_lower or 'true/false' in description_lower:
            return False  # Default to False for boolean functions
        elif 'list' in description_lower:
            return []  # Empty list as default
        elif 'string' in description_lower:
            return ""  # Empty string as default
        elif 'number' in description_lower or 'integer' in description_lower:
            return 0  # Zero as default
        else:
            # Default fallback - use None instead of a misleading string
            return None


class LLMQuestionGenerator:
    """Class to generate coding questions using OpenAI's API"""
    
    def __init__(self):
        self.client = openai_client
        self.previous_questions = set()
        self.use_local_questions = not bool(OPENAI_API_KEY)

    def generate_question(self, difficulty: str = "medium", topic: str = None) -> Dict[str, Any]:
        """Generate a Python coding question using LLM"""
        try:
            # Use OpenAI API to generate the question
            if OPENAI_API_KEY and not self.use_local_questions:
                try:
                    question_text = self._generate_raw_question(difficulty, topic)
                    question_info = self._parse_question(question_text)
                    
                    # If we don't have a valid question, fall back to default
                    if not question_info.get('function_name'):
                        logger.warning("LLM generated question didn't have required fields")
                        return self._get_local_question(difficulty, topic)
                    
                    question_info['difficulty'] = difficulty
                    return {"success": True, "question": question_info}
                except Exception as e:
                    logger.error(f"Error generating question with LLM: {e}")
                    return self._get_local_question(difficulty, topic)
            else:
                logger.info("No OpenAI API key provided or using local questions")
                return self._get_local_question(difficulty, topic)
                
        except Exception as e:
            logger.error(f"Error generating question: {e}")
            return self._get_local_question("medium", None)  # Default fallback

    def _get_local_questions(self) -> Dict[str, List[Dict[str, str]]]:
        """Return a dictionary of pre-defined local questions for fallback"""
        return {
            "easy": [
                {
                    "problem": """Write a function that finds the second largest element in a list of integers. If the list has fewer than 2 elements, return -1.""",
                    "signature": "def find_second_largest(arr: List[int]) -> int:",
                    "examples": [
                        ("Input: [1, 3, 2, 5, 4]", "Output: 4"),
                        ("Input: [1, 1, 1]", "Output: -1"),
                        ("Input: [7]", "Output: -1")
                    ],
                    "constraints": [
                        "1 <= len(arr) <= 10^5",
                        "-10^9 <= arr[i] <= 10^9"
                    ]
                },
                {
                    "problem": """Write a function that counts the number of vowels in a given string.""",
                    "signature": "def count_vowels(text: str) -> int:",
                    "examples": [
                        ("Input: 'hello'", "Output: 2"),
                        ("Input: 'PYTHON'", "Output: 1"),
                        ("Input: ''", "Output: 0")
                    ],
                    "constraints": [
                        "0 <= len(text) <= 10^4",
                        "text consists of printable ASCII characters"
                    ]
                }
            ],
            "medium": [
                {
                    "problem": """Write a function that checks if two strings are anagrams of each other, ignoring spaces and case.""",
                    "signature": "def are_anagrams(str1: str, str2: str) -> bool:",
                    "examples": [
                        ("Input: 'listen', 'silent'", "Output: True"),
                        ("Input: 'Hello World', 'World Hello'", "Output: True"),
                        ("Input: 'Python', 'Java'", "Output: False")
                    ],
                    "constraints": [
                        "0 <= len(str1), len(str2) <= 5 * 10^4",
                        "str1 and str2 consist of printable ASCII characters"
                    ]
                },
                {
                    "problem": """Write a function that finds the first non-repeating character in a string.""",
                    "signature": "def first_unique_char(s: str) -> str:",
                    "examples": [
                        ("Input: 'leetcode'", "Output: 'l'"),
                        ("Input: 'hello'", "Output: 'h'"),
                        ("Input: 'aabb'", "Output: ''")
                    ],
                    "constraints": [
                        "1 <= len(s) <= 10^5",
                        "s consists of only lowercase English letters"
                    ]
                }
            ],
            "hard": [
                {
                    "problem": """Write a function that finds the longest palindromic substring in a given string.""",
                    "signature": "def longest_palindrome(s: str) -> str:",
                    "examples": [
                        ("Input: 'babad'", "Output: 'bab'"),
                        ("Input: 'cbbd'", "Output: 'bb'"),
                        ("Input: 'a'", "Output: 'a'")
                    ],
                    "constraints": [
                        "1 <= len(s) <= 1000",
                        "s consists of only lowercase English letters"
                    ]
                },
                {
                    "problem": """Write a function that implements a LRU (Least Recently Used) cache with a given capacity.""",
                    "signature": "class LRUCache:",
                    "examples": [
                        ("cache = LRUCache(2)", "None"),
                        ("cache.put(1, 1)", "None"),
                        ("cache.get(1)", "Returns: 1")
                    ],
                    "constraints": [
                        "1 <= capacity <= 3000",
                        "0 <= key <= 10^4",
                        "0 <= value <= 10^5",
                        "At most 2 * 10^5 calls will be made to get and put"
                    ]
                }
            ]
        }

    def _get_local_question(self, difficulty: str, topic: str = None) -> Dict[str, Any]:
        """Get a random local question based on difficulty (for fallback)"""
        questions = self._get_local_questions()
        difficulty = difficulty.lower() if difficulty else "medium"
        if difficulty not in questions:
            difficulty = "medium"
        
        question = random.choice(questions[difficulty])
        
        # Format examples for frontend
        formatted_examples = []
        for input_text, output_text in question["examples"]:
            formatted_examples.append({
                "input_text": input_text,
                "output_text": output_text
            })
        
        return {
            "success": True,
            "question": {
                "problem_statement": question["problem"],
                "function_signature": question["signature"],
                "examples": formatted_examples,
                "constraints": question["constraints"],
                "difficulty": difficulty,
                "function_name": self._extract_function_name(question["signature"])
            }
        }
    
    def _extract_function_name(self, signature: str) -> str:
        """Extract function name from signature"""
        if signature.startswith("class"):
            # For class-based questions, return the class name
            match = re.match(r'class\s+(\w+)', signature)
            if match:
                return match.group(1)
            return "Solution"
        else:
            # For function-based questions
            match = re.match(r'def\s+(\w+)', signature)
            if match:
                return match.group(1)
            return "solution"

    @limits(calls=RATE_LIMIT_MINUTE, period=60)
    def _generate_raw_question(self, difficulty: str, topic: str = None) -> str:
        """Generate raw question text using OpenAI's API"""
        try:
            # Construct the prompt
            prompt = self._construct_prompt(difficulty, topic)
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",  # or your preferred model
                messages=[
                    {"role": "system", "content": "You are a Python programming teacher creating coding questions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # Extract and return the question text
            return response.choices[0].message.content.strip()
            
        except RateLimitException:
            logger.warning("Rate limit exceeded for LLM API")
            self.use_local_questions = True
            raise
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def _construct_prompt(self, difficulty: str, topic: str = None) -> str:
        """Construct the prompt for OpenAI API"""
        topic_str = f" about {topic}" if topic else ""
        
        return f"""Generate a Python coding question{topic_str} of {difficulty} difficulty.
        The response must follow this exact format:
        
        Problem Statement:
        [Write a clear description of what the function should do]

        Function Signature:
        ```python
        from typing import List, Dict  # Include if needed
        def function_name(params) -> return_type:
        ```

        Examples:
        Input: [exact input value(s)]
        Output: [exact expected output]

        [Provide at least 3 test cases with varied inputs]
        
        Constraints:
        [List any constraints on input size, value ranges, etc.]
        """

    def _parse_question(self, question_text: str) -> Dict[str, Any]:
        """Parse the raw question text into structured format"""
        try:
            # Basic validation of question text
            if not question_text or not isinstance(question_text, str):
                logger.error(f"Invalid question text received: {question_text}")
                raise ValueError("Invalid question text format")

            # Extract components
            lines = question_text.strip().split('\n')
            
            problem_statement = ""
            function_signature = ""
            imports = []
            examples = []
            constraints = []
            function_name = None
            
            current_section = None
            current_example = {}
            in_code_block = False
            code_lines = []
            
            for line in lines:
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                
                # Handle code blocks with triple backticks
                if line_stripped == '```' or line_stripped == '```python':
                    in_code_block = not in_code_block
                    if line_stripped == '```python':
                        current_section = "signature"
                    continue
                    
                if line_stripped.startswith('Problem Statement:'):
                    current_section = "problem"
                    continue
                elif line_stripped.startswith('Function Signature:'):
                    current_section = "signature"
                    continue
                elif line_stripped.startswith('Examples:'):
                    current_section = "examples"
                    continue
                elif line_stripped.startswith('Constraints:'):
                    current_section = "constraints"
                    continue
                elif line_stripped.startswith('from typing import'):
                    imports.append(line_stripped)
                    if current_section != "signature":
                        current_section = "signature"
                    continue
                
                if in_code_block and (current_section == "signature" or not current_section):
                    # Collect all code lines within triple backticks
                    code_lines.append(line)
                    if line_stripped.startswith('def '):
                        match = re.match(r'def\s+(\w+)\s*\(', line_stripped)
                        if match:
                            function_name = match.group(1)
                    elif line_stripped.startswith('class '):
                        match = re.match(r'class\s+(\w+)', line_stripped)
                        if match:
                            function_name = match.group(1)
                    continue
                
                if current_section == "problem":
                    problem_statement += line + " "
                elif current_section == "signature" and not in_code_block:
                    if line_stripped.startswith('def ') or line_stripped.startswith('class '):
                        function_signature = line_stripped
                        # Extract function name from signature
                        if line_stripped.startswith('def '):
                            match = re.match(r'def\s+(\w+)\s*\(', line_stripped)
                            if match:
                                function_name = match.group(1)
                        else:
                            match = re.match(r'class\s+(\w+)', line_stripped)
                            if match:
                                function_name = match.group(1)
                elif current_section == "examples":
                    if line_stripped.lower().startswith('input:'):
                        if current_example.get('input_text'):  # Save previous example if exists
                            examples.append(current_example.copy())
                        current_example = {'input_text': line}
                    elif line_stripped.lower().startswith('output:') and current_example.get('input_text'):
                        current_example['output_text'] = line
                        examples.append(current_example.copy())
                        current_example = {}
                elif current_section == "constraints":
                    constraints.append(line_stripped)

            # If we collected code inside triple backticks, use it
            if code_lines and not function_signature:
                function_signature = '\n'.join(code_lines)

            # Add last example if pending
            if current_example.get('input_text') and current_example.get('output_text'):
                examples.append(current_example)

            # If List is used in signature but import is missing, add it
            if 'List[' in function_signature and not any('typing import List' in imp for imp in imports):
                imports.append('from typing import List')

            # Combine imports and function signature
            full_signature = '\n'.join(imports + [function_signature]) if imports else function_signature
            
            # Add default constraints if none were parsed
            if not constraints:
                if 'int' in full_signature.lower():
                    constraints.append('-10^9 <= values <= 10^9')
                if 'list' in full_signature.lower() or 'array' in full_signature.lower():
                    constraints.append('1 <= array length <= 10^5')
                if 'str' in full_signature.lower():
                    constraints.append('1 <= string length <= 10^4')
                
            # Ensure we have all required components
            if not problem_statement.strip():
                logger.error("No problem statement found")
                raise ValueError("Missing problem statement")
                
            if not full_signature.strip():
                logger.error("No function signature found")
                raise ValueError("Missing function signature")
                
            if not function_name:
                logger.warning("No function name extracted, using default")
                function_name = "solution"  # Default name
            
            # Log successful parsing
            logger.info(f"Successfully parsed question with function: {function_name}")
            
            return {
                "problem_statement": problem_statement.strip(),
                "function_signature": full_signature.strip(),
                "function_name": function_name,
                "examples": examples,
                "constraints": constraints
            }
            
        except Exception as e:
            logger.exception("Error parsing question")
            raise


class QuestionInfo:
    """Class to handle question information and validation"""
    
    def __init__(self, raw_info: Dict[str, Any]):
        self.raw_info = raw_info
        self.validate_and_normalize()
    
    def validate_and_normalize(self):
        """Validate and normalize question information"""
        required_fields = ['problem_statement', 'function_signature']
        for field in required_fields:
            if not self.raw_info.get(field):
                raise ValueError(f"Missing required field: {field}")
        
        # Make sure we have a function name
        if 'function_name' not in self.raw_info:
            self.raw_info['function_name'] = self._extract_function_name(self.raw_info['function_signature'])
            
        # Extract parameters from function signature if not already present
        if 'parameters' not in self.raw_info:
            self.raw_info['parameters'] = self._extract_parameters(self.raw_info['function_signature'])
        
        # Normalize parameters
        self.raw_info['parameters'] = self._normalize_parameters(self.raw_info['parameters'])
        
        # Normalize examples for test case generation
        if 'examples' in self.raw_info:
            # Convert examples to format for test case generation
            normalized_examples = []
            for example in self.raw_info['examples']:
                if 'input_text' in example and 'output_text' in example:
                    # Parse input and output text
                    inputs = self._parse_input_text(example['input_text'], self.raw_info['parameters'])
                    output = self._parse_output_text(example['output_text'])
                    
                    normalized_examples.append({
                        "inputs": inputs,
                        "output": output
                    })
            
            self.raw_info['normalized_examples'] = normalized_examples
                
        # Ensure constraints exist
        if 'constraints' not in self.raw_info or not self.raw_info['constraints']:
            self.raw_info['constraints'] = ['1 <= input size <= 10^5']

    def _extract_function_name(self, function_signature: str) -> str:
        """Extract function name from the signature"""
        if function_signature.startswith("class"):
            match = re.match(r'class\s+(\w+)', function_signature)
            if match:
                return match.group(1)
        else:
            match = re.match(r'def\s+(\w+)', function_signature)
            if match:
                return match.group(1)
        return "solution"  # Default name

    def _extract_parameters(self, function_signature: str) -> List[Dict[str, str]]:
        """Extract parameters from function signature"""
        # Check if it's a class
        if function_signature.startswith("class"):
            return []  # For class-based questions, don't extract params
            
        # Match everything between parentheses
        match = re.search(r'\((.*?)\)', function_signature)
        if not match:
            return []
            
        params_str = match.group(1)
        if not params_str.strip():
            return []
            
        parameters = []
        for param in params_str.split(','):
            param = param.strip()
            if not param or param == 'self':
                continue
                
            if ':' in param:
                name, type_hint = param.split(':', 1)
                parameters.append({
                    'name': name.strip(),
                    'type': type_hint.strip().rstrip(')')  # Remove trailing ) if present
                })
            else:
                parameters.append({
                    'name': param,
                    'type': 'Any'
                })
                
        return parameters

    def _normalize_parameters(self, parameters: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Normalize parameter information"""
        normalized = []
        for param in parameters:
            if isinstance(param, dict) and 'name' in param:
                normalized.append({
                    'name': param['name'],
                    'type': param.get('type', 'Any')
                })
        return normalized
    
    def _parse_input_text(self, input_text: str, parameters: List[Dict[str, str]]) -> Dict[str, Any]:
        """Parse the input text from examples into a dictionary of inputs"""
        # Remove "Input: " prefix
        input_text = input_text.replace("Input:", "").strip()
        
        # Try to parse as Python literal
        try:
            # For multi-parameter functions, try to match params by position
            input_values = eval(input_text)
            
            # If input_values is a tuple or list and we have multiple parameters
            if isinstance(input_values, (list, tuple)) and len(parameters) > 1:
                return {param['name']: val for param, val in zip(parameters, input_values)}
            
            # If we have a single parameter
            if len(parameters) == 1:
                return {parameters[0]['name']: input_values}
                
            # Default case
            if len(parameters) > 0:
                return {parameters[0]['name']: input_values}
            else:
                return {"input": input_values}
                
        except (SyntaxError, ValueError, NameError):
            # If we can't parse it directly, just use a default parameter name
            if len(parameters) > 0:
                return {parameters[0]['name']: input_text}
            else:
                return {"input": input_text}
    
    def _parse_output_text(self, output_text: str) -> Any:
        """Parse the output text from examples"""
        # Remove "Output: " prefix
        output_text = output_text.replace("Output:", "").strip()
        
        # Try to parse as Python literal
        try:
            return eval(output_text)
        except (SyntaxError, ValueError, NameError):
            # If we can't parse it, return as string
            return output_text


class TestCaseGenerator:
    """Main class for generating test cases from LLM Python questions"""
    
    def __init__(self, pynguine=None):
        self.pynguine = pynguine or Pynguine()
        self.skip_optional_probability = 0.7  # Probability to skip optional parameters
    
    def generate_test_cases(self, question_info: Dict[str, Any], num_tests: int = 8) -> List[Dict[str, Any]]:
        """Generate test cases for a question"""
        # Convert raw question info to QuestionInfo object
        info = QuestionInfo(question_info)
        
        # Use normalized examples if available
        examples = info.raw_info.get('normalized_examples', [])
        
        # Generate tests using Pynguine
        function_signature = info.raw_info['function_signature']
        problem_statement = info.raw_info['problem_statement']
        
        test_cases = self.pynguine.generate_tests(
            function_signature=function_signature,
            description=problem_statement,
            examples=examples,
            num_tests=num_tests
        )
        
        return test_cases
    
    def format_test_code(self, question_info: Dict[str, Any], test_cases: List[Dict[str, Any]]) -> str:
        """
        Generate Python code for running the test cases
        
        Args:
            question_info: Parsed question information from LLMQuestionGenerator
            test_cases: Test cases generated by generate_test_cases
            
        Returns:
            Python code that can be executed to test a solution
        """
        function_name = question_info["function_name"]
        
        code = [
            "def run_tests(user_solution):",
            "    test_results = []",
            "    total_tests = 0",
            "    passed_tests = 0",
            ""
        ]
        
        # Add test cases
        for i, test in enumerate(test_cases):
            # Ensure inputs is a dictionary
            if not isinstance(test["inputs"], dict):
                test["inputs"] = {"input": test["inputs"]}
                
            inputs_str = ", ".join([f"{k}={repr(v)}" for k, v in test["inputs"].items()])
            expected = repr(test["expected_output"])
            
            code.extend([
                f"    # Test case {i+1}",
                f"    try:",
                f"        total_tests += 1",
                f"        result = user_solution({inputs_str})",
                f"        expected = {expected}",
                f"        passed = result == expected",
                f"        if passed:",
                f"            passed_tests += 1",
                f"        test_results.append({{",
                f"            'test_id': {test['test_id']},",
                f"            'inputs': {repr(test['inputs'])},",
                f"            'expected_output': expected,",
                f"            'actual_output': result,",
                f"            'passed': passed,",
                f"            'is_example': {bool(test.get('is_example', False))}",
                f"        }})",
                f"    except Exception as e:",
                f"        test_results.append({{",
                f"            'test_id': {test['test_id']},",
                f"            'inputs': {repr(test['inputs'])},",
                f"            'expected_output': {expected},",
                f"            'error': str(e),",
                f"            'passed': False,",
                f"            'is_example': {bool(test.get('is_example', False))}",
                f"        }})",
                ""
            ])
        
        # Add return statement
        code.extend([
            "    return {",
            "        'total_tests': total_tests,",
            "        'passed_tests': passed_tests,",
            "        'passing_ratio': passed_tests / total_tests if total_tests > 0 else 0,",
            "        'results': test_results",
            "    }"
        ])
        
        return "\n".join(code)


class ChatbotHandler:
    """Handles chatbot interactions with the coding buddy"""
    
    def __init__(self):
        self.client = openai_client
        self.conversation_history = {}  # Store conversation history by session
        self.max_history_length = 10  # Maximum number of messages to keep in history
    
    def _get_session_id(self):
        """Get unique session ID for the current user"""
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        return session['session_id']
    
    def _init_conversation(self, session_id):
        """Initialize conversation if it doesn't exist"""
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = [
                {"role": "system", "content": """You are a helpful coding assistant called 'Coding Buddy'. 
                Your job is to help the user with programming challenges. You should:
                1. Provide hints rather than complete solutions
                2. Guide users through debugging their code
                3. Explain programming concepts when relevant
                4. Be encouraging and supportive
                Keep responses concise and focused on helping the user learn.
                """}
            ]
    
    def _clean_old_conversations(self):
        """Remove old conversation histories to save memory"""
        # Keep only the 100 most recent conversations
        if len(self.conversation_history) > 100:
            keys_to_remove = sorted(self.conversation_history.keys(), 
                                   key=lambda k: self.conversation_history[k][-1].get('timestamp', 0))[:50]
            for key in keys_to_remove:
                del self.conversation_history[key]
    
    @limits(calls=RATE_LIMIT_MINUTE, period=60)
    def get_response(self, user_message: str, question_info=None, code_solution=None, test_results=None) -> str:
        """Get a response from the chatbot for the user's message"""
        session_id = self._get_session_id()
        self._init_conversation(session_id)
        
        # Add context about the current question and code if available
        context_parts = []
        if question_info:
            context_parts.append(f"Current Question: {question_info.get('function_name', 'Unknown')}")
            context_parts.append(f"Problem: {question_info.get('problem_statement', 'No description')}")
            context_parts.append(f"Function Signature: {question_info.get('function_signature', 'No signature')}")
        
        if code_solution:
            context_parts.append(f"User's Current Code:\n```python\n{code_solution}\n```")
        
        if test_results:
            passed = test_results.get('passed_tests', 0)
            total = test_results.get('total_tests', 0)
            context_parts.append(f"Test Results: {passed}/{total} tests passed")
            
            # Add details about failed tests if any
            if passed < total and 'results' in test_results:
                failed_tests = [t for t in test_results['results'] if not t.get('passed', False)]
                if failed_tests:
                    context_parts.append("Failed Tests:")
                    for i, test in enumerate(failed_tests[:3]):  # Show only first 3 failed tests
                        error = test.get('error', '')
                        inputs = test.get('inputs', {})
                        expected = test.get('expected_output', '')
                        actual = test.get('actual_output', '')
                        
                        if error:
                            context_parts.append(f"Test {test.get('test_id', i+1)} Error: {error}")
                        else:
                            context_parts.append(f"Test {test.get('test_id', i+1)} Expected: {expected}, Got: {actual}")
        
        # Create context message if we have any context
        if context_parts:
            context = "\n".join(context_parts)
            self.conversation_history[session_id].append({
                "role": "system", 
                "content": f"Here's the current context:\n{context}"
            })
        
        # Add user message to history
        self.conversation_history[session_id].append({
            "role": "user",
            "content": user_message,
            "timestamp": time.time()
        })
        
        # Truncate history if too long (keep system message)
        if len(self.conversation_history[session_id]) > self.max_history_length + 1:
            system_message = self.conversation_history[session_id][0]
            self.conversation_history[session_id] = [system_message] + self.conversation_history[session_id][-(self.max_history_length):]
        
        try:
            # Use OpenAI API if available
            if OPENAI_API_KEY:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=self.conversation_history[session_id],
                    temperature=0.7,
                    max_tokens=800
                )
                
                assistant_message = response.choices[0].message.content.strip()
            else:
                # Fallback response if no API key
                assistant_message = self._get_fallback_response(user_message, question_info, code_solution, test_results)
            
            # Add assistant response to history
            self.conversation_history[session_id].append({
                "role": "assistant",
                "content": assistant_message,
                "timestamp": time.time()
            })
            
            # Clean up old conversations periodically
            self._clean_old_conversations()
            
            return assistant_message
            
        except Exception as e:
            logger.error(f"Error getting chatbot response: {e}")
            return f"I'm having trouble generating a response right now. Please try again later."
    
    def _get_fallback_response(self, user_message, question_info, code_solution, test_results):
        """Generate a simple response when API is not available"""
        # Simple response patterns based on user message
        message_lower = user_message.lower()
        
        if "error" in message_lower or "bug" in message_lower:
            return "It looks like you might be dealing with an error. Try adding print statements to see the values of your variables at each step to track down where the issue occurs."
            
        if "hint" in message_lower:
            return "Here's a hint: Break down the problem into smaller steps. First understand what each input and output example means, then work through each step logically."
            
        if "help" in message_lower:
            return "I'm here to help! What specific part of the problem are you struggling with? Understanding the requirements, designing an algorithm, or debugging your solution?"
            
        if "test" in message_lower and test_results:
            passed = test_results.get('passed_tests', 0)
            total = test_results.get('total_tests', 0)
            
            if passed == total:
                return "Great job! All tests are passing. Your solution works correctly."
            else:
                return f"You're passing {passed} out of {total} tests. Keep going! Check your logic for edge cases that might not be handled correctly."
        
        # Default response
        return "I'm here to help with your coding challenge. Could you tell me what specific aspect you need assistance with? I can help you understand the problem, develop an algorithm, or debug your solution."


class CodeTester:
    """Class for executing user code and running tests"""
    
    def __init__(self):
        self.temp_dir = Path(os.getcwd()) / "temp"
        self.temp_dir.mkdir(exist_ok=True)
        
    def cleanup_old_files(self, max_age_seconds: int = 3600):
        """Clean up old temporary files"""
        current_time = time.time()
        for file_path in self.temp_dir.glob("*"):
            if current_time - file_path.stat().st_mtime > max_age_seconds:
                try:
                    file_path.unlink()
                except Exception:
                    pass

    @staticmethod
    def sanitize_module_name(name: str) -> str:
        """Ensure module name is valid Python identifier"""
        return f"code_mod_{abs(hash(name)) % 10000}"

    def execute_code(self, user_code: str, function_name: str, test_code: str, timeout: int = 5) -> Dict[str, Any]:
        """
        Execute the user's code and run tests with improved security and error handling
        """
        # Clean up old files first
        self.cleanup_old_files()
        
        # Generate unique execution ID
        execution_id = str(uuid.uuid4())
        module_name = self.sanitize_module_name(execution_id)
        
        code_file = self.temp_dir / f"{module_name}.py"
        test_file = self.temp_dir / f"test_{module_name}.py"
        
        try:
            # Validate inputs
            if not isinstance(user_code, str) or not isinstance(function_name, str):
                raise ValueError("Invalid input types")
            
            if not function_name.isidentifier():
                raise ValueError("Invalid function name")
            
            # Write files with proper encoding and error handling
            code_file.write_text(user_code, encoding='utf-8')
            
            # Create test file with proper imports and safety measures
            test_code_content = [
                "import sys",
                "import signal",
                "import resource",
                "from contextlib import contextmanager",
                "",
                "# Set up timeout handler",
                "@contextmanager",
                "def timeout(seconds):",
                "    def signal_handler(signum, frame):",
                "        raise TimeoutError('Execution timed out')",
                "    signal.signal(signal.SIGALRM, signal_handler)",
                "    signal.alarm(seconds)",
                "    try:",
                "        yield",
                "    finally:",
                "        signal.alarm(0)",
                "",
                "import platform",
                "",
                "# Set resource limits",
                "def set_resource_limits():",
                "    \"\"\"Set resource limits with fallback for different platforms\"\"\"",
                "    try:",
                "        # Maximum CPU time in seconds",
                "        resource.setrlimit(resource.RLIMIT_CPU, (3, 3))",
                "    except (ValueError, resource.error, AttributeError):",
                "        pass",
                "",
                "    try:",
                "        # Maximum memory size (100 MB) - using a lower value to avoid errors",
                "        # Get the current limit first",
                "        current_limit = resource.getrlimit(resource.RLIMIT_AS)",
                "        # Use either 100MB or 75% of current limit, whichever is smaller",
                "        new_limit = min(100 * 1024 * 1024, int(current_limit[1] * 0.75) if current_limit[1] != resource.RLIM_INFINITY else 100 * 1024 * 1024)",
                "        resource.setrlimit(resource.RLIMIT_AS, (new_limit, new_limit))",
                "    except (ValueError, resource.error, AttributeError):",
                "        pass",
                "",
                "    try:",
                "        # Maximum number of processes",
                "        resource.setrlimit(resource.RLIMIT_NPROC, (10, 10))",
                "    except (ValueError, resource.error, AttributeError):",
                "        pass",
                "",
                "# Apply resource limits only on Unix-like systems",
                "if platform.system() != 'Windows':",
                "    set_resource_limits()",
                "",
                f"sys.path.insert(0, '{self.temp_dir}')",
                "# Block potentially dangerous imports",
                "sys.modules['os'] = None",
                "sys.modules['subprocess'] = None",
                "sys.modules['multiprocessing'] = None",
                "sys.modules['socket'] = None",
                "sys.modules['requests'] = None",
                "sys.modules['urllib'] = None",
                "",
                f"import {module_name}",
                f"{function_name} = {module_name}.{function_name}",
                "",
                test_code,
                "",
                "import json",
                "with timeout(4):",  # Inner timeout as additional safety
                f"    results = run_tests({function_name})",
                "print(json.dumps(results))"
            ]
            
            test_file.write_text('\n'.join(test_code_content), encoding='utf-8')
            
            # Execute in subprocess with resource limits
            result = subprocess.run(
                [sys.executable, str(test_file)],
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, 'PYTHONPATH': str(self.temp_dir)},
            )
            
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': result.stderr[:500],  # Limit error message size
                    'total_tests': 0,
                    'passed_tests': 0,
                    'passing_ratio': 0,
                    'results': []
                }
            
            try:
                return {
                    'success': True,
                    **json.loads(result.stdout)
                }
            except json.JSONDecodeError:
                return {
                    'success': False,
                    'error': 'Invalid test output format',
                    'total_tests': 0,
                    'passed_tests': 0,
                    'passing_ratio': 0,
                    'results': []
                }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f'Execution timed out after {timeout} seconds',
                'total_tests': 0,
                'passed_tests': 0,
                'passing_ratio': 0,
                'results': []
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)[:500],  # Limit error message size
                'total_tests': 0,
                'passed_tests': 0,
                'passing_ratio': 0,
                'results': []
            }
        
        finally:
            # Clean up files
            try:
                code_file.unlink(missing_ok=True)
                test_file.unlink(missing_ok=True)
            except Exception:
                pass


# Initialize components
auth.init_db()
room.init_room_db()
question_generator = LLMQuestionGenerator()
test_case_generator = TestCaseGenerator(Pynguine())
code_tester = CodeTester()
chatbot_handler = ChatbotHandler()

# Use a proper cache with expiration
questions_db = TTLCache(maxsize=app.config['MAX_CACHE_SIZE'], ttl=app.config['CACHE_TTL'])

# Initialize authentication routes
auth.init_auth(app)




# Add context processors for user data
@app.context_processor
def inject_user_data():
    if 'user_id' in session:
        return {'logged_in': True, 'username': session.get('username')}
    return {'logged_in': False}

@app.context_processor
def inject_user_stats():
    if 'user_id' in session:
        try:
            db = auth.get_db()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM user_stats WHERE user_id = ?", (session['user_id'],))
            stats = cursor.fetchone()
            
            if stats:
                return {
                    'user_stats': {
                        'problems_solved': stats['problems_solved'],
                        'current_streak': stats['current_streak'],
                        'longest_streak': stats['longest_streak'],
                        'points': stats['points']
                    }
                }
        except Exception as e:
            logger.error(f"Error fetching user stats: {e}")
    
    # Default empty stats
    return {
        'user_stats': {
            'problems_solved': 0,
            'current_streak': 0,
            'longest_streak': 0,
            'points': 0
        }
    }

@app.before_request
def validate_request():
    """Validate incoming requests"""
    if request.method == 'POST':
        # Skip validation for non-API endpoints
        if (request.endpoint and not request.endpoint.startswith('api_') and
            request.endpoint not in ['login', 'register', 'index', 'create_room', 'join_room']):
            if not request.is_json:
                return jsonify({
                    'success': False,
                    'error': 'Content-Type must be application/json'
                }), 400
        
        if request.content_length and request.content_length > app.config['MAX_CONTENT_LENGTH']:
            return jsonify({
                'success': False,
                'error': 'Request too large'
            }), 413

@app.route('/')
def index():
    """Render the main application page or redirect to login"""
    if 'user_id' not in session:
        # User is not logged in, redirect to login page
        return redirect(url_for('login'))
    
    # Check if we're coming from a room with a question
    room_id = request.args.get('room_id')
    question_id = request.args.get('question_id')
    
    # If we have both room_id and question_id, load that specific question
    preloaded_question = None
    room_data = None
    
    if room_id and question_id:
        try:
            # Get the room data to verify user membership
            conn = room.get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM rooms WHERE id = ?", (room_id,))
            room_data = cursor.fetchone()
            
            if room_data and room_data['question_id'] == question_id:
                # Verify user is a member of this room
                cursor.execute(
                    "SELECT id FROM room_members WHERE room_id = ? AND user_id = ?", 
                    (room_id, session['user_id'])
                )
                if cursor.fetchone():
                    # User is a member, get the question
                    question_data = questions_db.get(question_id)
                    if question_data:
                        preloaded_question = {
                            'question_id': question_id,
                            'question_info': question_data['question_info'],
                            'example_test_cases': [tc for tc in question_data['test_cases'] if tc.get('is_example', False)]
                        }
            conn.close()
        except Exception as e:
            logger.error(f"Error loading room question: {e}")
            if 'conn' in locals() and conn:
                conn.close()
    
    # User is logged in, show the main app
    return render_template('index.html', preloaded_question=preloaded_question, room_data=room_data)

@app.route('/favicon.ico')
def favicon():
    """Handle favicon requests"""
    return '', 204  # Return empty response with "No Content" status

@app.route('/api/chat-completion', methods=['POST'])
def chat_completion():
    """Handle chat completion requests with proper LLM integration"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request data',
                'message': "I couldn't process your message. Please try again."
            }), 400

        user_message = data.get('user_message', '').strip()
        if not user_message:
            return jsonify({
                'success': False,
                'error': 'Empty message',
                'message': "Please type a message first."
            }), 400
        
        # Get context information from the request
        question_info = data.get('question_info', {})
        code_solution = data.get('code_solution', '')
        test_results = data.get('test_results', {})
        
        try:
            # Get response from chatbot handler
            response = chatbot_handler.get_response(
                user_message, 
                question_info=question_info,
                code_solution=code_solution,
                test_results=test_results
            )
            
            return jsonify({
                'success': True,
                'message': response
            })
            
        except RateLimitException:
            return jsonify({
                'success': False,
                'error': 'Rate limit exceeded',
                'message': "I'm getting a lot of requests right now. Please try again in a moment."
            }), 429
            
    except Exception as e:
        logger.error(f"Error in chat completion: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': "An unexpected error occurred. Please try again."
        }), 500

@app.route('/api/generate-question', methods=['POST'])
def generate_question():
    """Generate a coding question based on difficulty and topic"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid request data'}), 400
            
        difficulty = data.get('difficulty', 'medium')
        topic = data.get('topic')
        
        if difficulty not in ['easy', 'medium', 'hard']:
            return jsonify({'success': False, 'error': 'Invalid difficulty level'}), 400
        
        try:
            # Generate the question using LLM
            question_response = question_generator.generate_question(difficulty, topic)
            logger.info(f"Generated question with difficulty: {difficulty}")
            
            if not question_response.get('success'):
                logger.error(f"Question generation failed: {question_response.get('error', 'Unknown error')}")
                return jsonify(question_response), 400
                
            question_info = question_response['question']
            
            # Ensure we have required fields in question_info
            required_fields = ['problem_statement', 'function_signature', 'function_name']
            for field in required_fields:
                if field not in question_info:
                    return jsonify({
                        'success': False, 
                        'error': f'Generated question missing required field: {field}'
                    }), 500
            
            # Generate test cases using Pynguine
            test_cases = test_case_generator.generate_test_cases(question_info)
            test_code = test_case_generator.format_test_code(question_info, test_cases)
            
            # Store the question and test cases
            question_id = str(uuid.uuid4())
            questions_db[question_id] = {
                'question_info': question_info,
                'test_cases': test_cases,
                'test_code': test_code,
                'created_at': time.time()
            }
            
            session['current_question_id'] = question_id
            
            # Extract only example test cases for the response
            example_test_cases = [tc for tc in test_cases if tc.get('is_example', False)]
            
            return jsonify({
                'success': True,
                'question_id': question_id,
                'question_info': question_info,
                'example_test_cases': example_test_cases
            })
            
        except RateLimitException:
            return jsonify({
                'success': False,
                'error': 'Rate limit exceeded',
                'message': "You're generating questions too quickly. Please wait a moment and try again."
            }), 429
        except Exception as e:
            logger.exception("Error in question generation process")
            return jsonify({
                'success': False,
                'error': f'Question generation failed: {str(e)}'
            }), 500
            
    except Exception as e:
        logger.exception("Error in generate_question endpoint")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/api/submit-solution', methods=['POST'])
@login_required
def submit_solution():
    """Submit a solution for testing"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid request data'}), 400
            
        question_id = data.get('question_id')
        code = data.get('code', '').strip()
        
        if not code:
            return jsonify({'success': False, 'error': 'No code provided'}), 400
            
        # Validate code length
        if len(code) > 50000:  # 50KB limit
            return jsonify({'success': False, 'error': 'Code submission too large'}), 400
            
        # Sanitize user code - prevent malicious imports
        if any(pattern in code for pattern in [
            "import os", "import subprocess", "import sys", 
            "from os import", "from subprocess import", "from sys import",
            "__import__('os')", "__import__('subprocess')", 
            "eval(", "exec("
        ]):
            return jsonify({
                'success': False,
                'error': 'Code contains restricted imports or functions'
            }), 403
            
        question_data = questions_db.get(question_id)
        if not question_data:
            return jsonify({
                'success': False,
                'error': 'Question not found or expired'
            }), 404
        
        function_name = question_data['question_info']['function_name']
        test_code = question_data['test_code']
        
        # Execute user code
        results = execute_code_simplified(code, function_name, test_code)
        
        # If all tests passed, update user stats
        if results.get('success') and results.get('passing_ratio') == 1:
            update_user_stats_on_success()
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except RateLimitException:
        return jsonify({
            'success': False,
            'error': 'Rate limit exceeded',
            'message': "You're submitting solutions too quickly. Please wait a moment and try again."
        }), 429
    except Exception as e:
        logger.exception("Error in submit_solution endpoint")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def update_user_stats_on_success():
    """Update user stats when a problem is solved successfully"""
    if 'user_id' in session:
        try:
            # Update user stats
            UserAuth.update_user_stats(session['user_id'], {
                'problems_solved': 1,  # Increment problems solved count
                'current_streak': 1,   # Increment streak
                'points': 10           # Award points
            })
            logger.info(f"Updated stats for user {session['user_id']} after solving problem")
        except Exception as e:
            logger.error(f"Error updating user stats: {e}")

def execute_code_simplified(user_code: str, function_name: str, test_code: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Execute the user's code and run tests with simplified security measures
    that are more likely to work across platforms.
    """
    # Create a temporary directory if it doesn't exist
    temp_dir = Path(os.getcwd()) / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    # Generate unique execution ID
    execution_id = str(uuid.uuid4())
    module_name = f"code_mod_{abs(hash(execution_id)) % 10000}"
    
    code_file = temp_dir / f"{module_name}.py"
    test_file = temp_dir / f"test_{module_name}.py"
    
    try:
        # Validate inputs
        if not isinstance(user_code, str) or not isinstance(function_name, str):
            raise ValueError("Invalid input types")
        
        if not function_name.isidentifier():
            raise ValueError("Invalid function name")
        
        # Write files with proper encoding and error handling
        code_file.write_text(user_code, encoding='utf-8')
        
        # Create test file with simplified safety measures
        test_code_content = [
            "import sys",
            "import signal",
            "from contextlib import contextmanager",
            "",
            "# Set up timeout handler",
            "@contextmanager",
            "def timeout(seconds):",
            "    def signal_handler(signum, frame):",
            "        raise TimeoutError('Execution timed out')",
            "    try:",
            "        # Check if SIGALRM is available (Unix-like systems)",
            "        if hasattr(signal, 'SIGALRM'):",
            "            old_handler = signal.signal(signal.SIGALRM, signal_handler)",
            "            signal.alarm(seconds)",
            "        yield",
            "    finally:",
            "        if hasattr(signal, 'SIGALRM'):",
            "            signal.alarm(0)",
            "            signal.signal(signal.SIGALRM, old_handler)",
            "",
            f"sys.path.insert(0, '{temp_dir}')",
            f"import {module_name}",
            f"{function_name} = {module_name}.{function_name}",
            "",
            test_code,
            "",
            "import json",
            "try:",
            "    with timeout(4):",  # Inner timeout as additional safety
            f"        results = run_tests({function_name})",
            "    print(json.dumps(results))",
            "except Exception as e:",
            "    print(json.dumps({",
            "        'success': False,",
            "        'error': str(e),",
            "        'total_tests': 0,",
            "        'passed_tests': 0,",
            "        'passing_ratio': 0,",
            "        'results': []",
            "    }))"
        ]
        
        test_file.write_text('\n'.join(test_code_content), encoding='utf-8')
        
        # Execute in subprocess with basic timeout
        result = subprocess.run(
            [sys.executable, str(test_file)],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, 'PYTHONPATH': str(temp_dir)},
        )
        
        if result.returncode != 0:
            return {
                'success': False,
                'error': result.stderr[:500],  # Limit error message size
                'total_tests': 0,
                'passed_tests': 0,
                'passing_ratio': 0,
                'results': []
            }
        
        try:
            return {
                'success': True,
                **json.loads(result.stdout)
            }
        except json.JSONDecodeError:
            return {
                'success': False,
                'error': 'Invalid test output format',
                'total_tests': 0,
                'passed_tests': 0,
                'passing_ratio': 0,
                'results': []
            }
        
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': f'Execution timed out after {timeout} seconds',
            'total_tests': 0,
            'passed_tests': 0,
            'passing_ratio': 0,
            'results': []
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': str(e)[:500],  # Limit error message size
            'total_tests': 0,
            'passed_tests': 0,
            'passing_ratio': 0,
            'results': []
        }
    
    finally:
        # Clean up files
        try:
            if code_file.exists():
                code_file.unlink()
            if test_file.exists():
                test_file.unlink()
        except Exception:
            pass

@app.route('/api/get-question/<question_id>', methods=['GET'])
@login_required
def get_question(question_id):
    """Get a specific question by ID"""
    try:
        question_data = questions_db.get(question_id)
        if not question_data:
            return jsonify({
                'success': False,
                'error': 'Question not found or expired'
            }), 404
        
        # Extract only example test cases for the response
        example_test_cases = [tc for tc in question_data['test_cases'] if tc.get('is_example', False)]
        
        return jsonify({
            'success': True,
            'question_info': question_data['question_info'],
            'example_test_cases': example_test_cases
        })
        
    except Exception as e:
        logger.exception("Error in get_question endpoint")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Error handlers
@app.errorhandler(400)
def bad_request(error):
    """Handle bad request errors"""
    return jsonify({
        'success': False,
        'error': 'Bad request',
        'message': str(error)
    }), 400

@app.errorhandler(404)
def not_found(error):
    """Handle not found errors"""
    return jsonify({
        'success': False,
        'error': 'Not found',
        'message': str(error)
    }), 404

@app.errorhandler(429)
def rate_limit_exceeded(error):
    """Handle rate limiting errors"""
    return jsonify({
        'success': False,
        'error': 'Too many requests',
        'message': 'Rate limit exceeded. Please try again later.'
    }), 429

@app.errorhandler(500)
def server_error(error):
    """Handle internal server errors"""
    logger.exception("Internal server error")
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'message': 'An unexpected error occurred on the server.'
    }), 500

@app.errorhandler(Exception)
def handle_error(error):
    """Global error handler"""
    logger.exception(f"Unhandled exception: {error}")
    return jsonify({
        'success': False,
        'error': 'Server error',
        'message': 'An unexpected error occurred.'
    }), 500

def cleanup_resources():
    """Clean up resources before shutting down"""
    try:
        # Clean up temporary files
        shutil.rmtree(code_tester.temp_dir, ignore_errors=True)
        logger.info("Cleaned up temporary files")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

# Register signal handlers for graceful shutdown
def signal_handler(sig, frame):
    """Handle termination signals"""
    logger.info(f"Received signal {sig}, shutting down gracefully")
    cleanup_resources()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == '__main__':
    try:
        # Create temp directory if it doesn't exist
        os.makedirs(code_tester.temp_dir, exist_ok=True)
        
        # Clean up old temporary files on startup
        code_tester.cleanup_old_files(max_age_seconds=1800)  # 30 minutes
        
        # Log startup information
        logger.info(f"Starting server on port {int(os.getenv('PORT', 5000))}")
        logger.info(f"OpenAI API Key configured: {bool(OPENAI_API_KEY)}")
        
        # Start the application
        app.run(
            host='0.0.0.0',
            port=int(os.getenv('PORT', 5000)),
            debug=os.getenv('FLASK_ENV') == 'development',
            threaded=True
        )
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        sys.exit(1)