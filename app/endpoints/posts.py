from flask import Blueprint, request, jsonify
import uuid, psycopg2, json
from datetime import datetime
from app.config import Config
import boto3
from botocore.exceptions import NoCredentialsError

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

    try:
        uuid.UUID(user_id)
    except ValueError:
        return False

    cur.execute("SELECT id FROM relyexchange.users WHERE id = %s", (user_id,))
    return cur.fetchone() is not None


def is_contact_of_user(contact_id, owner_id, cur):
    """
    Check if the provided contact_id belongs to the owner's contacts.
    Also return the contact's name.
    """
    cur.execute('''SELECT id, "firstname", "lastname" 
                   FROM relyexchange.contacts 
                   WHERE id = %s AND user_id = %s''', (contact_id, owner_id))
    return cur.fetchone()

# --- Supabase Storage / S3 configuration ---

print(Config.S3_URL)
s3_url = Config.S3_URL 
access_key = Config.S3_ACCESS_KEY 
secret_key = Config.S3_SECRET_KEY
session = boto3.session.Session()
s3_client = session.client(
    's3',
    endpoint_url=s3_url,
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key
)

def upload_file_to_supabase(bucket_name, file_obj, folder_name, file_name):
    """
    Uploads a file object to Supabase Storage (S3) under a given folder and returns the public URL.
    """
    try:
        object_key = f"{folder_name}/{file_name}"
        s3_client.upload_fileobj(file_obj, bucket_name, object_key)
        file_url = f"{s3_client.meta.endpoint_url}/{bucket_name}/{object_key}"
        return file_url
    except FileNotFoundError:
        print("The file was not found.")
        return None
    except NoCredentialsError:
        print("Credentials not available.")
        return None


def convert_to_presigned_url(url, bucket, expires_in=3600):
    """
    Convert a stored S3 URL to a presigned URL.
    
    Parameters:
      url (str): The original S3 URL.
      bucket (str): The name of the S3 bucket.
      expires_in (int): Time in seconds for the presigned URL to remain valid.
    
    Returns:
      str: A presigned URL if url is not None and the object key can be determined; otherwise, the original URL or None.
    """
    if not url:
        return None

    try:
        # Assume the URL is formatted as: <endpoint_url>/<bucket>/<object_key>
        parts = url.split(f"/{bucket}/")
        if len(parts) < 2:
            # If the URL doesn't match our expected format, return it unchanged.
            return url
        
        object_key = parts[-1]
        # Generate a presigned URL using the globally configured s3_client.
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": object_key},
            ExpiresIn=expires_in
        )
        return presigned_url
    except Exception as e:
        print(f"Error generating presigned URL: {e}")
        return url


