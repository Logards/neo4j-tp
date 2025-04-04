# app/__init__.py
from flask import Flask
from .config import Config
from . import database

def create_app(config_class=Config):
    """Factory pour créer et configurer l'application Flask."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialiser les extensions (ex: connexion DB)
    database.init_app(app)

    # Importer et enregistrer les Blueprints
    from .routes import users, posts, comments # Assurez-vous que les variables de blueprint sont bien nommées dans les fichiers .py

    app.register_blueprint(users.users_bp)
    app.register_blueprint(posts.posts_bp)
    app.register_blueprint(comments.comments_bp)

    # Route simple pour vérifier que l'app fonctionne
    @app.route('/hello')
    def hello():
        return 'Hello, World!'

    return app