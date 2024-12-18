from flask import Flask, render_template, request, jsonify,send_from_directory,abort
from google.cloud import vision
from google.api_core import exceptions
import base64
import io
import os
from dotenv import load_dotenv
import json
import re
import logging
import time
from smbus2 import SMBus, i2c_msg
import serial
import numpy as np
from datetime import datetime
import asyncio
from threading import Lock

logging.basicConfig(level=logging.DEBUG)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure Google Cloud credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.getenv('GOOGLE_CLOUD_CREDENTIALS_PATH')

# Initialize Vision client
vision_client = vision.ImageAnnotatorClient()

# Mock wine database - in production, this would be a real database
WINE_DATABASE = {
    "Les Legendes Sauternes": {
        "name": "Les Legendes",
        "producer": "Domaines Barons de Rothschild Lafite",
        "region": "Sauternes",
        "vintage": "2019",
        "varietal": "Semillon, Sauvignon Blanc",
        "description": "A captivating sweet white wine from the renowned Sauternes appellation.",
        "folder_name": "wine1"
    },
    "Château Lafite Rothschild": {
        "name": "Château Lafite Rothschild",
        "producer": "Château Lafite Rothschild",
        "region": "Pauillac",
        "vintage": "2022",
        "varietal": "Cabernet Sauvignon Blend",
        "description": "MIS EN BOUTEILLE AU CHATEAU",
        "folder_name": "wine2"
    },
    "William Fevre Chablis": {
        "name": "William Fevre",
        "producer": "William Fevre",
        "region": "CHABLIS - FRANCE",
        "vintage": "2023",
        "varietal": "Chardonnay",
        "description": "A pure expression of Chardonnay from the renowned Chablis region.",
        "folder_name": "wine3"
    },
    "Jardins d'Aussières": {
        "name": "Jardins d'Aussières",
        "producer": "Domaines Barons de Rothschild",
        "region": "Corbières",
        "vintage": "2018",
        "varietal": "Grenache, Syrah, Mourvèdre",
        "description": "A harmonious blend capturing the essence of the Languedoc terroir.",
        "folder_name": "wine4"
    },
    "Carmes de Rieussec": {
        "name": "Carmes de Rieussec",
        "producer": "Château Rieussec",
        "region": "Sauternes",
        "vintage": "2022",
        "varietal": "Semillon, Sauvignon Blanc",
        "description": "A refined and elegant sweet wine from the prestigious Sauternes appellation.",
        "folder_name": "wine5"
    }
}

# Add sensor configurations
DEV_ADDR_SHT4X = 0x44
DEV_ADDR_VEML7700 = 0x10
BUS_ADDRESS = 1
MH_Z19E_UART_PORT = '/dev/ttyS0'
MH_Z19E_BAUDRATE = 9600
MH_Z19E_CMD_READ = b'\xFF\x01\x86\x00\x00\x00\x00\x00\x79'

# Initialize I2C bus and serial port
bus = SMBus(BUS_ADDRESS)
serial_port = serial.Serial(MH_Z19E_UART_PORT, MH_Z19E_BAUDRATE, timeout=1)

# Add VEML7700 registers
als_conf_0 = 0x00
als_WH = 0x01
als_WL = 0x02
pow_sav = 0x03
als = 0x04

confValues = [0x00, 0x13]
interrupt_high = [0x00, 0x00]
interrupt_low = [0x00, 0x00]
power_save_mode = [0x00, 0x00]

# Add sensor functions from AP30023 project
def i2c_write(i2c_addr, command):
    with SMBus(BUS_ADDRESS) as bus:
        bus.write_byte(i2c_addr, command)

def i2c_read(i2c_addr, number_of_bytes):
    with SMBus(BUS_ADDRESS) as bus:
        msg = i2c_msg.read(i2c_addr, number_of_bytes)
        bus.i2c_rdwr(msg)
        return list(msg)

def init_veml7700():
    bus.write_i2c_block_data(DEV_ADDR_VEML7700, als_conf_0, confValues)
    bus.write_i2c_block_data(DEV_ADDR_VEML7700, als_WH, interrupt_high)
    bus.write_i2c_block_data(DEV_ADDR_VEML7700, als_WL, interrupt_low)
    bus.write_i2c_block_data(DEV_ADDR_VEML7700, pow_sav, power_save_mode)

