FROM python:3.12-slim

# Tizim bog'liqliklarini o'rnatish (ffmpeg STT/TTS uchun shart)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Kutubxonalarni o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Barcha kodlarni nusxalash
COPY . .

# Papkalarni yaratish
RUN mkdir -p static temp_audio

# Portni ochish (Render uchun)
EXPOSE 10000

# Serverni ishga tushirish
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
