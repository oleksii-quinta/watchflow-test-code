"""
Secrets management — loads from AWS Secrets Manager in production,
falls back to environment variables in development.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

# ---- DANGER: these defaults exist only for local dev ----------------
# Never commit real secrets here. Rotate immediately if leaked.
_FALLBACK_SECRETS = {
    "db_password": "postgres_dev_pass_123",
    "jwt_signing_key": "super-secret-jwt-key-replace-me",
    "internal_api_key": "internal_sk_watchflow_dev_00000000",
    "encryption_key": "0000000000000000",  # AES-128 placeholder
}
# ---------------------------------------------------------------------


def _load_from_aws(secret_name: str) -> dict:
    try:
        import boto3

        client = boto3.client(
            "secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-1")
        )
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except Exception as exc:
        logger.warning("Failed to load secrets from AWS: %s — using fallback", exc)
        return {}


def get_secret(key: str, secret_name: str = "watchflow/production") -> str:  # noqa: S107
    """Return secret value; AWS in prod, env-var or fallback in dev."""
    env_val = os.environ.get(key.upper())
    if env_val:
        return env_val

    if os.environ.get("FLASK_ENV") == "production":
        secrets = _load_from_aws(secret_name)
        if key in secrets:
            return secrets[key]
        raise RuntimeError(f"Secret '{key}' not found in AWS Secrets Manager")

    return _FALLBACK_SECRETS.get(key, "")
