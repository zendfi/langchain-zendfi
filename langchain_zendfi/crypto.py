"""
Device-Bound Session Keys - Client-Side Cryptography
=====================================================

This module provides TRUE non-custodial session keys where:
- Client generates keypair (backend NEVER sees private key)
- Client encrypts with PIN + device fingerprint
- Backend stores encrypted blob (cannot decrypt!)
- Client decrypts for each payment

Security: PBKDF2 key derivation + AES-256-GCM encryption
(Compatible with TypeScript SDK's device-bound-crypto.ts)

Requires: pynacl, cryptography

@module crypto
"""

import os
import base64
import hashlib
import secrets
import platform
import uuid
from dataclasses import dataclass, asdict
from typing import Optional, Tuple
from datetime import datetime

# Cryptography imports
try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.public import PrivateKey
    from nacl.encoding import Base64Encoder, RawEncoder
    HAS_NACL = True
except ImportError:
    HAS_NACL = False

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


# ============================================
# Types
# ============================================

@dataclass
class DeviceFingerprint:
    """Device fingerprint for binding session keys."""
    fingerprint: str
    generated_at: int
    components: dict
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass 
class EncryptedSessionKey:
    """Encrypted session key data (stored on backend)."""
    encrypted_data: str  # Base64 encoded encrypted private key
    nonce: str  # Base64 encoded nonce (12 bytes)
    public_key: str  # Base58 Solana public key
    device_fingerprint: str
    version: str = "pbkdf2-aes256gcm-v1"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "EncryptedSessionKey":
        return cls(
            encrypted_data=data["encrypted_data"],
            nonce=data["nonce"],
            public_key=data["public_key"],
            device_fingerprint=data["device_fingerprint"],
            version=data.get("version", "pbkdf2-aes256gcm-v1"),
        )


@dataclass
class SessionKeypair:
    """Ed25519 keypair for Solana signing."""
    public_key: str  # Base58 encoded
    secret_key: bytes  # 64-byte Ed25519 secret key
    signing_key: Optional[object] = None  # PyNaCl SigningKey
    
    def sign(self, message: bytes) -> bytes:
        """Sign a message with this keypair."""
        if not HAS_NACL:
            raise ImportError("PyNaCl required for signing. Install with: pip install pynacl")
        if self.signing_key is None:
            self.signing_key = SigningKey(self.secret_key[:32])
        return self.signing_key.sign(message).signature
    
    def sign_base64(self, message: bytes) -> str:
        """Sign a message and return base64-encoded signature."""
        return base64.b64encode(self.sign(message)).decode()


# ============================================
# Device Fingerprinting
# ============================================

