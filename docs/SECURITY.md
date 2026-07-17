# Security guide

- Rotate every credential that has ever been pasted into a chat, issue or screenshot.
- Never commit `.env`.
- Use Cloudflare Full (strict), origin TLS and restricted inbound firewall rules.
- Restrict aaPanel access to trusted IPs or a VPN.
- Keep the database, Redis, Qdrant and Ollama on the private Docker network.
- Use a unique `SECRET_KEY` and a valid Fernet `ENCRYPTION_KEY`.
- Enable database backups and test restoration.
- Review agent tool permissions; an agent must never receive unrestricted shell or database access.
- Treat phone, payment and medical workflows as high-risk and require explicit policy checks/human approval.
