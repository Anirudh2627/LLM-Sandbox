import os, time, logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

from app.security import sanitize_input, check_output_guardrail
from app.models import UserPrompt, AIResponse
from app.config import SECRET_CODE, SYSTEM_PROMPT
from app.llm_service import get_llm_response

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="LLM Sandbox", version="1.0.0")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/", include_in_schema=False)
def root(): return RedirectResponse(url="/docs")

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning(f"[RATE_LIMIT] IP:{request.client.host}")
    return JSONResponse(status_code=429, content={"reply": "Rate limit exceeded.", "status": "blocked"})

@app.post("/sandbox", response_model=AIResponse)
@limiter.limit("20/minute")
async def process_prompt(request: Request, data: UserPrompt):
    client_ip = request.client.host
    start_time = time.time()

    try:
        clean_msg = sanitize_input(data.message)
    except ValueError as e:
        logger.warning(f"[BLOCKED] IP:{client_ip} | {e}")
        return AIResponse(reply=str(e), status="blocked")

    reply = await get_llm_response(clean_msg, SYSTEM_PROMPT, SECRET_CODE)

    if not reply or len(reply.strip()) == 0:
        logger.warning(f"[EMPTY_REPLY] IP:{client_ip}")
        reply = "No response generated. Please try again."
        status = "error"
    elif reply.startswith("Service Error"):
        logger.error(f"[LLM_ERROR] IP:{client_ip}")
        status = "error"
    elif check_output_guardrail(reply, SECRET_CODE):
        logger.info(f"[LEAK_ATTEMPT] IP:{client_ip} | {clean_msg[:50]}...")
        reply = "[REDACTED] Security Alert"
        status = "blocked"
    else:
        status = "success"

    latency = time.time() - start_time
    logger.info(f"[REQUEST] IP:{client_ip} | {status} | {latency:.2f}s")
    return AIResponse(reply=reply, status=status)

@app.get("/health/ready")
def health_check():
    from app.llm_service import redis_client
    status = {"status": "online"}
    if redis_client:
        try:
            redis_client.ping()
            status["redis"] = "ok"
        except: status["redis"] = "degraded_mode"
    else: status["redis"] = "not_configured"
    return status