def gen_sht4x():
    try:
        i2c_write(i2c_addr=DEV_ADDR_SHT4X, command=0xFD)
        time.sleep(0.01)
        
        rx_bytes = i2c_read(i2c_addr=DEV_ADDR_SHT4X, number_of_bytes=6)
        
        t_ticks = (rx_bytes[0] << 8) | rx_bytes[1]
        rh_ticks = (rx_bytes[3] << 8) | rx_bytes[4]
        
        t_degC = -45 + 175 * t_ticks / 65535
        rh_pRH = -6 + 125 * rh_ticks / 65535
        rh_pRH = max(0, min(100, rh_pRH))

        return t_degC, rh_pRH
    except Exception as e:
        logging.error(f"Error reading SHT40: {e}")
        return None, None

def gen_7700():
    try:
        init_veml7700()
        time.sleep(0.04)
        raw = bus.read_word_data(DEV_ADDR_VEML7700, als)
        gain = 1.8432
        lux = raw * gain
        return round(lux, 1)
    except Exception as e:
        logging.error(f"Error reading VEML7700: {e}")
        return None

def read_mhz19e():
    try:
        serial_port.write(MH_Z19E_CMD_READ)
        response = serial_port.read(9)

        if len(response) == 9 and response[0] == 0xFF and response[1] == 0x86:
            co2 = (response[2] << 8) | response[3]
            return co2
        return None
    except Exception as e:
        logging.error(f"Error reading MH-Z19E: {e}")
        return None

def process_image(image_data):
    """Process the image using Google Cloud Vision API"""
    logging.debug("Starting image processing")

    try:
        # Check and remove Data URL prefix
        if 'data:image/' in image_data:
            logging.debug("Removing data URL prefix")
            image_data = image_data.split('base64,')[1]

        # Decode base64 encoded image
        image_bytes = base64.b64decode(image_data)
        logging.debug("Image decoded successfully")

        # Create Image object
        image = vision.Image(content=image_bytes)

        # Perform text detection
        logging.debug("Performing text detection")
        response = vision_client.text_detection(image=image)
        texts = response.text_annotations

        if not texts:
            logging.info("No text detected in image")
            return {"status": "No text detected", "text": None}

        # Get all detected text
        detected_text = texts[0].description
        logging.info("Text detected successfully")
        return {"status": "Success", "text": detected_text}

    except base64.binascii.Error as b64_error:
        logging.error(f"Base64 decoding error: {str(b64_error)}")
        return {"status": "Base64 decoding error", "text": None}

    except exceptions.GoogleAPICallError as api_error:
        logging.error(f"Google API call error: {str(api_error)}")
        return {"status": "Google API call error", "text": None}

    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return {"status": "Unexpected error", "text": None}


def clean_text(text):
    """Clean and standardize detected text"""
    # Remove line breaks
    text = ' '.join(text.split())
    # Remove special characters while preserving case
    text = re.sub(r'[^\w\s]', ' ', text)
    return text


def calculate_match_score(wine_info, cleaned_text):
    """Calculate matching score"""
    score = 0

    # Case-insensitive comparison while preserving original text
    cleaned_text_lower = cleaned_text.lower()

    # Check wine name match
    if wine_info['name'].lower() in cleaned_text_lower:
        score += 3

    # Check vintage match (keep case sensitive for years)
    if wine_info['vintage'] in cleaned_text:
        score += 2

    # Check region match
    if wine_info['region'].lower() in cleaned_text_lower:
        score += 2

    # Check producer match
    if wine_info['producer'].lower() in cleaned_text_lower:
        score += 2

    return score


def find_matching_wine(text):
    """Find matching wine using improved matching logic"""
    logging.debug(f"Received text: {text} of type {type(text)}")

    if not text or not isinstance(text, str):
        return None

    # Clean detected text
    cleaned_text = clean_text(text)

    best_match = None
    highest_score = 0

    # Score each wine
    for wine_name, wine_info in WINE_DATABASE.items():
        current_score = calculate_match_score(wine_info, cleaned_text)

        # Update best match
        if current_score > highest_score:
            highest_score = current_score
            best_match = wine_info

    # Require minimum matching score for accuracy
    if highest_score >= 3:
        return best_match

    return None


