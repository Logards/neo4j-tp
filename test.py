import requests
import json

BASE_URL = "http://localhost:5000"


def print_response(response):
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print("---")


def test_create_users():
    """Create test users"""
    print("Creating users...")

    # Create user 1
    response = requests.post(
        f"{BASE_URL}/users",
        json={"name": "Alice", "email": "alice@example.com"}
    )
    print_response(response)
    user1_id = response.json()["id"]

    # Create user 2
    response = requests.post(
        f"{BASE_URL}/users",
        json={"name": "Bob", "email": "bob@example.com"}
    )
    print_response(response)
    user2_id = response.json()["id"]

    return user1_id, user2_id


def test_create_friendship(user1_id, user2_id):
    """Make users friends"""
    print(f"Making {user1_id} and {user2_id} friends...")

    response = requests.post(
        f"{BASE_URL}/users/{user1_id}/friends",
        json={"friend_id": user2_id}
    )
    print_response(response)

    # Check if they are friends
    response = requests.get(f"{BASE_URL}/users/{user1_id}/friends/{user2_id}")
    print_response(response)


def test_create_posts(user1_id, user2_id):
    """Create posts for users"""
    print("Creating posts...")

    # Create post for user 1
    response = requests.post(
        f"{BASE_URL}/users/{user1_id}/posts",
        json={"title": "Alice's First Post", "content": "Hello from Alice!"}
    )
    print_response(response)
    post1_id = response.json()["id"]

    # Create post for user 2
    response = requests.post(
        f"{BASE_URL}/users/{user2_id}/posts",
        json={"title": "Bob's First Post", "content": "Hello from Bob!"}
    )
    print_response(response)
    post2_id = response.json()["id"]

    return post1_id, post2_id


def test_add_comments(post1_id, post2_id, user1_id, user2_id):
    """Add comments to posts"""
    print("Adding comments...")

    # User 2 comments on user 1's post
    response = requests.post(
        f"{BASE_URL}/posts/{post1_id}/comments",
        json={"content": "Great post, Alice!", "user_id": user2_id}
    )
    print_response(response)
    comment1_id = response.json()["id"]

    # User 1 comments on user 2's post
    response = requests.post(
        f"{BASE_URL}/posts/{post2_id}/comments",
        json={"content": "Thanks for sharing, Bob!", "user_id": user1_id}
    )
    print_response(response)
    comment2_id = response.json()["id"]

    return comment1_id, comment2_id


def test_like_posts_and_comments(post1_id, post2_id, comment1_id, comment2_id, user1_id, user2_id):
    """Test liking posts and comments"""
    print("Adding likes...")

    # User 1 likes user 2's post
    response = requests.post(
        f"{BASE_URL}/posts/{post2_id}/like",
        json={"user_id": user1_id}
    )
    print_response(response)

    # User 2 likes user 1's post
    response = requests.post(
        f"{BASE_URL}/posts/{post1_id}/like",
        json={"user_id": user2_id}
    )
    print_response(response)

    # User 1 likes comment on their post
    response = requests.post(
        f"{BASE_URL}/comments/{comment1_id}/like",
        json={"user_id": user1_id}
    )
    print_response(response)

    # User 2 likes comment on their post
    response = requests.post(
        f"{BASE_URL}/comments/{comment2_id}/like",
        json={"user_id": user2_id}
    )
    print_response(response)


def test_get_all_data():
    """Get all data from the API"""
    print("Getting all users...")
    response = requests.get(f"{BASE_URL}/users")
    print_response(response)

    print("Getting all posts...")
    response = requests.get(f"{BASE_URL}/posts")
    print_response(response)

    print("Getting all comments...")
    response = requests.get(f"{BASE_URL}/comments")
    print_response(response)


def run_tests():
    """Run all tests"""
    user1_id, user2_id = test_create_users()
    test_create_friendship(user1_id, user2_id)
    post1_id, post2_id = test_create_posts(user1_id, user2_id)
    comment1_id, comment2_id = test_add_comments(post1_id, post2_id, user1_id, user2_id)
    test_like_posts_and_comments(post1_id, post2_id, comment1_id, comment2_id, user1_id, user2_id)
    test_get_all_data()


if __name__ == "__main__":
    run_tests()