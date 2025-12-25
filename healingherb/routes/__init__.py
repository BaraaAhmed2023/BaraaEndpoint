# This file makes the routes directory a Python package
# Export all route blueprints for easy import

from .auth import auth_bp
from .appointments import appointments_bp
from .daily_stats import daily_stats_bp
from .herbs import herbs_bp
from .medical_tests import medical_tests_bp
from .questions import questions_bp
from .recipes import recipes_bp
from .recipe_ratings import recipe_ratings_bp
from .reports import reports_bp
from .ai import ai_bp

__all__ = [
    'auth_bp',
    'appointments_bp',
    'daily_stats_bp',
    'herbs_bp',
    'medical_tests_bp',
    'questions_bp',
    'recipes_bp',
    'recipe_ratings_bp',
    'reports_bp',
    'ai_bp'
]