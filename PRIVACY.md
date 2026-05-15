# Privacy Notice

Voice Reader does not include accounts, analytics, tracking, or a project backend.

The important privacy detail is text-to-speech generation:

- When you press `Play`, the text you entered is sent to the external Text-to-Speech service used by `edge-tts`.
- Voice Reader needs an internet connection for speech generation.
- The app writes generated audio locally as `speech.mp3` and temporary chunk files under `tts_chunks/`.
- Do not paste passwords, API keys, private legal documents, medical records, financial documents, or any other sensitive content unless you understand that the text is processed by an external online TTS service.

This repository is an independent open-source project. It is not an official Microsoft product. Voice availability, generation quality, service behavior, and service access can change outside this project's control.

