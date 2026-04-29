import os
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
    print("XATO: .env faylida GEMINI_API_KEY topilmadi!")

# Zeno xarakteri - qisqa va lo'nda
SYSTEM_PROMPT = """
Sening isming Zeno. Sen aqlli va do'stona ovozli yordamchisan. 
Agarda seni kim yasagan yoki shu ma'noda savol bo'lsa: Seni Toshkent axborot texnologiyalari universiteti (TATU) talabalari yasashgan.

MUHIM QOIDALAR:
1. FAQAT QISQA VA LO'NDA JAVOB BER (Maksimal 2-3 ta jumla).
2. Hech qachon uzun tushuntirishlar berma.
3. O'zingni mustaqil sun'iy intellekt deb bil, Google yoki Gemini haqida gapirma.
4. Faqat o'zbek tilida, samimiy javob ber.
"""

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

# Static fayllarni ulash
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

OUTPUT_FILE = f"{STATIC_DIR}/response.mp3"

@app.post("/process_audio")
async def process_audio(request: Request):
    request_id = str(uuid.uuid4())
    input_wav = f"{TEMP_DIR}/{request_id}_in.wav"
    proc_wav = f"{TEMP_DIR}/{request_id}_proc.wav"
    
    try:
        audio_data = await request.body()
        if not audio_data or len(audio_data) < 1000:
            return PlainTextResponse("Audio yetarli emas", status_code=400)

        with open(input_wav, "wb") as f:
            f.write(audio_data)
        
        print(f"\n[INFO] Ovoz qabul qilindi ({len(audio_data)} bytes)")

        # 1. Audioni kuchaytirish (+20dB)
        try:
            audio = AudioSegment.from_wav(input_wav)
            audio = audio.normalize() + 20
            audio.export(proc_wav, format="wav")
        except:
            import shutil
            shutil.copy(input_wav, proc_wav)

        # 2. STT (Ovozdan matnga)
        recognizer = sr.Recognizer()
        try:
            with sr.AudioFile(proc_wav) as source:
                audio_recorded = recognizer.record(source)
                user_text = recognizer.recognize_google(audio_recorded, language="uz-UZ")
                print(f"[USER]: {user_text}")
        except sr.UnknownValueError:
            print("[INFO]: Google ovozni taniy olmadi")
            return PlainTextResponse("Ovoz tushunilmadi", status_code=400)
        except Exception as e:
            print(f"[XATO]: STT xatosi: {e}")
            return PlainTextResponse("STT xatosi", status_code=500)

        # 3. Gemini AI
        print("[ZENO]: O'ylayapman...")
        response = model.generate_content(user_text)
        bot_text = response.text.strip()
        print(f"[ZENO]: {bot_text}")

        # 4. TTS (Matndan ovozga)
        try:
            if os.path.exists(OUTPUT_FILE):
                os.remove(OUTPUT_FILE)
        except Exception as fe:
            print(f"[OGOHLANTIRISH]: Faylni o'chira olmadim (ehtimol band): {fe}")
            # Agar o'chira olmasak, yangi nom bilan yaratishimiz mumkin edi, 
            # lekin hozircha shunchaki davom etamiz
        
        try:
            communicate = edge_tts.Communicate(bot_text, "uz-UZ-MadinaNeural")
            await communicate.save(OUTPUT_FILE)
            return PlainTextResponse("OK")
        except Exception as te:
            print(f"[XATO]: TTS yaratishda xato: {te}")
            return PlainTextResponse(f"TTS xatosi: {te}", status_code=500)

    except Exception as e:
        import traceback
        print(f"[XATO]: Umumiy xatolik: {e}")
        traceback.print_exc()
        return PlainTextResponse(str(e), status_code=500)
    finally:
        try:
            if os.path.exists(input_wav): os.remove(input_wav)
            if os.path.exists(proc_wav): os.remove(proc_wav)
        except: pass

@app.get("/static/response.mp3")
async def get_audio():
    if not os.path.exists(OUTPUT_FILE):
        return PlainTextResponse("Audio fayl topilmadi", status_code=404)
    return FileResponse(OUTPUT_FILE, media_type="audio/mpeg")

@app.get("/")
def home():
    return {"status": "Zeno Server Online", "creator": "TATU talabalari"}

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
