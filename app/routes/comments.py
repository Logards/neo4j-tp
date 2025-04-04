# app/routes/comments.py
import uuid
from flask import Blueprint, request, jsonify
from app.database import get_db
import datetime
# Importer les helpers si besoin
# from .users import user_node_to_dict
# from .posts import get_user_id_from_request

comments_bp = Blueprint('comments', __name__) # Pas de préfixe global

# Helper function to convert Comment node to dictionary
def comment_node_to_dict(node):
    created_at = node.get("created_at")
    # Convertir DateTime de Neo4j en chaîne ISO format si nécessaire
    if created_at and not isinstance(created_at, str):
        created_at = created_at.isoformat()

    return {
        "id": node.get("id"),
        "content": node.get("content"),
        "created_at": created_at
    }

# Helper function to get user ID from request body (pour LIKES et création)
def get_user_id_from_request():
    data = request.get_json()
    if not data or 'user_id' not in data:
        return None
    return data['user_id']


@comments_bp.route('/posts/<string:post_id>/comments', methods=['GET'])
def get_post_comments(post_id):
    """Récupère les commentaires d'un post."""
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    # Vérifier si le post existe
    post_check = graph.evaluate("MATCH (p:Post {id: $id}) RETURN count(p) > 0", id=post_id)
    if not post_check:
        return jsonify({"error": f"Post with id {post_id} not found"}), 404

    query = """
    MATCH (p:Post {id: $post_id})-[:HAS_COMMENT]->(c:Comment)<-[:CREATED]-(u:User)
    RETURN c, u.id as author_id, u.name as author_name
    ORDER BY c.created_at ASC // Afficher les commentaires du plus ancien au plus récent
    """
    try:
        results = graph.run(query, post_id=post_id).data()
        comments = []
        for record in results:
            comment_data = comment_node_to_dict(record['c'])
            comment_data['author'] = {'id': record['author_id'], 'name': record['author_name']}
            comments.append(comment_data)
        return jsonify(comments), 200
    except Exception as e:
        print(f"Error fetching comments for post {post_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@comments_bp.route('/posts/<string:post_id>/comments', methods=['POST'])
def add_comment_to_post(post_id):
    """Ajoute un commentaire à un post."""
    data = request.get_json()
    user_id = get_user_id_from_request()

    if not user_id:
        return jsonify({"error": "Missing 'user_id' in request body"}), 400
    if not data or 'content' not in data:
        return jsonify({"error": "Missing 'content' in request body"}), 400

    content = data['content']
    comment_id = str(uuid.uuid4())
    created_at = datetime.datetime.utcnow().isoformat() + "Z"

    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    # Vérifier existence User et Post
    check_u = graph.evaluate("MATCH (n:User {id: $id}) RETURN count(n)>0", id=user_id)
    check_p = graph.evaluate("MATCH (n:Post {id: $id}) RETURN count(n)>0", id=post_id)
    if not check_u: return jsonify({"error": f"User {user_id} not found"}), 404
    if not check_p: return jsonify({"error": f"Post {post_id} not found"}), 404

    query = """
    MATCH (u:User {id: $user_id})
    MATCH (p:Post {id: $post_id})
    CREATE (c:Comment {
        id: $comment_id,
        content: $content,
        created_at: datetime($created_at)
    })
    CREATE (u)-[:CREATED]->(c)
    CREATE (p)-[:HAS_COMMENT]->(c)
    RETURN c
    """
    try:
        result = graph.run(query, user_id=user_id, post_id=post_id, comment_id=comment_id, content=content, created_at=created_at).data()
        if result:
            comment_node = result[0]['c']
            # Récupérer l'auteur pour la réponse
            author_info = graph.run("MATCH (u:User {id:$uid}) RETURN u.id as id, u.name as name", uid=user_id).data()[0]
            comment_data = comment_node_to_dict(comment_node)
            comment_data['author'] = author_info
            return jsonify(comment_data), 201
        else:
            return jsonify({"error": "Failed to create comment"}), 500
    except Exception as e:
        print(f"Error creating comment for post {post_id} by user {user_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@comments_bp.route('/posts/<string:post_id>/comments/<string:comment_id>', methods=['DELETE'])
def delete_comment_from_post(post_id, comment_id):
    """Supprime un commentaire spécifique d'un post."""
    # Note: Cette route est un peu redondante avec DELETE /comments/<id>
    # mais on la garde car elle est spécifiée.
    # On pourrait vérifier que le commentaire appartient bien au post_id si nécessaire.
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    # Vérifier si le commentaire existe et est lié au post
    check_query = """
    MATCH (p:Post {id: $post_id})-[:HAS_COMMENT]->(c:Comment {id: $comment_id})
    RETURN count(c) as count
    """
    count_result = graph.run(check_query, post_id=post_id, comment_id=comment_id).data()
    if count_result[0]['count'] == 0:
        return jsonify({"error": "Comment not found or not associated with this post"}), 404

    # Supprimer le commentaire et ses relations LIKES
    query = """
    MATCH (c:Comment {id: $comment_id})
    DETACH DELETE c
    """
    try:
        graph.run(query, comment_id=comment_id)
        return jsonify({"message": "Comment deleted successfully"}), 200
    except Exception as e:
        print(f"Error deleting comment {comment_id}: {e}")
        return jsonify({"error": "An unexpected error occurred while deleting comment"}), 500

@comments_bp.route('/comments', methods=['GET'])
def get_all_comments():
    """Récupère tous les commentaires."""
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    query = """
    MATCH (c:Comment)<-[:CREATED]-(u:User)
    MATCH (p:Post)-[:HAS_COMMENT]->(c) // Trouver le post associé
    RETURN c, u.id as author_id, u.name as author_name, p.id as post_id
    ORDER BY c.created_at DESC
    """
    try:
        results = graph.run(query).data()
        comments = []
        for record in results:
            comment_data = comment_node_to_dict(record['c'])
            comment_data['author'] = {'id': record['author_id'], 'name': record['author_name']}
            comment_data['post_id'] = record['post_id']
            comments.append(comment_data)
        return jsonify(comments), 200
    except Exception as e:
        print(f"Error fetching all comments: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@comments_bp.route('/comments/<string:comment_id>', methods=['GET'])
def get_comment_by_id(comment_id):
    """Récupère un commentaire par son ID."""
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    query = """
    MATCH (c:Comment {id: $id})<-[:CREATED]-(u:User)
    MATCH (p:Post)-[:HAS_COMMENT]->(c)
    RETURN c, u.id as author_id, u.name as author_name, p.id as post_id
    """
    try:
        result = graph.run(query, id=comment_id).data()
        if result:
            record = result[0]
            comment_data = comment_node_to_dict(record['c'])
            comment_data['author'] = {'id': record['author_id'], 'name': record['author_name']}
            comment_data['post_id'] = record['post_id']
            return jsonify(comment_data), 200
        else:
            return jsonify({"error": "Comment not found"}), 404
    except Exception as e:
        print(f"Error fetching comment {comment_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@comments_bp.route('/comments/<string:comment_id>', methods=['PUT'])
def update_comment(comment_id):
    """Met à jour un commentaire par son ID."""
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({"error": "Missing 'content' in request body"}), 400

    content = data['content']
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    query = """
    MATCH (c:Comment {id: $id})
    SET c.content = $content
    RETURN c
    """
    try:
        result = graph.run(query, id=comment_id, content=content).data()
        if result:
            comment_node = result[0]['c']
            return jsonify(comment_node_to_dict(comment_node)), 200
        else:
            return jsonify({"error": "Comment not found"}), 404
    except Exception as e:
        print(f"Error updating comment {comment_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@comments_bp.route('/comments/<string:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    """Supprime un commentaire par son ID."""
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    # Vérifier si le commentaire existe
    check_query = "MATCH (c:Comment {id: $id}) RETURN count(c) as count"
    count_result = graph.run(check_query, id=comment_id).data()
    if count_result[0]['count'] == 0:
        return jsonify({"error": "Comment not found"}), 404

    # Supprimer le commentaire et ses relations (CREATED, HAS_COMMENT, LIKES)
    query = """
    MATCH (c:Comment {id: $id})
    DETACH DELETE c
    """
    try:
        graph.run(query, id=comment_id)
        return jsonify({"message": "Comment deleted successfully"}), 200
    except Exception as e:
        print(f"Error deleting comment {comment_id}: {e}")
        return jsonify({"error": "An unexpected error occurred while deleting comment"}), 500


# --- Routes pour les Likes sur les Commentaires ---

@comments_bp.route('/comments/<string:comment_id>/like', methods=['POST'])
def like_comment(comment_id):
    """Ajoute un like à un commentaire."""
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "Missing 'user_id' in request body"}), 400

    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    query = """
    MATCH (u:User {id: $user_id})
    MATCH (c:Comment {id: $comment_id})
    MERGE (u)-[r:LIKES]->(c)
    RETURN count(r) > 0 as liked
    """
    try:
        result = graph.run(query, user_id=user_id, comment_id=comment_id).data()
        if result:
            return jsonify({"message": f"User {user_id} liked comment {comment_id}"}), 201
        else:
            check_u = graph.evaluate("MATCH (n:User {id: $id}) RETURN count(n)>0", id=user_id)
            check_c = graph.evaluate("MATCH (n:Comment {id: $id}) RETURN count(n)>0", id=comment_id)
            if not check_u: return jsonify({"error": f"User {user_id} not found"}), 404
            if not check_c: return jsonify({"error": f"Comment {comment_id} not found"}), 404
            return jsonify({"error": "Failed to like comment"}), 500
    except Exception as e:
        print(f"Error liking comment {comment_id} by user {user_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@comments_bp.route('/comments/<string:comment_id>/like', methods=['DELETE'])
def unlike_comment(comment_id):
    """Retire un like d'un commentaire."""
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "Missing 'user_id' in request body"}), 400

    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    query = """
    MATCH (u:User {id: $user_id})-[r:LIKES]->(c:Comment {id: $comment_id})
    DELETE r
    RETURN count(r) as deleted_count
    """
    try:
        result = graph.run(query, user_id=user_id, comment_id=comment_id).data()
        if result and result[0]['deleted_count'] > 0:
            return jsonify({"message": f"User {user_id} unliked comment {comment_id}"}), 200
        else:
            check_query = """
            MATCH (u:User {id: $user_id}), (c:Comment {id: $comment_id})
            RETURN exists((u)-[:LIKES]->(c)) as liked
            """
            check_result = graph.run(check_query, user_id=user_id, comment_id=comment_id).data()
            if not check_result:
                return jsonify({"error": "User or Comment not found"}), 404
            elif not check_result[0]['liked']:
                return jsonify({"error": "Like relationship does not exist"}), 404
            else:
                return jsonify({"error": "Failed to unlike comment"}), 500
    except Exception as e:
        print(f"Error unliking comment {comment_id} by user {user_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500