class DeviceFingerprintGenerator:
    """
    Generate a unique device fingerprint for session key binding.
    
    For Python/server environments, uses:
    - Platform info
    - Machine identifier
    - Python version
    - Random entropy (on first generation)
    """
    
    _cached_fingerprint: Optional[DeviceFingerprint] = None
    
    @classmethod
    def generate(cls, use_cache: bool = True) -> DeviceFingerprint:
        """
        Generate a device fingerprint.
        
        Args:
            use_cache: If True, return cached fingerprint if available.
                       For servers, you typically want consistent fingerprints.
        """
        if use_cache and cls._cached_fingerprint is not None:
            return cls._cached_fingerprint
        
        components = {}
        
        # Platform info
        components["platform"] = platform.system()
        components["platform_version"] = platform.version()
        components["machine"] = platform.machine()
        components["processor"] = platform.processor()
        components["python_version"] = platform.python_version()
        
        # Node name (hostname)
        components["node"] = platform.node()
        
        # For server environments, we add a stable machine ID
        # Try to get machine-id on Linux, or generate one
        machine_id = cls._get_machine_id()
        if machine_id:
            components["machine_id"] = machine_id
        
        # Add some entropy for uniqueness
        components["entropy"] = cls._get_stable_entropy()
        
        # Combine and hash
        combined = "|".join(
            f"{k}:{v}" for k, v in sorted(components.items())
        )
        fingerprint = hashlib.sha256(combined.encode()).hexdigest()
        
        result = DeviceFingerprint(
            fingerprint=fingerprint,
            generated_at=int(datetime.now().timestamp() * 1000),
            components=components,
        )
        
        if use_cache:
            cls._cached_fingerprint = result
        
        return result
    
    @classmethod
    def _get_machine_id(cls) -> Optional[str]:
        """Try to get a stable machine ID."""
        # Linux
        try:
            with open("/etc/machine-id", "r") as f:
                return f.read().strip()
        except (FileNotFoundError, PermissionError):
            pass
        
        # macOS
        try:
            import subprocess
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True
            )
            for line in result.stdout.split("\n"):
                if "IOPlatformUUID" in line:
                    return line.split('"')[-2]
        except Exception:
            pass
        
        # Fallback: use a generated UUID stored in temp
        try:
            id_file = "/tmp/.zendfi_machine_id"
            if os.path.exists(id_file):
                with open(id_file, "r") as f:
                    return f.read().strip()
            else:
                new_id = str(uuid.uuid4())
                with open(id_file, "w") as f:
                    f.write(new_id)
                return new_id
        except Exception:
            pass
        
        return None
    
    @classmethod
    def _get_stable_entropy(cls) -> str:
        """Get stable entropy for this machine."""
        # Use the machine ID or a stable random value
        entropy_file = "/tmp/.zendfi_entropy"
        try:
            if os.path.exists(entropy_file):
                with open(entropy_file, "r") as f:
                    return f.read().strip()
            else:
                entropy = secrets.token_hex(16)
                with open(entropy_file, "w") as f:
                    f.write(entropy)
                return entropy
        except Exception:
            # Last resort fallback
            return hashlib.sha256(platform.node().encode()).hexdigest()[:32]
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear the cached fingerprint."""
        cls._cached_fingerprint = None


# ============================================
# Key Generation
# ============================================

def generate_keypair() -> SessionKeypair:
    """
    Generate a new Ed25519 keypair for Solana.
    
    Returns:
        SessionKeypair with public_key (base58) and secret_key (64 bytes)
    """
    if not HAS_NACL:
        raise ImportError(
            "PyNaCl required for key generation. Install with: pip install pynacl"
        )
    
    # Generate Ed25519 keypair
    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key
    
    # Solana uses 64-byte secret key format: [32-byte seed][32-byte public key]
    secret_key = bytes(signing_key) + bytes(verify_key)
    
    # Base58 encode the public key (Solana format)
    public_key = base58_encode(bytes(verify_key))
    
    return SessionKeypair(
        public_key=public_key,
        secret_key=secret_key,
        signing_key=signing_key,
    )


def keypair_from_secret(secret_key: bytes) -> SessionKeypair:
    """
    Reconstruct a keypair from a 64-byte secret key.
    
    Args:
        secret_key: 64-byte Solana secret key format
        
    Returns:
        SessionKeypair
    """
    if not HAS_NACL:
        raise ImportError("PyNaCl required. Install with: pip install pynacl")
    
    if len(secret_key) != 64:
        raise ValueError(f"Secret key must be 64 bytes, got {len(secret_key)}")
    
    # First 32 bytes are the seed
    signing_key = SigningKey(secret_key[:32])
    verify_key = signing_key.verify_key
    public_key = base58_encode(bytes(verify_key))
    
    return SessionKeypair(
        public_key=public_key,
        secret_key=secret_key,
        signing_key=signing_key,
    )


# ============================================
# Encryption (PBKDF2 + AES-256-GCM)
# ============================================

class SessionKeyCrypto:
    """
    Encrypt/decrypt session keys with PIN + device fingerprint.
    
    Uses PBKDF2 for key derivation and AES-256-GCM for encryption.
    Compatible with the TypeScript SDK's device-bound-crypto.ts.
    """
    
    # PBKDF2 parameters (matching TypeScript SDK)
    PBKDF2_ITERATIONS = 100000
    KEY_LENGTH = 32  # 256 bits for AES-256
    NONCE_LENGTH = 12  # 96 bits for AES-GCM
    
    @classmethod
    def encrypt(
        cls,
        keypair: SessionKeypair,
        pin: str,
        device_fingerprint: str,
    ) -> EncryptedSessionKey:
        """
        Encrypt a session keypair with PIN + device fingerprint.
        
        Args:
            keypair: The SessionKeypair to encrypt
            pin: 6-digit numeric PIN
            device_fingerprint: Device fingerprint hash
            
        Returns:
            EncryptedSessionKey that can be stored on backend
        """
        if not HAS_CRYPTOGRAPHY:
            raise ImportError(
                "cryptography package required. Install with: pip install cryptography"
            )
        
        # Validate PIN
        if not pin or not pin.isdigit() or len(pin) != 6:
            raise ValueError("PIN must be exactly 6 numeric digits")
        
        # Derive encryption key
        encryption_key = cls._derive_key(pin, device_fingerprint)
        
        # Generate random nonce
        nonce = secrets.token_bytes(cls.NONCE_LENGTH)
        
        # Encrypt the secret key with AES-256-GCM
        aesgcm = AESGCM(encryption_key)
        encrypted_data = aesgcm.encrypt(nonce, keypair.secret_key, None)
        
        return EncryptedSessionKey(
            encrypted_data=base64.b64encode(encrypted_data).decode(),
            nonce=base64.b64encode(nonce).decode(),
            public_key=keypair.public_key,
            device_fingerprint=device_fingerprint,
            version="pbkdf2-aes256gcm-v1",
        )
    
    @classmethod
    def decrypt(
        cls,
        encrypted: EncryptedSessionKey,
        pin: str,
        device_fingerprint: str,
    ) -> SessionKeypair:
        """
        Decrypt an encrypted session key with PIN + device fingerprint.
        
        Args:
            encrypted: The EncryptedSessionKey from storage
            pin: 6-digit numeric PIN (same as used for encryption)
            device_fingerprint: Device fingerprint (must match)
            
        Returns:
            SessionKeypair ready for signing
            
        Raises:
            ValueError: If PIN is wrong or device fingerprint doesn't match
        """
        if not HAS_CRYPTOGRAPHY:
            raise ImportError(
                "cryptography package required. Install with: pip install cryptography"
            )
        
        # Validate PIN
        if not pin or not pin.isdigit() or len(pin) != 6:
            raise ValueError("PIN must be exactly 6 numeric digits")
        
        # Verify device fingerprint
        if encrypted.device_fingerprint != device_fingerprint:
            raise ValueError(
                "Device fingerprint mismatch - wrong device or security threat"
            )
        
        # Derive encryption key
        encryption_key = cls._derive_key(pin, device_fingerprint)
        
        # Decode base64
        encrypted_data = base64.b64decode(encrypted.encrypted_data)
        nonce = base64.b64decode(encrypted.nonce)
        
        try:
            # Decrypt with AES-256-GCM
            aesgcm = AESGCM(encryption_key)
            secret_key = aesgcm.decrypt(nonce, encrypted_data, None)
            
            # Reconstruct keypair
            return keypair_from_secret(secret_key)
            
        except Exception as e:
            raise ValueError(f"Decryption failed - wrong PIN or corrupted data: {e}")
    
    @classmethod
    def _derive_key(cls, pin: str, device_fingerprint: str) -> bytes:
        """
        Derive encryption key from PIN + device fingerprint using PBKDF2.
        
        Uses SHA-256 hash of device fingerprint as salt.
        """
        salt = hashlib.sha256(device_fingerprint.encode()).digest()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=cls.KEY_LENGTH,
            salt=salt,
            iterations=cls.PBKDF2_ITERATIONS,
            backend=default_backend(),
        )
        
        return kdf.derive(pin.encode())


# ============================================
# Base58 Encoding (Solana format)
# ============================================

# Base58 alphabet used by Bitcoin/Solana
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58_encode(data: bytes) -> str:
    """Encode bytes to base58 (Solana format)."""
    # Count leading zeros
    leading_zeros = 0
    for byte in data:
        if byte == 0:
            leading_zeros += 1
        else:
            break
    
    # Convert to integer
    num = int.from_bytes(data, "big")
    
    # Convert to base58
    result = ""
    while num > 0:
        num, remainder = divmod(num, 58)
        result = BASE58_ALPHABET[remainder] + result
    
    # Add leading '1's for each leading zero byte
    return "1" * leading_zeros + result


def base58_decode(s: str) -> bytes:
    """Decode base58 string to bytes."""
    # Count leading '1's
    leading_ones = 0
    for char in s:
        if char == "1":
            leading_ones += 1
        else:
            break
    
    # Convert from base58
    num = 0
    for char in s:
        num = num * 58 + BASE58_ALPHABET.index(char)
    
    # Convert to bytes
    result = []
    while num > 0:
        num, remainder = divmod(num, 256)
        result.append(remainder)
    
    # Add leading zeros
    return bytes(leading_ones) + bytes(reversed(result))


# ============================================
# Signing Utilities
# ============================================

def sign_message(keypair: SessionKeypair, message: bytes) -> bytes:
    """
    Sign a message with the session keypair.
    
    Args:
        keypair: SessionKeypair with signing capability
        message: Message bytes to sign
        
    Returns:
        64-byte Ed25519 signature
    """
    return keypair.sign(message)


def sign_message_base64(keypair: SessionKeypair, message: bytes) -> str:
    """
    Sign a message and return base64-encoded signature.
    
    Args:
        keypair: SessionKeypair with signing capability
        message: Message bytes to sign
        
    Returns:
        Base64-encoded signature string
    """
    return keypair.sign_base64(message)


def create_delegation_message(
    session_key_id: str,
    max_amount_usd: float,
    expires_at: str,
) -> str:
    """
    Create the delegation message that needs to be signed for autonomy.
    
    This is the exact format required by ZendFi's autonomy API,
    matching the TypeScript SDK's format exactly.
    
    Args:
        session_key_id: UUID of the session key
        max_amount_usd: Maximum spending amount in USD
        expires_at: ISO 8601 expiration timestamp
        
    Returns:
        Message string to be signed
    """
    return f"I authorize autonomous delegate for session {session_key_id} to spend up to ${max_amount_usd} until {expires_at}"


# ============================================
# Verification Utilities
# ============================================

def verify_dependencies() -> dict:
    """
    Check if required cryptography dependencies are installed.
    
    Returns:
        Dict with status of each dependency
    """
    return {
        "pynacl": HAS_NACL,
        "cryptography": HAS_CRYPTOGRAPHY,
        "all_installed": HAS_NACL and HAS_CRYPTOGRAPHY,
    }


# ============================================
# Lit Protocol Integration
# ============================================

@dataclass
class LitEncryptionResult:
    """Result from Lit Protocol encryption."""
    ciphertext: str
    data_hash: str
    
    def to_dict(self) -> dict:
        return {
            "ciphertext": self.ciphertext,
            "data_hash": self.data_hash,
        }
# Default URL for Lit microservice
LIT_SERVICE_URL = os.environ.get("LIT_SERVICE_URL", "https://lit-service.zendfi.tech")


def encrypt_keypair_with_lit(
    keypair: SessionKeypair,
    network: str = "datil",
    service_url: Optional[str] = None,
    timeout_seconds: int = 30,
) -> Optional[LitEncryptionResult]:
    """
    Encrypt a session keypair with Lit Protocol for autonomous signing.
    
    This enables the backend to decrypt and sign transactions when the client
    is offline, using Lit Protocol's distributed key management.
    
    Uses the hosted Lit encryption service at https://lit-service.zendfi.tech
    For local development, set LIT_SERVICE_URL=http://localhost:3100
    
    Args:
        keypair: The session keypair to encrypt
        network: Lit network ('datil', 'datil-dev', 'datil-test')
        service_url: URL of Lit service (default: https://lit-service.zendfi.tech)
        timeout_seconds: Timeout for encryption (default 30s)
        
    Returns:
        LitEncryptionResult with ciphertext and data hash, or None if failed
    """
    import json
    
    # Try microservice first (fast path)
    url = service_url or LIT_SERVICE_URL
    secret_key_b64 = base64.b64encode(keypair.secret_key).decode()
    
    try:
        import urllib.request
        import urllib.error
        
        # Check if service is available
        health_req = urllib.request.Request(f"{url}/health", method='GET')
        try:
            with urllib.request.urlopen(health_req, timeout=10) as resp:
                health = json.loads(resp.read().decode())
                if not health.get("connected"):
                    print(f"[LitProtocol] Service not ready (status: {health.get('status')})")
                    return None
        except urllib.error.URLError as e:
            # Service not running
            print(f"[LitProtocol] Lit service unavailable at {url}: {e}")
            return None
        except Exception as e:
            print(f"[LitProtocol] Health check failed: {e}")
            return None
        
        # Call encrypt endpoint
        encrypt_req = urllib.request.Request(
            f"{url}/encrypt",
            data=json.dumps({"secret_key_base64": secret_key_b64}).encode(),
            headers={"Content-Type": "application/json"},
            method='POST',
        )
        
        with urllib.request.urlopen(encrypt_req, timeout=timeout_seconds) as resp:
            result = json.loads(resp.read().decode())
            
            if "error" in result:
                print(f"[LitProtocol] Encryption error: {result['error']}")
                return None
            
            print("[LitProtocol] ✅ Encryption successful (via microservice)")
            return LitEncryptionResult(
                ciphertext=result["ciphertext"],
                data_hash=result["dataHash"],
            )
            
    except urllib.error.HTTPError as e:
        print(f"[LitProtocol] Service error: {e.code} {e.reason}")
        return None
    except Exception as e:
        print(f"[LitProtocol] Microservice error: {e}")
        return None


# ============================================
# Exports
# ============================================

__all__ = [
    # Types
    "DeviceFingerprint",
    "EncryptedSessionKey",
    "SessionKeypair",
    "LitEncryptionResult",
    # Device fingerprinting
    "DeviceFingerprintGenerator",
    # Key generation
    "generate_keypair",
    "keypair_from_secret",
    # Encryption
    "SessionKeyCrypto",
    # Base58
    "base58_encode",
    "base58_decode",
    # Signing
    "sign_message",
    "sign_message_base64",
    "create_delegation_message",
    # Lit Protocol
    "encrypt_keypair_with_lit",
    # Utilities
    "verify_dependencies",
    # Flags
    "HAS_NACL",
    "HAS_CRYPTOGRAPHY",
]
