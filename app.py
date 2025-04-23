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
from datetime import datetime

# Import authentication module
import auth
from auth import login_required, UserAuth
# Add these imports at the top of your app.py file
import room
from flask_socketio import SocketIO, join_room, leave_room, emit
from screen import socketio

# Create database directory if it doesn't exist
os.makedirs(os.path.join(os.getcwd(), 'database'), exist_ok=True)

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize the app first
app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB max-limit
app.config['MAX_CACHE_SIZE'] = 1000  # 1000 questions in cache
app.config['CACHE_TTL'] = 3600  # 1 hour TTL
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes

# For proper IP handling behind proxies
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Initialize SocketIO after app but before routes
socketio.init_app(app, cors_allowed_origins="*")

# Initialize OpenAI client
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    logger.warning("No OpenAI API key provided. LLM features will be limited.")
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Constants
RATE_LIMIT_MINUTE = 30  # API calls per minute

# Use a proper cache with expiration
questions_db = TTLCache(maxsize=app.config['MAX_CACHE_SIZE'], ttl=app.config['CACHE_TTL'])

def initialize_databases():
    """Ensure all database tables are created"""
    # Initialize auth database
    auth.init_db()
    # Initialize room database
    room.init_room_db()
    logger.info("All databases initialized at startup")

# Initialize databases
initialize_databases()

@app.template_filter('format_datetime')
def format_datetime_filter(value, format="%Y-%m-%d %H:%M:%S"):
    """Format a datetime object to string."""
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return value
    return value.strftime(format)

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

@app.route('/rooms')
@login_required
def rooms():
    """Show list of user's rooms"""
    user_id = session.get('user_id')
    user_rooms = room.get_user_rooms(user_id)
    return render_template('room.html', rooms=user_rooms)

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

@app.route('/rooms/join', methods=['GET', 'POST'])
@login_required
def join_room_route():
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
        # Try to get the room
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
            try:
                # Get question from cache
                cached_question = questions_db.get(question_id)
                
                if cached_question:
                    # Only create question_data if we have valid cache data
                    question_info = cached_question.get('question_info')
                    test_cases = cached_question.get('test_cases', [])
                    
                    if question_info:  # Verify question_info exists
                        example_test_cases = [tc for tc in test_cases if tc.get('is_example', False)]
                        
                        question_data = {
                            'id': question_id,
                            'info': question_info,
                            'example_test_cases': example_test_cases
                        }
                    else:
                        # Log the issue if question_info is missing
                        logger.warning(f"Question {question_id} has no question_info")
                else:
                    # Log if the question isn't in the cache
                    logger.warning(f"Question {question_id} not found in cache")
            except Exception as e:
                # Log any errors in this process
                logger.error(f"Error retrieving question data: {str(e)}")
        
        # Add current year for the footer
        current_year = datetime.now().year
        
        # Render the template with the data
        return render_template(
            'room_detail.html',
            room=room_data, 
            is_creator=is_creator,
            question=question_data,
            user_stats=user_stats,
            current_year=current_year
        )
        
    except Exception as e:
        logger.error(f"Error in room_detail: {str(e)}")
        flash(f'Error accessing room: {str(e)}', 'error')
        return redirect(url_for('rooms'))

## Fix the profile update route in app.py

