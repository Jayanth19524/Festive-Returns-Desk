// Touch ID (WebAuthn) helpers. The private key never leaves the Mac; we send only public data and signatures.
const b64u = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64u = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
const getJson = (u) => fetch(u).then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.detail || r.status); return j; });
const postJson = (u, b) => fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) })
  .then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.detail || r.status); return j; });

// One-time: create the owner's Touch ID key and register its public half with the server.
export async function registerOwnerKey() {
  const { challenge, rp_id } = await getJson("/api/webauthn/register-challenge");
  const cred = await navigator.credentials.create({ publicKey: {
    rp: { id: rp_id, name: "Festive Returns Desk" },
    user: { id: new TextEncoder().encode("owner"), name: "owner", displayName: "Shop owner" },
    challenge: unb64u(challenge),
    pubKeyCredParams: [{ type: "public-key", alg: -7 }],  // ES256
    authenticatorSelection: { authenticatorAttachment: "platform", userVerification: "required" },
    attestation: "none",
  } });
  return postJson("/api/webauthn/register", {
    credential_id: b64u(cred.rawId),
    client_data_json: b64u(cred.response.clientDataJSON),
    public_key: b64u(cred.response.getPublicKey()),
  });
}

// Per case: the server gives a one-time challenge for THIS case; Touch ID signs it; the server verifies.
export async function approveWithTouchId(caseId) {
  const { challenge, rp_id, credential_id } = await getJson(`/api/cases/${caseId}/approval-challenge`);
  const cred = await navigator.credentials.get({ publicKey: {
    rpId: rp_id, challenge: unb64u(challenge), userVerification: "required",
    allowCredentials: [{ type: "public-key", id: unb64u(credential_id) }],
  } });
  return postJson(`/api/cases/${caseId}/approve-signed`, {
    credential_id: b64u(cred.rawId),
    client_data_json: b64u(cred.response.clientDataJSON),
    authenticator_data: b64u(cred.response.authenticatorData),
    signature: b64u(cred.response.signature),
  });
}
