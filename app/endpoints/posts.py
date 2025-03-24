from flask import Blueprint, request, jsonify
import uuid, psycopg2
from datetime import datetime
from app.config import Config

posts_bp = Blueprint('posts', __name__)

def get_db_connection():
    conn = psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        dbname=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD
    )
    return conn

def is_registered_user(user_id, cur):
    """
    Check if a given user_id exists in the registered users table.
    """
    cur.execute("SELECT uuid FROM relyexchange.users WHERE uuid = %s", (user_id,))
    return cur.fetchone() is not None

def is_contact_of_user(contact_id, owner_id, cur):
    """
    Check if the provided contact_id belongs to the owner's contacts.
    """
    cur.execute("SELECT id FROM relyexchange.contacts WHERE id = %s AND user_id = %s", (contact_id, owner_id))
    return cur.fetchone() is not None

@posts_bp.route('/posts/<user_id>', methods=['POST'])
def create_post(user_id):
    """
    Create a new post.
    Path Variable:
      - user_id: the ID of the user creating the post.
    Expects JSON with:
      - content: text content of the post.
      - mentions: (optional) list of IDs (registered user IDs or contact IDs) mentioned in the post.
      - shares: (optional) list of IDs (registered user IDs or contact IDs) with whom the post is shared.
    The endpoint checks if each provided ID is either a registered user or a contact of the posting user.
    """
    # Validate the user_id from the URL
    try:
        uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user_id format'}), 400

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    content = data.get('content')
    if not content:
        return jsonify({'error': 'content is required'}), 400

    # Optional arrays for mentions and shares
    mentions = data.get('mentions', [])
    shares = data.get('shares', [])

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Insert the post record
        insert_post_query = """
            INSERT INTO relyexchange.posts (user_id, content, created_at)
            VALUES (%s, %s, NOW())
            RETURNING post_id, user_id, content, created_at
        """
        cur.execute(insert_post_query, (user_id, content))
        post = cur.fetchone()
        post_id = post[0]

        # Process mentions
        for mention in mentions:
            # try:
            #     uuid.UUID(mention)
            # except ValueError:
            #     return jsonify({'error': f'Invalid mention id format: {mention}'}), 400

            if is_registered_user(mention, cur):
                # Registered user: store in mentioned_user_id column.
                cur.execute("""
                    INSERT INTO relyexchange.post_mentions (post_id, mentioned_user_id, mentioned_contact_id)
                    VALUES (%s, %s, NULL)
                    ON CONFLICT DO NOTHING
                """, (post_id, mention))
            elif is_contact_of_user(mention, user_id, cur):
                # Contact: store in mentioned_contact_id column.
                cur.execute("""
                    INSERT INTO relyexchange.post_mentions (post_id, mentioned_user_id, mentioned_contact_id)
                    VALUES (%s, NULL, %s)
                    ON CONFLICT DO NOTHING
                """, (post_id, mention))
            else:
                return jsonify({'error': f'Mentioned ID {mention} is neither a registered user nor a contact of the posting user.'}), 400

        # Process shares
        for share in shares:
            # try:
            #     uuid.UUID(share)
            # except ValueError:
            #     return jsonify({'error': f'Invalid share id format: {share}'}), 400

            if is_registered_user(share, cur):
                cur.execute("""
                    INSERT INTO relyexchange.post_shares (post_id, shared_user_id, shared_contact_id)
                    VALUES (%s, %s, NULL)
                    ON CONFLICT DO NOTHING
                """, (post_id, share))
            elif is_contact_of_user(share, user_id, cur):
                cur.execute("""
                    INSERT INTO relyexchange.post_shares (post_id, shared_user_id, shared_contact_id)
                    VALUES (%s, NULL, %s)
                    ON CONFLICT DO NOTHING
                """, (post_id, share))
            else:
                return jsonify({'error': f'Shared ID {share} is neither a registered user nor a contact of the posting user.'}), 400

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'message': 'Post created successfully',
            'post': {
                'post_id': post_id,
                'user_id': user_id,
                'content': content,
                'created_at': post[3]
            }
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@posts_bp.route('/posts/<post_id>', methods=['GET'])
def get_post(post_id):
    """
    Retrieve a post along with its mentions and shares.
    """
    try:
        uuid.UUID(post_id)
    except ValueError:
        return jsonify({'error': 'Invalid post_id format'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT post_id, user_id, content, created_at 
            FROM relyexchange.posts
            WHERE post_id = %s
        """, (post_id,))
        post = cur.fetchone()
        if not post:
            return jsonify({'error': 'Post not found'}), 404

        # Get mentioned user IDs
        cur.execute("""
            SELECT mentioned_user_id FROM relyexchange.post_mentions 
            WHERE post_id = %s
        """, (post_id,))
        mentions = [row[0] for row in cur.fetchall()]

        # Get shared user IDs
        cur.execute("""
            SELECT shared_with_user_id FROM relyexchange.post_shares 
            WHERE post_id = %s
        """, (post_id,))
        shares = [row[0] for row in cur.fetchall()]

        cur.close()
        conn.close()

        post_data = {
            'post_id': post[0],
            'user_id': post[1],
            'content': post[2],
            'created_at': post[3],
            'mentions': mentions,
            'shares': shares
        }
        return jsonify({'post': post_data}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@posts_bp.route('/posts/<post_id>', methods=['PUT'])
def update_post(post_id):
    """
    Update a post.
    Only the owner (provided as user_id in JSON) can update the post.
    Expects JSON with:
      - user_id: the ID of the user updating the post
      - content: the new content
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
        # Check if the post belongs to the user
        cur.execute("SELECT user_id FROM relyexchange.posts WHERE post_id = %s", (post_id,))
        row = cur.fetchone()
        if not row or row[0] != user_id:
            return jsonify({'error': 'Post not found or unauthorized'}), 403

        cur.execute("""
            UPDATE relyexchange.posts
            SET content = %s
            WHERE post_id = %s
            RETURNING post_id, user_id, content, created_at
        """, (content, post_id))
        updated_post = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'message': 'Post updated successfully',
            'post': {
                'post_id': updated_post[0],
                'user_id': updated_post[1],
                'content': updated_post[2],
                'created_at': updated_post[3]
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@posts_bp.route('/posts/<post_id>', methods=['DELETE'])
def delete_post(post_id):
    """
    Delete a post.
    The user deleting the post must be the owner.
    Expects user_id as a query parameter.
    """
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id query parameter is required'}), 400

    try:
        uuid.UUID(post_id)
        uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid UUID format'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM relyexchange.posts WHERE post_id = %s", (post_id,))
        row = cur.fetchone()
        if not row or row[0] != user_id:
            return jsonify({'error': 'Post not found or unauthorized'}), 403

        cur.execute("DELETE FROM relyexchange.posts WHERE post_id = %s", (post_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'Post deleted successfully'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@posts_bp.route('/posts/user/<user_id>', methods=['GET'])
def get_posts_by_user(user_id):
    """
    Retrieve all posts created by a specific user.
    """
    try:
        uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user_id format'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT post_id, user_id, content, created_at 
            FROM relyexchange.posts
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        rows = cur.fetchall()
        posts = [{
            'post_id': row[0],
            'user_id': row[1],
            'content': row[2],
            'created_at': row[3]
        } for row in rows]
        cur.close()
        conn.close()
        return jsonify({'posts': posts}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