@app.route('/api/profile/update', methods=['POST'])
@login_required
def api_update_profile():
    """API endpoint to update user profile"""
    try:
        # Get the request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request data'
            }), 400
            
        # Extract fields for update
        username = data.get('username')
        email = data.get('email')
        
        # Verify some data was provided
        if not username and not email:
            return jsonify({
                'success': False,
                'error': 'No update data provided'
            }), 400
        
        # Get user ID from session
        user_id = session.get('user_id')
        
        # Update the profile
        # *** FIXED FUNCTION CALL - use regular function call instead of static method ***
        import auth  # Make sure auth is imported
        success, message = auth.update_user_profile(user_id, username, email)
        
        if success:
            # Update session with new username if it was changed
            if username:
                session['username'] = username
                
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
        
    except Exception as e:
        logger.exception("Error updating profile")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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
        
        # Store the question with a persistent key in the database
        question_id = str(uuid.uuid4())
        
        # Make sure questions_db is actually persisted
        questions_db[question_id] = {
            'question_info': question_info,
            'test_cases': test_cases,
            'test_code': test_code,
            'created_at': time.time()
        }
        
        # Print debug info to logs
        logger.info(f"Generated question {question_id} with function: {question_info.get('function_name')}")
        
        # Assign to the room
        cursor.execute(
            "UPDATE rooms SET question_id = ? WHERE id = ?",
            (question_id, room_id)
        )
        conn.commit()
        conn.close()
        
        # Format the response to match what the frontend expects
        return jsonify({
            'success': True,
            'question_id': question_id,
            'question_info': question_info
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
        function_signature = question_data['question_info'].get('function_signature', '')
        
        # More flexible function signature check
        # Extract just the first line with function/class definition
        signature_first_line = None
        for line in function_signature.split('\n'):
            if 'def ' in line or 'class ' in line:
                signature_first_line = line.strip()
                break
                
        if signature_first_line and signature_first_line not in code:
            return jsonify({
                'success': False,
                'error': f'Please keep the function signature intact. Make sure your code includes: "{signature_first_line}"'
            }), 400
            
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

@app.route('/api/room/<room_id>/save-code', methods=['POST'])
@login_required
def api_save_room_code(room_id):
    """API endpoint to save user's code draft in a room"""
    try:
        # Get the request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request data'
            }), 400
            
        # Extract code and question ID
        code = data.get('code')
        question_id = data.get('question_id')
        
        if not code or not question_id:
            return jsonify({
                'success': False,
                'error': 'Code and question ID are required'
            }), 400
            
        # Get current user ID
        user_id = session.get('user_id')
        
        # Save the code draft
        if room.save_code_draft(room_id, user_id, question_id, code):
            return jsonify({
                'success': True,
                'message': 'Code saved successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save code'
            }), 500
            
    except Exception as e:
        logger.exception("Error saving room code draft")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/room/<room_id>/get-code/<question_id>', methods=['GET'])
