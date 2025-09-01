import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from google.cloud import vision
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, JWTManager

# --- APP & DB CONFIGURATION ---
app = Flask(__name__)
# Configure the database (SQLite)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///translations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Configure JWT for authentication
# Change this to a random secret key
app.config['JWT_SECRET_KEY'] = 'super-secret-key-change-this'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
CORS(app)

# --- DATABASE MODELS ---


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    translations = db.relationship('Translation', backref='author', lazy=True)


class Translation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_text = db.Column(db.Text, nullable=False)
    translated_text = db.Column(db.Text, nullable=False)
    target_lang = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


# --- Google Vision Credentials (Stays the same) ---
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google-credentials.json'

# --- AUTHENTICATION ENDPOINTS ---


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    hashed_password = bcrypt.generate_password_hash(
        data['password']).decode('utf-8')
    new_user = User(email=data['email'], password=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User created successfully"}), 201


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    if user and bcrypt.check_password_hash(user.password, data['password']):
        access_token = create_access_token(identity={'email': user.email})
        return jsonify(access_token=access_token)
    return jsonify({"message": "Invalid credentials"}), 401

# --- CORE TRANSLATION ENDPOINT (Unchanged) ---


@app.route('/api/translate', methods=['POST'])
def translate_endpoint():
    # ... (All the code for file upload, OCR, and translation remains here) ...
    # ... (This function is exactly the same as before) ...
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']
    target_lang = request.form.get('target_lang', 'de')
    image_content = file.read()

    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_content)
    response = client.text_detection(image=image)
    texts = response.text_annotations

    if texts:
        detected_text = texts[0].description
    else:
        return jsonify({"original": "No text found in image.", "translation": ""})

    try:
        url = "https://translate.fedilab.app/translate"
        payload = {"q": detected_text, "source": "auto",
                   "target": target_lang, "format": "text"}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        translated_text = response.json().get("translatedText", "Translation failed.")
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Translation service is currently unavailable."}), 503

    return jsonify({
        "original": detected_text,
        "translation": translated_text,
        "target_lang": target_lang
    })

# --- NOTEBOOK ENDPOINTS (Coming soon) ---
# We will add endpoints here to save and retrieve translations.
# --- NOTEBOOK ENDPOINTS ---
@app.route('/api/translations', methods=['POST'])
@jwt_required() # This protects the route, requiring a valid token
def save_translation():
    current_user_email = get_jwt_identity()['email']
    user = User.query.filter_by(email=current_user_email).first()
    
    data = request.get_json()
    new_translation = Translation(
        original_text=data['original'],
        translated_text=data['translation'],
        target_lang=data['target_lang'],
        author=user
    )
    db.session.add(new_translation)
    db.session.commit()
    return jsonify({"message": "Translation saved successfully"}), 201

@app.route('/api/translations', methods=['GET'])
@jwt_required()
def get_translations():
    current_user_email = get_jwt_identity()['email']
    user = User.query.filter_by(email=current_user_email).first()
    
    translations_list = []
    for t in user.translations:
        translations_list.append({
            "id": t.id,
            "original": t.original_text,
            "translation": t.translated_text,
            "lang": t.target_lang
        })
    return jsonify(translations_list)

# --- MAIN EXECUTION BLOCK ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # This creates the database file and tables
    app.run(debug=True, port=5001)
