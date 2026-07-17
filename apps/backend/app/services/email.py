import httpx

from app.core.config import settings


class EmailDeliveryError(RuntimeError):
    pass


async def send_email(to: str, subject: str, text_body: str, html_body: str | None = None) -> dict:
    if not settings.mail_enabled:
        raise EmailDeliveryError("Email delivery is disabled")
    if not settings.smtp2go_api_key:
        raise EmailDeliveryError("SMTP2GO_API_KEY is missing")
    payload = {
        "sender": f"{settings.mail_from_name} <{settings.mail_from_address}>",
        "to": [to],
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body or f"<p>{text_body}</p>",
        "custom_headers": [{"header": "Reply-To", "value": settings.mail_reply_to}],
    }
    headers = {"X-Smtp2go-Api-Key": settings.smtp2go_api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{settings.smtp2go_api_url.rstrip('/')}/email/send", headers=headers, json=payload
        )
    if response.is_error:
        raise EmailDeliveryError(f"SMTP2GO HTTP {response.status_code}: {response.text[:300]}")
    return response.json()