@posts_bp.route('/posts/<user_id>', methods=['POST'])
def create_post(user_id):
    """
    Create a new post.
    The client may send:
      - A JSON payload with "content", "mentions", and "shares", OR
      - A multipart/form-data payload that includes a file (key "file") along with "content", "mentions", and "shares".
    If a file is provided (allowed types: mp3, jpeg, jpg, png, txt), it is uploaded to Supabase Storage,
    and the returned URL is stored in the post record.
    The post may tag users from our system and/or contacts. (In the response, tagged contact names are provided.)
    """
    try:
        uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user_id format'}), 400

    content = None
    mentions = []
    shares = []
    file_url = None

    if 'file' in request.files:
        file = request.files['file']
        allowed_extensions = ['mp3', 'jpeg', 'jpg', 'png', 'txt']
        filename = file.filename
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        if ext not in allowed_extensions:
            return jsonify({'error': 'Invalid file type. Allowed types: mp3, jpeg, jpg, png, txt'}), 400
        
        bucket_name_supabase = "relyexchange"
        folder_name = "voicenotes"
        file_url = upload_file_to_supabase(bucket_name_supabase, file, folder_name, filename)

    content = request.form.get('content', '')
    try:
        mentions = json.loads(request.form.get('mentions', '[]'))
        shares = json.loads(request.form.get('shares', '[]'))
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON format for mentions or shares'}), 400

        
    # else:
    #     data = request.get_json()
    #     if not data:
    #         return jsonify({'error': 'No data provided'}), 400
    #     content = data.get('content')
    #     if content is None:
    #         return jsonify({'error': 'content is required'}), 400
    #     mentions = data.get('mentions', [])
    #     shares = data.get('shares', [])
    #     file_url = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Insert the post record (assumes posts table has an attachment_url and soft-delete fields)
        insert_post_query = """
            INSERT INTO relyexchange.posts (user_id, content, attachment_url, created_at, is_deleted)
            VALUES (%s, %s, %s, NOW(), false)
            RETURNING post_id, user_id, content, attachment_url, created_at
        """
        cur.execute(insert_post_query, (user_id, content, file_url))
        post = cur.fetchone()
        post_id = post[0]

        # Process mentions: Insert into post_mentions table.
        for mention in mentions:
            reg_user = is_registered_user(mention, cur)
            print("reg_user",reg_user)
            if reg_user:
                # Registered user; we store the mention.
                cur.execute("""
                    INSERT INTO relyexchange.post_mentions (post_id, mentioned_user_id, mentioned_contact_id)
                    VALUES (%s, %s, NULL)
                    ON CONFLICT DO NOTHING
                """, (post_id, mention))
            else:
                # Not a registered user; check if it's a contact.
                contact = is_contact_of_user(mention, user_id, cur)
                print("contact",contact)
                if contact:
                    cur.execute("""
                        INSERT INTO relyexchange.post_mentions (post_id, mentioned_user_id, mentioned_contact_id)
                        VALUES (%s, NULL, %s)
                        ON CONFLICT DO NOTHING
                    """, (post_id, mention))
                else:
                    return jsonify({'error': f'Mentioned ID {mention} is neither a registered user nor a contact of the posting user.'}), 400

        # Process shares: Similar to mentions.
        for share in shares:
            reg_user = is_registered_user(share, cur)
            if reg_user:
                cur.execute("""
                    INSERT INTO relyexchange.post_shares (post_id, shared_with_user_id, shared_contact_id)
                    VALUES (%s, %s, NULL)
                    ON CONFLICT DO NOTHING
                """, (post_id, share))
            else:
                contact = is_contact_of_user(share, user_id, cur)
                if contact:
                    cur.execute("""
                        INSERT INTO relyexchange.post_shares (post_id, shared_with_user_id, shared_contact_id)
                        VALUES (%s, NULL, %s)
                        ON CONFLICT DO NOTHING
                    """, (post_id, share))
                else:
                    return jsonify({'error': f'Shared ID {share} is neither a registered user nor a contact of the posting user.'}), 400

        conn.commit()
        cur.close()
        conn.close()

        # Return basic post info. Additional details (e.g. tagged names) can be fetched in GET.
        return jsonify({
            'message': 'Post created successfully',
            'post': {
                'post_id': post[0],
                'user_id': post[1],
                'content': post[2],
                'attachment_url': post[3],
                'created_at': post[4]
            }
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@posts_bp.route('/posts/<post_id>', methods=['GET'])
def get_post(post_id):
    """
    Retrieve a post along with its mentions, shares, and comments.
    The response includes:
      - Post content and attachment_url.
      - Mentions: For each mention, if the mention is a registered user, return the user’s name (from the 'name' column);
                  if from a contact, return the contact’s first and last names.
      - Shares: Similarly include details.
      - Comments: All non-deleted comments with commenter details.
    """
    try:
        uuid.UUID(post_id)
    except ValueError:
        return jsonify({'error': 'Invalid post_id format'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get the post (only if not soft-deleted).
        cur.execute("""
            SELECT post_id, user_id, content, attachment_url, created_at 
            FROM relyexchange.posts
            WHERE post_id = %s AND is_deleted = false
        """, (post_id,))
        post = cur.fetchone()
        if not post:
            return jsonify({'error': 'Post not found'}), 404

        # Get mentions with user/contact details.
        cur.execute("""
            SELECT pm.mentioned_user_id, u.name,
                   pm.mentioned_contact_id, c."firstname", c."lastname"
            FROM relyexchange.post_mentions pm
            LEFT JOIN relyexchange.users u ON pm.mentioned_user_id = u.id
            LEFT JOIN relyexchange.contacts c ON pm.mentioned_contact_id = c.id
            WHERE pm.post_id = %s
        """, (post_id,))
        mention_rows = cur.fetchall()
        mentions = []
        for row in mention_rows:
            # row[0] is mentioned_user_id, row[1] is u.name
            # row[2] is mentioned_contact_id, row[3] and row[4] are contact's firstname and lastname.
            if row[0]:  # Registered user mention.
                mentions.append({
                    'user_id': row[0],
                    'name': row[1],  # Directly use the single name column.
                    'type': 'registered'
                })
            elif row[2]:  # Contact mention.
                mentions.append({
                    'contact_id': row[2],
                    'name': f"{row[3]} {row[4]}" if row[3] and row[4] else None,
                    'type': 'contact'
                })

        # Get shares (similar approach).
        cur.execute("""
            SELECT ps.shared_with_user_id, u.name,
                   ps.shared_contact_id, c."firstname", c."lastname"
            FROM relyexchange.post_shares ps
            LEFT JOIN relyexchange.users u ON ps.shared_with_user_id = u.id
            LEFT JOIN relyexchange.contacts c ON ps.shared_contact_id = c.id
            WHERE ps.post_id = %s
        """, (post_id,))
        share_rows = cur.fetchall()
        shares = []
        for row in share_rows:
            # row[0] is shared_with_user_id, row[1] is u.name,
            # row[2] is shared_contact_id, row[3] and row[4] are contact names.
            if row[0]:
                shares.append({
                    'user_id': row[0],
                    'name': row[1],
                    'type': 'registered'
                })
            elif row[2]:
                shares.append({
                    'contact_id': row[2],
                    'name': f"{row[3]} {row[4]}" if row[3] and row[4] else None,
                    'type': 'contact'
                })

        # Get comments with commenter details.
        cur.execute("""
            SELECT c.comment_id, c.post_id, c.user_id, u.name, c.content, c.created_at 
            FROM relyexchange.comments c
            LEFT JOIN relyexchange.users u ON c.user_id = u.id
            WHERE c.post_id = %s AND c.is_deleted = false
            ORDER BY c.created_at ASC
        """, (post_id,))
        comment_rows = cur.fetchall()
        comments = []
        for row in comment_rows:
            comments.append({
                'comment_id': row[0],
                'post_id': row[1],
                'user_id': row[2],
                'user_name': row[3],  # Directly use the name column.
                'content': row[4],
                'created_at': row[5]
            })

        cur.close()
        conn.close()
        attachment_url = post[3]
        presigned_url = convert_to_presigned_url(attachment_url, bucket="relyexchange", expires_in=3600)
        post_data = {
            'post_id': post[0],
            'user_id': post[1],
            'content': post[2],
            'attachment_url': presigned_url,
            'created_at': post[4],
            'mentions': mentions,
            'shares': shares,
            'comments': comments
        }
        return jsonify({'post': post_data}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@posts_bp.route('/posts/<post_id>', methods=['PUT'])
def update_post(post_id):
    """
    Update a post.
    The client may update content and optionally provide a new file.
    Only the owner (provided as user_id in the payload) can update the post.
    All functionality (mentions, shares, attachment) is maintained.
    """
    data = {}
    if 'file' in request.files:
        file = request.files['file']
        allowed_extensions = ['mp3', 'jpeg', 'jpg', 'png', 'txt']
        filename = file.filename
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        if ext not in allowed_extensions:
            return jsonify({'error': 'Invalid file type. Allowed types: mp3, jpeg, jpg, png, txt'}), 400

        data['content'] = request.form.get('content', '')
        try:
            data['mentions'] = json.loads(request.form.get('mentions', '[]'))
            data['shares'] = json.loads(request.form.get('shares', '[]'))
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid JSON format for mentions or shares'}), 400

        bucket_name_supabase = "relyexchange"
        folder_name = "posts"
        file_url = upload_file_to_supabase(bucket_name_supabase, file, folder_name, filename)
        data['attachment_url'] = file_url
    else:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        if 'mentions' not in data:
            data['mentions'] = []
        if 'shares' not in data:
            data['shares'] = []

    user_id = data.get('user_id')
    content = data.get('content')
    if not user_id or content is None:
        return jsonify({'error': 'user_id and content are required'}), 400

    try:
        uuid.UUID(post_id)
        uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid UUID format'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Verify post ownership.
        cur.execute("SELECT user_id FROM relyexchange.posts WHERE post_id = %s AND is_deleted = false", (post_id,))
        row = cur.fetchone()
        if not row or row[0] != user_id:
            return jsonify({'error': 'Post not found or unauthorized'}), 403

        if 'attachment_url' in data:
            update_query = """
                UPDATE relyexchange.posts
                SET content = %s, attachment_url = %s
                WHERE post_id = %s
                RETURNING post_id, user_id, content, attachment_url, created_at
            """
            cur.execute(update_query, (content, data['attachment_url'], post_id))
        else:
            update_query = """
                UPDATE relyexchange.posts
                SET content = %s
                WHERE post_id = %s
                RETURNING post_id, user_id, content, attachment_url, created_at
            """
            cur.execute(update_query, (content, post_id))
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
                'attachment_url': updated_post[3],
                'created_at': updated_post[4]
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@posts_bp.route('/posts/<post_id>', methods=['DELETE'])
def delete_post(post_id):
    """
    Soft delete a post.
    Instead of removing the record, mark it as deleted.
    Also soft-delete related comments.
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
        cur.execute("SELECT user_id FROM relyexchange.posts WHERE post_id = %s AND is_deleted = false", (post_id,))
        row = cur.fetchone()
        if not row or row[0] != user_id:
            return jsonify({'error': 'Post not found or unauthorized'}), 403

        # Soft delete the post.
        cur.execute("""
            UPDATE relyexchange.posts 
            SET is_deleted = true, deleted_at = NOW() 
            WHERE post_id = %s
        """, (post_id,))
        # Also soft delete its comments.
        cur.execute("""
            UPDATE relyexchange.comments 
            SET is_deleted = true, deleted_at = NOW() 
            WHERE post_id = %s
        """, (post_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'Post soft deleted successfully'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@posts_bp.route('/posts/user/<user_id>', methods=['GET'])
def get_posts_by_user(user_id):
    """
    Retrieve all posts created by a specific user.
    For each post, return:
      - Content, attachment_url, created_at.
      - Mentions (with details of whether the tag is a registered user or contact, and the person’s name).
      - Shares (similarly).
      - Comments (all non-deleted comments with commenter details).
    """
    try:
        uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user_id format'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Get posts for the user (non-deleted).
        cur.execute("""
            SELECT post_id, user_id, content, attachment_url, created_at 
            FROM relyexchange.posts
            WHERE user_id = %s AND is_deleted = false
            ORDER BY created_at DESC
        """, (user_id,))
        rows = cur.fetchall()
        posts = []
        for row in rows:
            post_id = row[0]
            # Get mentions.
            cur.execute("""
                SELECT pm.mentioned_user_id, u.name,
                       pm.mentioned_contact_id, c."firstname", c."lastname"
                FROM relyexchange.post_mentions pm
                LEFT JOIN relyexchange.users u ON pm.mentioned_user_id = u.id
                LEFT JOIN relyexchange.contacts c ON pm.mentioned_contact_id = c.id
                WHERE pm.post_id = %s
            """, (post_id,))
            mention_rows = cur.fetchall()
            mentions = []
            for m in mention_rows:
                if m[0]:  # Registered user mention.
                    mentions.append({
                        'user_id': m[0],
                        'name': m[1],  # Use the single 'name' column.
                        'type': 'registered'
                    })
                elif m[2]:  # Contact mention.
                    mentions.append({
                        'contact_id': m[2],
                        'name': f"{m[3]} {m[4]}" if m[3] and m[4] else None,
                        'type': 'contact'
                    })
            # Get shares.
            cur.execute("""
                SELECT ps.shared_with_user_id, u.name,
                       ps.shared_contact_id, c."firstname", c."lastname"
                FROM relyexchange.post_shares ps
                LEFT JOIN relyexchange.users u ON ps.shared_with_user_id = u.id
                LEFT JOIN relyexchange.contacts c ON ps.shared_contact_id = c.id
                WHERE ps.post_id = %s
            """, (post_id,))
            share_rows = cur.fetchall()
            shares = []
            for s in share_rows:
                if s[0]:
                    shares.append({
                        'user_id': s[0],
                        'name': s[1],
                        'type': 'registered'
                    })
                elif s[2]:
                    shares.append({
                        'contact_id': s[2],
                        'name': f"{s[3]} {s[4]}" if s[3] and s[4] else None,
                        'type': 'contact'
                    })
            # Get comments.
            cur.execute("""
                SELECT c.comment_id, c.post_id, c.user_id, u.name, c.content, c.created_at 
                FROM relyexchange.comments c
                LEFT JOIN relyexchange.users u ON c.user_id = u.id
                WHERE c.post_id = %s AND c.is_deleted = false
                ORDER BY c.created_at ASC
            """, (post_id,))
            comment_rows = cur.fetchall()
            comments = []
            for cm in comment_rows:
                print(cm)
                comments.append({
                    'comment_id': cm[0],
                    'post_id': cm[1],
                    'user_id': cm[2],
                    'user_name': cm[3],
                    'content': cm[4],
                    'created_at': cm[5]
                })
            attachment_url = row[3]
            presigned_url = convert_to_presigned_url(attachment_url, bucket="relyexchange", expires_in=3600)
            posts.append({
                'post_id': row[0],
                'user_id': row[1],
                'content': row[2],
                'attachment_url': presigned_url,
                'created_at': row[4],
                'mentions': mentions,
                'shares': shares,
                'comments': comments
            })
        cur.close()
        conn.close()
        return jsonify({'posts': posts}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
