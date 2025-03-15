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
    # Validate the user_id is a proper UUID.
    try:
        uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user_id format. Must be a UUID.'}), 400
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Execute query to fetch contacts for the given user_id.
        cur.execute("SELECT * FROM relyexchange.contacts WHERE user_id = %s", (user_id,))
        rows = cur.fetchall()
        
        # If no contacts are found, return an empty list with a suitable message.
        if not rows:
            cur.close()
            conn.close()
            return jsonify({'contacts': [], 'message': 'No contacts found for this user.'}), 200

        # Get column names from the cursor description.
        columns = [desc[0] for desc in cur.description]
        # Create a list of dictionaries, each representing a contact.
        contacts = [dict(zip(columns, row)) for row in rows]
        
        cur.close()
        conn.close()
        
        # Return the response in a consistent JSON format.
        return jsonify({'contacts': contacts}), 200
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500


    