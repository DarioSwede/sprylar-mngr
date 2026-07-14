// WebCrypto-motsvarighet till scripts/crypto_utils.py.
// Parametrarna (PBKDF2-SHA256, 210 000 iterationer, AES-256-GCM) MÅSTE
// matcha exakt mellan Python och JS, annars går det inte att låsa upp.
const KDF_ITERATIONS = 210000;

function b64ToBytes(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

async function deriveAesKey(password, saltB64, iterations) {
  const salt = b64ToBytes(saltB64);
  const passKey = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveKey"]
  );
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations: iterations || KDF_ITERATIONS, hash: "SHA-256" },
    passKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["decrypt"]
  );
}

// Kastar ett fel (fel lösenord / trasig data) om dekrypteringen misslyckas.
async function decryptStore(blob, password) {
  const key = await deriveAesKey(password, blob.salt, blob.iterations);
  const iv = b64ToBytes(blob.iv);
  const ciphertext = b64ToBytes(blob.ciphertext);
  const plainBuf = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, ciphertext);
  return JSON.parse(new TextDecoder().decode(plainBuf));
}
