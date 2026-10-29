"""KAKEHASHI core wrapper: the single entry point to Key Vault for every chat."""

from .core.crypto_service import CryptoService
from .core.key_vault_connector import (
    DEFAULT_CACHE_TTL_SECONDS,
    KeyVaultAuthenticationError,
    KeyVaultConnector,
    KeyVaultError,
)
from .models.crypto_models import EncryptedData, KeyVersion

__all__ = [
    "CryptoService",
    "DEFAULT_CACHE_TTL_SECONDS",
    "EncryptedData",
    "KeyVaultAuthenticationError",
    "KeyVaultConnector",
    "KeyVaultError",
    "KeyVersion",
]
