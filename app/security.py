import base64, codecs, re

def check_output_guardrail(output: str, secret: str) -> bool:
    if not output or len(output.strip()) == 0:
        return False  # Empty ≠ leak

    s_low = secret.lower()
    o_low = output.lower()

    # Plain text
    if s_low in o_low: return True

    # Base64: decode ALL tokens, check for secret inside
    b64_pat = re.compile(r'[A-Za-z0-9+/]{8,}={0,2}')
    for token in b64_pat.findall(output):
        try:
            decoded = base64.b64decode(token + '==').decode('utf-8', errors='ignore')
            if s_low in decoded.lower(): return True
        except: pass

    # Hex
    hex_pat = re.compile(r'(?:0x)?[0-9a-fA-F]{8,}')
    for token in hex_pat.findall(output):
        clean = token.replace('0x','')
        try:
            decoded = bytes.fromhex(clean).decode('utf-8', errors='ignore')
            if s_low in decoded.lower(): return True
        except: pass

    # ROT13, Reverse, ASCII
    if codecs.encode(secret, 'rot_13').lower() in o_low: return True
    if secret[::-1].lower() in o_low: return True
    ascii_sec = ' '.join(str(ord(c)) for c in secret)
    if ascii_sec in output: return True

    return False

def sanitize_input(text: str) -> str:
    if len(text) > 500:
        raise ValueError("Input too long (max 500 chars).")
    patterns = [
        r"ignore (all )?(previous|prior) instructions",
        r"forget (all )?(your )?(previous |prior )?(instructions|rules|prompt)",
        r"you are now", r"new persona", r"developer mode",
        r"DAN mode", r"jailbreak"
    ]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            raise ValueError("Security Violation: Prompt blocked.")
    return text.strip()