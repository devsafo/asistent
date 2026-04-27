import os
import io
import asyncio
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, FileResponse
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
    print("XATO: GEMINI_API_KEY topilmadi!")

# Zeno xarakteri uchun tizim ko'rsatmasi
SYSTEM_PROMPT = """
Sening isming Zeno. Sen juda aqlli, bilimdon va do'stona ovozli yordamchisan. 
Vazifang: Foydalanuvchining har qanday savoliga yoki buyrug'iga juda batafsil, aniq va foydali javob berish.
Hech qachon dangasalik qilma. Agar savol murakkab bo'lsa, uni qismlarga bo'lib tushuntir. 
Javoblaring mazmunli va to'liq bo'lsin. Har doim o'zbek tilida javob ber.
O'zingni doimo "Zeno ovozli yordamchisi" deb bil.
"""

# Foydalanuvchi talab qilgan model (Gemini 2.5 Flash)
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    system_instruction=SYSTEM_PROMPT
)

app = FastAPI()

# Kataloglar
STATIC_DIR = "static"
TEMP_DIR = "temp_audio"
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Asosiy javob audio fayli manzili
OUTPUT_FILE = f"{STATIC_DIR}/response.mp3"

@app.post("/process_audio")
async def process_audio(request: Request):
    request_id = str(uuid.uuid4())
    input_filename = f"{TEMP_DIR}/{request_id}_input.wav"
    processed_filename = f"{TEMP_DIR}/{request_id}_processed.wav"
    
    try:
        # 1. Ovozni qabul qilish
        audio_bytes = await request.body()
        if not audio_bytes or len(audio_bytes) < 1000:
            return PlainTextResponse("Audio yetarli emas", status_code=400)

        with open(input_filename, "wb") as f:
            f.write(audio_bytes)
        
        print(f"\n[INFO] Yangi so'rov keldi: {len(audio_bytes)} bytes")

        # 2. Ovozni normallashtirish va balandlatish (+15dB)
        try:
            audio_segment = AudioSegment.from_wav(input_filename)
            normalized = audio_segment.normalize()
            final_audio = normalized + 15 
            final_audio.export(processed_filename, format="wav")
        except Exception as e:
            print(f"[XATO] Pydub xatosi: {e}")
            # Agar pydub xato bersa, asl faylni ishlatish
            with open(input_filename, "rb") as f_in:
                with open(processed_filename, "wb") as f_out:
                    f_out.write(f_in.read())

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

        # 4. Gemini LLM (Zeno javobi)
        print("[ZENO] O'ylayapman...")
        response = model.generate_content(user_text)
        bot_text = response.text.strip()
        print(f"[ZENO] {bot_text}")

        # 5. Text-to-Speech (Matndan ovozga)
        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)
            
        communicate = edge_tts.Communicate(bot_text, "uz-UZ-MadinaNeural")
        await communicate.save(OUTPUT_FILE)
        
        print("[INFO] Javob audiosi tayyor")
        return PlainTextResponse("OK")

    except Exception as e:
        print(f"[XATO] Umumiy xatolik: {e}")
        return PlainTextResponse(str(e), status_code=500)
    finally:
        # Vaqtinchalik fayllarni tozalash
        if os.path.exists(input_filename): os.remove(input_filename)
        if os.path.exists(processed_filename): os.remove(processed_filename)

@app.get("/static/response.mp3")
async def get_audio():
    # Windows/Render uchun ishonchli FileResponse
    return FileResponse(OUTPUT_FILE, media_type="audio/mpeg")

@app.get("/")
def health_check():
    return {"status": "Zeno Online", "model": "Gemini 2.5 Flash"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
