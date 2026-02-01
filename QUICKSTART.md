# 🌙 Nocturnal Eye - Quick Start Guide

## ⚡ 5-Minute Setup

### 1. Prerequisites
- Raspberry Pi 4 (2GB+ RAM)
- Camera connected to Raspberry Pi
- TerrariumPI running and streaming video
- Python 3.9+

### 2. Installation

```bash
# Navigate to the project
cd ~/Desktop/nocturnal-eye

# Activate virtual environment
source venv/bin/activate

# Verify dependencies installed
pip list | grep -E "opencv|numpy|flask"
```

### 3. Configuration

Edit `config.yaml`:

```yaml
# Update stream URL to match your TerrariumPI setup
stream:
  url: "http://localhost:8090/webcam/1/stream.m3u8"  # ← CHANGE THIS

# Define your zones (feeding, basking, hiding spots)
zones:
  - name: "Feeding Station"
    x: 100
    y: 200
    radius: 50
```

### 4. Run the Application

**Terminal 1 - Main Service:**
```bash
cd ~/Desktop/nocturnal-eye
source venv/bin/activate
python main.py
```

**Terminal 2 - API Server:**
```bash
cd ~/Desktop/nocturnal-eye
source venv/bin/activate
python -m src.api.app
```

### 5. Access the API

```bash
# Health check
curl http://localhost:5001/api/health

# Today's activity
curl http://localhost:5001/api/activity/today | jq

# Weekly stats
curl http://localhost:5001/api/stats/weekly | jq

# Get heatmap image
curl http://localhost:5001/api/heatmap?date=2026-01-31 > today_heatmap.png
```

---

## 🧪 Test Without Camera

Want to test before connecting your camera?

```bash
# Run component tests
python test_components.py

# Run API tests
python test_api.py

# Both show all functionality working
```

---

## 📁 Project Structure

```
nocturnal-eye/
├── main.py                    # Main application
├── config.yaml               # Configuration
├── requirements.txt          # Dependencies
├── test_components.py        # Component tests
├── test_api.py              # API tests
├── src/
│   ├── stream_consumer.py   # HLS stream reader
│   ├── motion_detector.py   # Motion detection
│   ├── database.py          # SQLite database
│   ├── tracker.py           # Object tracking
│   ├── visualizer.py        # Heatmap generation
│   └── api/
│       └── app.py           # Flask REST API
├── data/                     # Databases
├── logs/                     # Application logs
└── static/heatmaps/         # Generated heatmaps
```

---

## 🔧 Configuration Tuning

### Sensitivity Issues?

**Too many false positives:**
```yaml
motion:
  sensitivity: 20  # Increase value
  min_area: 1500  # Increase minimum size
```

**Missing detections:**
```yaml
motion:
  sensitivity: 12  # Decrease value
  min_area: 800   # Decrease minimum size
```

### Camera Not Found?

```bash
# Check if TerrariumPI stream is running
curl -v http://localhost:8090/webcam/1/stream.m3u8

# Test with ffplay
ffplay http://localhost:8090/webcam/1/stream.m3u8
```

---

## 📊 Understanding the Output

### Main.py Output
```
🌙 Nocturnal Eye starting up...
✓ Connected to video stream
🦎 Active: 2 gecko(s) detected
📊 Statistics:
  Frames: 1024
  Motions: 156
  Active tracks: 1
  Database events: 4532
```

### API Responses

**Health Check:**
```json
{
  "status": "healthy",
  "database": "connected",
  "stats": {
    "total_events": 4532,
    "database_size_mb": 1.2
  }
}
```

**Activity Summary:**
```json
{
  "summary": {
    "date": "2026-01-31",
    "total_events": 156,
    "center_of_activity": {"x": 320, "y": 240},
    "first_activity": "2026-01-31 20:15:30",
    "last_activity": "2026-01-31 23:45:12"
  },
  "hourly_distribution": {
    0: 8, 1: 12, 2: 15, ...
  }
}
```

---

## 🚀 Production Deployment

### Install as Systemd Service

```bash
# Copy service files
sudo cp nocturnal-eye.service /etc/systemd/system/
sudo cp nocturnal-eye-api.service /etc/systemd/system/

# Enable services
sudo systemctl enable nocturnal-eye
sudo systemctl enable nocturnal-eye-api

# Start services
sudo systemctl start nocturnal-eye
sudo systemctl start nocturnal-eye-api

# Check status
sudo systemctl status nocturnal-eye
sudo systemctl status nocturnal-eye-api

# View logs
journalctl -u nocturnal-eye -f
journalctl -u nocturnal-eye-api -f
```

---

## 🐛 Troubleshooting

### "Connection refused" errors
- Ensure TerrariumPI is running: `sudo systemctl status terrariumpi`
- Check camera is connected: `vcgencmd get_camera`
- Verify stream URL in config.yaml

### High CPU usage
- Reduce fps_target in config.yaml (try 1)
- Enable region_of_interest to analyze smaller area
- Disable shadow detection if not needed

### Database errors
- Reset database: `rm data/gecko_activity.db`
- Check disk space: `df -h`
- Verify write permissions: `ls -l data/`

### API not responding
- Check if Flask app started: `netstat -an | grep 5001`
- Look for errors: `tail logs/nocturnal_eye.log`
- Try restarting: `sudo systemctl restart nocturnal-eye-api`

---

## 📚 Next Steps

- **Add More Zones**: Define additional zones in config.yaml
- **Customize Sensitivity**: Adjust motion detection for your setup
- **Schedule Monitoring**: Set specific hours in config.yaml
- **Backup Data**: Copy data/ directory regularly
- **Monitor Trends**: Track weekly activity patterns via API

---

## 🆘 Getting Help

**Check Logs:**
```bash
tail -f logs/nocturnal_eye.log
```

**Test Components:**
```bash
python test_components.py
```

**Test API:**
```bash
python test_api.py
```

**Run in Debug Mode:**
```bash
python main.py --debug
```

---

## 💡 Tips & Tricks

### Record sample video for testing
```bash
# Get first 5 minutes of stream
ffmpeg -i http://localhost:8090/webcam/1/stream.m3u8 -t 300 -c copy sample.mp4

# Test with sample
python main.py --input sample.mp4
```

### Export activity data
```bash
# Get all events as JSON
curl http://localhost:5001/api/events/latest?limit=1000 | jq > activity.json
```

### Generate heatmap report
```bash
# Create heatmaps for last 7 days
for i in {0..6}; do
  DATE=$(date -d "-$i days" +%Y-%m-%d)
  curl http://localhost:5001/api/heatmap?date=$DATE > heatmap_${DATE}.png
done
```

---

## 🎓 Learning Resources

- **Strategy Document**: [docs/GECKO_TRACKING_STRATEGY.md](../TerrariumPI/docs/GECKO_TRACKING_STRATEGY.md)
- **Full README**: [README.md](README.md)
- **Configuration**: [config.yaml](config.yaml)

---

**Ready to track your gecko? 🦎 Connect your camera and let's go!**

Questions? Check the logs: `tail -f logs/nocturnal_eye.log`
