# app/routes/users.py
import uuid
from flask import Blueprint, request, jsonify
from app.database import get_db
# Remplacer ConstraintError par une exception plus générale et/ou vérifier le code d'erreur
from py2neo.errors import ClientError # Erreur probable pour les violations de contrainte
from datetime import datetime

users_bp = Blueprint('users', __name__, url_prefix='/users')

# Helper function to convert Node object to dictionary
def user_node_to_dict(node):
    # Utiliser .get() pour éviter les erreurs si une propriété manque (peu probable ici)
    return {
        "id": node.get("id"),
        "name": node.get("name"),
        "email": node.get("email"),
        # Convertir le datetime Neo4j en string ISO si ce n'est pas déjà fait
        "created_at": datetime.now().timestamp(),
    }

@users_bp.route('', methods=['POST'])
def create_user():
    """Crée un nouvel utilisateur."""
    data = request.get_json()
    if not data or not 'name' in data or not 'email' in data:
        return jsonify({"error": "Missing name or email in request body"}), 400

    name = data['name']
    email = data['email']
    user_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat() + "Z" # ISO 8601 format

    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    # Assurez-vous d'avoir créé la contrainte dans Neo4j !
    # Exemple: CREATE CONSTRAINT unique_user_email IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE

    query = """
    CREATE (u:User {
        id: $id,
        name: $name,
        email: $email,
        created_at: datetime($created_at) // Stocker comme type datetime Neo4j
    })
    RETURN u
    """
    try:
        result = graph.run(query, id=user_id, name=name, email=email, created_at=created_at).data()
        if result:
            user_node = result[0]['u']
            return jsonify(user_node_to_dict(user_node)), 201
        else:
            # Ne devrait pas arriver si la query est correcte et la DB fonctionne
            return jsonify({"error": "Failed to create user, no result returned"}), 500
    except ClientError as e:
         # Vérifier si l'erreur est une violation de contrainte
         error_code = getattr(e, 'code', '') # Obtenir le code d'erreur Neo4j
         error_message = str(e).lower()

         is_constraint_violation = False
         if "Neo.ClientError.Schema.ConstraintValidationFailed" in error_code:
             is_constraint_violation = True
         # Fallback: vérifier le message si le code n'est pas standardisé/disponible
         elif "constraint" in error_message and ("unique" in error_message or "violation" in error_message):
              is_constraint_violation = True

         if is_constraint_violation:
             # Essayer d'être spécifique sur la contrainte violée
             if "email" in error_message: # Le message d'erreur mentionne souvent la propriété
                 return jsonify({"error": f"Email '{email}' already exists."}), 409 # 409 Conflict
             else:
                 # Contrainte générique (ex: sur l'ID si on l'avait rendue unique)
                 return jsonify({"error": f"A unique constraint was violated."}), 409
         else:
             # Autre type d'erreur client Neo4j
             print(f"ClientError creating user: {e.code} - {e}")
             return jsonify({"error": "A database client error occurred"}), 500
    except Exception as e: # Attraper toute autre exception (connexion, etc.)
        print(f"Unexpected error creating user: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500


@users_bp.route('/<string:user_id>', methods=['PUT'])
def update_user(user_id):
    """Met à jour un utilisateur par son ID."""
    data = request.get_json()
    if not data or ('name' not in data and 'email' not in data):
        return jsonify({"error": "Missing name or email in request body to update"}), 400

    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500

    set_clauses = []
    params = {'id': user_id}
    if 'name' in data:
        set_clauses.append("u.name = $name")
        params['name'] = data['name']
    if 'email' in data:
        set_clauses.append("u.email = $email")
        params['email'] = data['email']

    if not set_clauses: # Si le JSON est vide après filtrage
        return jsonify({"error": "No valid fields provided for update"}), 400

    query = f"""
    MATCH (u:User {{id: $id}})
    SET {', '.join(set_clauses)}
    RETURN u
    """
    try:
        result = graph.run(query, params).data()
        if result:
            user_node = result[0]['u']
            return jsonify(user_node_to_dict(user_node)), 200
        else:
            # Le MATCH a échoué, l'utilisateur n'existe pas
            return jsonify({"error": "User not found"}), 404
    except ClientError as e: # Gestion similaire à create_user
         error_code = getattr(e, 'code', '')
         error_message = str(e).lower()
         is_constraint_violation = False
         if "Neo.ClientError.Schema.ConstraintValidationFailed" in error_code:
             is_constraint_violation = True
         elif "constraint" in error_message and ("unique" in error_message or "violation" in error_message):
              is_constraint_violation = True

         if is_constraint_violation:
             if "email" in error_message:
                 return jsonify({"error": f"Email '{data.get('email')}' already exists for another user."}), 409
             else:
                 return jsonify({"error": f"A unique constraint was violated during update."}), 409
         else:
             print(f"ClientError updating user {user_id}: {e.code} - {e}")
             return jsonify({"error": "A database client error occurred"}), 500
    except Exception as e:
        print(f"Unexpected error updating user {user_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# --- Les autres routes (GET, DELETE, Friends) restent inchangées ---
# GET /users (inchangé)
@users_bp.route('', methods=['GET'])
def get_users():
    """Récupère la liste de tous les utilisateurs."""
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500
    query = "MATCH (u:User) RETURN u ORDER BY u.name"
    try:
        results = graph.run(query).data()
        users = [user_node_to_dict(record['u']) for record in results]
        return jsonify(users), 200
    except Exception as e:
        print(f"Error fetching users: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# GET /users/<id> (inchangé)
@users_bp.route('/<string:user_id>', methods=['GET'])
def get_user_by_id(user_id):
    """Récupère un utilisateur par son ID."""
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500
    query = "MATCH (u:User {id: $id}) RETURN u"
    try:
        result = graph.run(query, id=user_id).data()
        if result:
            user_node = result[0]['u']
            return jsonify(user_node_to_dict(user_node)), 200
        else:
            return jsonify({"error": "User not found"}), 404
    except Exception as e:
        print(f"Error fetching user {user_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# DELETE /users/<id> (inchangé)
@users_bp.route('/<string:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Supprime un utilisateur par son ID."""
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500
    check_query = "MATCH (u:User {id: $id}) RETURN count(u) as count"
    count_result = graph.run(check_query, id=user_id).data()
    if count_result[0]['count'] == 0:
        return jsonify({"error": "User not found"}), 404
    query = "MATCH (u:User {id: $id}) DETACH DELETE u"
    try:
        graph.run(query, id=user_id)
        return jsonify({"message": "User deleted successfully"}), 200
    except Exception as e:
        print(f"Error deleting user {user_id}: {e}")
        return jsonify({"error": "An unexpected error occurred while deleting user"}), 500

# GET /users/<id>/friends (inchangé)
@users_bp.route('/<string:user_id>/friends', methods=['GET'])
def get_user_friends(user_id):
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500
    query = """
    MATCH (u:User {id: $id})-[:FRIENDS_WITH]->(friend:User)
    RETURN friend
    """
    try:
        results = graph.run(query, id=user_id).data()
        friends = [user_node_to_dict(record['friend']) for record in results]
        return jsonify(friends), 200
    except Exception as e:
        print(f"Error fetching friends for user {user_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# POST /users/<id>/friends (inchangé)
@users_bp.route('/<string:user_id>/friends', methods=['POST'])
def add_friend(user_id):
    data = request.get_json()
    if not data or 'friend_id' not in data:
        return jsonify({"error": "Missing friend_id in request body"}), 400
    friend_id = data['friend_id']
    if user_id == friend_id:
        return jsonify({"error": "User cannot be friends with themselves"}), 400
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500
    query = """
    MATCH (u1:User {id: $user_id})
    MATCH (u2:User {id: $friend_id})
    MERGE (u1)-[r1:FRIENDS_WITH]->(u2)
    MERGE (u2)-[r2:FRIENDS_WITH]->(u1)
    RETURN count(u1) > 0 as u1_found, count(u2) > 0 as u2_found
    """
    try:
        result = graph.run(query, user_id=user_id, friend_id=friend_id).data()
        if result and result[0]['u1_found'] and result[0]['u2_found']:
             return jsonify({"message": f"User {user_id} and {friend_id} are now friends (or already were)"}), 201 # Ou 200
        else:
            # Vérifier quel utilisateur manque si MERGE n'a rien retourné ou si les flags sont false
            check_u1 = graph.evaluate("MATCH (u:User {id: $id}) RETURN count(u) > 0", id=user_id)
            check_u2 = graph.evaluate("MATCH (u:User {id: $id}) RETURN count(u) > 0", id=friend_id)
            if not check_u1: return jsonify({"error": f"User with id {user_id} not found"}), 404
            if not check_u2: return jsonify({"error": f"User with id {friend_id} not found"}), 404
            return jsonify({"error": "Failed to add friend relationship"}), 500 # Autre erreur
    except Exception as e:
        print(f"Error adding friend for user {user_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# DELETE /users/<id>/friends/<friend_id> (inchangé)
@users_bp.route('/<string:user_id>/friends/<string:friend_id>', methods=['DELETE'])
def remove_friend(user_id, friend_id):
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500
    query = """
    MATCH (u1:User {id: $user_id})-[r1:FRIENDS_WITH]->(u2:User {id: $friend_id})
    MATCH (u2)-[r2:FRIENDS_WITH]->(u1) // S'assurer que u2 existe aussi
    DELETE r1, r2
    RETURN count(u1) // Simple check que u1 a été trouvé
    """
    try:
        result = graph.run(query, user_id=user_id, friend_id=friend_id).data()
        if result : # Si la requête s'exécute et supprime (ou tente de supprimer)
            # Il faut vérifier si la relation existait vraiment
             check_query = "RETURN exists( (:User {id:$user_id})-[:FRIENDS_WITH]-(:User {id:$friend_id}) )"
             was_friend = graph.evaluate(check_query, user_id=user_id, friend_id=friend_id)
             # Si le résultat de DELETE est non vide, la suppression a eu lieu ou aurait eu lieu
             # Si was_friend était true avant, c'est un succès 200
             # Si was_friend était false, on peut retourner un message indiquant qu'ils n'étaient pas amis (ou 404)
             # Le plus simple est de retourner 200 si la requête DELETE ne lève pas d'erreur et que les noeuds existent.
             # Si la relation n'existait pas, DELETE ne fait rien mais ne lève pas d'erreur si les noeuds sont trouvés.

             # Vérifions l'existence des noeuds au cas où MATCH échouerait silencieusement
             check_u1 = graph.evaluate("MATCH (u:User {id: $id}) RETURN count(u) > 0", id=user_id)
             check_u2 = graph.evaluate("MATCH (u:User {id: $id}) RETURN count(u) > 0", id=friend_id)
             if not check_u1 or not check_u2:
                 return jsonify({"error": "One or both users not found"}), 404

             return jsonify({"message": f"Friendship between {user_id} and {friend_id} removed (if existed)"}), 200

        else: # Si le MATCH initial échoue (un des users n'existe pas)
             return jsonify({"error": "One or both users not found"}), 404

    except Exception as e:
        print(f"Error removing friend for user {user_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# GET /users/<id>/friends/<friend_id> (inchangé)
@users_bp.route('/<string:user_id>/friends/<string:friend_id>', methods=['GET'])
def check_friendship(user_id, friend_id):
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500
    query = """
    MATCH (u1:User {id: $user_id}), (u2:User {id: $friend_id})
    RETURN exists((u1)-[:FRIENDS_WITH]->(u2)) as are_friends
    """
    try:
        result = graph.run(query, user_id=user_id, friend_id=friend_id).data()
        if result:
            return jsonify({"are_friends": result[0]['are_friends']}), 200
        else:
            return jsonify({"error": "One or both users not found"}), 404
    except Exception as e:
        print(f"Error checking friendship between {user_id} and {friend_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# GET /users/<id>/mutual_friends/<other_id> (inchangé)
@users_bp.route('/<string:user_id>/mutual_friends/<string:other_user_id>', methods=['GET'])
def get_mutual_friends(user_id, other_user_id):
    graph = get_db()
    if not graph: return jsonify({"error": "Database connection failed"}), 500
    query = """
    MATCH (u1:User {id: $user_id})-[:FRIENDS_WITH]->(mutual_friend:User)
          <-[:FRIENDS_WITH]-(u2:User {id: $other_user_id})
    WHERE u1 <> u2
    RETURN mutual_friend
    """
    try:
        check_u1 = graph.evaluate("MATCH (u:User {id: $id}) RETURN count(u) > 0", id=user_id)
        check_u2 = graph.evaluate("MATCH (u:User {id: $id}) RETURN count(u) > 0", id=other_user_id)
        if not check_u1 or not check_u2:
             missing = [u for u, exists in [(user_id, check_u1), (other_user_id, check_u2)] if not exists]
             return jsonify({"error": f"User(s) not found: {', '.join(missing)}"}), 404

        results = graph.run(query, user_id=user_id, other_user_id=other_user_id).data()
        mutual_friends = [user_node_to_dict(record['mutual_friend']) for record in results]
        return jsonify(mutual_friends), 200
    except Exception as e:
        print(f"Error fetching mutual friends for {user_id} and {other_user_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500