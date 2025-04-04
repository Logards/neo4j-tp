# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Classe de configuration de base."""
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24))

    NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', 'password')