@login_required
def api_get_room_code(room_id, question_id):
    """API endpoint to get user's saved code draft"""
    try:
        # Get current user ID
        user_id = session.get('user_id')
        
        # Get the saved code draft
        saved_code = room.get_code_draft(room_id, user_id, question_id)
        
        return jsonify({
            'success': True,
            'code': saved_code
        })
        
    except Exception as e:
        logger.exception("Error getting room code draft")
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
        # Before getting the room data, make sure the user exists and is authenticated
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'Authentication required',
                'redirect': url_for('login', next=request.url)
            }), 401
        
        # Get the room data with error handling
        room_data = room.get_room_by_code(room_code)
        
        if not room_data:
            return jsonify({
                'success': False,
                'error': 'Room not found'
            }), 404
        
        # Check if user is a member of this room
        is_member = False
        for member in room_data.get('members', []):
            if member.get('user_id') == user_id:
                is_member = True
                break
                
        if not is_member:
            # Auto-join if not a member
            try:
                room_data = room.join_room(room_code, user_id)
            except Exception as e:
                logger.error(f"Error joining room: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': 'Failed to join room'
                }), 403
        
        # Build the response data
        response_data = {
            'id': room_data['id'],
            'room_code': room_data['room_code'],
            'name': room_data['name'],
            'creator': {
                'id': room_data['creator_id'],
                'username': room_data['creator_name']
            },
            'members': room_data['members'],
            'is_active': room_data.get('is_active', True)
        }
        
        # Add question data if available
        if room_data['question_id']:
            question_id = room_data['question_id']
            cached_question = questions_db.get(question_id)
            
            if cached_question:
                question_info = cached_question.get('question_info')
                
                if question_info:
                    response_data['question'] = {
                        'id': question_id,
                        'info': {
                            'problem_statement': question_info.get('problem_statement', ''),
                            'function_name': question_info.get('function_name', ''),
                            'function_signature': question_info.get('function_signature', ''),
                            'difficulty': question_info.get('difficulty', 'medium'),
                            'examples': question_info.get('examples', []),
                            'constraints': question_info.get('constraints', [])
                        }
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
        example_test_cases = [tc for tc in question_data.get('test_cases', []) if tc.get('is_example', False)]
        
        # Make sure we have all required fields
        question_info = question_data.get('question_info', {})
        
        # Ensure all required fields are present
        if not question_info.get('function_name'):
            logger.warning(f"Question {question_id} missing function_name")
            question_info['function_name'] = "solution"
            
        if not question_info.get('function_signature'):
            logger.warning(f"Question {question_id} missing function_signature")
            question_info['function_signature'] = "def solution():"
            
        if not question_info.get('problem_statement'):
            logger.warning(f"Question {question_id} missing problem_statement")
            question_info['problem_statement'] = "Solve the given problem."
        
        return jsonify({
            'success': True,
            'question_info': question_info,
            'example_test_cases': example_test_cases
        })
        
    except Exception as e:
        logger.exception("Error in get_question endpoint")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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

@app.route('/api/update-stats', methods=['POST'])
@login_required
def update_stats():
    """Update user stats when a problem is solved"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid request data'}), 400
            
        problems_solved = data.get('problems_solved', 0)
        streak = data.get('streak', 0)  
        points = data.get('points', 0)
        difficulty = data.get('difficulty', 'medium')
        
        # Get user ID from session
        user_id = session.get('user_id')
        
        # Update user stats
        UserAuth.update_user_stats(user_id, {
            'problems_solved': problems_solved,
            'current_streak': streak,
            'points': points
        })
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.exception("Error updating stats")
        return jsonify({'success': False, 'error': str(e)}), 500

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
        
        # Ensure function_name is a valid identifier (more flexible validation)
        if not function_name.replace('_', '').isalnum():
            raise ValueError(f"Invalid function name: {function_name}")
        
        # Check if function or class exists in user code
        if not re.search(fr'def\s+{re.escape(function_name)}\s*\(', user_code) and \
           not re.search(fr'class\s+{re.escape(function_name)}\s*[:\(]', user_code):
            raise ValueError(f"Could not find definition for '{function_name}' in your code")
        
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

def cleanup_resources():
    """Clean up resources before shutting down"""
    try:
        # Clean up temporary files
        temp_dir = Path(os.getcwd()) / "temp"
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
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

# This is a conceptual implementation of Pynguine
class Pynguine:
    @staticmethod
    def generate_tests(function_signature: str, description: str,
                       examples: Optional[List[Dict[str, Any]]] = None,
                       num_tests: int = 5) -> List[Dict[str, Any]]:
        """
        Generate test cases based on the function signature, description, and provided examples.
        
        Args:
            function_signature (str): The Python function signature (or class definition) to test.
            description (str): A description of what the function should do.
            examples (Optional[List[Dict[str, Any]]]): A list of example test cases with keys "inputs" and "output".
            num_tests (int): Total number of test cases to generate.
            
        Returns:
            List[Dict[str, Any]]: A list of test cases. Each test case is a dictionary containing:
                - "test_id": A unique identifier for the test case.
                - "is_example": True if the test case comes from provided examples, otherwise False.
                - "inputs": A dictionary mapping parameter names to generated sample inputs.
                - "expected_output": The expected output based on the function's logic.
        """
        # Extract function name and parameters from the function signature
        if "def " in function_signature:
            # Look for the first line with 'def '
            signature_line = [line for line in function_signature.split('\n') if "def " in line][0]
            match = re.match(r'def\s+(\w+)\s*\((.*?)\)', signature_line)
            
            if not match:
                # Try a fallback regex pattern
                match = re.search(r'def\s+(\w+)\s*\((.*?)\)(?:\s*->.*?)?:', function_signature, re.DOTALL)
            
            if not match:
                logger.error(f"Failed to parse function signature: {function_signature}")
                function_name = "solution"
                params = [("input", None)]
            else:
                function_name = match.group(1)
                params_str = match.group(2)
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
            # Handle class-based definitions (default to using 'self' only)
            match = re.match(r'class\s+(\w+)', function_signature)
            if match:
                function_name = match.group(1)
                params = [("self", None)]
            else:
                function_name = "Solution"
                params = [("self", None)]
        else:
            logger.warning(f"Unrecognized function signature format: {function_signature}")
            function_name = "solution"
            params = [("input", None)]
        
        test_cases: List[Dict[str, Any]] = []
        
        # Incorporate provided examples first
        if examples:
            for i, example in enumerate(examples):
                test_cases.append({
                    "test_id": i + 1,
                    "is_example": True,
                    "inputs": example.get("inputs", {}),
                    "expected_output": example.get("output")
                })
        
        # Generate additional test cases to reach the desired total number
        for i in range(len(test_cases), num_tests):
            test_case = {
                "test_id": i + 1,
                "is_example": False,
                "inputs": {},
                "expected_output": None
            }
            
            # Generate sample inputs for each parameter (skip 'self')
            for param_name, param_type in params:
                if param_name != 'self':
                    test_case["inputs"][param_name] = Pynguine._generate_sample_input(
                        param_name, param_type, description
                    )
            
            # Determine the expected output based on the function's logic
            test_case["expected_output"] = Pynguine._generate_expected_output(
                function_name, test_case["inputs"], description
            )
            test_cases.append(test_case)
        
        return test_cases

    @staticmethod
    def _generate_sample_input(param_name: str, param_type: Optional[str], description: str) -> Any:
        """
        Generate a sample input for a given parameter based on its name and type hint.
        
        Args:
            param_name (str): The name of the parameter.
            param_type (Optional[str]): The type hint for the parameter.
            description (str): The function description which may help in inferring the input.
            
        Returns:
            Any: A generated sample input that is simple and related to the parameter.
        """
        # Use the type hint if available to determine the input type
        if param_type:
            if 'int' in param_type:
                return random.randint(-10, 10)
            elif 'float' in param_type:
                return round(random.uniform(-10, 10), 1)
            elif 'str' in param_type:
                return f"test_{random.randint(1, 5)}"
            elif 'list' in param_type or 'List' in param_type:
                # Create a short list with items based on the list type if provided
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
        
        # If no type hint is available, infer the sample input from the parameter name
        if 'num' in param_name or 'count' in param_name or 'index' in param_name:
            return random.randint(1, 10)
        elif 'name' in param_name or 'text' in param_name or 'str' in param_name:
            return f"sample_{random.randint(1, 3)}"
        elif 'list' in param_name or 'array' in param_name:
            return [random.randint(1, 5) for _ in range(random.randint(2, 4))]
        elif 'dict' in param_name or 'map' in param_name:
            return {f"k{i}": random.randint(1, 5) for i in range(random.randint(1, 2))}
        elif 'flag' in param_name or 'enable' in param_name:
            return random.choice([True, False])
        else:
            return f"input_{random.randint(1, 3)}"

    @staticmethod
    def _generate_expected_output(function_name: str, inputs: Dict[str, Any], description: str) -> Any:
        """
        Generate an expected output based on the function name, its inputs, and the description.
        This method includes special handling for common algorithmic tasks.
        
        Args:
            function_name (str): The name of the function being tested.
            inputs (Dict[str, Any]): The generated inputs for the function.
            description (str): The description of the function's intended behavior.
            
        Returns:
            Any: The expected output based on common logic patterns.
        """
        function_name_lower = function_name.lower()
        description_lower = description.lower()
        
        # Palindrome check logic
        if 'palindrome' in function_name_lower or ('palindrome' in description_lower and 'is_' in function_name_lower):
            for input_val in inputs.values():
                if isinstance(input_val, str):
                    cleaned = ''.join(char.lower() for char in input_val if char.isalnum())
                    return cleaned == cleaned[::-1]
        
        # Anagram check logic
        elif 'anagram' in function_name_lower or 'anagram' in description_lower:
            input_values = list(inputs.values())
            if len(input_values) >= 2 and all(isinstance(x, str) for x in input_values[:2]):
                s1, s2 = input_values[0], input_values[1]
                return sorted(s1.lower()) == sorted(s2.lower())
        
        # Sum/Add logic
        elif 'sum' in function_name_lower or 'add' in function_name_lower:
            numeric_inputs = [v for v in inputs.values() if isinstance(v, (int, float))]
            if numeric_inputs:
                return sum(numeric_inputs)
            for input_val in inputs.values():
                if isinstance(input_val, list) and all(isinstance(x, (int, float)) for x in input_val):
                    return sum(input_val)
        
        # Average/mean logic
        elif 'average' in function_name_lower or 'mean' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, list) and input_val and all(isinstance(x, (int, float)) for x in input_val):
                    return sum(input_val) / len(input_val)
        
        # Maximum value logic
        elif 'max' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, list) and input_val:
                    try:
                        return max(input_val)
                    except TypeError:
                        pass
        
        # Minimum value logic
        elif 'min' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, list) and input_val:
                    try:
                        return min(input_val)
                    except TypeError:
                        pass
        
        # Count or length logic
        elif any(x in function_name_lower for x in ['count', 'length', 'len']):
            for input_val in inputs.values():
                if isinstance(input_val, (list, str, dict)):
                    return len(input_val)
        
        # Reverse logic
        elif 'reverse' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, list):
                    return input_val[::-1]
                elif isinstance(input_val, str):
                    return input_val[::-1]
        
        # Sort logic
        elif 'sort' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, list):
                    try:
                        return sorted(input_val)
                    except TypeError:
                        pass
        
        # Find missing number logic
        elif 'find' in function_name_lower and 'missing' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, list) and input_val and all(isinstance(x, int) for x in input_val):
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
        
        # Fibonacci sequence logic
        elif 'fibonacci' in function_name_lower or 'fib' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, int) and input_val >= 0:
                    if input_val <= 1:
                        return input_val
                    a, b = 0, 1
                    for _ in range(2, input_val + 1):
                        a, b = b, a + b
                    return b
        
        # Factorial logic
        elif 'factorial' in function_name_lower:
            for input_val in inputs.values():
                if isinstance(input_val, int) and input_val >= 0:
                    result = 1
                    for i in range(2, input_val + 1):
                        result *= i
                    return result
        
        # Fallback defaults based on description hints
        if 'boolean' in description_lower or 'true/false' in description_lower:
            return False
        elif 'list' in description_lower:
            return []
        elif 'string' in description_lower:
            return ""
        elif 'number' in description_lower or 'integer' in description_lower:
            return 0
        else:
            return None

class TestCaseGenerator:
    """Main class for generating test cases from LLM Python questions"""
    
    def __init__(self, pynguine=None):
        self.pynguine = pynguine or Pynguine()
        self.skip_optional_probability = 0.7  # Probability to skip optional parameters
    
    def generate_test_cases(self, question_info: Dict[str, Any], num_tests: int = 8) -> List[Dict[str, Any]]:
        """Generate test cases for a question"""
        # Convert raw question info to QuestionInfo object
        function_signature = question_info['function_signature']
        problem_statement = question_info['problem_statement']
        
        # Use normalized examples if available
        examples = question_info.get('examples', [])
        normalized_examples = []
        
        for example in examples:
            # Convert examples to standard format
            if isinstance(example, dict) and 'input_text' in example and 'output_text' in example:
                # Parse input and output from text representations
                input_text = example['input_text'].replace("Input:", "").strip()
                output_text = example['output_text'].replace("Output:", "").strip()
                
                try:
                    inputs = eval(input_text)
                    output = eval(output_text)
                    
                    if not isinstance(inputs, dict):
                        # Convert to dict format if needed
                        param_match = re.search(r'def\s+\w+\s*\(\s*([^)]*)\s*\)', function_signature)
                        if param_match:
                            params = [p.strip().split(':')[0].strip() for p in param_match.group(1).split(',') if p.strip()]
                            if len(params) == 1:
                                # Single parameter
                                inputs = {params[0]: inputs}
                            elif isinstance(inputs, (list, tuple)) and len(inputs) <= len(params):
                                # Multiple parameters as tuple/list
                                inputs = {param: val for param, val in zip(params, inputs)}
                    
                    normalized_examples.append({
                        "inputs": inputs,
                        "output": output
                    })
                except (SyntaxError, ValueError, NameError):
                    # Skip examples we can't parse properly
                    logger.warning(f"Failed to parse example: {input_text} -> {output_text}")
                    continue
        
        # Generate tests using Pynguine
        test_cases = self.pynguine.generate_tests(
            function_signature=function_signature,
            description=problem_statement,
            examples=normalized_examples,
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

# Initialize components
question_generator = LLMQuestionGenerator()
test_case_generator = TestCaseGenerator(Pynguine())
chatbot_handler = ChatbotHandler()

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
            request.endpoint not in ['login', 'register', 'index', 'create_room', 'join_room_route']):
            if not request.is_json and request.endpoint.startswith('api/'):
                return jsonify({
                    'success': False,
                    'error': 'Content-Type must be application/json'
                }), 400
        
        if request.content_length and request.content_length > app.config['MAX_CONTENT_LENGTH']:
            return jsonify({
                'success': False,
                'error': 'Request too large'
            }), 413

if __name__ == '__main__':
    try:
        port = int(os.getenv('PORT', 5000))
        debug_mode = os.getenv('FLASK_ENV') == 'development'
        
        # Most compatible method for running with socketio
        socketio.run(app, host='0.0.0.0', port=port, debug=debug_mode)
            
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        sys.exit(1)