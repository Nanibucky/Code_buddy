import os
import re
import time
import uuid
import logging
import hashlib
import sqlite3
from typing import Dict, Any, Optional, Tuple
from functools import wraps
from datetime import datetime, timedelta

from flask import Flask, request, session, redirect, url_for, render_template, flash, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database initialization
DB_PATH = os.path.join(os.getcwd(), 'database', 'users.db')

def init_db():
    """Initialize the database with required tables"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        is_active BOOLEAN DEFAULT 1
    )
    ''')
    
    # Create stats table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_stats (
        user_id TEXT PRIMARY KEY,
        problems_solved INTEGER DEFAULT 0,
        current_streak INTEGER DEFAULT 0,
        longest_streak INTEGER DEFAULT 0,
        points INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Create user_activity table for tracking login attempts
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        activity_type TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ip_address TEXT,
        user_agent TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    conn.commit()
    conn.close()
    
    logger.info("Database initialized successfully")

# In auth.py, modify get_db function:
def get_db():
    """Get database connection with robust error handling"""
    # Don't rely on Flask's g object, create a fresh connection every time
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        # Create connection with row factory
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {str(e)}")
        raise

# Make sure close_db is properly implemented:
def close_db(e=None):
    """Close database connection with proper error handling"""
    db = g.pop('db', None)
    if db is not None:
        try:
            db.close()
        except sqlite3.Error as e:
            logger.error(f"Error closing database connection: {str(e)}")

class UserAuth:
    """User authentication and management class"""
    
    @staticmethod
    def validate_password(password: str) -> bool:
        """Validate password strength with improved security checks"""
        if not password or len(password) < 8:
            return False
        if not re.search(r"[A-Z]", password):  # At least one uppercase letter
            return False
        if not re.search(r"[a-z]", password):  # At least one lowercase letter
            return False
        if not re.search(r"\d", password):  # At least one number
            return False
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):  # At least one special character
            return False
        return True
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_regex, email))
    
    @staticmethod
    def validate_username(username: str) -> bool:
        """Validate username format (alphanumeric, 3-20 chars)"""
        username_regex = r'^[a-zA-Z0-9_]{3,20}$'
        return bool(re.match(username_regex, username))
    
    @staticmethod
    def register_user(username: str, email: str, password: str) -> Tuple[bool, str]:
        """
        Register a new user
        
        Args:
            username: The desired username
            email: User's email address
            password: User's password
            
        Returns:
            Tuple of (success, message)
        """
        conn = None
        try:
            # Validate inputs
            if not UserAuth.validate_username(username):
                return False, "Username must be 3-20 characters and contain only letters, numbers, and underscores"
                
            if not UserAuth.validate_email(email):
                return False, "Invalid email format"
                
            if not UserAuth.validate_password(password):
                return False, "Password must be at least 8 characters and include uppercase, lowercase, digits, and special characters"
            
            # Create a new direct connection to the database instead of using get_db()
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check if username or email already exists
            cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
            if cursor.fetchone():
                conn.close()
                return False, "Username or email already exists"
            
            # Generate user ID
            user_id = str(uuid.uuid4())
            
            # Hash the password
            password_hash = generate_password_hash(password)
            
            # Insert new user
            cursor.execute(
                "INSERT INTO users (id, username, email, password_hash) VALUES (?, ?, ?, ?)",
                (user_id, username, email, password_hash)
            )
            
            # Initialize user stats
            cursor.execute(
                "INSERT INTO user_stats (user_id) VALUES (?)",
                (user_id,)
            )
            
            # Log registration activity (with safe handling for missing request context)
            try:
                ip_address = request.remote_addr
                user_agent = request.user_agent.string
            except RuntimeError:
                # If outside of request context
                ip_address = "unknown"
                user_agent = "unknown"
                
            cursor.execute(
                "INSERT INTO user_activity (user_id, activity_type, ip_address, user_agent) VALUES (?, ?, ?, ?)",
                (user_id, "registration", ip_address, user_agent)
            )
            
            conn.commit()
            logger.info(f"User registered successfully: {username}")
            conn.close()
            return True, "Registration successful"
                
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                    conn.close()
                except sqlite3.Error:
                    pass
            logger.error(f"Error during user registration: {str(e)}")
            return False, f"Registration failed: {str(e)}"
    
    @staticmethod
    def login_user(username_or_email: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Authenticate a user
        
        Args:
            username_or_email: Username or email
            password: User's password
            
        Returns:
            Tuple of (success, message, user_data)
        """
        conn = None
        try:
            # Create a new connection directly instead of using get_db()
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Find user by username or email
            cursor.execute(
                "SELECT * FROM users WHERE username = ? OR email = ?",
                (username_or_email, username_or_email)
            )
            user = cursor.fetchone()
            
            if not user:
                conn.close()
                return False, "Invalid username or password", None
            
            # Check password
            if not check_password_hash(user['password_hash'], password):
                # Log failed login attempt
                try:
                    ip_address = request.remote_addr
                    user_agent = request.user_agent.string
                except RuntimeError:
                    # If outside of request context
                    ip_address = "unknown"
                    user_agent = "unknown"
                    
                cursor.execute(
                    "INSERT INTO user_activity (user_id, activity_type, ip_address, user_agent) VALUES (?, ?, ?, ?)",
                    (user['id'], "failed_login", ip_address, user_agent)
                )
                conn.commit()
                conn.close()
                return False, "Invalid username or password", None
            
            # Update last login timestamp
            cursor.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user['id'],)
            )
            
            # Get user stats
            cursor.execute("SELECT * FROM user_stats WHERE user_id = ?", (user['id'],))
            stats = cursor.fetchone()
            
            # Log successful login
            try:
                ip_address = request.remote_addr
                user_agent = request.user_agent.string
            except RuntimeError:
                # If outside of request context
                ip_address = "unknown"
                user_agent = "unknown"
                
            cursor.execute(
                "INSERT INTO user_activity (user_id, activity_type, ip_address, user_agent) VALUES (?, ?, ?, ?)",
                (user['id'], "successful_login", ip_address, user_agent)
            )
            
            conn.commit()
            
            # Prepare user data to return
            user_data = {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'created_at': user['created_at'],
                'stats': {
                    'problems_solved': stats['problems_solved'] if stats else 0,
                    'current_streak': stats['current_streak'] if stats else 0,
                    'longest_streak': stats['longest_streak'] if stats else 0,
                    'points': stats['points'] if stats else 0
                }
            }
            
            conn.close()
            logger.info(f"User logged in successfully: {user['username']}")
            return True, "Login successful", user_data
                
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                    conn.close()
                except sqlite3.Error:
                    pass
            logger.error(f"Error during login: {str(e)}")
            return False, f"Login failed: {str(e)}", None
    
    @staticmethod
    def update_user_stats(user_id: str, stats_update: Dict[str, int]) -> bool:
        """
        Update user statistics
        
        Args:
            user_id: The user's ID
            stats_update: Dictionary with stat keys and their increment values
            
        Returns:
            Success status
        """
        try:
            db = get_db()
            cursor = db.cursor()
            
            # Validate user exists
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if not cursor.fetchone():
                logger.warning(f"Attempted to update stats for non-existent user: {user_id}")
                return False
            
            # Get current stats
            cursor.execute("SELECT * FROM user_stats WHERE user_id = ?", (user_id,))
            current_stats = cursor.fetchone()
            
            # Update each stat
            updates = []
            values = []
            
            for stat, increment in stats_update.items():
                if stat in ['problems_solved', 'current_streak', 'longest_streak', 'points']:
                    updates.append(f"{stat} = {stat} + ?")
                    values.append(increment)
            
            if not updates:
                return True  # Nothing to update
            
            # Special handling for longest_streak
            if 'current_streak' in stats_update:
                new_streak = current_stats['current_streak'] + stats_update['current_streak']
                if new_streak > current_stats['longest_streak']:
                    updates.append("longest_streak = ?")
                    values.append(new_streak)
            
            # Execute update
            query = f"UPDATE user_stats SET {', '.join(updates)} WHERE user_id = ?"
            values.append(user_id)
            
            cursor.execute(query, values)
            db.commit()
            
            logger.info(f"Stats updated for user {user_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user stats: {str(e)}")
            return False

