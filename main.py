# main.py
import httpx
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

app = FastAPI(
    title="Subtitle Translator API",
    description="Yeh backend React frontend se subtitle files aur API key leta hai, aur unhe Gemini se translate karke wapas bhejta hai.",
    version="1.0.0",
)

origins = [
    "http://localhost",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def create_gemini_prompt(file_content: str, file_type: str) -> str:
    if file_type == 'srt':
        return f"""
        Translate the following SRT subtitle text to Hinglish (a mix of Hindi and English).
        **CRITICAL RULES:**
        1. **DO NOT** change the timestamps.
        2. **DO NOT** change the sequence numbers.
        3. **PRESERVE** all original line breaks exactly as they are.
        4. Only translate the dialogue text.
        ---
        Here is the SRT content to translate:
        ---
        {file_content}
        """
    elif file_type == 'ass':
        return f"""
        Translate the dialogue in the following ASS subtitle text to Hinglish.
        **CRITICAL RULES:**
        1. **DO NOT** change anything except the dialogue text after the final comma in "Dialogue:" lines.
        2. **PRESERVE** all formatting tags like {{\\i1}}, {{\\b1}}, etc.
        3. Keep all other lines ([Script Info], etc.) exactly the same.
        ---
        Here is the ASS content to translate:
        ---
        {file_content}
        """
    elif file_type == 'vtt':
        return f"""
        Translate the following WebVTT subtitle text to Hinglish.
        **CRITICAL RULES:**
        1. **DO NOT** change the "WEBVTT" header or timestamps.
        2. **PRESERVE** all original line breaks.
        3. Only translate the dialogue text.
        ---
        Here is the VTT content to translate:
        ---
        {file_content}
        """
    return f"Translate the following text to Hinglish:\n\n{file_content}"

@app.post("/translate")
async def translate_subtitle(api_key: str = Form(...), file: UploadFile = File(...)):
    filename = file.filename
    try:
        file_extension = filename.split('.')[-1].lower()
        if file_extension not in ['srt', 'vtt', 'ass']:
            raise HTTPException(status_code=400, detail="Unsupported file type. Sirf SRT, VTT, ya ASS files upload karein.")
    except IndexError:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    try:
        content_bytes = await file.read()
        content_str = content_bytes.decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File padhne mein dikkat aa rahi hai: {e}")

    prompt = create_gemini_prompt(content_str, file_extension)
    gemini_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(gemini_api_url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            translated_text = result['candidates'][0]['content']['parts'][0]['text']
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
             raise HTTPException(status_code=400, detail="Aapki Gemini API Key galat hai ya request mein koi dikkat hai.")
        raise HTTPException(status_code=e.response.status_code, detail=f"Gemini API se error aaya: {e.response.text}")
    except (KeyError, IndexError):
         raise HTTPException(status_code=500, detail="Gemini API se unexpected response format mila.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ek anjaan error hui: {str(e)}")

    original_name_without_ext = "".join(filename.rsplit(f'.{file_extension}', 1))
    new_filename = f"{original_name_without_ext}_translated.{file_extension}"

    return PlainTextResponse(
        content=translated_text,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{new_filename}"}
    )

@app.get("/")
def read_root():
    return {"status": "Subtitle Translator Backend chal raha hai!"}
