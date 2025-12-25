import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
from flask import current_app

def get_db():
    """Get database connection based on configuration"""
    db_url = current_app.config['DATABASE_URL']
    
    if db_url.startswith('postgresql://'):
        # PostgreSQL connection
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        conn.autocommit = True
        return conn
    else:
        # SQLite connection
        conn = sqlite3.connect(db_url)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    """Initialize database tables"""
    db = get_db()
    cursor = db.cursor()
    
    # Users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        age INTEGER,
        height REAL,
        weight REAL,
        gender TEXT,
        diseases TEXT,
        allergies TEXT,
        medications TEXT,
        is_email_verified BOOLEAN DEFAULT FALSE,
        email_verification_token TEXT,
        reset_password_token TEXT,
        reset_token_expiry TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Appointments table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS appointments (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        appointments_to TEXT,
        date DATE NOT NULL,
        time TIME NOT NULL,
        location TEXT NOT NULL,
        appointment_type TEXT DEFAULT 'regular',
        notes_or_details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    ''')
    
    # Daily stats table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS daily_stats (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        date DATE NOT NULL,
        sugar_level REAL NOT NULL,
        blood_pressure_systolic INTEGER NOT NULL,
        blood_pressure_diastolic INTEGER NOT NULL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        UNIQUE(user_id, date)
    )
    ''')
    
    # Herbs table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS herbs (
        id TEXT PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        description TEXT NOT NULL,
        uses TEXT NOT NULL,
        benefits TEXT,
        harms TEXT,
        image_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Herb stories table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS herb_stories (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        herb_id TEXT NOT NULL,
        short_description TEXT NOT NULL,
        story TEXT NOT NULL,
        image_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (herb_id) REFERENCES herbs (id) ON DELETE CASCADE
    )
    ''')
    
    # Medical tests table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS medical_tests (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        date DATE NOT NULL,
        time TIME,
        title TEXT NOT NULL,
        subtitle TEXT,
        result TEXT NOT NULL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    ''')
    
    # Questions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id TEXT PRIMARY KEY,
        author_id TEXT NOT NULL,
        title TEXT NOT NULL,
        body TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (author_id) REFERENCES users (id) ON DELETE CASCADE
    )
    ''')
    
    # Answers table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS answers (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL,
        author_id TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (question_id) REFERENCES questions (id) ON DELETE CASCADE,
        FOREIGN KEY (author_id) REFERENCES users (id) ON DELETE CASCADE
    )
    ''')
    
    # Recipes table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS recipes (
        id TEXT PRIMARY KEY,
        author_id TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        ingredients TEXT,
        instructions TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (author_id) REFERENCES users (id) ON DELETE CASCADE
    )
    ''')
    
    # Recipe ratings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS recipe_ratings (
        id TEXT PRIMARY KEY,
        recipe_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        rating INTEGER NOT NULL CHECK (rating >= 0 AND rating <= 5),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(recipe_id, user_id),
        FOREIGN KEY (recipe_id) REFERENCES recipes (id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    ''')
    
    # AI chat messages table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ai_chat_messages (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        message TEXT NOT NULL,
        response TEXT NOT NULL,
        model TEXT NOT NULL,
        tokens_used INTEGER DEFAULT 0,
        is_user BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    ''')
    
    # AI feedback table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ai_feedback (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        message_id TEXT NOT NULL,
        rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
        feedback TEXT,
        helpful BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (message_id) REFERENCES ai_chat_messages (id) ON DELETE CASCADE
    )
    ''')
    
    # Refresh tokens table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS refresh_tokens (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        token_hash TEXT NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    ''')
    
    db.commit()
    cursor.close()
    db.close()