# Authentication middleware
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # For API endpoints, return JSON response
            if request.path.startswith('/api/'):
                return jsonify({
                    'success': False,
                    'error': 'Authentication required',
                    'redirect': url_for('login', next=request.url)
                }), 401
            # For regular endpoints, redirect to login page
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Add this function to auth.py

def update_user_profile(user_id: str, username: str = None, email: str = None) -> Tuple[bool, str]:
    """
    Update the user's profile information
    
    Args:
        user_id: The user's ID
        username: New username (optional)
        email: New email (optional)
        
    Returns:
        Tuple of (success, message)
    """
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Validate inputs if provided
        if username and not UserAuth.validate_username(username):
            return False, "Username must be 3-20 characters and contain only letters, numbers, and underscores"
            
        if email and not UserAuth.validate_email(email):
            return False, "Invalid email format"
        
        # Check if username already exists (for someone else)
        if username:
            cursor.execute("SELECT id FROM users WHERE username = ? AND id != ?", (username, user_id))
            if cursor.fetchone():
                return False, "Username already taken by another user"
        
        # Check if email already exists (for someone else)
        if email:
            cursor.execute("SELECT id FROM users WHERE email = ? AND id != ?", (email, user_id))
            if cursor.fetchone():
                return False, "Email already associated with another account"
        
        # Build update query based on what's changing
        update_fields = []
        params = []
        
        if username:
            update_fields.append("username = ?")
            params.append(username)
            
        if email:
            update_fields.append("email = ?")
            params.append(email)
            
        if not update_fields:
            return True, "No changes requested"
            
        # Add user_id to params
        params.append(user_id)
        
        # Execute update
        query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()
        
        logger.info(f"Updated profile for user {user_id}")
        return True, "Profile updated successfully"
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error updating user profile: {str(e)}")
        return False, f"Failed to update profile: {str(e)}"
    finally:
        if conn:
            conn.close()

