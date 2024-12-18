# Smart Wine Label Recognition and Environment Monitoring System

## Project Overview
This is an integrated system that combines wine label recognition with environmental monitoring capabilities. The system not only identifies wine labels using Google Cloud Vision API but also monitors and analyzes the storage environment conditions to ensure optimal wine preservation.

## Core Features

### Wine Label Recognition
- Real-time camera feed with front/back camera switching
- High-precision text recognition using Google Cloud Vision API
- Automatic matching with wine database
- Display of detailed wine information and story

### Environmental Monitoring
- Real-time sensor data collection:
  * Temperature and Humidity (SHT40)
  * Light Level (VEML7700)
  * CO2 Concentration (MH-Z19E)
- Data updates every 500ms
- Historical data recording and analysis
- Environment stability evaluation

### Data Analysis
- Statistical analysis of environmental parameters
- Calculation of stability scores
- Historical data visualization
- Ideal range compliance monitoring

## Technical Architecture

### Frontend
- HTML5 for structure
- JavaScript for dynamic interactions
- CSS for styling and animations
- Real-time data updates using AJAX
- Camera access using MediaDevices API

### Backend
- Flask web framework
- Google Cloud Vision API integration
- Sensor data processing
- JSON-based data persistence
- Concurrent access control

### Sensors
- SHT40: Temperature and humidity sensor
  * Temperature range: -40 to 125°C
  * Humidity range: 0-100% RH
- VEML7700: Ambient light sensor
  * Range: 0 to 120k lux
- MH-Z19E: CO2 sensor
  * Range: 0-5000ppm

### Data Storage
- JSON file-based storage system
- Separate files for each wine's environmental history
- Rolling storage with 30 most recent records
- Automatic cleanup of old records

## Installation

### Hardware Requirements
- Raspberry Pi 2W
- SHT40 sensor
- VEML7700 sensor
- MH-Z19E sensor
- Camera module

### Software Requirements
- Python 3.7+
- Google Cloud Platform account
- Required Python packages:
  ```
  flask
  google-cloud-vision
  numpy
  python-dotenv
  smbus2
  pyserial
  ```

### Setup Steps
1. Clone the repository
```bash
git clone [repository URL]
cd wine-monitoring-system
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Configure environment variables
```bash
# Create .env file
GOOGLE_CLOUD_CREDENTIALS_PATH=/path/to/credentials.json
```

4. Configure sensor connections
```bash
# I2C configuration for SHT40 and VEML7700
# Serial configuration for MH-Z19E
```

## System Architecture

### Data Flow
1. Image Capture → Google Vision API → Wine Database Matching
2. Sensor Data Collection → Real-time Display
3. Environmental Data → Statistical Analysis → Stability Evaluation

### Storage Structure
```
sensor_data/
  ├── wine1_env_history.json
  ├── wine2_env_history.json
  └── ...
```

### Ideal Environmental Ranges
- Temperature: 10-15°C
- Humidity: 50-80%
- Light: 0-100 lux
- CO2: 400-1000 ppm

## API Endpoints

### Wine Analysis
```
POST /analyze
Request: {
    "image": "base64_encoded_image"
}
Response: {
    "wineInfo": {...},
    "sensorData": {...},
    "historicalData": {...},
    "consistencyEval": {...}
}
```

### Sensor Data
```
GET /get_sensor_data
Response: {
    "sht40": {"temperature": float, "humidity": float},
    "veml7700": {"lux": float},
    "mh_z19e": {"co2": int}
}
```

## Environment Stability Evaluation

### Stability Score Calculation
- Based on standard deviation of measurements
- Scaled to 0-100 range
- Considers ideal range compliance
- Updates with each new measurement

### Consistency Metrics
- Stability score for each parameter
- Percentage within ideal range
- Visual indicators for status
- Trend analysis

## Error Handling
- Camera access errors
- Sensor reading failures
- Data storage issues
- API communication errors

## Performance Considerations
- 500ms sensor update interval
- 30 record history limit
- File locking for concurrent access
- Efficient data structure design

## Security Features
- Input validation
- Error logging
- File access control
- Secure API communication

## Future Enhancements
- Database integration
- Mobile app development
- Cloud data backup
- Advanced analytics features

## Contributing
Contributions are welcome! Please read our contributing guidelines and submit pull requests to our repository.

## License
MIT License

## Support
For support and queries:
- Create an issue in the repository
- Contact the development team
- Check the documentation

## Acknowledgments
- Google Cloud Platform
- Flask Framework
- Sensor manufacturers
- Open source community