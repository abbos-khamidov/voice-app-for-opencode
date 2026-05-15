# Docker

Docker is included for containerized TTS generation, not for the desktop GUI.

Desktop GUI/audio apps need access to the host display and audio system, which is not portable across macOS, Windows, and Linux containers. This image runs a small CLI that generates an MP3 using the same Python TTS service.

## Build

```bash
docker build -f docker/Dockerfile -t text-reader-tts .
```

## Run

```bash
docker run --rm -v "$PWD:/app/output" text-reader-tts \
  --text "Привет. Hello from Docker." \
  --voice en-US-AvaMultilingualNeural \
  --output /app/output/speech.mp3
```
