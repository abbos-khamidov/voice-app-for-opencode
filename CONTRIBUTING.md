# Contributing

Thanks for helping improve Voice Reader.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Run the app:

```bash
python main.py
```

Run tests:

```bash
pytest
```

## Contribution Guidelines

- Keep changes focused and easy to review.
- Do not commit generated audio files such as `speech.mp3` or files under `tts_chunks/`.
- Keep user-facing text clear and professional.
- Add tests for text preparation, chunking, or other non-UI logic when changing behavior.
- Mention whether a change affects macOS, Windows, Docker, or all versions.

## Privacy-Sensitive Changes

Any change that sends text, audio, logs, or settings to a remote service must be documented in `PRIVACY.md` and clearly explained in the pull request.

