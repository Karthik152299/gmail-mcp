import base64
from email.message import EmailMessage
from googleapiclient.discovery import build
from gmail_auth import get_creds


def send_email(to: str, subject: str, body: str) -> str:
    creds = get_creds()
    service = build("gmail", "v1", credentials=creds)

    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    result = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": encoded})
        .execute()
    )

    return result["id"]
