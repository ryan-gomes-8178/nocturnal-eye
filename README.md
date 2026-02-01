# 🌙👁️ Nocturnal Eye

**Gecko Activity Tracking System for TerrariumPI**

Real-time motion detection, behavioral analysis, and activity insights for nocturnal reptiles using computer vision.

---

## 🦎 Features

### Phase 1: Motion Detection ✅
- HLS stream consumption from TerrariumPI
- Real-time motion detection using OpenCV
- Background subtraction with shadow removal
- Configurable sensitivity and filtering

### Phase 2: Activity Tracking ✅
- Object centroid tracking across frames
- Movement vector calculation (direction, speed)
- SQLite database for persistent storage
- Heatmap generation for spatial analysis

### Phase 3: Behavioral Analytics ✅
- Hotspot identification (frequently visited areas)
- Rest spot detection (stationary periods)
- Zone-based activity correlation (feeding, basking, hiding)
- Temporal analysis (hourly/daily patterns)
- RESTful API for data access

### Phase 4: TerrariumPI Integration (Coming Soon)
- Dashboard integration
- Real-time activity widgets
- Environmental correlation (temp/humidity)

### Phase 5: AI Insights (Future)
- Behavior classification (hunting, exploring, resting)
- Natural language activity summaries
- Anomaly detection and health monitoring

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- OpenCV
- TerrariumPI running with camera stream
- Raspberry Pi 4 (2GB+ RAM recommended)

### Installation

```bash
# Clone the repository
cd ~/Desktop
git clone <repository-url> nocturnal-eye
cd nocturnal-eye

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure
cp config.yaml config/local.yaml
nano config/local.yaml  # Edit stream URL and zones

# Initialize database
python src/database.py --init

# Run
python main.py
```

### Configuration

Edit `config.yaml` to customize:
- **Stream URL**: Point to your TerrariumPI camera
- **Motion Sensitivity**: Adjust detection threshold
- **Zones**: Define feeding, basking, and hiding areas
- **Schedule**: Set active monitoring hours (nighttime)

---

## 📊 API Endpoints

Once running, access the API at `http://localhost:5001`:

- `GET /api/health` - Service health check
- `GET /api/activity/today` - Today's activity summary
- `GET /api/activity/range?start=YYYY-MM-DD&end=YYYY-MM-DD` - Date range query
- `GET /api/heatmap?date=YYYY-MM-DD` - Generate heatmap image
- `GET /api/stats/weekly` - Weekly statistics
- `GET /api/events/latest?limit=50` - Recent motion events
- `GET /api/zones` - Zone activity breakdown

---

## 🗂️ Project Structure

```
nocturnal-eye/
├── main.py                      # Application entry point
├── config.yaml                  # Configuration file
├── requirements.txt             # Python dependencies
├── src/
│   ├── __init__.py
│   ├── stream_consumer.py      # HLS stream reader
│   ├── motion_detector.py      # OpenCV motion detection
│   ├── tracker.py              # Object tracking logic
│   ├── database.py             # SQLite operations
│   ├── visualizer.py           # Heatmap generation
│   └── api/
│       ├── __init__.py
│       ├── app.py              # Flask application
│       └── routes.py           # API endpoints
├── data/
│   └── gecko_activity.db       # Activity database
├── logs/
│   └── nocturnal_eye.log       # Application logs
├── static/
│   └── heatmaps/               # Generated heatmap images
├── config/
│   └── zones.json              # Zone definitions
└── tests/
    └── ...                     # Unit tests
```

---

## 🔧 System Requirements

### Hardware
- **Raspberry Pi 4** (2GB+ RAM)
- **Camera**: Raspberry Pi Camera Module v2/v3 or USB webcam
- **IR Illuminator**: For nighttime visibility
- **Storage**: 1GB+ free space

### Performance
- **CPU Usage**: ~15-30% (processing at 2 FPS)
- **Memory**: ~200-300MB
- **Storage**: ~100MB/week for activity data

---

## 🛠️ Development

### Running Tests
```bash
pytest tests/ -v --cov=src
```

### Debug Mode
```bash
# Enable detailed logging
python main.py --debug

# Process single video file for testing
python main.py --input tests/sample_video.mp4 --debug
```

### Creating Test Data
```bash
# Record 1-minute clip from stream for testing
ffmpeg -i http://localhost:8090/webcam/1/stream.m3u8 -t 60 -c copy tests/sample_video.mp4
```

---

## 📈 Usage Examples

### Monitor Live Activity
```bash
# Start the service
python main.py

# View logs in real-time
tail -f logs/nocturnal_eye.log
```

### Generate Heatmap
```bash
# Via API
curl http://localhost:5001/api/heatmap?date=2026-01-31 > heatmap.png

# Or using Python
python -c "from src.visualizer import HeatmapGenerator; \
           HeatmapGenerator().generate_heatmap('2026-01-31')"
```

### Query Activity Data
```bash
# Get today's summary
curl http://localhost:5001/api/activity/today | jq

# Get weekly stats
curl http://localhost:5001/api/stats/weekly | jq
```

---

## 🐛 Troubleshooting

### Stream Connection Issues
```bash
# Test stream manually
ffplay http://localhost:8090/webcam/1/stream.m3u8

# Check TerrariumPI is running
systemctl status terrariumpi.service
```

### High CPU Usage
- Reduce `fps_target` in config (try 1 FPS)
- Enable `region_of_interest` to analyze smaller area
- Increase `nice_value` to lower process priority

### False Positives
- Increase `min_area` threshold
- Enable `detect_shadows`
- Adjust `sensitivity` (higher = less sensitive)

### Database Errors
```bash
# Reset database
python src/database.py --reset

# Backup existing data
cp data/gecko_activity.db data/gecko_activity_backup.db
```

---

## 🚀 Deployment

### Systemd Service
```bash
# Copy service file
sudo cp nocturnal-eye.service /etc/systemd/system/

# Enable and start
sudo systemctl enable nocturnal-eye
sudo systemctl start nocturnal-eye

# Check status
sudo systemctl status nocturnal-eye

# View logs
journalctl -u nocturnal-eye -f
```

### Auto-start on Boot
The systemd service will automatically start after TerrariumPI is running.

---

## 📚 Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design.

**Key Design Decisions:**
1. **HLS Stream Consumer**: Non-invasive approach, no camera conflicts
2. **Independent Service**: Isolated from TerrariumPI for stability
3. **SQLite Database**: Lightweight, embedded, no external dependencies
4. **REST API**: Clean integration point for future dashboards
5. **Modular Design**: Easy to extend with new analysis modules

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

MIT License - see [LICENSE](LICENSE) for details

---

## 🙏 Acknowledgments

- **TerrariumPI**: The awesome terrarium automation platform
- **OpenCV**: Computer vision library powering motion detection
- **Flask**: Lightweight API framework

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/nocturnal-eye/issues)
- **Documentation**: [Full Docs](docs/)
- **Strategy**: See [GECKO_TRACKING_STRATEGY.md](../TerrariumPI/docs/GECKO_TRACKING_STRATEGY.md)

---

**Made with 💚 for reptile enthusiasts and their nocturnal friends!**

🦎 Happy tracking! 🌙
