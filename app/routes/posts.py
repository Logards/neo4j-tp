# app/routes/posts.py
import uuid
from flask import Blueprint, request, jsonify
from app.database import get_db
import datetime
# Importer le helper depuis users.py ou le définir ici aussi
# from .users import user_node_to_dict (si user_node_to_dict est global)

posts_bp = Blueprint('posts', __name__) # Pas de préfixe global

# Helper function to convert Post node to dictionary
def post_node_to_dict(node):
    created_at = node.get("created_at")
    # Convertir DateTime de Neo4j en chaîne ISO format si nécessaire
    if created_at and not isinstance(created_at, str):
        created_at = created_at.isoformat()

    return {
        "id": node.get("id"),
        "title": node.get("title"),
        "content": node.get("content"),
        "created_at": created_at
    }

# Helper function to get user ID from request body (pour LIKES)
def get_user_id_from_request():
    data = request.get_json()
    if not data or 'user_id' not in data:
        return None
    return data['user_id']


@posts_bp.route('/posts', methods=['GET'])
def get_posts():
    """Récupère tous les posts."""
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    # Récupérer les posts et optionnellement leur auteur
    query = """
    MATCH (p:Post)<-[:CREATED]-(u:User)
    RETURN p, u.id as author_id, u.name as author_name
    ORDER BY p.created_at DESC
    """
    try:
        results = graph.run(query).data()
        posts = []
        for record in results:
            post_data = post_node_to_dict(record['p'])
            post_data['author'] = {'id': record['author_id'], 'name': record['author_name']}
            posts.append(post_data)
        return jsonify(posts), 200
    except Exception as e:
        print(f"Error fetching posts: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@posts_bp.route('/posts/<string:post_id>', methods=['GET'])
def get_post_by_id(post_id):
    """Récupère un post par son ID."""
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    query = """
    MATCH (p:Post {id: $id})<-[:CREATED]-(u:User)
    RETURN p, u.id as author_id, u.name as author_name
    """
    try:
        result = graph.run(query, id=post_id).data()
        if result:
            record = result[0]
            post_data = post_node_to_dict(record['p'])
            post_data['author'] = {'id': record['author_id'], 'name': record['author_name']}
            # On pourrait aussi compter les likes et commentaires ici
            return jsonify(post_data), 200
        else:
            return jsonify({"error": "Post not found"}), 404
    except Exception as e:
        print(f"Error fetching post {post_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@posts_bp.route('/users/<string:user_id>/posts', methods=['GET'])
def get_user_posts(user_id):
    """Récupère les posts créés par un utilisateur spécifique."""
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    # Vérifier si l'utilisateur existe
    user_check = graph.evaluate("MATCH (u:User {id: $id}) RETURN count(u) > 0", id=user_id)
    if not user_check:
        return jsonify({"error": f"User with id {user_id} not found"}), 404

    query = """
    MATCH (u:User {id: $user_id})-[:CREATED]->(p:Post)
    RETURN p
    ORDER BY p.created_at DESC
    """
    try:
        results = graph.run(query, user_id=user_id).data()
        posts = [post_node_to_dict(record['p']) for record in results]
        return jsonify(posts), 200
    except Exception as e:
        print(f"Error fetching posts for user {user_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@posts_bp.route('/users/<string:user_id>/posts', methods=['POST'])
def create_post_for_user(user_id):
    """Crée un nouveau post pour un utilisateur."""
    data = request.get_json()
    if not data or 'title' not in data or 'content' not in data:
        return jsonify({"error": "Missing title or content in request body"}), 400

    title = data['title']
    content = data['content']
    post_id = str(uuid.uuid4())
    created_at = datetime.datetime.utcnow().isoformat() + "Z"

    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    # Vérifier si l'utilisateur existe avant de créer le post
    user_check = graph.evaluate("MATCH (u:User {id: $id}) RETURN count(u) > 0", id=user_id)
    if not user_check:
        return jsonify({"error": f"User with id {user_id} not found, cannot create post"}), 404

    query = """
    MATCH (u:User {id: $user_id})
    CREATE (p:Post {
        id: $post_id,
        title: $title,
        content: $content,
        created_at: datetime($created_at)
    })
    CREATE (u)-[:CREATED]->(p)
    RETURN p
    """
    try:
        result = graph.run(query, user_id=user_id, post_id=post_id, title=title, content=content, created_at=created_at).data()
        if result:
            post_node = result[0]['p']
            return jsonify(post_node_to_dict(post_node)), 201
        else:
            # Ne devrait pas arriver si le MATCH user réussit
            return jsonify({"error": "Failed to create post"}), 500
    except Exception as e:
        print(f"Error creating post for user {user_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@posts_bp.route('/posts/<string:post_id>', methods=['PUT'])
def update_post(post_id):
    """Met à jour un post par son ID."""
    data = request.get_json()
    if not data or ('title' not in data and 'content' not in data):
        return jsonify({"error": "Missing title or content in request body"}), 400

    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    set_clauses = []
    params = {'id': post_id}
    if 'title' in data:
        set_clauses.append("p.title = $title")
        params['title'] = data['title']
    if 'content' in data:
        set_clauses.append("p.content = $content")
        params['content'] = data['content']

    query = f"""
    MATCH (p:Post {{id: $id}})
    SET {', '.join(set_clauses)}
    RETURN p
    """
    try:
        result = graph.run(query, params).data()
        if result:
            post_node = result[0]['p']
            return jsonify(post_node_to_dict(post_node)), 200
        else:
            return jsonify({"error": "Post not found"}), 404
    except Exception as e:
        print(f"Error updating post {post_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@posts_bp.route('/posts/<string:post_id>', methods=['DELETE'])
def delete_post(post_id):
    """Supprime un post par son ID."""
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    # Vérifier si le post existe
    check_query = "MATCH (p:Post {id: $id}) RETURN count(p) as count"
    count_result = graph.run(check_query, id=post_id).data()
    if count_result[0]['count'] == 0:
        return jsonify({"error": "Post not found"}), 404

    # Supprimer le post et ses relations (CREATED, LIKES, HAS_COMMENT)
    # Aussi supprimer les commentaires liés et leurs relations LIKES
    query = """
    MATCH (p:Post {id: $id})
    // Optionnel : trouver et supprimer les commentaires liés et leurs likes
    OPTIONAL MATCH (p)-[:HAS_COMMENT]->(c:Comment)
    OPTIONAL MATCH (c)<-[cl:LIKES]-(:User)
    DETACH DELETE c, cl
    // Supprimer le post et ses propres relations (CREATED, LIKES)
    DETACH DELETE p
    """
    try:
        graph.run(query, id=post_id)
        return jsonify({"message": "Post and associated comments deleted successfully"}), 200
    except Exception as e:
        print(f"Error deleting post {post_id}: {e}")
        return jsonify({"error": "An unexpected error occurred while deleting post"}), 500

# --- Routes pour les Likes sur les Posts ---

@posts_bp.route('/posts/<string:post_id>/like', methods=['POST'])
def like_post(post_id):
    """Ajoute un like à un post."""
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "Missing 'user_id' in request body"}), 400

    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    query = """
    MATCH (u:User {id: $user_id})
    MATCH (p:Post {id: $post_id})
    // MERGE évite de créer un doublon de la relation LIKES
    MERGE (u)-[r:LIKES]->(p)
    RETURN count(r) > 0 as liked // Pour savoir si MERGE a créé ou trouvé
    """
    try:
        result = graph.run(query, user_id=user_id, post_id=post_id).data()
        if result: # Si les MATCH ont réussi
             # liked = result[0]['liked'] # Indique si la relation existait déjà ou vient d'être créée
            return jsonify({"message": f"User {user_id} liked post {post_id}"}), 201 # Ou 200 si existait déjà
        else:
             # Vérifier quelle entité manque
            check_u = graph.evaluate("MATCH (n:User {id: $id}) RETURN count(n)>0", id=user_id)
            check_p = graph.evaluate("MATCH (n:Post {id: $id}) RETURN count(n)>0", id=post_id)
            if not check_u: return jsonify({"error": f"User {user_id} not found"}), 404
            if not check_p: return jsonify({"error": f"Post {post_id} not found"}), 404
            return jsonify({"error": "Failed to like post"}), 500 # Autre erreur
    except Exception as e:
        print(f"Error liking post {post_id} by user {user_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@posts_bp.route('/posts/<string:post_id>/like', methods=['DELETE'])
def unlike_post(post_id):
    """Retire un like d'un post."""
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "Missing 'user_id' in request body"}), 400

    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    query = """
    MATCH (u:User {id: $user_id})-[r:LIKES]->(p:Post {id: $post_id})
    DELETE r
    RETURN count(r) as deleted_count // Pour vérifier
    """
    try:
        result = graph.run(query, user_id=user_id, post_id=post_id).data()
        if result and result[0]['deleted_count'] > 0:
            return jsonify({"message": f"User {user_id} unliked post {post_id}"}), 200
        else:
            # Vérifier si les entités existent mais la relation n'existe pas
            check_query = """
            MATCH (u:User {id: $user_id}), (p:Post {id: $post_id})
            RETURN exists((u)-[:LIKES]->(p)) as liked
            """
            check_result = graph.run(check_query, user_id=user_id, post_id=post_id).data()
            if not check_result:
                return jsonify({"error": "User or Post not found"}), 404
            elif not check_result[0]['liked']:
                return jsonify({"error": "Like relationship does not exist"}), 404
            else:
                return jsonify({"error": "Failed to unlike post"}), 500
    except Exception as e:
        print(f"Error unliking post {post_id} by user {user_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500