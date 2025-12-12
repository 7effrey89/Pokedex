# Face Recognition Feature - Setup and Usage Guide

## Overview

The face recognition feature automatically identifies users during voice conversations by comparing captured images against profile pictures stored in the `profiles_pic` directory.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `face-recognition` (1.3.0) - Face detection and recognition
- `opencv-python` (4.8.1.78) - Image processing
- `Pillow` (>= 10.2.0) - Image handling
- All other required dependencies

### 2. Add Profile Pictures

1. Take clear, front-facing photos of users
2. Save them in the `profiles_pic` directory
3. Name files as: `FirstName.jpg` or `FirstName.png`
4. Examples:
   ```
   profiles_pic/
   ├── John.jpg
   ├── Alice.png
   ├── Bob.jpeg
   └── Sarah.gif
   ```

### 3. Enable Feature

1. Start the Flask application:
   ```bash
   python app.py
   ```

2. Open the web interface in your browser

3. Click the **Tools** button (⚙️) in the header

4. Find **Face Identification** 👤 and toggle it ON

5. Click **Save Changes**

### 4. Test It Out

1. Click the **Voice** button (🎤) to start a voice conversation

2. Allow camera and microphone access when prompted

3. Start speaking - the app will:
   - Automatically capture your image
   - Compare it against profiles
   - Greet you by name if you're recognized

## How It Works

### Technical Flow

1. **Voice Detection**: When you start speaking during a voice conversation, the `speech_started` event triggers

2. **Image Capture**: 
   - Camera activates automatically (front-facing)
   - Captures a single frame
   - Converts to JPEG (quality: 0.6 for efficiency)

3. **Face Recognition**:
   - Sends image to `/api/face/identify` endpoint
   - Backend compares against known faces in `profiles_pic`
   - Returns identification result

4. **User Greeting**:
   - **First detection**: "Hello, [Name]! Nice to see you."
   - **Same person continues**: No greeting (avoids repetition)
   - **New person detected**: Greets the new person

### Rate Limiting

To prevent excessive camera access:
- **Cooldown period**: 10 seconds between identifications
- Only triggers when user starts speaking
- Automatic cleanup of camera resources

### Privacy & Security

✅ **Local Processing**: All face comparison happens on your server, not external services

✅ **No Storage**: Captured images are not saved, only used for comparison

✅ **Git Ignored**: Profile pictures are excluded from version control

✅ **Opt-in**: Feature is disabled by default, must be manually enabled

✅ **Transparent**: Clear privacy notice in tool description

## Troubleshooting

### No Greeting Appears

**Possible causes:**
- Face identification is disabled in Tools settings
- No profile pictures in `profiles_pic` directory
- Camera permission not granted
- Image quality too poor for recognition

**Solutions:**
1. Enable Face Identification in Tools
2. Add clear photos to `profiles_pic/`
3. Allow camera access in browser
4. Check browser console for errors

### Wrong Person Identified

**Possible causes:**
- Similar-looking people in profiles
- Poor lighting during capture
- Low quality profile pictures

**Solutions:**
1. Use distinct, high-quality profile photos
2. Ensure good lighting when using voice feature
3. Add multiple photos per person (different angles)

### Camera Not Activating

**Possible causes:**
- Browser doesn't support camera API
- Camera in use by another application
- Permission denied

**Solutions:**
1. Use Chrome, Edge, or Safari (recommended)
2. Close other apps using camera
3. Check browser camera permissions

### "Face not recognized"

**Possible causes:**
- Person not in `profiles_pic` directory
- Face angle too different from profile photo
- Poor image quality

**Solutions:**
1. Add a profile picture with your name
2. Face the camera directly
3. Ensure good lighting conditions

## API Reference

### Face Identification Endpoints

#### POST /api/face/identify

Identify a user from a base64-encoded image.

**Request:**
```json
{
  "image": "data:image/jpeg;base64,..."
}
```

**Response:**
```json
{
  "name": "John",
  "confidence": 0.85,
  "is_new_user": true,
  "greeting_message": "Hello, John! Nice to see you."
}
```

#### GET /api/face/status

Get current status of face recognition service.

**Response:**
```json
{
  "enabled": true,
  "profiles_loaded": 3,
  "profile_names": ["John", "Alice", "Bob"],
  "current_user": "John",
  "profiles_directory": "profiles_pic",
  "tolerance": 0.6,
  "model": "hog"
}
```

#### POST /api/face/reload

Reload profile pictures from directory (useful after adding new photos).

**Response:**
```json
{
  "message": "Profiles reloaded successfully",
  "status": { ... }
}
```

#### POST /api/face/reset

Reset the currently identified user (next identification will trigger greeting).

**Response:**
```json
{
  "message": "Current user reset successfully"
}
```

## Configuration

### Face Recognition Parameters

Edit `face_recognition_service.py` to adjust:

```python
self.tolerance = 0.6  # Lower = more strict (0.4-0.6 recommended)
self.model = "hog"    # "hog" = fast, "cnn" = accurate (requires GPU)
```

### Rate Limiting

Edit `static/js/app.js` to adjust:

```javascript
this.faceIdentificationCooldown = 10000; // milliseconds
```

### Image Quality

Edit `static/js/app.js` to adjust:

```javascript
const base64Image = canvas.toDataURL('image/jpeg', 0.6); // 0.6 = 60% quality
```

## Best Practices

### Profile Photos

✅ **DO:**
- Use clear, well-lit photos
- Front-facing angle
- Single person per photo
- Multiple photos per person (different angles)
- Keep filenames simple (FirstName.ext)

❌ **DON'T:**
- Use group photos
- Use photos with accessories (sunglasses, hats)
- Use blurry or low-resolution images
- Use photos with heavy filters

### Usage

✅ **DO:**
- Test with good lighting
- Face the camera when speaking
- Wait for greeting before continuing
- Reload profiles after adding new photos

❌ **DON'T:**
- Share profile pictures publicly
- Add photos without consent
- Use in poorly lit environments
- Expect 100% accuracy

## Performance Tips

1. **Optimize Profile Count**: More profiles = slower comparison
   - Recommended: < 20 profiles for instant results

2. **Image Quality**: Balance quality vs. performance
   - Current: 0.6 quality works well for recognition

3. **Model Choice**: 
   - `hog` model: Fast, CPU-friendly (default)
   - `cnn` model: More accurate, requires GPU

4. **Cooldown Period**: Adjust based on usage pattern
   - Longer cooldown = less camera access
   - Shorter cooldown = more frequent checks

## Security Considerations

### Data Privacy

- Profile pictures stored locally in `profiles_pic/`
- Not transmitted to external services
- Not logged or saved elsewhere
- Can be deleted at any time

### Access Control

- Feature disabled by default
- Requires explicit user enablement
- Can be toggled off anytime
- Camera access requires browser permission

### Network Security

- API endpoints check if feature is enabled
- Base64 encoding for image transmission
- No persistent storage of captured images
- Local processing only

## Support

For issues or questions:

1. Check browser console for error messages
2. Verify all dependencies are installed
3. Test with sample profile pictures
4. Review this documentation
5. Open an issue on GitHub

## License

Same license as the main Pokemon Chat application.