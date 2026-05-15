FROM python:3.12-slim

WORKDIR /app

COPY docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services ./services
COPY docker/tts_cli.py ./tts_cli.py

ENTRYPOINT ["python", "tts_cli.py"]
