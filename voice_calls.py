@"
import asyncio
import os
from fastapi import FastAPI, Request, Response
from dotenv import load_dotenv
from pipecat.transports.whatsapp import WhatsAppTransport
from pipecat.services.groq import GroqLLMService
from pipecat.services.deepgram import DeepgramSTTService, DeepgramTTSService
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner

load_dotenv()

voice_app = FastAPI()

WHATSAPP_TOKEN = os.getenv("VOICE_WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("VOICE_PHONE_NUMBER_ID")
APP_SECRET = os.getenv("VOICE_APP_SECRET")
VERIFY_TOKEN = os.getenv("VOICE_VERIFY_TOKEN")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

@voice_app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    body = await request.body()
    data = await request.json()
    if "entry" in data:
        for entry in data["entry"]:
            for change in entry.get("changes", []):
                if change.get("field") == "calls":
                    await handle_incoming_call(change.get("value", {}))
    return Response(status_code=200)

@voice_app.get("/webhook/whatsapp")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, status_code=200)
    return Response(status_code=403)

async def handle_incoming_call(call_data: dict):
    call_id = call_data.get("id")
    from_number = call_data.get("from")
    print(f"Incoming call from {from_number}, call_id: {call_id}")
    
    transport = WhatsAppTransport(
        whatsapp_token=WHATSAPP_TOKEN,
        phone_number_id=PHONE_NUMBER_ID,
        app_secret=APP_SECRET
    )
    stt = DeepgramSTTService(api_key=DEEPGRAM_API_KEY)
    llm = GroqLLMService(api_key=GROQ_API_KEY, model="llama3-8b-8192")
    tts = DeepgramTTSService(api_key=DEEPGRAM_API_KEY, voice="aura-asteria-en")
    
    pipeline = Pipeline([stt, llm, tts])
    task = PipelineTask(pipeline)
    runner = PipelineRunner()
    await runner.run(task)

def run_voice_service():
    import uvicorn
    uvicorn.run(voice_app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    run_voice_service()
"@ | Out-File -FilePath voice_calls.py -Encoding utf8