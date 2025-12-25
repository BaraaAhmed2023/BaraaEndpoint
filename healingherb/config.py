import os
from datetime import timedelta

class Config:
    # Flask
    SECRET_KEY = 'dev-secret-key-change-in-production'
    
    # Database
    DATABASE_URL = 'sqlite:///healingherb.db'
    
    # JWT
    JWT_SECRET_KEY = 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    
    # AI (Google Gemini)
    GEMINI_API_KEY = "AIzaSyDn4Rrkoa9JyL4-BP7fgjJRlYNaGVwQNf8"
    GEMINI_MODEL = 'gemini-2.5-flash'
    # Rate limiting
    RATE_LIMIT = 10  # requests per window
    RATE_LIMIT_WINDOW = 900  # 15 minutes in seconds
    
    # AI Limits
    AI_MAX_TOKENS = 4096
    AI_MAX_HISTORY = 10
    AI_RATE_LIMIT = 60
    
    # Default AI Model
    DEFAULT_AI_MODEL = 'gemini-2.5-flash'
    
class DevelopmentConfig(Config):
    DEBUG = True
    
class ProductionConfig(Config):
    DEBUG = False
    
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}