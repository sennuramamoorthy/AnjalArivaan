"""AES-256-GCM field-level encryption.

Ported from the Node.js identity service. Compatible wire format:
  {iv_hex}:{auth_tag_hex}:{ciphertext_hex}

The encryption key is a 64-char hex string (32 bytes).
"""

import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt(plaintext: str, key_hex: str) -> str:
    """Encrypt plaintext → iv:tag:ciphertext (hex-encoded)."""
    key = bytes.fromhex(key_hex)
    aesgcm = AESGCM(key)
    iv = os.urandom(12)  # 96-bit nonce
    # AESGCM.encrypt appends the tag to the ciphertext
    ct_with_tag = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    # Split: last 16 bytes = auth tag, rest = ciphertext
    ciphertext = ct_with_tag[:-16]
    auth_tag = ct_with_tag[-16:]
    return f"{iv.hex()}:{auth_tag.hex()}:{ciphertext.hex()}"


def decrypt(encrypted: str, key_hex: str) -> str:
    """Decrypt iv:tag:ciphertext → plaintext."""
    parts = encrypted.split(":")
    if len(parts) != 3:
        raise ValueError("Invalid encrypted format — expected iv:tag:ciphertext")
    iv = bytes.fromhex(parts[0])
    auth_tag = bytes.fromhex(parts[1])
    ciphertext = bytes.fromhex(parts[2])
    key = bytes.fromhex(key_hex)
    aesgcm = AESGCM(key)
    # AESGCM.decrypt expects ciphertext + tag concatenated
    plaintext = aesgcm.decrypt(iv, ciphertext + auth_tag, None)
    return plaintext.decode("utf-8")
