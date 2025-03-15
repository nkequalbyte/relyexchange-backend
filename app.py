# # from flask import Flask, request, jsonify
# # import csv
# # from io import StringIO
# # import os
# # import uuid
# # from datetime import datetime
# # import psycopg2
# # from psycopg2.extras import execute_values

# # app = Flask(__name__)

# # # --- Configuration ---
# # # You can set these environment variables or replace the defaults with your settings.
# DB_HOST = os.environ.get('DB_HOST', 'aws-0-us-east-1.pooler.supabase.com')
# DB_PORT = os.environ.get('DB_PORT', '6543')
# DB_NAME = os.environ.get('DB_NAME', 'postgres')
# DB_USER = os.environ.get('DB_USER', 'postgres.hdesapbxgxecjzfuggjo')
# DB_PASSWORD = os.environ.get('DB_PASSWORD', '0oocbYXnrWknAbt7')

# # def get_db_connection():
# #     """
# #     Establishes and returns a connection to the PostgreSQL database.
# #     """
# #     conn = psycopg2.connect(
# #         host=DB_HOST,
# #         port=DB_PORT,
# #         dbname=DB_NAME,
# #         user=DB_USER,
# #         password=DB_PASSWORD
# #     )
# #     return conn

# # # --- Define the expected CSV columns ---
# # REQUIRED_COLUMNS = [
# #     'FirstName', 'LastName', 'Companies', 'Title', 'Emails', 'PhoneNumbers',
# #     'Addresses', 'Sites', 'InstantMessageHandles', 'FullName', 'Birthday',
# #     'Location', 'BookmarkedAt', 'Profiles'
# # ]

# # @app.route('/upload/<user_id>', methods=['POST'])
# # def upload_csv(user_id):
# #     """
# #     Endpoint to upload a CSV file and insert contacts for the given user_id into the database.
# #     """
# #     # Validate that user_id is a proper UUID.
# #     print(user_id)
# #     try:
# #         uuid.UUID(user_id)
# #     except ValueError:
# #         return jsonify({'error': 'Invalid user_id format. Must be a UUID.'}), 400

# #     # Ensure the file part exists in the request.
# #     print(request.files)
# #     if 'contact' not in request.files:
# #         return jsonify({'error': 'No file part in the request.'}), 400

# #     file = request.files['contact']

# #     # Check if a file was selected.
# #     if file.filename == '':
# #         return jsonify({'error': 'No file selected for uploading.'}), 400

# #     # Check that the uploaded file is a CSV.
# #     if not file.filename.endswith('.csv'):
# #         return jsonify({'error': 'File is not a CSV file.'}), 400

# #     try:
# #         # Read the file stream into a text buffer.
# #         file_stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
# #     except Exception as e:
# #         return jsonify({'error': f'Error reading file: {str(e)}'}), 400

# #     reader = csv.DictReader(file_stream)
# #     header = reader.fieldnames

# #     # Validate that the CSV has all required columns.
# #     missing_columns = [col for col in REQUIRED_COLUMNS if col not in header]
# #     if missing_columns:
# #         return jsonify({'error': f'Missing required columns: {", ".join(missing_columns)}'}), 400

# #     records = []
# #     for row in reader:
# #         # Parse the Birthday column into a date object, if present.
# #         birthday = row.get('Birthday')
# #         if birthday:
# #             try:
# #                 birthday = datetime.strptime(birthday, '%Y-%m-%d').date()
# #             except ValueError:
# #                 birthday = None
# #         else:
# #             birthday = None

# #         # Parse the BookmarkedAt column into a datetime object, if present.
# #         bookmarked_at = row.get('BookmarkedAt')
# #         if bookmarked_at:
# #             try:
# #                 bookmarked_at = datetime.strptime(bookmarked_at, '%Y-%m-%d %H:%M:%S')
# #             except ValueError:
# #                 try:
# #                     bookmarked_at = datetime.strptime(bookmarked_at, '%Y-%m-%d')
# #                 except ValueError:
# #                     bookmarked_at = None
# #         else:
# #             bookmarked_at = None

