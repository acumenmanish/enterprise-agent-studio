from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings


class CredentialVaultError(ValueError):
    pass


def _fernet(settings: Settings) -> Fernet:
    key = settings.credential_encryption_key
    if key is None or not key.get_secret_value().strip():
        raise CredentialVaultError(
            "Set CREDENTIAL_ENCRYPTION_KEY in the backend environment to save "
            "per-agent secret overrides."
        )
    try:
        return Fernet(key.get_secret_value().encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise CredentialVaultError("CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key.") from exc


def encrypt_secret(settings: Settings, secret: str) -> bytes:
    return _fernet(settings).encrypt(secret.encode("utf-8"))


def decrypt_secret(settings: Settings, encrypted_secret: bytes) -> str:
    try:
        return _fernet(settings).decrypt(encrypted_secret).decode("utf-8")
    except InvalidToken as exc:
        raise CredentialVaultError(
            "The saved model-key override cannot be decrypted. Check CREDENTIAL_ENCRYPTION_KEY."
        ) from exc
