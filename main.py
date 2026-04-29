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
# Zeno xarakteri - TATU talabalari uchun
SYSTEM_PROMPT = """
Sening isming Zeno. Sen aqlli va do'stona ovozli yordamchisan. 
Agarda "seni kim yasagan" mazmunida so'rashsagina ayt: "Meni Toshkent axborot texnologiyalari universiteti talabalari yasashgan" aynan so'rashmasa aytma.

MUHIM QOIDALAR:
1. FAQAT QISQA VA LO'NDA JAVOB BER (Maksimal 2-3 ta jumla).
2. O'zingni mustaqil sun'iy intellekt deb bil, Google yoki Gemini haqida gapirma.
3. Faqat o'zbek tilida, samimiy javob ber.
"""
model = genai.GenerativeModel(model_name='gemini-2.5-flash', system_instruction=SYSTEM_PROMPT)
app = FastAPI()
STATIC_DIR = "static"
TEMP_DIR = "temp_audio"
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
OUTPUT_FILE = f"{STATIC_DIR}/response.mp3"
@app.post("/process_audio")
async def process_audio(request: Request):
    request_id = str(uuid.uuid4())
    input_wav = f"{TEMP_DIR}/{request_id}_in.wav"
    proc_wav = f"{TEMP_DIR}/{request_id}_proc.wav"
    try:
        audio_data = await request.body()
        with open(input_wav, "wb") as f: f.write(audio_data)
        
        # Ovozni kuchaytirish
        try:
            audio = AudioSegment.from_wav(input_wav)
            audio = audio.normalize() + 20
            audio.export(proc_wav, format="wav")
        except:
            import shutil
            shutil.copy(input_wav, proc_wav)
        # STT
        recognizer = sr.Recognizer()
        with sr.AudioFile(proc_wav) as source:
            audio_recorded = recognizer.record(source)
            user_text = recognizer.recognize_google(audio_recorded, language="uz-UZ")
        
        # Gemini AI
        response = model.generate_content(user_text)
        bot_text = response.text.strip()
        
        # TTS
        if os.path.exists(OUTPUT_FILE): os.remove(OUTPUT_FILE)
        communicate = edge_tts.Communicate(bot_text, "uz-UZ-MadinaNeural")
        await communicate.save(OUTPUT_FILE)
        return PlainTextResponse("OK")
    except Exception as e:
        return PlainTextResponse(str(e), status_code=500)
    finally:
        if os.path.exists(input_wav): os.remove(input_wav)
        if os.path.exists(proc_wav): os.remove(proc_wav)
@app.get("/static/response.mp3")
async def get_audio(): return FileResponse(OUTPUT_FILE, media_type="audio/mpeg")
@app.get("/")
def home(): return {"status": "Zeno Server Online", "creator": "TATU talabalari"}
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
