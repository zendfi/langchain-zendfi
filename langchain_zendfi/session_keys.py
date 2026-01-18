"""
Session Keys API - Device-Bound Non-Custodial Session Keys
==========================================================

TRUE non-custodial session keys where:
- Client generates keypair (backend NEVER sees private key)
- Client encrypts with PIN + device fingerprint
- Backend stores encrypted blob (cannot decrypt!)
- Client decrypts and signs for each payment

Compatible with TypeScript SDK's aip/session-keys.ts

@module session_keys
"""

import asyncio
import base64
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, Awaitable

from langchain_zendfi.crypto import (
    DeviceFingerprintGenerator,
    SessionKeyCrypto,
    EncryptedSessionKey,
    SessionKeypair,
    generate_keypair,
    base58_encode,
    create_delegation_message,
    encrypt_keypair_with_lit,
    LitEncryptionResult,
    HAS_NACL,
    HAS_CRYPTOGRAPHY,
)


# ============================================
# Types
# ============================================

@dataclass
class CreateSessionKeyOptions:
    """
    Options for creating a device-bound session key.
    
    Lit Protocol Note:
        The `enable_lit_protocol` option enables TRUE autonomous signing where
        the backend can sign transactions even when the client is offline.
        
        However, Lit Protocol encryption takes 4-5 minutes due to network latency
        (connecting to all Lit nodes). For faster development/demos, set to False.
        
        Without Lit Protocol, session keys still work perfectly - they just require
        the client to be online to provide the signing capability.
    """
    user_wallet: str
    agent_id: str
    limit_usdc: float
    duration_days: int = 7
    pin: str = ""
    agent_name: Optional[str] = None
    generate_recovery_qr: bool = False
    # Lit Protocol options (for autonomous signing)
    # Default: False for fast setup. Set True for offline autonomous signing (takes 4-5 min)
    enable_lit_protocol: bool = False
    lit_network: str = "datil"  # 'datil' (mainnet), 'datil-dev', 'datil-test'


@dataclass
class SessionKeyResult:
    """Result from creating a session key."""
    session_key_id: str
    agent_id: str
    session_wallet: str
    limit_usdc: float
    expires_at: str
    cross_app_compatible: bool
    agent_name: Optional[str] = None
    recovery_qr: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SessionKeyInfo:
    """Current status of a session key."""
    session_key_id: str
    is_active: bool
    is_approved: bool
    limit_usdc: float
    used_amount_usdc: float
    remaining_usdc: float
    expires_at: str
    days_until_expiry: int
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PaymentResult:
    """Result from making a payment with session key."""
    payment_id: str
    signature: str
    status: str
    
    def to_dict(self) -> dict:
        return asdict(self)


# ============================================
# Device-Bound Session Key
# ============================================

