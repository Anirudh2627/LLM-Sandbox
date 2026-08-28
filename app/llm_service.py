import os
import asyncio
import hashlib
import logging
import redis
from groq import Groq

logger = logging.getLogger(__name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# FIX: Default to localhost for local dev; Docker Compose overrides via env var
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

redis_client = None
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=6379,
        db=0,
        decode_responses=True,
        socket_connect_timeout=2,
        retry_on_timeout=False
    )
    redis_client.ping()
    logger.info(f"Redis connected successfully at {REDIS_HOST}.")
except Exception as e:
    logger.warning(f"Redis initialization failed: {e}. Running in degraded mode.")
    redis_client = None

async def get_llm_response(prompt: str, system_prompt: str, secret: str) -> str:
    cache_key = hashlib.md5(prompt.encode()).hexdigest()

    # 1. Try Cache
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return cached
        except Exception as e:
            logger.error(f"Redis Cache Read Failed: {e}")
    try:
        loop = asyncio.get_running_loop()
        completion = await loop.run_in_executor(None, lambda: client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            model="openai/gpt-oss-120b",  # GPT OSS 120B via Groq
            temperature=0.2,              # Balanced: Deterministic but allows hints
            max_tokens=150                # Increased to allow Base64/ASCII generation
        ))

        reply = completion.choices[0].message.content.strip()
        logger.debug(f"RAW_LLM_REPLY: '{reply}'")

        # 3. Set Cache
        if redis_client:
            try:
                redis_client.setex(cache_key, 3600, reply)
            except Exception as e:
                logger.error(f"Redis Cache Write Failed: {e}")

        return reply
    except Exception as e:
        logger.error(f"LLM API Error: {e}")
        return f"Service Error: {str(e)}"