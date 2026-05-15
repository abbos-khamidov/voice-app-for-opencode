# Windows Version

C# WinForms version of the text reader app.

## Requirements

- Windows 10 or newer
- .NET 8 SDK
- Python with `edge-tts` installed:

```powershell
py -m pip install edge-tts
```

The app calls the `edge-tts` command-line tool to generate MP3 chunks, then plays them through Windows Media Player.

## Run

```powershell
cd windows\VoiceReader.Windows
dotnet run
```

## Notes

- Playback starts after the first generated chunk.
- The selected voice is kept across mixed-language text.
- Speed can be changed while playback is running; the current playback rate updates immediately and future chunks are generated with the new speed.
