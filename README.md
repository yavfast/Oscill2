# Oscill2

A project for working with USB oscilloscope - Android application and web interface for signal acquisition and visualization.

## Description

Oscill2 is a comprehensive solution for working with USB oscilloscopes, including:

- **Android Application** - native mobile interface with chart visualization via MPAndroidChart
- **Web Interface** - web application built with FastAPI + vanilla JS for browser access
- **Communication Client** - Python library for device communication via serial port

## Project Structure

```
Oscill2/
├── app/                    # Android application (Gradle)
│   └── src/
│       └── main/
├── web_oscill/            # Web application
│   ├── main.py           # FastAPI server
│   ├── oscill_client.py  # Device communication client
│   ├── device_service.py # Device management service
│   ├── converters.py     # Data converters
│   └── static/           # Web interface static files
├── docs/                  # Documentation
│   └── protocol/         # Communication protocols
├── scripts/              # Helper scripts
├── external/             # External libraries (MPAndroidChart)
└── requirements.txt      # Python dependencies
```

## Web Application

### Features

- Connect to oscilloscope via serial port
- Real-time signal acquisition and visualization
- Parameter configuration: voltage, time, trigger, filters
- Measurements: frequency, period, Vpp, Vmax, Vmin, Vavg
- Frame history
- REST API for integration

### Running Web Application

Use the `web_oscill.sh` script for automatic startup:

```bash
./web_oscill.sh
```

The script automatically:
- Checks and creates Python venv (`.venv`)
- Installs required dependencies
- Stops previous server instances
- Starts server at `http://127.0.0.1:8000`
- Opens browser with web interface

#### Manual Launch

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start server
python -m uvicorn web_oscill.main:app --host 127.0.0.1 --port 8000
```

### API Endpoints

- `POST /api/connect` - connect to device
- `POST /api/disconnect` - disconnect
- `GET /api/status` - device status
- `GET /api/acquire/single` - acquire single frame
- `POST /api/config` - configure parameters
- `GET /api/frames` - frame history
- `POST /api/acquisition/start` - start data acquisition
- `POST /api/acquisition/stop` - stop acquisition

## Android Application

The Android application provides a native mobile interface for working with the oscilloscope.

### Build

```bash
./gradlew assembleDebug
```

### Installation

```bash
./gradlew installDebug
```

## Dependencies

### Python (web application)

- FastAPI >= 0.111.0
- Uvicorn[standard] >= 0.30.0
- PySerial >= 3.5
- NumPy >= 2.0.0
- Pydantic >= 2.8.0
- orjson >= 3.10.0

### Android

- Gradle 8.x
- Android SDK
- MPAndroidChart (included in external/)

## Documentation

Detailed documentation is located in the `docs/` directory:

- `docs/project.md` - general project description
- `docs/web_app.md` - web application documentation
- `docs/web_app_frontend.md` - frontend documentation
- `docs/protocol/` - device communication protocols

## Testing

Test scripts are located in `scripts/`:

```bash
# Connection test
python scripts/test_connect.py

# Full oscilloscope test
python scripts/oscill_test.py
```

## License

This project uses MPAndroidChart (Apache License 2.0).

## Author

yavfast