# Initialize auth routes
def init_auth_routes(app: Flask):
    """
    Initialize authentication routes for the app
    
    Args:
        app: Flask application instance
    """
    # Register end-of-request handler to close DB connection
    app.teardown_appcontext(close_db)
    
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            # Basic form validation
            if not all([username, email, password, confirm_password]):
                flash('All fields are required', 'error')
                return render_template('register.html')
            
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return render_template('register.html')
            
            # Register the user
            success, message = UserAuth.register_user(username, email, password)
            
            if success:
                flash(message, 'success')
                return redirect(url_for('login'))
            else:
                flash(message, 'error')
                return render_template('register.html')
        
        return render_template('register.html')
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username_or_email = request.form.get('username_or_email', '').strip()
            password = request.form.get('password', '')
            remember = request.form.get('remember', False)
            
            # Basic form validation
            if not all([username_or_email, password]):
                flash('All fields are required', 'error')
                return render_template('login.html')
            
            try:
                # Authenticate the user
                success, message, user_data = UserAuth.login_user(username_or_email, password)
                
                if success and user_data:
                    # Set session data
                    session.clear()
                    session['user_id'] = user_data['id']
                    session['username'] = user_data['username']
                    
                    # Handle "remember me" functionality
                    if remember:
                        # Session lasts for 30 days
                        session.permanent = True
                        app.permanent_session_lifetime = timedelta(days=30)
                    else:
                        # Default session timeout (30 minutes in app.py)
                        session.permanent = False
                    
                    # Redirect to next page or home
                    next_page = request.args.get('next')
                    return redirect(next_page or url_for('index'))
                else:
                    flash(message, 'error')
                    return render_template('login.html')
            except Exception as e:
                logger.error(f"Login error: {str(e)}")
                flash(f'Login error occurred. Please try again.', 'error')
                return render_template('login.html')
        
        return render_template('login.html')
    
    @app.route('/logout')
    def logout():
        session.clear()
        flash('You have been logged out', 'info')
        return redirect(url_for('index'))
    
    @app.route('/api/auth-status')
    def auth_status():
        """Return the current user's authentication status and basic info"""
        if 'user_id' in session:
            return jsonify({
                'authenticated': True,
                'username': session.get('username')
            })
        else:
            return jsonify({
                'authenticated': False
            })
    


    # User profile endpoint
    @app.route('/profile')
    @login_required
    def profile():
        # Get user data
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            "SELECT u.*, s.* FROM users u JOIN user_stats s ON u.id = s.user_id WHERE u.id = ?",
            (session['user_id'],)
        )
        user_data = cursor.fetchone()
        
        if not user_data:
            session.clear()  # User doesn't exist anymore, clear session
            flash('User not found. Please login again.', 'error')
            return redirect(url_for('login'))
        
        # Get recent activity
        cursor.execute(
            "SELECT activity_type, timestamp FROM user_activity WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10",
            (session['user_id'],)
        )
        activities = cursor.fetchall()
        
        return render_template('profile.html', user=user_data, activities=activities)
    
    logger.info("Auth routes initialized")

# Initialize everything
def init_auth(app: Flask):
    """Initialize all authentication components"""
    # Make sure the DB is set up
    init_db()
    
    # Setup routes
    init_auth_routes(app)
    
    logger.info("Authentication system initialized")