# #         # Create a tuple of values in the order expected by the INSERT statement.
# #         record = (
# #             user_id,
# #             row.get('FirstName'),
# #             row.get('LastName'),
# #             row.get('Companies'),
# #             row.get('Title'),
# #             row.get('Emails'),
# #             row.get('PhoneNumbers'),
# #             row.get('Addresses'),
# #             row.get('Sites'),
# #             row.get('InstantMessageHandles'),
# #             row.get('FullName'),
# #             birthday,
# #             row.get('Location'),
# #             bookmarked_at,
# #             row.get('Profiles'),
# #         )
# #         records.append(record)

# #     if not records:
# #         return jsonify({'error': 'No data found in CSV file.'}), 400

# #     # Define the insert query. Note that the id and CreatedAt columns are handled by the DB.
# #     insert_query = """
# #         INSERT INTO relyexchange.contacts (
# #             user_id, FirstName, LastName, Companies, Title, Emails, PhoneNumbers,
# #             Addresses, Sites, InstantMessageHandles, FullName, Birthday, Location,
# #             BookmarkedAt, Profiles
# #         )
# #         VALUES %s
# #     """

# #     try:
# #         conn = get_db_connection()
# #         cur = conn.cursor()
# #         # Use psycopg2's execute_values for bulk insertion.
# #         execute_values(cur, insert_query, records)
# #         conn.commit()
# #         cur.close()
# #         conn.close()
# #         return jsonify({'message': f'Successfully inserted {len(records)} contacts.'}), 201
# #     except Exception as e:
# #         return jsonify({'error': f'Database error: {str(e)}'}), 500

# # if __name__ == '__main__':
# #     app.run(debug=True)


# from flask import Flask, request, jsonify
# import csv
# from io import StringIO
# import os
# import uuid
# from datetime import datetime
# import psycopg2
# from psycopg2.extras import execute_values

# app = Flask(__name__)

# # --- Configuration ---
# DB_HOST = os.environ.get('DB_HOST', 'aws-0-us-east-1.pooler.supabase.com')
# DB_PORT = os.environ.get('DB_PORT', '6543')
# DB_NAME = os.environ.get('DB_NAME', 'postgres')
# DB_USER = os.environ.get('DB_USER', 'postgres.hdesapbxgxecjzfuggjo')
# DB_PASSWORD = os.environ.get('DB_PASSWORD', '0oocbYXnrWknAbt7')

# def get_db_connection():
#     """
#     Establishes and returns a connection to the PostgreSQL database.
#     """
#     conn = psycopg2.connect(
#         host=DB_HOST,
#         port=DB_PORT,
#         dbname=DB_NAME,
#         user=DB_USER,
#         password=DB_PASSWORD
#     )
#     return conn

# # --- Define the expected CSV columns ---
# REQUIRED_COLUMNS = [
#     'FirstName', 'LastName', 'Companies', 'Title', 'Emails', 'PhoneNumbers',
#     'Addresses', 'Sites', 'InstantMessageHandles', 'FullName', 'Birthday',
#     'Location', 'BookmarkedAt', 'Profiles'
# ]

# @app.route('/upload/<user_id>', methods=['POST'])
# def upload_csv(user_id):
#     """
#     Endpoint to upload a CSV file and insert contacts for the given user_id into the database.
    
#     If any contact records already exist for the user_id, new records will be filtered
#     based on the PhoneNumbers column. If a record with the same phone number already exists,
#     that record is skipped.
    
#     If no record is found for the user_id, all contacts from the CSV are inserted.
#     """
#     # Validate that user_id is a proper UUID.
#     try:
#         uuid.UUID(user_id)
#     except ValueError:
#         return jsonify({'error': 'Invalid user_id format. Must be a UUID.'}), 400

#     # Look for file under the key "contact"
#     if 'contact' not in request.files:
#         return jsonify({'error': 'No file part in the request.'}), 400

