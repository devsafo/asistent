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
if GENAI_API_KEY:
    genai.configure(api_key=GENAI_API_KEY)
else:
    print("OGOHLANTIRISH: GEMINI_API_KEY muhit o'zgaruvchisi topilmadi!")

# Foydalanuvchi talab qilgan model
model = genai.GenerativeModel('gemini-2.5-flash')

app = FastAPI()

# Kataloglarni yaratish
STATIC_DIR = "static"
TEMP_DIR = "temp_audio"
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Static fayllarni ulash (javob audio fayllari uchun)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.post("/process_audio")
async def process_audio(request: Request):
    request_id = str(uuid.uuid4())
    input_filename = f"{TEMP_DIR}/{request_id}_input.wav"
    processed_filename = f"{TEMP_DIR}/{request_id}_processed.wav"
    output_filename = f"{STATIC_DIR}/response.mp3"
    
    try:
        # 1. Ovozni qabul qilish
        audio_bytes = await request.body()
        if not audio_bytes or len(audio_bytes) < 100:
            return PlainTextResponse("Audio ma'lumot yetarli emas", status_code=400)

        with open(input_filename, "wb") as f:
            f.write(audio_bytes)
        
        print(f"\n[INFO] Yangi so'rov: {len(audio_bytes)} bytes")

        # 2. Ovozni normallashtirish va balandlatish
        try:
            audio_segment = AudioSegment.from_wav(input_filename)
            normalized = audio_segment.normalize()
            final_audio = normalized + 10  # Ovozni 10dB ga balandlatish
            final_audio.export(processed_filename, format="wav")
        except Exception as e:
            print(f"[XATO] Pydub xatosi: {e}")
            return PlainTextResponse("Audio formatda xato", status_code=400)

        # 3. Speech-to-Text (Ovozdan matnga)
        recognizer = sr.Recognizer()
        try:
            with sr.AudioFile(processed_filename) as source:
                audio_data = recognizer.record(source)
                user_text = recognizer.recognize_google(audio_data, language="uz-UZ")
                print(f"[USER] {user_text}")
        except sr.UnknownValueError:
            print("[INFO] Ovoz tushunilmadi")
            return PlainTextResponse("Ovoz tushunilmadi", status_code=400)
        except Exception as e:
            print(f"[XATO] STT xatosi: {e}")
            return PlainTextResponse("STT xatosi", status_code=500)

        # 4. Gemini LLM (Aqlli javob)
        if not GENAI_API_KEY:
            return PlainTextResponse("API kalit o'rnatilmagan", status_code=500)
            
        prompt = f"Sen aqlli o'zbek tilidagi yordamchisan. Foydalanuvchi gapiga juda qisqa va do'stona javob ber: {user_text}"
        response = model.generate_content(prompt)
        bot_text = response.text.strip()
        print(f"[ZEN] {bot_text}")

        # 5. Text-to-Speech (Matndan ovozga)
        communicate = edge_tts.Communicate(bot_text, "uz-UZ-MadinaNeural")
        await communicate.save(output_filename)
        
        print("[INFO] Javob audiosi tayyorlandi")
        return PlainTextResponse("OK")

    except Exception as e:
        print(f"[XATO] Umumiy xatolik: {e}")
        return PlainTextResponse(str(e), status_code=500)

@app.get("/")
def health_check():
    return {"status": "Online", "model": "Gemini 2.5 Flash", "api_key_configured": bool(GENAI_API_KEY)}

if __name__ == "__main__":
    import uvicorn
    # Port Render yoki Mahalliy muhitga moslashadi
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
