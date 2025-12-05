from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import base64
import os
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256
import pyotp

app = FastAPI()

# ------------------------------
# Configuration
# ------------------------------
PRIVATE_KEY_PATH = "student_private.pem"
SEED_FILE = "data/seed.txt"

# ------------------------------
# Request Models
# ------------------------------
class DecryptSeedRequest(BaseModel):
    encrypted_seed: str

class Verify2FARequest(BaseModel):
    code: str

# ------------------------------
# Helper Functions
# ------------------------------
def save_seed(hex_seed: str):
    os.makedirs(os.path.dirname(SEED_FILE), exist_ok=True)
    with open(SEED_FILE, "w") as f:
        f.write(hex_seed)

def read_seed() -> str:
    if not os.path.exists(SEED_FILE):
        raise HTTPException(status_code=500, detail="Seed not decrypted yet")
    with open(SEED_FILE, "r") as f:
        return f.read().strip()

def generate_totp(hex_seed: str) -> str:
    key_bytes = bytes.fromhex(hex_seed)
    base32_seed = base64.b32encode(key_bytes).decode("utf-8")
    totp = pyotp.TOTP(base32_seed)
    return totp.now()

def verify_totp(hex_seed: str, code: str) -> bool:
    key_bytes = bytes.fromhex(hex_seed)
    base32_seed = base64.b32encode(key_bytes).decode("utf-8")
    totp = pyotp.TOTP(base32_seed)
    return totp.verify(code, valid_window=1)

def seconds_remaining() -> int:
    return 30 - (int(pyotp.utils.time.time()) % 30)

# ------------------------------
# Endpoint 1: POST /decrypt-seed
# ------------------------------
@app.post("/decrypt-seed")
def decrypt_seed(req: DecryptSeedRequest):
    try:
        # Decode base64
        enc_bytes = base64.b64decode(req.encrypted_seed)

        # Load private key and prepare decryptor
        with open(PRIVATE_KEY_PATH, "rb") as f:
            key = RSA.import_key(f.read())
        decryptor = PKCS1_OAEP.new(key, hashAlgo=SHA256)

        # Decrypt
        decrypted_bytes = decryptor.decrypt(enc_bytes)
        hex_seed = decrypted_bytes.hex()  # lowercase hex

        # Validate 64-character hex
        if len(hex_seed) != 64 or not all(c in "0123456789abcdef" for c in hex_seed):
            raise ValueError("Invalid seed format")

        # Save seed
        save_seed(hex_seed)

        return {"status": "ok"}

    except Exception:
        raise HTTPException(status_code=500, detail="Decryption failed")

# ------------------------------
# Endpoint 2: GET /generate-2fa
# ------------------------------
@app.get("/generate-2fa")
def generate_2fa():
    try:
        hex_seed = read_seed()
        code = generate_totp(hex_seed)
        valid_for = seconds_remaining()
        return {"code": code, "valid_for": valid_for}
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Seed not decrypted yet")

# ------------------------------
# Endpoint 3: POST /verify-2fa
# ------------------------------
@app.post("/verify-2fa")
def verify_2fa(req: Verify2FARequest):
    if not req.code or req.code.strip() == "":
        raise HTTPException(status_code=400, detail="Missing code")
    try:
        hex_seed = read_seed()
        is_valid = verify_totp(hex_seed, req.code)
        return {"valid": is_valid}
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Seed not decrypted yet")