class DeviceBoundSessionKey:
    """
    A device-bound session key that never exposes the private key.
    
    The keypair is generated client-side and encrypted with PIN + device
    fingerprint. The backend only stores the encrypted blob.
    
    Usage:
        # Create a new session key
        session_key = await DeviceBoundSessionKey.create(
            pin="123456",
            limit_usdc=100.0,
            duration_days=7,
            user_wallet="7xKNH...",
        )
        
        # Get encrypted data to send to backend
        encrypted = session_key.get_encrypted_data()
        
        # Later, unlock with PIN
        session_key.unlock_with_pin("123456")
        
        # Sign transactions
        signature = session_key.sign(message)
    """
    
    def __init__(self):
        self._keypair: Optional[SessionKeypair] = None
        self._encrypted: Optional[EncryptedSessionKey] = None
        self._device_fingerprint: Optional[str] = None
        self._session_key_id: Optional[str] = None
        
        # Cached unlocked keypair (in memory)
        self._cached_keypair: Optional[SessionKeypair] = None
        self._cache_expires_at: Optional[datetime] = None
    
    @classmethod
    async def create(
        cls,
        pin: str,
        limit_usdc: float,
        duration_days: int,
        user_wallet: str,
        generate_recovery_qr: bool = False,
    ) -> "DeviceBoundSessionKey":
        """
        Create a new device-bound session key.
        
        Args:
            pin: 6-digit numeric PIN for encryption
            limit_usdc: Spending limit in USDC
            duration_days: Duration in days (1-30)
            user_wallet: User's main wallet address
            generate_recovery_qr: Whether to generate recovery QR
            
        Returns:
            DeviceBoundSessionKey instance
        """
        if not HAS_NACL or not HAS_CRYPTOGRAPHY:
            raise ImportError(
                "Missing crypto dependencies. Install with: "
                "pip install pynacl cryptography"
            )
        
        instance = cls()
        
        # Generate device fingerprint
        device_fp = DeviceFingerprintGenerator.generate()
        instance._device_fingerprint = device_fp.fingerprint
        
        # Generate Ed25519 keypair
        keypair = generate_keypair()
        instance._keypair = keypair
        
        # Encrypt keypair with PIN + device fingerprint
        encrypted = SessionKeyCrypto.encrypt(
            keypair=keypair,
            pin=pin,
            device_fingerprint=device_fp.fingerprint,
        )
        instance._encrypted = encrypted
        
        return instance
    
    def get_encrypted_data(self) -> EncryptedSessionKey:
        """Get the encrypted session key data for backend storage."""
        if self._encrypted is None:
            raise ValueError("Session key not initialized")
        return self._encrypted
    
    def get_device_fingerprint(self) -> str:
        """Get the device fingerprint."""
        if self._device_fingerprint is None:
            raise ValueError("Session key not initialized")
        return self._device_fingerprint
    
    def get_public_key(self) -> str:
        """Get the session wallet public key (base58)."""
        if self._keypair is not None:
            return self._keypair.public_key
        if self._encrypted is not None:
            return self._encrypted.public_key
        raise ValueError("Session key not initialized")
    
    def set_session_key_id(self, session_key_id: str) -> None:
        """Set the session key ID (from backend response)."""
        self._session_key_id = session_key_id
    
    def get_session_key_id(self) -> Optional[str]:
        """Get the session key ID."""
        return self._session_key_id
    
    @property
    def is_unlocked(self) -> bool:
        """Check if the session key is unlocked (has usable keypair)."""
        # Just created - has raw keypair
        if self._keypair is not None:
            return True
        # Cached from unlock
        return self.is_cached()
    
    def is_cached(self) -> bool:
        """Check if the keypair is cached (unlocked) and not expired."""
        if self._cached_keypair is None:
            return False
        if self._cache_expires_at is None:
            return False
        return datetime.now() < self._cache_expires_at
    
    def unlock_with_pin(
        self,
        pin: str,
        cache_ttl_minutes: int = 30,
    ) -> SessionKeypair:
        """
        Unlock the session key with PIN and cache the keypair.
        
        Args:
            pin: 6-digit PIN used during creation
            cache_ttl_minutes: How long to cache the keypair (default: 30 min)
            
        Returns:
            The unlocked SessionKeypair
        """
        if self._encrypted is None:
            raise ValueError("Session key not initialized")
        
        # Get current device fingerprint
        device_fp = DeviceFingerprintGenerator.generate()
        
        # Decrypt
        keypair = SessionKeyCrypto.decrypt(
            encrypted=self._encrypted,
            pin=pin,
            device_fingerprint=device_fp.fingerprint,
        )
        
        # Cache it
        self._cached_keypair = keypair
        self._cache_expires_at = datetime.now() + timedelta(minutes=cache_ttl_minutes)
        
        return keypair
    
    def lock(self) -> None:
        """Clear the cached keypair and raw keypair."""
        self._keypair = None  # Clear raw keypair too
        self._cached_keypair = None
        self._cache_expires_at = None
    
    def get_keypair(self, pin: Optional[str] = None) -> SessionKeypair:
        """
        Get the keypair for signing.
        
        If cached, returns immediately. Otherwise, requires PIN.
        
        Args:
            pin: PIN to decrypt (only required if not cached)
            
        Returns:
            SessionKeypair for signing
        """
        # Check cache first
        if self.is_cached() and self._cached_keypair is not None:
            return self._cached_keypair
        
        # If we have the raw keypair (just created), use it
        if self._keypair is not None:
            return self._keypair
        
        # Need to decrypt
        if pin is None:
            raise ValueError(
                "PIN required: session key not unlocked. "
                "Provide PIN or call unlock_with_pin() first."
            )
        
        return self.unlock_with_pin(pin)
    
    def sign(self, message: bytes, pin: Optional[str] = None) -> bytes:
        """
        Sign a message with the session key.
        
        Args:
            message: Message bytes to sign
            pin: PIN to decrypt (only required if not cached)
            
        Returns:
            64-byte Ed25519 signature
        """
        keypair = self.get_keypair(pin)
        return keypair.sign(message)
    
    def sign_base64(self, message: bytes, pin: Optional[str] = None) -> str:
        """
        Sign a message and return base64-encoded signature.
        
        Args:
            message: Message bytes to sign
            pin: PIN to decrypt (only required if not cached)
            
        Returns:
            Base64-encoded signature string
        """
        return base64.b64encode(self.sign(message, pin)).decode()


