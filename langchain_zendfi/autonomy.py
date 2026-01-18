"""
Autonomy API - Enable Autonomous Agent Signing
===============================================

The Autonomy API enables AI agents to make payments without user interaction
for each transaction, while maintaining cryptographic security through:

1. **Delegation Signatures** - User signs a message authorizing the agent
2. **Spending Limits** - Hard caps on total spending
3. **Time Bounds** - Automatic expiration
4. **Lit Protocol** (optional) - Threshold cryptography for key management

Compatible with TypeScript SDK's aip/autonomy.ts

@module autonomy
"""

import re
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, Awaitable, List


# ============================================
# Types
# ============================================

@dataclass
class EnableAutonomyRequest:
    """Request to enable autonomous mode for a session key."""
    max_amount_usd: float
    duration_hours: int
    delegation_signature: str
    expires_at: Optional[str] = None
    lit_encrypted_keypair: Optional[str] = None
    lit_data_hash: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class AutonomousDelegate:
    """An enabled autonomous delegate."""
    delegate_id: str
    session_key_id: str
    max_amount_usd: float
    spent_usd: float
    remaining_usd: float
    is_active: bool
    created_at: str
    expires_at: str
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AutonomyStatus:
    """Current autonomy status for a session key."""
    session_key_id: str
    autonomous_mode_enabled: bool
    delegate: Optional[AutonomousDelegate] = None
    
    def to_dict(self) -> dict:
        result = {
            "session_key_id": self.session_key_id,
            "autonomous_mode_enabled": self.autonomous_mode_enabled,
            "delegate": self.delegate.to_dict() if self.delegate else None,
        }
        return result


@dataclass
class SpendingAttestation:
    """ZendFi's signed commitment to spending state."""
    delegate_id: str
    session_key_id: str
    merchant_id: str
    spent_usd: float
    limit_usd: float
    requested_usd: float
    remaining_after_usd: float
    timestamp_ms: int
    nonce: str
    payment_id: str
    version: int


@dataclass
class SignedSpendingAttestation:
    """Signed attestation with ZendFi's cryptographic signature."""
    attestation: SpendingAttestation
    signature: str  # Base64-encoded Ed25519 signature
    signer_public_key: str  # Base58-encoded ZendFi public key


@dataclass
class AttestationAuditResponse:
    """Response from the attestation audit endpoint."""
    delegate_id: str
    attestation_count: int
    attestations: List[SignedSpendingAttestation]
    zendfi_attestation_public_key: Optional[str]


# ============================================
# Autonomy Manager
# ============================================

# Type for the HTTP request function
RequestFn = Callable[[str, str, Optional[Dict[str, Any]]], Awaitable[Dict[str, Any]]]


