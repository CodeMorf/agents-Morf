# Security policy

Do not open a public issue for a vulnerability or leaked secret. Rotate the affected credential immediately and contact the repository maintainers privately.

Secrets must be injected through environment variables or a production secret manager. API keys stored through the administration API are encrypted with `ENCRYPTION_KEY`; losing that key prevents decryption.