# ============================================
# Session Keys Manager
# ============================================

# Type for the HTTP request function
RequestFn = Callable[[str, str, Optional[Dict[str, Any]]], Awaitable[Dict[str, Any]]]


class SessionKeysManager:
    """
    Manages device-bound session keys.
    
    This class handles:
    - Creating new session keys with PIN encryption
    - Loading existing session keys from backend
    - Unlocking/locking session keys
    - Making payments with client-side signing
    - Checking session key status
    
    Usage:
        # Initialize with request function (from ZendFiClient)
        manager = SessionKeysManager(client._request)
        
        # Create a session key
        result = await manager.create(CreateSessionKeyOptions(
            user_wallet="7xKNH...",
            agent_id="shopping-agent",
            limit_usdc=100.0,
            pin="123456",
        ))
        
        # Unlock for signing
        manager.unlock(result.session_key_id, "123456")
        
        # Make payments without PIN
        payment = await manager.make_payment(
            session_key_id=result.session_key_id,
            amount=5.0,
            recipient="8xYZA...",
        )
    """
    
    def __init__(self, request_fn: RequestFn, debug: bool = False):
        self._request = request_fn
        self._debug = debug
        
        # Local storage for session keys
        self._session_keys: Dict[str, DeviceBoundSessionKey] = {}
        self._session_metadata: Dict[str, Dict[str, Any]] = {}
    
    def _log(self, *args) -> None:
        """Debug logging."""
        if self._debug:
            print("[ZendFi SessionKeys]", *args)
    
    async def create(self, options: CreateSessionKeyOptions) -> SessionKeyResult:
        """
        Create a new device-bound session key.
        
        The keypair is generated client-side and encrypted with your PIN.
        The backend NEVER sees your private key.
        
        Args:
            options: Session key configuration
            
        Returns:
            SessionKeyResult with session key ID and wallet
        """
        if not options.pin or len(options.pin) < 4:
            raise ValueError("PIN must be at least 4 characters")
        
        self._log(f"Creating session key for agent: {options.agent_id}")
        
        # Create device-bound session key (client-side)
        session_key = await DeviceBoundSessionKey.create(
            pin=options.pin,
            limit_usdc=options.limit_usdc,
            duration_days=options.duration_days,
            user_wallet=options.user_wallet,
            generate_recovery_qr=options.generate_recovery_qr,
        )
        
        # Get encrypted data
        encrypted = session_key.get_encrypted_data()
        
        self._log(f"Session wallet: {encrypted.public_key[:8]}...")
        
        # Encrypt with Lit Protocol for autonomous signing (if enabled)
        # NOTE: Lit Protocol can take 2-5 minutes due to network latency
        lit_encryption: Optional[LitEncryptionResult] = None
        if options.enable_lit_protocol:
            self._log("Encrypting session key with Lit Protocol (may take 2-5 min)...")
            keypair = session_key.get_keypair()
            if keypair:
                lit_encryption = encrypt_keypair_with_lit(
                    keypair=keypair,
                    network=options.lit_network,
                )
                if lit_encryption:
                    self._log("✓ Lit Protocol encryption successful - autonomous signing enabled")
                else:
                    self._log("⚠ Lit Protocol encryption failed/timeout - using client signing fallback")
            else:
                self._log("⚠ Cannot get keypair for Lit encryption - session key may be locked")
        else:
            self._log("ℹ Lit Protocol disabled - using client signing mode (set enable_lit_protocol=True for autonomous)")
        
        # Generate recovery QR if requested (placeholder for now)
        recovery_qr: Optional[str] = None
        if options.generate_recovery_qr:
            # TODO: Generate actual QR code
            recovery_qr = base64.b64encode(
                f"{encrypted.public_key}:{encrypted.nonce}".encode()
            ).decode()
        
        # Prepare backend request
        request_data = {
            "user_wallet": options.user_wallet,
            "agent_id": options.agent_id,
            "agent_name": options.agent_name or f"LangChain Agent ({options.agent_id})",
            "limit_usdc": options.limit_usdc,
            "duration_days": options.duration_days,
            "encrypted_session_key": encrypted.encrypted_data,
            "nonce": encrypted.nonce,
            "session_public_key": encrypted.public_key,
            "device_fingerprint": session_key.get_device_fingerprint(),
            "recovery_qr_data": recovery_qr,
            # Lit Protocol encryption (for autonomous signing)
            "lit_encrypted_keypair": lit_encryption.ciphertext if lit_encryption else None,
            "lit_data_hash": lit_encryption.data_hash if lit_encryption else None,
        }
        
        # Call backend API
        response = await self._request(
            "POST",
            "/api/v1/ai/session-keys/device-bound/create",
            request_data,
        )
        
        session_key_id = response["session_key_id"]
        backend_session_wallet = response.get("session_wallet", "")
        local_public_key = encrypted.public_key
        
        # CRITICAL: Check if backend returned an existing session key
        # If so, the session_wallet won't match our locally generated keypair
        if backend_session_wallet and backend_session_wallet != local_public_key:
            self._log(f"⚠ Backend returned existing session key (different wallet)")
            self._log(f"  Backend: {backend_session_wallet[:16]}...")
            self._log(f"  Local:   {local_public_key[:16]}...")
            self._log(f"  → You must load the existing session key with PIN, or use a unique agent_id")
            
            # Don't store the local keypair - it won't work for signing!
            # Raise an error to help the user understand the issue
            raise ValueError(
                f"Session key already exists for agent '{options.agent_id}'. "
                f"The existing session wallet ({backend_session_wallet[:16]}...) doesn't match "
                f"the locally generated keypair. Options:\n"
                f"  1. Load the existing session with: session_keys.load('{session_key_id[:8]}...', pin)\n"
                f"  2. Use a unique agent_id (e.g., '{options.agent_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}')"
            )
        
        # Store session key locally
        session_key.set_session_key_id(session_key_id)
        self._session_keys[session_key_id] = session_key
        
        # Store metadata
        self._session_metadata[session_key_id] = {
            "agent_id": response.get("agent_id", options.agent_id),
            "agent_name": response.get("agent_name"),
            "user_wallet": options.user_wallet,
        }
        
        self._log(f"Session key created: {session_key_id[:8]}...")
        
        return SessionKeyResult(
            session_key_id=session_key_id,
            agent_id=response.get("agent_id", options.agent_id),
            session_wallet=response.get("session_wallet", encrypted.public_key),
            limit_usdc=response.get("limit_usdc", options.limit_usdc),
            expires_at=response.get("expires_at", ""),
            cross_app_compatible=response.get("cross_app_compatible", True),
            agent_name=response.get("agent_name"),
            recovery_qr=recovery_qr,
        )
    
    async def load(self, session_key_id: str, pin: str) -> None:
        """
        Load an existing session key from backend.
        
        Fetches the encrypted session key and decrypts it with your PIN.
        Use this when resuming a session on the same device.
        
        Args:
            session_key_id: UUID of the session key
            pin: PIN to decrypt the session key
        """
        self._log(f"Loading session key: {session_key_id[:8]}...")
        
        # Get current device fingerprint
        device_fp = DeviceFingerprintGenerator.generate()
        
        # Fetch encrypted session key from backend
        response = await self._request(
            "POST",
            "/api/v1/ai/session-keys/device-bound/get-encrypted",
            {
                "session_key_id": session_key_id,
                "device_fingerprint": device_fp.fingerprint,
            },
        )
        
        if not response.get("device_fingerprint_valid", True):
            raise ValueError(
                "Device fingerprint mismatch - this session key was created "
                "on a different device."
            )
        
        # Reconstruct encrypted session key
        encrypted = EncryptedSessionKey(
            encrypted_data=response["encrypted_session_key"],
            nonce=response["nonce"],
            public_key="",  # Will be set after decryption
            device_fingerprint=device_fp.fingerprint,
        )
        
        # Decrypt to verify PIN
        keypair = SessionKeyCrypto.decrypt(encrypted, pin, device_fp.fingerprint)
        encrypted.public_key = keypair.public_key
        
        # Create session key instance
        session_key = DeviceBoundSessionKey()
        session_key._encrypted = encrypted
        session_key._device_fingerprint = device_fp.fingerprint
        session_key.set_session_key_id(session_key_id)
        
        # Store locally
        self._session_keys[session_key_id] = session_key
        
        self._log(f"Session key loaded: {session_key_id[:8]}...")
    
    def unlock(
        self,
        session_key_id: str,
        pin: str,
        cache_ttl_minutes: int = 30,
    ) -> None:
        """
        Unlock a session key for auto-signing.
        
        After unlocking, payments can be made without entering PIN.
        
        Args:
            session_key_id: UUID of the session key
            pin: PIN to decrypt
            cache_ttl_minutes: How long to cache (default: 30 min)
        """
        session_key = self._session_keys.get(session_key_id)
        if session_key is None:
            raise ValueError(
                f"Session key {session_key_id[:8]}... not loaded. "
                "Call create() or load() first."
            )
        
        session_key.unlock_with_pin(pin, cache_ttl_minutes)
        self._log(f"Session key unlocked: {session_key_id[:8]}...")
    
    def lock(self, session_key_id: str) -> None:
        """
        Lock a session key (clear cached keypair).
        
        Args:
            session_key_id: UUID of the session key
        """
        session_key = self._session_keys.get(session_key_id)
        if session_key:
            session_key.lock()
            self._log(f"Session key locked: {session_key_id[:8]}...")
    
    def get_keypair(
        self,
        session_key_id: str,
        pin: Optional[str] = None,
    ) -> SessionKeypair:
        """
        Get the keypair for a session key.
        
        Args:
            session_key_id: UUID of the session key
            pin: PIN if not unlocked
            
        Returns:
            SessionKeypair for signing
        """
        session_key = self._session_keys.get(session_key_id)
        if session_key is None:
            raise ValueError(f"Session key {session_key_id[:8]}... not loaded.")
        
        return session_key.get_keypair(pin)
    
    def sign(
        self,
        session_key_id: str,
        message: bytes,
        pin: Optional[str] = None,
    ) -> bytes:
        """
        Sign a message with a session key.
        
        Args:
            session_key_id: UUID of the session key
            message: Message to sign
            pin: PIN if not unlocked
            
        Returns:
            64-byte Ed25519 signature
        """
        session_key = self._session_keys.get(session_key_id)
        if session_key is None:
            raise ValueError(f"Session key {session_key_id[:8]}... not loaded.")
        
        return session_key.sign(message, pin)
    
    def sign_delegation(
        self,
        session_key_id: str,
        max_amount_usd: float,
        expires_at: str,
        pin: Optional[str] = None,
    ) -> str:
        """
        Sign a delegation message for enabling autonomy.
        
        Args:
            session_key_id: UUID of the session key
            max_amount_usd: Maximum spending amount
            expires_at: ISO 8601 expiration timestamp
            pin: PIN if not unlocked
            
        Returns:
            Base64-encoded delegation signature
        """
        # Create delegation message
        message = create_delegation_message(
            session_key_id=session_key_id,
            max_amount_usd=max_amount_usd,
            expires_at=expires_at,
        )
        
        # Sign it
        session_key = self._session_keys.get(session_key_id)
        if session_key is None:
            raise ValueError(f"Session key {session_key_id[:8]}... not loaded.")
        
        return session_key.sign_base64(message.encode(), pin)
    
    async def get_status(self, session_key_id: str) -> SessionKeyInfo:
        """
        Get session key status from backend.
        
        Args:
            session_key_id: UUID of the session key
            
        Returns:
            SessionKeyInfo with current status
        """
        response = await self._request(
            "POST",
            "/api/v1/ai/session-keys/status",
            {"session_key_id": session_key_id},
        )
        
        return SessionKeyInfo(
            session_key_id=session_key_id,
            is_active=response.get("is_active", False),
            is_approved=response.get("is_approved", False),
            limit_usdc=response.get("limit_usdc", 0),
            used_amount_usdc=response.get("used_amount_usdc", 0),
            remaining_usdc=response.get("remaining_usdc", 0),
            expires_at=response.get("expires_at", ""),
            days_until_expiry=response.get("days_until_expiry", 0),
        )
    
    async def make_payment(
        self,
        session_key_id: str,
        amount: float,
        recipient: str,
        description: str = "",
    ) -> PaymentResult:
        """
        Make a payment using a session key.
        
        The backend will sign the transaction using Lit Protocol shards,
        enabling true autonomous payments without user interaction.
        
        Args:
            session_key_id: UUID of the session key
            amount: Amount in USDC
            recipient: Recipient wallet address
            description: Payment description
            
        Returns:
            PaymentResult with payment_id, signature, and status
        """
        response = await self._request(
            "POST",
            "/api/v1/ai/session-keys/payment",
            {
                "session_key_id": session_key_id,
                "amount": amount,
                "recipient": recipient,
                "description": description,
            },
        )
        
        return PaymentResult(
            payment_id=response.get("payment_id", ""),
            signature=response.get("signature", ""),
            status=response.get("status", "pending"),
        )
    
    async def revoke(self, session_key_id: str) -> None:
        """
        Revoke a session key.
        
        Permanently deactivates the session key. Cannot be undone.
        
        Args:
            session_key_id: UUID of the session key
        """
        await self._request(
            "POST",
            "/api/v1/ai/session-keys/revoke",
            {"session_key_id": session_key_id},
        )
        
        # Clear local state
        self._session_keys.pop(session_key_id, None)
        self._session_metadata.pop(session_key_id, None)
        
        self._log(f"Session key revoked: {session_key_id[:8]}...")
    
    def get_session_wallet(self, session_key_id: str) -> str:
        """
        Get the session wallet address for a session key.
        
        Args:
            session_key_id: UUID of the session key
            
        Returns:
            Base58 public key of the session wallet
        """
        session_key = self._session_keys.get(session_key_id)
        if session_key is None:
            raise ValueError(f"Session key {session_key_id[:8]}... not loaded.")
        
        return session_key.get_public_key()
    
    def is_loaded(self, session_key_id: str) -> bool:
        """Check if a session key is loaded."""
        return session_key_id in self._session_keys
    
    def is_unlocked(self, session_key_id: str) -> bool:
        """Check if a session key is unlocked (cached)."""
        session_key = self._session_keys.get(session_key_id)
        if session_key is None:
            return False
        return session_key.is_cached()
    
    def get_session_key(self, session_key_id: str) -> Optional[DeviceBoundSessionKey]:
        """
        Get the session key object for a given ID.
        
        Args:
            session_key_id: UUID of the session key
            
        Returns:
            DeviceBoundSessionKey if loaded, None otherwise
        """
        return self._session_keys.get(session_key_id)


# ============================================
# Exports
# ============================================

__all__ = [
    # Types
    "CreateSessionKeyOptions",
    "SessionKeyResult",
    "SessionKeyInfo",
    "PaymentResult",
    # Classes
    "DeviceBoundSessionKey",
    "SessionKeysManager",
]