class AutonomyManager:
    """
    Manages autonomous agent signing.
    
    This class handles:
    - Enabling autonomous mode for session keys
    - Revoking autonomous mode
    - Checking autonomy status
    - Creating delegation messages
    - Fetching spending attestations (audit trail)
    
    Usage:
        # Initialize with request function (from ZendFiClient)
        manager = AutonomyManager(client._request)
        
        # Create delegation message
        message = manager.create_delegation_message(
            session_key_id="sk_123",
            max_amount_usd=100.0,
            expires_at="2024-12-10T00:00:00Z",
        )
        
        # Sign the message with session key
        signature = session_keys_manager.sign_delegation(
            session_key_id="sk_123",
            max_amount_usd=100.0,
            expires_at="2024-12-10T00:00:00Z",
            pin="123456",
        )
        
        # Enable autonomy
        delegate = await manager.enable(
            session_key_id="sk_123",
            request=EnableAutonomyRequest(
                max_amount_usd=100.0,
                duration_hours=24,
                delegation_signature=signature,
            ),
        )
    """
    
    def __init__(self, request_fn: RequestFn, debug: bool = False):
        self._request = request_fn
        self._debug = debug
    
    def _log(self, *args) -> None:
        """Debug logging."""
        if self._debug:
            print("[ZendFi Autonomy]", *args)
    
    async def enable(
        self,
        session_key_id: str,
        request: EnableAutonomyRequest,
    ) -> AutonomousDelegate:
        """
        Enable autonomous signing for a session key.
        
        This grants an AI agent the ability to sign transactions on behalf of
        the user, up to the specified spending limit and duration.
        
        Prerequisites:
        1. Create a device-bound session key first
        2. Generate a delegation signature (see `create_delegation_message`)
        3. Optionally encrypt keypair with Lit Protocol for true autonomy
        
        Args:
            session_key_id: UUID of the session key
            request: Autonomy configuration including delegation signature
            
        Returns:
            The created autonomous delegate
        """
        # Validate request
        self.validate_request(request)
        
        self._log(f"Enabling autonomy for session: {session_key_id[:8]}...")
        
        # Prepare API request
        request_data = {
            "max_amount_usd": request.max_amount_usd,
            "duration_hours": request.duration_hours,
            "delegation_signature": request.delegation_signature,
            "expires_at": request.expires_at,
            "lit_encrypted_keypair": request.lit_encrypted_keypair,
            "lit_data_hash": request.lit_data_hash,
            "metadata": request.metadata,
        }
        
        # Call backend API
        response = await self._request(
            "POST",
            f"/api/v1/ai/session-keys/{session_key_id}/enable-autonomy",
            request_data,
        )
        
        delegate = AutonomousDelegate(
            delegate_id=response["delegate_id"],
            session_key_id=response.get("session_key_id", session_key_id),
            max_amount_usd=response.get("max_amount_usd", request.max_amount_usd),
            spent_usd=response.get("spent_usd", 0),
            remaining_usd=response.get("remaining_usd", request.max_amount_usd),
            is_active=response.get("is_active", True),
            created_at=response.get("created_at", datetime.now().isoformat()),
            expires_at=response.get("expires_at", ""),
        )
        
        self._log(f"Autonomy enabled. Delegate: {delegate.delegate_id[:8]}...")
        
        return delegate
    
    async def revoke(self, session_key_id: str, reason: Optional[str] = None) -> None:
        """
        Revoke autonomous mode for a session key.
        
        Immediately invalidates the autonomous delegate, preventing any further
        automatic payments. The session key itself remains valid for manual use.
        
        Args:
            session_key_id: UUID of the session key
            reason: Optional reason for revocation (logged for audit)
        """
        self._log(f"Revoking autonomy for session: {session_key_id[:8]}...")
        
        await self._request(
            "POST",
            f"/api/v1/ai/session-keys/{session_key_id}/revoke-autonomy",
            {"reason": reason} if reason else {},
        )
        
        self._log(f"Autonomy revoked for: {session_key_id[:8]}...")
    
    async def get_status(self, session_key_id: str) -> AutonomyStatus:
        """
        Get autonomy status for a session key.
        
        Returns whether autonomous mode is enabled and details about the
        active delegate including remaining spending allowance.
        
        Args:
            session_key_id: UUID of the session key
            
        Returns:
            Autonomy status with delegate details
        """
        response = await self._request(
            "GET",
            f"/api/v1/ai/session-keys/{session_key_id}/autonomy-status",
            None,
        )
        
        delegate = None
        if response.get("autonomous_mode_enabled") and response.get("delegate"):
            d = response["delegate"]
            delegate = AutonomousDelegate(
                delegate_id=d["delegate_id"],
                session_key_id=d.get("session_key_id", session_key_id),
                max_amount_usd=d.get("max_amount_usd", 0),
                spent_usd=d.get("spent_usd", 0),
                remaining_usd=d.get("remaining_usd", 0),
                is_active=d.get("is_active", False),
                created_at=d.get("created_at", ""),
                expires_at=d.get("expires_at", ""),
            )
        
        return AutonomyStatus(
            session_key_id=session_key_id,
            autonomous_mode_enabled=response.get("autonomous_mode_enabled", False),
            delegate=delegate,
        )
    
    def create_delegation_message(
        self,
        session_key_id: str,
        max_amount_usd: float,
        expires_at: str,
    ) -> str:
        """
        Create the delegation message that needs to be signed.
        
        This generates the exact message format required for the delegation
        signature. The user must sign this message with their session key.
        
        Message format:
        ```
        I authorize ZendFi autonomous payments:
        Session: {session_key_id}
        Max Amount: ${max_amount_usd} USD
        Expires: {expires_at}
        This signature enables automated transactions up to the specified limit.
        ```
        
        Args:
            session_key_id: UUID of the session key
            max_amount_usd: Maximum spending amount in USD
            expires_at: ISO 8601 expiration timestamp
            
        Returns:
            The message to be signed
        """
        return (
            f"I authorize ZendFi autonomous payments:\n"
            f"Session: {session_key_id}\n"
            f"Max Amount: ${max_amount_usd:.2f} USD\n"
            f"Expires: {expires_at}\n"
            f"This signature enables automated transactions up to the specified limit."
        )
    
    def validate_request(self, request: EnableAutonomyRequest) -> None:
        """
        Validate delegation signature parameters.
        
        Helper method to check if autonomy parameters are valid before
        making the API call.
        
        Args:
            request: The enable autonomy request to validate
            
        Raises:
            ValueError: If validation fails
        """
        if request.max_amount_usd <= 0:
            raise ValueError("max_amount_usd must be positive")
        
        if request.duration_hours < 1 or request.duration_hours > 168:
            raise ValueError("duration_hours must be between 1 and 168 (7 days)")
        
        if not request.delegation_signature:
            raise ValueError("delegation_signature is required")
        
        # Basic base64 validation
        base64_pattern = re.compile(r'^[A-Za-z0-9+/]+=*$')
        if not base64_pattern.match(request.delegation_signature):
            raise ValueError("delegation_signature must be base64 encoded")
    
    async def get_attestations(self, delegate_id: str) -> AttestationAuditResponse:
        """
        Get spending attestations for a delegate (audit trail).
        
        Returns all cryptographically signed attestations ZendFi created for
        this delegate. Each attestation contains:
        - The spending state at the time of payment
        - ZendFi's Ed25519 signature
        - Timestamp and nonce (for replay protection)
        
        These attestations can be independently verified using ZendFi's public key
        to confirm spending limit enforcement was applied correctly.
        
        Args:
            delegate_id: UUID of the autonomous delegate
            
        Returns:
            Attestation audit response with all signed attestations
        """
        response = await self._request(
            "GET",
            f"/api/v1/ai/delegates/{delegate_id}/attestations",
            None,
        )
        
        attestations = []
        for item in response.get("attestations", []):
            att = item["attestation"]
            attestation = SpendingAttestation(
                delegate_id=att["delegate_id"],
                session_key_id=att["session_key_id"],
                merchant_id=att["merchant_id"],
                spent_usd=att["spent_usd"],
                limit_usd=att["limit_usd"],
                requested_usd=att["requested_usd"],
                remaining_after_usd=att["remaining_after_usd"],
                timestamp_ms=att["timestamp_ms"],
                nonce=att["nonce"],
                payment_id=att["payment_id"],
                version=att["version"],
            )
            attestations.append(SignedSpendingAttestation(
                attestation=attestation,
                signature=item["signature"],
                signer_public_key=item["signer_public_key"],
            ))
        
        return AttestationAuditResponse(
            delegate_id=response["delegate_id"],
            attestation_count=response["attestation_count"],
            attestations=attestations,
            zendfi_attestation_public_key=response.get("zendfi_attestation_public_key"),
        )


# ============================================
# Helper Functions
# ============================================

def calculate_expires_at(duration_hours: int) -> str:
    """
    Calculate expiration timestamp from duration.
    
    Args:
        duration_hours: Duration in hours
        
    Returns:
        ISO 8601 timestamp string
    """
    expires = datetime.utcnow() + timedelta(hours=duration_hours)
    return expires.isoformat() + "Z"


# ============================================
# Exports
# ============================================

__all__ = [
    # Types
    "EnableAutonomyRequest",
    "AutonomousDelegate",
    "AutonomyStatus",
    "SpendingAttestation",
    "SignedSpendingAttestation",
    "AttestationAuditResponse",
    # Classes
    "AutonomyManager",
    # Helpers
    "calculate_expires_at",
]
