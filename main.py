import os
import io
import asyncio
import uuid
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
import speech_recognition as sr
from pydub import AudioSegment
import google.generativeai as genai
import edge_tts
from dotenv import load_dotenv

load_dotenv()

# Gemini sozlamalari
GENAI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GENAI_API_KEY)
# Barqaror va yangi Gemini 1.5 Flash modeli
model = genai.GenerativeModel('models/gemini-1.5-flash')

app = FastAPI()

STATIC_DIR = "static"
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

TEMP_DIR = "temp_audio"
os.makedirs(TEMP_DIR, exist_ok=True)

@app.post("/process_audio")
async def process_audio(request: Request):
    request_id = str(uuid.uuid4())
    input_filename = f"{TEMP_DIR}/{request_id}_input.wav"
    processed_filename = f"{TEMP_DIR}/{request_id}_processed.wav"
    output_filename = f"{STATIC_DIR}/response.mp3"
    
    audio_bytes = await request.body()
    with open(input_filename, "wb") as buffer:
        buffer.write(audio_bytes)
    
    print(f"\n--- Yangi so'rov ---")

    try:
        # 1. Audioni balandlatish (Pydub)
        audio = AudioSegment.from_wav(input_filename)
        normalized_audio = audio.normalize()
        final_audio = normalized_audio + 10 
        final_audio.export(processed_filename, format="wav")

        # 2. STT (Google)
        recognizer = sr.Recognizer()
        with sr.AudioFile(processed_filename) as source:
            audio_data = recognizer.record(source)
            user_text = recognizer.recognize_google(audio_data, language="uz-UZ")
            print(f"Siz dedingiz: {user_text}")

        # 3. Gemini (LLM)
        prompt = f"Sen aqlli o'zbek tilidagi ovozli yordamchisan. Foydalanuvchining quyidagi gapiga juda qisqa va do'stona javob ber (maksimal 2 ta gap): {user_text}"
        response = model.generate_content(prompt)
        bot_text = response.text.strip()
        print(f"Gemini javobi: {bot_text}")

        # 4. TTS (Ovozlashtirish)
        communicate = edge_tts.Communicate(bot_text, "uz-UZ-MadinaNeural")
        await communicate.save(output_filename)
        
        print("Audio javob tayyorlandi.")
        return PlainTextResponse("OK")

    except sr.UnknownValueError:
        print("Xato: Ovoz tushunilmadi.")
        return PlainTextResponse("Xato: Ovoz tushunilmadi", status_code=400)
    except Exception as e:
        print(f"Xato: {e}")
        return PlainTextResponse(f"Xato: {str(e)}", status_code=500)

@app.get("/")
def read_root():
    return {"status": "Online"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
