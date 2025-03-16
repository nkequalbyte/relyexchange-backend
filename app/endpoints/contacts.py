from flask import Blueprint, request, jsonify
import csv
from io import StringIO
import uuid
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values
from app.config import Config

contacts_bp = Blueprint('contacts', __name__)

def get_db_connection():
    conn = psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        dbname=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD
    )
    return conn

# Define required columns for CSV
REQUIRED_COLUMNS = [
    'FirstName', 'LastName', 'Companies', 'Title', 'Emails', 'PhoneNumbers',
    'Addresses', 'Sites', 'InstantMessageHandles', 'FullName', 'Birthday',
    'Location', 'BookmarkedAt', 'Profiles'
]

@contacts_bp.route('/upload/<user_id>', methods=['POST'])
def upload_csv(user_id):
    try:
        uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user_id format. Must be a UUID.'}), 400

    if 'contact' not in request.files:
        return jsonify({'error': 'No file part in the request.'}), 400

    file = request.files['contact']
    if file.filename == '':
        return jsonify({'error': 'No file selected for uploading.'}), 400

    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File is not a CSV file.'}), 400

    try:
        file_stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
    except Exception as e:
        return jsonify({'error': f'Error reading file: {str(e)}'}), 400

    reader = csv.DictReader(file_stream)
    header = reader.fieldnames
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in header]
    if missing_columns:
        return jsonify({'error': f'Missing required columns: {", ".join(missing_columns)}'}), 400

    records = []
    for row in reader:
        birthday = None
        if row.get('Birthday'):
            try:
                birthday = datetime.strptime(row.get('Birthday'), '%Y-%m-%d').date()
            except ValueError:
                pass

        bookmarked_at = None
        if row.get('BookmarkedAt'):
            try:
                bookmarked_at = datetime.strptime(row.get('BookmarkedAt'), '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    bookmarked_at = datetime.strptime(row.get('BookmarkedAt'), '%Y-%m-%d')
                except ValueError:
                    pass

        record = (
            user_id,
            row.get('FirstName'),
            row.get('LastName'),
            row.get('Companies'),
            row.get('Title'),
            row.get('Emails'),
            row.get('PhoneNumbers'),
            row.get('Addresses'),
            row.get('Sites'),
            row.get('InstantMessageHandles'),
            row.get('FullName'),
            birthday,
            row.get('Location'),
            bookmarked_at,
            row.get('Profiles'),
        )
        records.append(record)

    if not records:
        return jsonify({'error': 'No data found in CSV file.'}), 400

    insert_query = """
        INSERT INTO relyexchange.contacts (
            user_id, FirstName, LastName, Companies, Title, Emails, PhoneNumbers,
            Addresses, Sites, InstantMessageHandles, FullName, Birthday, Location,
            BookmarkedAt, Profiles
        )
        VALUES %s
    """

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check for existing contacts for the given user_id
        cur.execute("SELECT PhoneNumbers FROM relyexchange.contacts WHERE user_id = %s", (user_id,))
        existing_records = cur.fetchall()

        if existing_records:
            existing_numbers = {rec[0] for rec in existing_records if rec[0]}
            new_records = [r for r in records if r[6] and r[6] not in existing_numbers]
        else:
            new_records = records

        if not new_records:
            cur.close()
            conn.close()
            return jsonify({'message': 'No new contacts to insert.'}), 200

        execute_values(cur, insert_query, new_records)
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': f'Successfully inserted {len(new_records)} contacts.'}), 201
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@contacts_bp.route('/<user_id>', methods=['GET'])
def get_contact(user_id):
    # Get pagination parameters from query string
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=25, type=int)
    
    # Validate pagination parameters
    if page < 1:
        return jsonify({'error': 'Page number must be greater than 0'}), 400
    if per_page < 1 or per_page > 100:
        return jsonify({'error': 'Per page must be between 1 and 100'}), 400
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Validate the user_id is a proper UUID
    try:
        uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user_id format. Must be a UUID.'}), 400
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get total count of contacts for pagination metadata
        cur.execute(
            "SELECT COUNT(*) FROM relyexchange.contacts WHERE user_id = %s",
            (user_id,)
        )
        total_contacts = cur.fetchone()[0]
        
        # Execute paginated query
        cur.execute("""
            SELECT * FROM relyexchange.contacts 
            WHERE user_id = %s 
            ORDER BY id 
            LIMIT %s OFFSET %s
        """, (user_id, per_page, offset))
        rows = cur.fetchall()
        
        # If no contacts are found, return an empty list with pagination metadata
        if not rows:
            pagination = {
                'total': total_contacts,
                'page': page,
                'per_page': per_page,
                'total_pages': (total_contacts + per_page - 1) // per_page,
                'has_next': False,
                'has_prev': page > 1
            }
            return jsonify({
                'contacts': [],
                'pagination': pagination,
                'message': 'No contacts found for this page.'
            }), 200

        # Get column names from the cursor description
        columns = [desc[0] for desc in cur.description]
        # Create a list of dictionaries, each representing a contact
        contacts = [dict(zip(columns, row)) for row in rows]
        
        # Calculate pagination metadata
        total_pages = (total_contacts + per_page - 1) // per_page
        pagination = {
            'total': total_contacts,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }
        
        cur.close()
        conn.close()
        
        # Return the response with pagination metadata
        return jsonify({
            'contacts': contacts,
            'pagination': pagination
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@contacts_bp.route('/<user_id>/<contact_id>', methods=['PUT'])
def update_contact(user_id, contact_id):
    # Validate UUIDs
    try:
        uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user_id or contact_id format. Must be UUIDs.'}), 400

    # Validate request body
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No update data provided'}), 400

    # Validate that only allowed fields are being updated
    allowed_fields = {
        'FirstName', 'LastName', 'Companies', 'Title', 'Emails', 'PhoneNumbers',
        'Addresses', 'Sites', 'InstantMessageHandles', 'FullName', 'Birthday',
        'Location', 'BookmarkedAt', 'Profiles'
    }
    
    invalid_fields = set(data.keys()) - allowed_fields
    if invalid_fields:
        return jsonify({'error': f'Invalid fields provided: {", ".join(invalid_fields)}'}), 400

    # Process special fields
    if 'Birthday' in data and data['Birthday']:
        try:
            datetime.strptime(data['Birthday'], '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Birthday must be in YYYY-MM-DD format'}), 400

    if 'BookmarkedAt' in data and data['BookmarkedAt']:
        try:
            datetime.strptime(data['BookmarkedAt'], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                datetime.strptime(data['BookmarkedAt'], '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': 'BookmarkedAt must be in YYYY-MM-DD HH:MM:SS or YYYY-MM-DD format'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # First verify the contact belongs to the user
        cur.execute(
            "SELECT id FROM relyexchange.contacts WHERE id = %s AND user_id = %s",
            (contact_id, user_id)
        )
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error': 'Contact not found or does not belong to the user'}), 404

        # Build the update query dynamically
        set_clause = ", ".join([f"{key} = %s" for key in data.keys()])
        values = list(data.values())
        values.extend([contact_id, user_id])  # Add WHERE clause parameters

        update_query = f"""
            UPDATE relyexchange.contacts 
            SET {set_clause}
            WHERE id = %s AND user_id = %s
            RETURNING *
        """

        cur.execute(update_query, values)
        updated_contact = cur.fetchone()
        
        conn.commit()

        # Convert the returned tuple to a dictionary
        columns = [desc[0] for desc in cur.description]
        updated_contact_dict = dict(zip(columns, updated_contact))

        cur.close()
        conn.close()

        return jsonify({
            'message': 'Contact updated successfully',
            'contact': updated_contact_dict
        }), 200

    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@contacts_bp.route('/<user_id>/<contact_id>', methods=['GET'])
def get_specific_contact(user_id, contact_id):
    # Validate UUIDs
    try:
        uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user_id or contact_id format. Must be UUIDs.'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get the specific contact
        cur.execute("""
            SELECT * FROM relyexchange.contacts 
            WHERE user_id = %s AND id = %s
        """, (user_id, contact_id))
        
        row = cur.fetchone()
        
        if not row:
            return jsonify({'error': 'Contact not found or does not belong to the user'}), 404

        # Get column names from the cursor description
        columns = [desc[0] for desc in cur.description]
        # Create a dictionary representing the contact
        contact = dict(zip(columns, row))
        
        cur.close()
        conn.close()
        
        return jsonify({'contact': contact}), 200
        
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

    