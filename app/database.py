# app/database.py
from py2neo import Graph
from flask import current_app, g

def get_db():
    """
    Ouvre une nouvelle connexion à la base de données si aucune n'existe pour le contexte actuel.
    Utilise le contexte d'application Flask 'g' pour stocker la connexion.
    """
    if 'graph' not in g:
        try:
            g.graph = Graph(
                current_app.config['NEO4J_URI'],
                auth=(current_app.config['NEO4J_USER'], current_app.config['NEO4J_PASSWORD'])
            )
            # Vérifie la connexion
            g.graph.run("RETURN 1")
            print("Successfully connected to Neo4j.")
        except Exception as e:
            print(f"Failed to connect to Neo4j: {e}")
            # Vous pourriez vouloir lever une exception ici ou gérer l'erreur autrement
            g.graph = None # Marquer comme non connecté
    return g.graph

def close_db(e=None):
    """
    Ferme la connexion à la base de données si elle existe dans le contexte 'g'.
    Cette fonction est généralement enregistrée pour être appelée à la fin de chaque requête.
    (py2neo gère le pooling, donc fermer explicitement n'est pas toujours nécessaire,
     mais c'est une bonne pratique pour libérer les ressources du contexte 'g').
    """
    graph = g.pop('graph', None)
    # py2neo gère son propre pool de connexions, donc il n'y a pas de méthode close() explicite
    # sur l'objet Graph principal à appeler ici. On retire juste l'objet de 'g'.
    if graph is not None:
        # Optionnel : loguer la "fermeture" du contexte
        # print("Closing Neo4j connection context.")
        pass

def init_app(app):
    """Enregistre les fonctions de gestion de la base de données avec l'application Flask."""
    app.teardown_appcontext(close_db)
