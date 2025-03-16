from flask import Blueprint, jsonify
import uuid
import psycopg2
from app.config import Config

users_bp = Blueprint('users', __name__)

def get_db_connection():
    conn = psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        dbname=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD
    )
    return conn

@users_bp.route('/users', methods=['GET'])
def get_users():
    # Dummy endpoint for demonstration
    return jsonify({'message': 'List of users would be returned here.'})

@users_bp.route('/users/<user_id>', methods=['GET'])
def get_user_by_uuid(user_id):
    # Validate the user_id is a proper UUID
    try:
        uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user_id format. Must be a UUID.'}), 400
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get the specific user
        cur.execute("""
            SELECT * FROM relyexchange.users 
            WHERE uuid = %s
        """, (user_id,))
        
        row = cur.fetchone()
        
        if not row:
            return jsonify({'error': 'User not found'}), 404

        # Get column names from the cursor description
        columns = [desc[0] for desc in cur.description]
        # Create a dictionary representing the user
        user = dict(zip(columns, row))
        
        cur.close()
        conn.close()
        
        return jsonify({'user': user}), 200
        
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
