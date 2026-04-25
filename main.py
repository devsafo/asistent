import os
import io
import asyncio
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
import speech_recognition as sr
from pydub import AudioSegment
import google.generativeai as genai
import edge_tts
from dotenv import load_dotenv

load_dotenv()

# Gemini sozlamalari
GENAI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GENAI_API_KEY:
    print("DIQQAT: GEMINI_API_KEY topilmadi! Render-da o'zgaruvchilarni tekshiring.")
else:
    genai.configure(api_key=GENAI_API_KEY)

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
    
    try:
        audio_bytes = await request.body()
        if not audio_bytes or len(audio_bytes) < 100:
            return PlainTextResponse("Xato: Audio bo'sh", status_code=400)

        with open(input_filename, "wb") as buffer:
            buffer.write(audio_bytes)
        
        print(f"\n--- Yangi so'rov ({len(audio_bytes)} bytes) ---")

        # 1. Audioni balandlatish
        try:
            audio = AudioSegment.from_wav(input_filename)
            normalized_audio = audio.normalize()
            final_audio = normalized_audio + 10 
            final_audio.export(processed_filename, format="wav")
        except Exception as ae:
            print(f"Audio error: {ae}")
            return PlainTextResponse(f"Xato: Audio format xato", status_code=400)

        # 2. STT (Google)
        recognizer = sr.Recognizer()
        try:
            with sr.AudioFile(processed_filename) as source:
                audio_data = recognizer.record(source)
                user_text = recognizer.recognize_google(audio_data, language="uz-UZ")
                print(f"Siz dedingiz: {user_text}")
        except sr.UnknownValueError:
            print("Xato: Ovoz tushunilmadi.")
            return PlainTextResponse("Ovoz tushunilmadi", status_code=400)
        except Exception as se:
            print(f"STT error: {se}")
            return PlainTextResponse("STT xatosi", status_code=500)

        # 3. Gemini (LLM)
        if not GENAI_API_KEY:
            return PlainTextResponse("API Key yo'q", status_code=500)
            
        prompt = f"Sen aqlli o'zbek tilidagi ovozli yordamchisan. Foydalanuvchining quyidagi gapiga juda qisqa va do'stona javob ber (maksimal 2 ta gap): {user_text}"
        response = model.generate_content(prompt)
        bot_text = response.text.strip()
        print(f"Gemini javobi: {bot_text}")

        # 4. TTS
        communicate = edge_tts.Communicate(bot_text, "uz-UZ-MadinaNeural")
        await communicate.save(output_filename)
        
        print("Javob tayyor.")
        return PlainTextResponse("OK")

    except Exception as e:
        print(f"General error: {e}")
        return PlainTextResponse(f"Server xatosi: {str(e)}", status_code=500)

@app.get("/")
def read_root():
    return {"status": "Online", "api_key_set": bool(GENAI_API_KEY)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