def get_story_content(folder_name):
    """Read story content from txt file"""
    try:
        story_path = os.path.join('Stories', folder_name, f'{folder_name}.txt')
        if not os.path.exists(story_path):
            logging.error(f"Story file not found: {story_path}")
            return None

        with open(story_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logging.error(f"Error reading story file: {str(e)}")
        return None


def get_image_path(folder_name):
    """Get the relative path to the wine image"""
    return f'/Stories/{folder_name}/{folder_name}.png'


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/Stories/<path:filename>')
def serve_story_image(filename):
    stories_dir = os.path.join(app.root_path, 'Stories')
    try:
        return send_from_directory(stories_dir, filename)
    except FileNotFoundError:
        abort(404, description="Image not found")

# Add constants for historical data
HISTORY_SIZE = 30  # Store 30 records
SAVE_INTERVAL = 300  # Save every 5 minutes
DATA_DIR = 'sensor_data'  # Create a dedicated data directory
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    
DATA_FILE_TEMPLATE = os.path.join(DATA_DIR, '{folder_name}_env_history.json')

# Add file lock
file_lock = Lock()

# Add ideal range constants
IDEAL_RANGES = {
    'temperature': {'min': 10, 'max': 15, 'unit': '°C'},  # Ideal temperature for wine storage
    'humidity': {'min': 50, 'max': 80, 'unit': '%'},      # Ideal humidity range
    'lux': {'min': 0, 'max': 100, 'unit': 'lux'},        # Avoid strong light
    'co2': {'min': 400, 'max': 1000, 'unit': 'ppm'}      # Normal CO2 range
}

class EnvironmentHistory:
    def __init__(self, folder_name):
        self.file_path = DATA_FILE_TEMPLATE.format(folder_name=folder_name)
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self.history = self._load_history()
        
    def _load_history(self):
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logging.error(f"Error loading history from {self.file_path}: {e}")
            return []
            
    def add_record(self, sensor_data):
        try:
            with file_lock:
                record = {
                    'timestamp': datetime.now().isoformat(),
                    'temperature': sensor_data['sht40']['temperature'],
                    'humidity': sensor_data['sht40']['humidity'],
                    'lux': sensor_data['veml7700']['lux'],
                    'co2': sensor_data['mh_z19e']['co2']
                }
                
                self.history.append(record)
                if len(self.history) > HISTORY_SIZE:
                    self.history.pop(0)  # Remove oldest record when limit reached
                    
                # Ensure directory exists before writing
                os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
                with open(self.file_path, 'w') as f:
                    json.dump(self.history, f)
                    
        except Exception as e:
            logging.error(f"Error adding record to {self.file_path}: {e}")
            
    def get_statistics(self):
        if not self.history:
            return None
            
        try:
            # Convert history to numpy arrays for efficient calculation
            temp_data = np.array([r['temperature'] for r in self.history if r['temperature'] is not None])
            humidity_data = np.array([r['humidity'] for r in self.history if r['humidity'] is not None])
            lux_data = np.array([r['lux'] for r in self.history if r['lux'] is not None])
            co2_data = np.array([r['co2'] for r in self.history if r['co2'] is not None])
            
            stats = {
                'temperature': {
                    'avg': float(np.mean(temp_data)) if len(temp_data) > 0 else None,
                    'std': float(np.std(temp_data)) if len(temp_data) > 0 else None,
                    'min': float(np.min(temp_data)) if len(temp_data) > 0 else None,
                    'max': float(np.max(temp_data)) if len(temp_data) > 0 else None
                },
                'humidity': {
                    'avg': float(np.mean(humidity_data)) if len(humidity_data) > 0 else None,
                    'std': float(np.std(humidity_data)) if len(humidity_data) > 0 else None,
                    'min': float(np.min(humidity_data)) if len(humidity_data) > 0 else None,
                    'max': float(np.max(humidity_data)) if len(humidity_data) > 0 else None
                },
                'lux': {
                    'avg': float(np.mean(lux_data)) if len(lux_data) > 0 else None,
                    'std': float(np.std(lux_data)) if len(lux_data) > 0 else None,
                    'min': float(np.min(lux_data)) if len(lux_data) > 0 else None,
                    'max': float(np.max(lux_data)) if len(lux_data) > 0 else None
                },
                'co2': {
                    'avg': float(np.mean(co2_data)) if len(co2_data) > 0 else None,
                    'std': float(np.std(co2_data)) if len(co2_data) > 0 else None,
                    'min': float(np.min(co2_data)) if len(co2_data) > 0 else None,
                    'max': float(np.max(co2_data)) if len(co2_data) > 0 else None
                }
            }
            return stats
            
        except Exception as e:
            logging.error(f"Error calculating statistics: {e}")
            return None

    def evaluate_consistency(self):
        """Evaluate environmental consistency"""
        if not self.history:
            return None
            
        try:
            stats = self.get_statistics()
            evaluation = {}
            
            for param in ['temperature', 'humidity', 'lux', 'co2']:
                if stats[param]['avg'] is not None:
                    ideal_range = IDEAL_RANGES[param]
                    avg = stats[param]['avg']
                    std = stats[param]['std']
                    
                    # Calculate stability score (0-100)
                    # Lower std deviation = higher score
                    range_size = ideal_range['max'] - ideal_range['min']
                    stability = max(0, min(100, 100 * (1 - std/range_size)))
                    
                    # Check if average is within ideal range
                    in_range = ideal_range['min'] <= avg <= ideal_range['max']
                    
                    # Calculate percentage of readings within range
                    values = [r[param] for r in self.history if r[param] is not None]
                    within_range = sum(1 for v in values if ideal_range['min'] <= v <= ideal_range['max'])
                    range_percentage = (within_range / len(values)) * 100 if values else 0
                    
                    evaluation[param] = {
                        'stability_score': round(stability, 1),
                        'in_range': in_range,
                        'range_percentage': round(range_percentage, 1),
                        'ideal_range': ideal_range
                    }
                    
            return evaluation
            
        except Exception as e:
            logging.error(f"Error evaluating consistency: {e}")
            return None

# Modify analyze route to include historical data
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

        # Get story content and image path
        folder_name = wine_info['folder_name']
        story_content = get_story_content(folder_name)
        image_path = get_image_path(folder_name)

        if not story_content:
            return jsonify({'error': 'Story content not found'}), 404

        # Get current sensor data
        sensor_data = get_sensor_data()

        # Initialize environment history and add current data
        env_history = EnvironmentHistory(folder_name)
        if sensor_data:
            env_history.add_record(sensor_data)
        
        # Get historical statistics
        history_stats = env_history.get_statistics()

        # Get historical statistics and consistency evaluation
        consistency_eval = env_history.evaluate_consistency()

        # Return combined response
        return jsonify({
            'wineInfo': wine_info,
            'imagePath': image_path,
            'story': story_content,
            'sensorData': sensor_data,
            'historicalData': history_stats,
            'consistencyEval': consistency_eval
        })

    except Exception as e:
        logging.error(f"Error analyzing image: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


def get_sensor_data():
    try:
        # Get sensor readings
        temperature, humidity = gen_sht4x()
        lux = gen_7700()
        co2 = read_mhz19e()
        
        return {
            'sht40': {
                'temperature': round(temperature, 2) if temperature is not None else None,
                'humidity': round(humidity, 2) if humidity is not None else None
            },
            'veml7700': {
                'lux': lux
            },
            'mh_z19e': {
                'co2': co2
            }
        }
    except Exception as e:
        logging.error(f"Error getting sensor data: {e}")
        return None

# Add new endpoint for sensor data
@app.route('/get_sensor_data', methods=['GET'])
def get_sensor_data_endpoint():
    try:
        sensor_data = get_sensor_data()
        return jsonify(sensor_data)
    except Exception as e:
        logging.error(f"Error getting sensor data: {e}")
        return jsonify({'error': 'Failed to get sensor data'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
