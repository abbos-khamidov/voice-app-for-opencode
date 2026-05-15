import argparse
from pathlib import Path

from services.tts_service import TTSService


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate speech.mp3 with edge-tts.")
    parser.add_argument("--text", required=True, help="Text to read aloud.")
    parser.add_argument("--voice", default="en-US-AvaMultilingualNeural")
    parser.add_argument("--speed", default="+0%")
    parser.add_argument("--pitch", default="+0Hz")
    parser.add_argument("--volume", default="+0%")
    parser.add_argument("--output", default="speech.mp3")
    args = parser.parse_args()

    TTSService().generate_speech(
        text=args.text,
        voice=args.voice,
        speed=args.speed,
        pitch=args.pitch,
        volume=args.volume,
        output_path=Path(args.output),
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
