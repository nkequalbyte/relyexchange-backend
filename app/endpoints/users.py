from flask import Blueprint, jsonify, request
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

@users_bp.route('/email/<email>', methods=['GET'])
def get_user_by_email(email):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get the specific user by email
        cur.execute("""
            SELECT * FROM relyexchange.users 
            WHERE email = %s
        """, (email,))
        
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

@users_bp.route('/users', methods=['POST'])
def create_user():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['email', 'name', 'uuid', 'loginBy']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate UUID format
        try:
            uuid.UUID(data['uuid'])
        except ValueError:
            return jsonify({'error': 'Invalid UUID format'}), 400
            
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Insert new user
        cur.execute("""
            INSERT INTO relyexchange.users (email, name, uuid, login_by)
            VALUES (%s, %s, %s, %s)
            RETURNING *
        """, (data['email'], data['name'], data['uuid'], data['loginBy']))
        
        conn.commit()
        
        # Get the inserted row
        row = cur.fetchone()
        columns = [desc[0] for desc in cur.description]
        user = dict(zip(columns, row))
        
        cur.close()
        conn.close()
        
        return jsonify({'message': 'User created successfully', 'user': user}), 201
        
    except psycopg2.IntegrityError as e:
        return jsonify({'error': 'User already exists with this email or UUID'}), 409
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
