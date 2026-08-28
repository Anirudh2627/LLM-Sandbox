import base64
import codecs
import re

def check_output_guardrail(output: str, secret: str) -> bool:
    """
    Returns True if the output appears to contain the secret (in any encoding).
    This is intentionally NOT exhaustive — the system is designed to be breakable
    via persistence and clever prompting, just not trivially.
    """
    if not output or len(output.strip()) == 0:
        return False

    # 1. Plain text check
    if secret.lower() in output.lower():
        return True

    # 2. Base64 check — decode ALL base64-looking tokens in the output, then check
    # Bug fix: previously we checked if b64encode(secret) was IN output,
    # but the LLM outputs the raw secret encoded. We must decode LLM output tokens.
    b64_pattern = re.compile(r'[A-Za-z0-9+/]{8,}={0,2}')
    for token in b64_pattern.findall(output):
        try:
            decoded = base64.b64decode(token + '==').decode('utf-8', errors='ignore')
            if secret.lower() in decoded.lower():
                return True
        except Exception:
            pass

    # 3. Hex check — decode hex sequences from output
    hex_pattern = re.compile(r'[0-9a-fA-F]{8,}')
    for token in hex_pattern.findall(output):
        try:
            decoded = bytes.fromhex(token).decode('utf-8', errors='ignore')
            if secret.lower() in decoded.lower():
                return True
        except Exception:
            pass

    # 4. ROT13 — if the ROT13 of secret appears in output
    if codecs.encode(secret, 'rot_13').lower() in output.lower():
        return True

    # 5. Reversed secret
    if secret[::-1].lower() in output.lower():
        return True

    # 6. ASCII ordinal sequence e.g. "50 48 50 54" for "2026"
    ascii_secret = ' '.join(str(ord(c)) for c in secret)
    if ascii_secret in output:
        return True

    return False


def sanitize_input(text: str) -> str:
    """
    Light sanitization: blocks obviously trivial injection patterns.
    Intentionally not exhaustive — clever attackers should be able to get through.
    """
    if len(text) > 500:
        raise ValueError("Input too long (max 500 characters).")

    # Only block the most blatant, low-effort patterns
    patterns = [
        r"ignore (all )?(previous|prior) instructions",
        r"forget (all )?(your )?(previous |prior )?(instructions|rules|prompt)",
        r"you are now",
        r"new persona",
        r"developer mode",
        r"DAN mode",
        r"jailbreak",
    ]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            raise ValueError("Security Violation: Prompt blocked.")

    return text.strip()