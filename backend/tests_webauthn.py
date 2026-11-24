"""WebAuthn verification tests using a SOFTWARE authenticator (a P-256 key made in Python).
They prove our server logic; they do NOT prove a real Touch ID prompt (that needs a human and a Mac).
Run: .venv/bin/python -m unittest backend.tests_webauthn -v
"""
import hashlib, json, os, tempfile, unittest
from pathlib import Path
os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "t.db")
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from backend.app import db, webauthn_owner as w

ORIGIN = "http://localhost:5174"


class Authn:
    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.spki = w.b64u(self.key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo))
        self.count = 0

    def cd(self, typ, challenge, origin=ORIGIN):
        return json.dumps({"type": typ, "challenge": challenge, "origin": origin}).encode()

    def assertion(self, challenge, flags=0x05, origin=ORIGIN, rp="localhost"):
        self.count += 1
        ad = hashlib.sha256(rp.encode()).digest() + bytes([flags]) + self.count.to_bytes(4, "big")
        cd = self.cd("webauthn.get", challenge, origin)
        sig = self.key.sign(ad + hashlib.sha256(cd).digest(), ec.ECDSA(hashes.SHA256()))
        return dict(credential_id="cred1", client_data_json=w.b64u(cd), authenticator_data=w.b64u(ad), signature=w.b64u(sig))


class T(unittest.TestCase):
    def setUp(self):
        db.reset()
        self.a = Authn()
        w.register("cred1", w.b64u(self.a.cd("webauthn.create", w.new_challenge("register"))), self.a.spki)

    def test_good_signature(self):
        w.verify_approval(7, **self.a.assertion(w.new_challenge("approve:7")))

    def test_wrong_case_challenge(self):
        with self.assertRaises(ValueError): w.verify_approval(8, **self.a.assertion(w.new_challenge("approve:7")))

    def test_challenge_single_use(self):
        ch = w.new_challenge("approve:7"); w.verify_approval(7, **self.a.assertion(ch))
        with self.assertRaises(ValueError): w.verify_approval(7, **self.a.assertion(ch))

    def test_no_user_verification(self):
        with self.assertRaises(ValueError): w.verify_approval(7, **self.a.assertion(w.new_challenge("approve:7"), flags=0x01))

    def test_wrong_origin(self):
        with self.assertRaises(ValueError): w.verify_approval(7, **self.a.assertion(w.new_challenge("approve:7"), origin="https://evil.example"))

    def test_other_key_rejected(self):
        evil = Authn(); good = evil.assertion(w.new_challenge("approve:7"))
        with self.assertRaises(ValueError): w.verify_approval(7, **good)

    def test_second_registration_refused(self):
        with self.assertRaises(ValueError): w.register("c2", w.b64u(self.a.cd("webauthn.create", w.new_challenge("register"))), self.a.spki)

if __name__ == "__main__": unittest.main()
