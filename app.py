from flask import Flask, render_template, request, jsonify
from google.cloud import vision
import base64
import io
import os
from dotenv import load_dotenv
import json
import re
import logging

logging.basicConfig(level=logging.DEBUG)

#Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure Google Cloud credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.getenv('GOOGLE_CLOUD_CREDENTIALS_PATH')

# Initialize Vision client
vision_client = vision.ImageAnnotatorClient()

# Mock wine database - in production, this would be a real database
WINE_DATABASE = {
    "Château Margaux": {
        "name": "Château Margaux",
        "producer": "Château Margaux",
        "region": "Bordeaux, France",
        "vintage": "2015",
        "varietal": "Cabernet Sauvignon Blend",
        "description": "First Growth Bordeaux with exceptional complexity and elegance."
    },
    "Opus One": {
        "name": "Opus One",
        "producer": "Opus One Winery",
        "region": "Napa Valley, USA",
        "vintage": "2018",
        "varietal": "Cabernet Sauvignon Blend",
        "description": "Premium Napa Valley wine, collaboration between Robert Mondavi and Baron Philippe de Rothschild."
    }
}


def process_image(image_data):
    """Process the image using Google Cloud Vision API"""
    logging.debug("Starting image processing")

    try:
        # 检查并移除 Data URL 前缀
        if 'data:image/' in image_data:
            logging.debug("Removing data URL prefix")
            image_data = image_data.split('base64,')[1]

        # 解码 base64编码的图像
        image_bytes = base64.b64decode(image_data)
        logging.debug("Image decoded successfully")

        # 创建 Image 对象
        image = vision.Image(content=image_bytes)

        # 执行文字检测
        logging.debug("Performing text detection")
        response = vision_client.text_detection(image=image)
        texts = response.text_annotations

        if not texts:
            logging.info("No text detected in image")
            return {"status": "No text detected", "text": None}

        # 获取所有检测到的文本
        detected_text = texts[0].description
        logging.info("Text detected successfully")
        return {"status": "Success", "text": detected_text}

    except base64.binascii.Error as b64_error:
        logging.error(f"Base64 decoding error: {str(b64_error)}")
        return {"status": "Base64 decoding error", "text": None}

    except vision.exceptions.GoogleAPICallError as api_error:
        logging.error(f"Google API call error: {str(api_error)}")
        return {"status": "Google API call error", "text": None}

    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return {"status": "Unexpected error", "text": None}


def find_matching_wine(text):
    """Find matching wine in database based on detected text"""
    logging.debug(f"Received text: {text} of type {type(text)}")

    if not text:
        return None

    if isinstance(text, dict):
        logging.error("Error: 'text' is a dictionary when it should be a string.")
        # Handle this error appropriately, perhaps by extracting a necessary value
        return None

    # Proceed with the original logic assuming text is now correctly a string
    text = text.lower()

    for wine_name, wine_info in WINE_DATABASE.items():
        if wine_name.lower() in text:
            return wine_info

    return None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        image_data = data.get('image')

        if not image_data:
            return jsonify({'error': 'No image data provided'}), 400

        # Process image with Google Cloud Vision
        detected_data = process_image(image_data)
        detected_text = detected_data.get('text')

        if detected_data['status'] != 'Success' or not detected_text:
            return jsonify({'error': detected_data['status']}), 404

        # Find matching wine
        wine_info = find_matching_wine(detected_text)

        if not wine_info:
            return jsonify({'error': 'No matching wine found'}), 404

        return jsonify({'wineInfo': wine_info})

    except Exception as e:
        logging.error(f"Error analyzing image: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
