import os
import requests  # We will use this library
from flask import Flask, jsonify, request
from flask_cors import CORS
from google.cloud import vision

app = Flask(__name__)
CORS(app)

# --- Google Vision Credentials (Stays the same) ---
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google-credentials.json'

@app.route('/api/translate', methods=['POST'])
def translate_endpoint():
    # --- Step 1: Perform OCR (This part is unchanged) ---
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']
    image_content = file.read()

    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_content)
    response = client.text_detection(image=image)
    texts = response.text_annotations

    if texts:
        detected_text = texts[0].description
    else:
        return jsonify({"original": "No text found in image.", "translation": ""})

    # --- Step 2: Translate Text using LibreTranslate ---
    try:
        # This is the public API endpoint for LibreTranslate
        url = "https://translate.fedilab.app/translate"
        
        payload = {
            "q": detected_text,
            "source": "en",  # Assuming original text is English
            "target": "de",  # Translating to German
            "format": "text"
        }
        headers = {"Content-Type": "application/json"}

        # Make the API call to LibreTranslate
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  # This will raise an error for bad responses

        # Extract the translation from the response
        translated_text = response.json().get("translatedText", "Translation failed.")

    except requests.exceptions.RequestException as e:
        # Handle cases where the translation service might be down
        print(f"Error calling translation API: {e}")
        return jsonify({"error": "Translation service is currently unavailable."}), 503

    # --- Step 3: Return the final result ---
    return jsonify({
        "original": detected_text,
        "translation": translated_text
    })

if __name__ == '__main__':
    app.run(debug=True, port=5001)