from app import create_app
from flask_cors import CORS
app = create_app()

# Allow all origins (for testing)
CORS(app)

if __name__ == '__main__':
    app.run(host="0.0.0.0",port=5000,debug=True)
    # app.run(host="127.0.0.1",port=5000,debug=True)
