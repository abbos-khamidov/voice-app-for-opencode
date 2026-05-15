# Text Reader App

MVP macOS desktop app that reads pasted text aloud.

## Features

- PyQt6 desktop window
- Large pasteable text area
- Play and Stop buttons
- Voice selector with English and Russian Edge TTS voices, including more natural English multilingual voices
- Live speed control from 0.50x to 2.00x
- Tone selector: Natural, Lively, Confident, Soft
- Generates `speech.mp3` with `edge-tts`
- Plays generated MP3 with `pygame`
- Basic status and error messages
- Skips symbols such as dashes and asterisks before speech generation
- Keeps the same selected voice across mixed-language text
- Starts playback after the first generated chunk while the rest is generated in the background

`pygame-ce` is used in `requirements.txt`; it imports as `pygame` and provides working mixer support on current macOS/Python versions.

## Setup on macOS

```bash
cd text-reader-app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

The app requires an internet connection when pressing Play because Edge TTS generates speech online.

## Windows Version

A C# WinForms version is available in `windows/VoiceReader.Windows`.

```powershell
cd windows\VoiceReader.Windows
dotnet run
```

See `windows/README.md` for Windows prerequisites.

## Docker

Docker support is available for containerized MP3 generation through a CLI, not for the desktop GUI.

```bash
docker build -f docker/Dockerfile -t text-reader-tts .
```

See `docker/README.md` for usage.

## Usage

1. Paste text into the text area.
2. Choose a voice.
3. Choose a speed, or change it while playback is running.
4. Click Play.
5. Click Stop to stop playback.
