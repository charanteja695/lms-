"""Generate an RSA key pair for RS256 access tokens.

    python scripts/generate_jwt_keys.py keys/

Mount the private key only into this service. Other services need nothing: they fetch
the public key from /.well-known/jwks.json.
"""

import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "keys")
    out_dir.mkdir(parents=True, exist_ok=True)
    private_path, public_path = out_dir / "jwt_private.pem", out_dir / "jwt_public.pem"
    if private_path.exists():
        print(f"{private_path} already exists; refusing to overwrite", file=sys.stderr)
        return 1

    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private_path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    public_path.write_bytes(
        key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    print(f"Wrote {private_path} and {public_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
