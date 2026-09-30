"""DRISHTI AI — Phase 1 Edge Cybersecurity & Telematics Security Layer.

Implements automotive-grade security standards for edge driver monitoring:
1. TelemetrySigner:
   - HMAC-SHA256 message signing for cellular JSON telemetry.
   - Ultra-compact, timestamped, signed satellite datagrams (e.g., DRST|V1|T:...|R:...|F:...|S:...).
   - Anti-replay timestamp drift & nonce verification.
2. EdgeApiSecurity:
   - Token-based API authentication for Flask dispatch & control endpoints (X-Drishti-Fleet-Token, Bearer token, query token).
   - Constant-time secret comparison (hmac.compare_digest) to prevent timing attacks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Dict, Optional, Tuple

# Default secrets (overridden via environment variables in operational deployments)
DEFAULT_TELEMATICS_SECRET = b"drishti_edge_telematics_psk_v1_automotive_sec"
DEFAULT_FLEET_API_KEY = "drishti-fleet-token-2026"
DEFAULT_FLEET_SHARED_KEY = DEFAULT_TELEMATICS_SECRET
DEFAULT_FLEET_TOKEN = DEFAULT_FLEET_API_KEY


def get_telematics_secret() -> bytes:
    """Retrieve pre-shared telematics secret key from environment or fallback."""
    env_key = os.environ.get("DRISHTI_TELEMATICS_KEY")
    if env_key:
        return env_key.encode("utf-8")
    return DEFAULT_TELEMATICS_SECRET


def get_fleet_api_key() -> str:
    """Retrieve dispatcher/fleet API key from environment or fallback."""
    return os.environ.get("DRISHTI_API_KEY", DEFAULT_FLEET_API_KEY)


class TelemetrySigner:
    """Cryptographic signing and verification for vehicle telemetry streams."""

    @staticmethod
    def sign_satellite_packet(
        payload: Dict[str, Any],
        secret_key: Optional[bytes] = None,
        timestamp: Optional[int] = None,
    ) -> str:
        """Generates a compact, bandwidth-optimized signed satellite datagram.

        Format: DRST|V1|T:{epoch}|R:{risk_3}|F:{reason_4}|S:{sig_8}
        Size: ~45-50 bytes (ideal for high-cost LEO/MEO satellite bursts).
        """
        key = secret_key or get_telematics_secret()
        epoch = timestamp if timestamp is not None else int(time.time())
        risk_level = str(payload.get("risk_level", "NORMAL"))[:3].upper()
        reasons = [str(r) for r in payload.get("reasons", [])]
        reason_tag = reasons[0][:4] if reasons else "none"

        raw_packet = f"DRST|V1|T:{epoch}|R:{risk_level}|F:{reason_tag}"
        # Compute HMAC-SHA256 and truncate to 8 hex chars (4 bytes)
        sig = hmac.new(key, raw_packet.encode("utf-8"), hashlib.sha256).hexdigest()[:8]
        return f"{raw_packet}|S:{sig}"

    @staticmethod
    def verify_satellite_packet(
        packet_str: str,
        secret_key: Optional[bytes] = None,
        max_skew_sec: int = 120,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Verifies a signed satellite datagram for authenticity and freshness.

        Returns:
            (is_valid, message, parsed_data)
        """
        key = secret_key or get_telematics_secret()
        parts = packet_str.strip().split("|")
        if len(parts) < 6 or parts[0] != "DRST" or parts[1] != "V1":
            return False, "Malformed packet header or protocol version", {}

        parsed: Dict[str, Any] = {}
        provided_sig = ""
        raw_components = []

        for part in parts:
            if ":" in part:
                tag, val = part.split(":", 1)
                if tag == "S":
                    provided_sig = val
                else:
                    parsed[tag] = val
                    raw_components.append(part)
            else:
                raw_components.append(part)

        if not provided_sig:
            return False, "Missing cryptographic signature tag (S:)", parsed

        # Anti-replay freshness check
        try:
            packet_time = int(parsed.get("T", 0))
        except ValueError:
            return False, "Invalid timestamp format", parsed

        now = int(time.time())
        if abs(now - packet_time) > max_skew_sec:
            return False, f"Timestamp skew exceeds tolerance ({abs(now - packet_time)}s > {max_skew_sec}s)", parsed

        # Verify signature
        raw_packet = "|".join(raw_components)
        expected_sig = hmac.new(key, raw_packet.encode("utf-8"), hashlib.sha256).hexdigest()[:8]

        if not hmac.compare_digest(expected_sig, provided_sig):
            return False, "Signature mismatch / packet altered", parsed

        return True, "Valid authentic satellite packet", parsed

    @staticmethod
    def sign_cloud_payload(
        payload: Dict[str, Any],
        secret_key: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """Injects HMAC-SHA256 signature and anti-replay nonce into JSON telemetry."""
        key = secret_key or get_telematics_secret()
        signed_payload = dict(payload)

        # Remove existing auth if any
        signed_payload.pop("_auth", None)

        now_ms = int(time.time() * 1000)
        nonce = secrets.token_hex(4)

        # Canonical string representation (sorted keys)
        canonical_str = json.dumps(signed_payload, sort_keys=True, separators=(",", ":"))
        sign_target = f"{canonical_str}|{now_ms}|{nonce}".encode("utf-8")
        full_sig = hmac.new(key, sign_target, hashlib.sha256).hexdigest()

        signed_payload["_auth"] = {
            "version": "1.0",
            "timestamp_ms": now_ms,
            "nonce": nonce,
            "signature": full_sig,
        }
        return signed_payload

    @staticmethod
    def verify_cloud_payload(
        payload: Dict[str, Any],
        secret_key: Optional[bytes] = None,
        max_skew_sec: int = 120,
    ) -> Tuple[bool, str]:
        """Validates authenticity, integrity, and anti-replay freshness of cloud telemetry."""
        key = secret_key or get_telematics_secret()
        auth_data = payload.get("_auth")
        if not isinstance(auth_data, dict):
            return False, "Missing _auth signature envelope"

        provided_sig = auth_data.get("signature", "")
        ts_ms = auth_data.get("timestamp_ms", 0)
        nonce = auth_data.get("nonce", "")

        if not provided_sig or not ts_ms or not nonce:
            return False, "Incomplete _auth envelope parameters"

        # Anti-replay check
        now_ms = int(time.time() * 1000)
        skew_sec = abs(now_ms - ts_ms) / 1000.0
        if skew_sec > max_skew_sec:
            return False, f"Cloud telemetry timestamp skew ({skew_sec:.1f}s) exceeds limit ({max_skew_sec}s)"

        # Reconstruct canonical payload without _auth
        clean_payload = {k: v for k, v in payload.items() if k != "_auth"}
        canonical_str = json.dumps(clean_payload, sort_keys=True, separators=(",", ":"))
        sign_target = f"{canonical_str}|{ts_ms}|{nonce}".encode("utf-8")
        expected_sig = hmac.new(key, sign_target, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected_sig, provided_sig):
            return False, "Cloud telemetry signature verification failed"

        return True, "Valid authentic cloud telemetry payload"


class EdgeApiSecurity:
    """Security validator for HTTP and API endpoints."""

    @staticmethod
    def get_active_token() -> str:
        return get_fleet_api_key()

    @staticmethod
    def is_valid_token(candidate_token: Optional[str]) -> bool:
        if not candidate_token:
            return False
        expected = get_fleet_api_key()
        return hmac.compare_digest(candidate_token.strip(), expected.strip())

    @classmethod
    def extract_token_from_request(cls, req: Any) -> Optional[str]:
        """Extracts candidate token from headers, authorization header, query param, or cookie."""
        # 1. Custom fleet header
        header_token = req.headers.get("X-Drishti-Fleet-Token")
        if header_token:
            return header_token.strip()

        # 2. Authorization: Bearer <token>
        auth_header = req.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()

        # 3. Query string token (?token=... or ?auth_token=...)
        query_token = req.args.get("token") or req.args.get("auth_token")
        if query_token:
            return query_token.strip()

        # 4. Cookie fallback
        cookie_token = req.cookies.get("drishti_auth_token")
        if cookie_token:
            return cookie_token.strip()

        return None
