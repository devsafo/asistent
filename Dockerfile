# Python-ning rasmiy versiyasini olamiz
FROM python:3.12-slim

# Tizimga ffmpeg-ni o'rnatamiz (pydub uchun zarur)
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Ishchi katalogni belgilaymiz
WORKDIR /app

# Kutubxonalarni o'rnatamiz
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Barcha kodlarni nusxalaymiz
COPY . .

# Static va Temp papkalarni yaratamiz
RUN mkdir -p static temp_audio

# Serverni ishga tushiramiz
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
