from flask import Blueprint, request, jsonify
import uuid, psycopg2
from app.config import Config

comments_bp = Blueprint('comments', __name__)

def get_db_connection():
    conn = psycopg2.connect(
         host=Config.DB_HOST,
         port=Config.DB_PORT,
         dbname=Config.DB_NAME,
         user=Config.DB_USER,
         password=Config.DB_PASSWORD
    )
    return conn

def is_user_allowed_to_comment(post_id, user_id, cur):
    """
    Check if a user is allowed to comment on a post.
    Allowed users include:
      - The owner of the post.
      - Users mentioned in the post.
      - Users with whom the post is shared.
    """
    query = """
    SELECT EXISTS (
        SELECT 1 FROM (
            SELECT user_id FROM relyexchange.posts WHERE post_id = %s
            UNION
            SELECT mentioned_user_id FROM relyexchange.post_mentions WHERE post_id = %s
            UNION
            SELECT shared_with_user_id FROM relyexchange.post_shares WHERE post_id = %s
        ) AS allowed_users
        WHERE allowed_users.user_id = %s
    )
    """
    cur.execute(query, (post_id, post_id, post_id, user_id))
    allowed = cur.fetchone()[0]
    return allowed

@comments_bp.route('/posts/<post_id>/comments', methods=['POST'])
def add_comment(post_id):
    """
    Add a comment to a post.
    Expects JSON with:
      - user_id: ID of the commenting user
      - content: the comment text
    The endpoint checks that the user is allowed to comment (post owner, mentioned, or shared).
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    user_id = data.get('user_id')
    content = data.get('content')
    if not user_id or not content:
        return jsonify({'error': 'user_id and content are required'}), 400

    try:
        uuid.UUID(post_id)
        uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid UUID format'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if not is_user_allowed_to_comment(post_id, user_id, cur):
            return jsonify({'error': 'User is not allowed to comment on this post'}), 403

        insert_query = """
            INSERT INTO relyexchange.comments (post_id, user_id, content, created_at)
            VALUES (%s, %s, %s, NOW())
            RETURNING comment_id, post_id, user_id, content, created_at
        """
        cur.execute(insert_query, (post_id, user_id, content))
        comment = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            'message': 'Comment added successfully',
            'comment': {
                'comment_id': comment[0],
                'post_id': comment[1],
                'user_id': comment[2],
                'content': comment[3],
                'created_at': comment[4]
            }
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@comments_bp.route('/posts/<post_id>/comments', methods=['GET'])
def get_comments(post_id):
    """
    Retrieve all comments for a given post.
    """
    try:
        uuid.UUID(post_id)
    except ValueError:
        return jsonify({'error': 'Invalid post_id format'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT comment_id, post_id, user_id, content, created_at 
            FROM relyexchange.comments
            WHERE post_id = %s
            ORDER BY created_at ASC
        """, (post_id,))
        rows = cur.fetchall()
        comments = [{
            'comment_id': row[0],
            'post_id': row[1],
            'user_id': row[2],
            'content': row[3],
            'created_at': row[4]
        } for row in rows]
        cur.close()
        conn.close()
        return jsonify({'comments': comments}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@comments_bp.route('/comments/<comment_id>', methods=['PUT'])
def update_comment(comment_id):
    """
    Update a comment.
    Expects JSON with:
      - user_id: the ID of the commenting user (must be the owner of the comment)
      - content: the updated text
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    user_id = data.get('user_id')
    content = data.get('content')
    if not user_id or not content:
        return jsonify({'error': 'user_id and content are required'}), 400

    try:
        uuid.UUID(comment_id)
        uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid UUID format'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM relyexchange.comments WHERE comment_id = %s", (comment_id,))
        row = cur.fetchone()
        if not row or row[0] != user_id:
            return jsonify({'error': 'Comment not found or unauthorized'}), 403

        cur.execute("""
            UPDATE relyexchange.comments
            SET content = %s
            WHERE comment_id = %s
            RETURNING comment_id, post_id, user_id, content, created_at
        """, (content, comment_id))
        updated_comment = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            'message': 'Comment updated successfully',
            'comment': {
                'comment_id': updated_comment[0],
                'post_id': updated_comment[1],
                'user_id': updated_comment[2],
                'content': updated_comment[3],
                'created_at': updated_comment[4]
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@comments_bp.route('/comments/<comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    """
    Delete a comment.
    Requires a query parameter 'user_id' to verify that the comment belongs to the user.
    """
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id query parameter is required'}), 400

    try:
        uuid.UUID(comment_id)
        uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid UUID format'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM relyexchange.comments WHERE comment_id = %s", (comment_id,))
        row = cur.fetchone()
        if not row or row[0] != user_id:
            return jsonify({'error': 'Comment not found or unauthorized'}), 403

        cur.execute("DELETE FROM relyexchange.comments WHERE comment_id = %s", (comment_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'Comment deleted successfully'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