#     file = request.files['contact']

#     # Check if a file was selected.
#     if file.filename == '':
#         return jsonify({'error': 'No file selected for uploading.'}), 400

#     # Check that the uploaded file is a CSV.
#     if not file.filename.endswith('.csv'):
#         return jsonify({'error': 'File is not a CSV file.'}), 400

#     try:
#         file_stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
#     except Exception as e:
#         return jsonify({'error': f'Error reading file: {str(e)}'}), 400

#     reader = csv.DictReader(file_stream)
#     header = reader.fieldnames

#     # Validate that the CSV has all required columns.
#     missing_columns = [col for col in REQUIRED_COLUMNS if col not in header]
#     if missing_columns:
#         return jsonify({'error': f'Missing required columns: {", ".join(missing_columns)}'}), 400

#     records = []
#     for row in reader:
#         # Parse the Birthday column into a date object, if present.
#         birthday = row.get('Birthday')
#         if birthday:
#             try:
#                 birthday = datetime.strptime(birthday, '%Y-%m-%d').date()
#             except ValueError:
#                 birthday = None
#         else:
#             birthday = None

#         # Parse the BookmarkedAt column into a datetime object, if present.
#         bookmarked_at = row.get('BookmarkedAt')
#         if bookmarked_at:
#             try:
#                 bookmarked_at = datetime.strptime(bookmarked_at, '%Y-%m-%d %H:%M:%S')
#             except ValueError:
#                 try:
#                     bookmarked_at = datetime.strptime(bookmarked_at, '%Y-%m-%d')
#                 except ValueError:
#                     bookmarked_at = None
#         else:
#             bookmarked_at = None

#         # Create a tuple of values in the order expected by the INSERT statement.
#         record = (
#             user_id,
#             row.get('FirstName'),
#             row.get('LastName'),
#             row.get('Companies'),
#             row.get('Title'),
#             row.get('Emails'),
#             row.get('PhoneNumbers'),    # Index 6: used to check uniqueness
#             row.get('Addresses'),
#             row.get('Sites'),
#             row.get('InstantMessageHandles'),
#             row.get('FullName'),
#             birthday,
#             row.get('Location'),
#             bookmarked_at,
#             row.get('Profiles'),
#         )
#         records.append(record)

#     if not records:
#         return jsonify({'error': 'No data found in CSV file.'}), 400

#     # Define the insert query. The id and CreatedAt columns are handled by the DB.
#     insert_query = """
#         INSERT INTO relyexchange.contacts (
#             user_id, FirstName, LastName, Companies, Title, Emails, PhoneNumbers,
#             Addresses, Sites, InstantMessageHandles, FullName, Birthday, Location,
#             BookmarkedAt, Profiles
#         )
#         VALUES %s
#     """

#     try:
#         conn = get_db_connection()
#         cur = conn.cursor()
        
#         # Check if any records exist for the given user_id.
#         cur.execute("SELECT PhoneNumbers FROM relyexchange.contacts WHERE user_id = %s", (user_id,))
#         existing_records = cur.fetchall()
#         print(existing_records)
        
#         if existing_records:
#             # If records exist, build a set of existing phone numbers.
#             existing_numbers = {rec[0] for rec in existing_records if rec[0]}
#             # Filter out records whose phone number is already present.
#             new_records = [r for r in records if r[6] and r[6] not in existing_numbers]
#             print(new_records)
#         else:
#             # If no records exist for the user, insert all CSV records.
#             new_records = records

#         if not new_records:
#             cur.close()
#             conn.close()
#             return jsonify({'message': 'No new contacts to insert.'}), 200

#         # Bulk insert new records.
#         execute_values(cur, insert_query, new_records)
#         conn.commit()
#         cur.close()
#         conn.close()
#         return jsonify({'message': f'Successfully inserted {len(new_records)} contacts.'}), 201
#     except Exception as e:
#         return jsonify({'error': f'Database error: {str(e)}'}), 500

# if __name__ == '__main__':
#     app.run(debug=True)
