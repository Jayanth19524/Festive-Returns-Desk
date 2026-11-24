"""Owner approval with Touch ID (WebAuthn), verified on the server with the `cryptography` package.

Registration: the browser makes a P-256 key in the Mac's secure enclave and sends us its PUBLIC key (SPKI, via
getPublicKey()). We keep that key. Approval: for one specific case we issue a one-time random challenge; the browser has
Touch ID sign it; we verify (1) the challenge and origin in clientDataJSON, (2) the rpIdHash and the user-verified flag in
authenticatorData, (3) the ES256 signature over authenticatorData + SHA-256(clientDataJSON) with the stored key.
Attestation is not checked (first registration is trusted, and only from the local machine). Relying-party id: localhost.
"""
import base64, hashlib, json, os, secrets, time
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from . import db

RP_ID = "localhost"
ORIGINS = os.getenv("WEBAUTHN_ORIGINS", "http://localhost:5174,http://localhost:8200").split(",")
CHALLENGE_TTL = 120
_challenges: dict[str, tuple[str, float]] = {}   # challenge -> (purpose, expires). In memory: fine for one process.


def b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def new_challenge(purpose: str) -> str:
    ch = b64u(secrets.token_bytes(32))
    _challenges[ch] = (purpose, time.time() + CHALLENGE_TTL)
    return ch


def _check_client_data(client_data_json: bytes, expected_type: str, purpose: str) -> None:
    cd = json.loads(client_data_json)
    if cd.get("type") != expected_type:
        raise ValueError("wrong clientData type")
    if cd.get("origin") not in ORIGINS:
        raise ValueError(f"origin {cd.get('origin')} not allowed")
    entry = _challenges.pop(cd.get("challenge", ""), None)  # single use
    if not entry or entry[0] != purpose or entry[1] < time.time():
        raise ValueError("unknown, reused, expired or mismatched challenge")


def has_credential() -> bool:
    with db.conn() as c:
        return c.execute("SELECT 1 FROM owner_credentials").fetchone() is not None


def register(credential_id: str, client_data_json: str, public_key_spki: str) -> None:
    if has_credential():
        raise ValueError("an owner key is already registered")
    _check_client_data(b64u_decode(client_data_json), "webauthn.create", "register")
    key = serialization.load_der_public_key(b64u_decode(public_key_spki))
    if not isinstance(key, ec.EllipticCurvePublicKey) or key.curve.name != "secp256r1":
        raise ValueError("only ES256 (P-256) keys are supported")
    with db.conn() as c:
        c.execute("INSERT INTO owner_credentials (credential_id, public_key, sign_count) VALUES (?,?,0)",
                  (credential_id, public_key_spki))


def verify_approval(case_id: int, credential_id: str, client_data_json: str, authenticator_data: str, signature: str) -> None:
    """Raises ValueError unless this is a fresh Touch ID signature, by the registered owner key, for THIS case."""
    with db.conn() as c:
        row = c.execute("SELECT * FROM owner_credentials WHERE credential_id=?", (credential_id,)).fetchone()
        if not row:
            raise ValueError("unknown credential")
        cd_raw, ad = b64u_decode(client_data_json), b64u_decode(authenticator_data)
        _check_client_data(cd_raw, "webauthn.get", f"approve:{case_id}")
        if ad[:32] != hashlib.sha256(RP_ID.encode()).digest():
            raise ValueError("rpIdHash mismatch")
        flags = ad[32]
        if not (flags & 0x01 and flags & 0x04):
            raise ValueError("user presence and user verification (Touch ID) required")
        key = serialization.load_der_public_key(b64u_decode(row["public_key"]))
        try:
            key.verify(b64u_decode(signature), ad + hashlib.sha256(cd_raw).digest(), ec.ECDSA(hashes.SHA256()))
        except InvalidSignature:
            raise ValueError("bad signature")
        sign_count = int.from_bytes(ad[33:37], "big")
        if sign_count and sign_count <= row["sign_count"]:
            raise ValueError("signature counter did not increase (cloned key?)")
        c.execute("UPDATE owner_credentials SET sign_count=? WHERE credential_id=?", (sign_count, credential_id))
