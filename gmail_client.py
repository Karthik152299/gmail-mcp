import base64
import html
import mimetypes
import os
from email.message import EmailMessage

from googleapiclient.discovery import build
from gmail_auth import get_creds


def _build_service():
    creds = get_creds()
    return build("gmail", "v1", credentials=creds)


def _encode_message(message: EmailMessage) -> str:
    return base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")


def _normalize_references(references):
    if not references:
        return None
    if isinstance(references, str):
        return references
    return " ".join([ref for ref in references if ref])


def _add_attachments(message: EmailMessage, attachments):
    if not attachments:
        return

    for attachment in attachments:
        if "content_base64" in attachment:
            data = base64.b64decode(attachment["content_base64"])
            filename = attachment.get("filename")
            if not filename:
                raise ValueError("Attachment filename is required with content_base64")
            mime_type = (
                attachment.get("mime_type")
                or mimetypes.guess_type(filename)[0]
                or "application/octet-stream"
            )
        else:
            path = attachment.get("path")
            if not path:
                raise ValueError("Attachment must include path or content_base64")
            with open(path, "rb") as handle:
                data = handle.read()
            filename = attachment.get("filename") or os.path.basename(path)
            mime_type = (
                attachment.get("mime_type")
                or mimetypes.guess_type(filename)[0]
                or "application/octet-stream"
            )

        maintype, subtype = mime_type.split("/", 1)
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)


def send_email(
    to: str,
    subject: str,
    body: str,
    html_body: str = None,
    attachments = None,
    thread_id: str = None,
    in_reply_to: str = None,
    references = None,
) -> str:
    service = _build_service()

    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to

    references_header = _normalize_references(references)
    if references_header:
        message["References"] = references_header

    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    _add_attachments(message, attachments)

    encoded = _encode_message(message)
    payload = {"raw": encoded}
    if thread_id:
        payload["threadId"] = thread_id

    result = (
        service.users()
        .messages()
        .send(userId="me", body=payload)
        .execute()
    )

    return result["id"]


def _get_message_metadata(service, message_id: str):
    message = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["Subject", "From", "To", "Date", "Message-ID", "References"],
        )
        .execute()
    )

    headers = {
        header["name"]: header["value"]
        for header in message.get("payload", {}).get("headers", [])
    }
    return message, headers


def reply_to_message(
    message_id: str,
    body: str,
    html_body: str = None,
    attachments = None,
    to_override: str = None,
) -> str:
    service = _build_service()
    message, headers = _get_message_metadata(service, message_id)

    to_address = to_override or headers.get("From")
    if not to_address:
        raise ValueError("Original message missing From header")

    subject = headers.get("Subject", "")
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}".strip()

    message_id_header = headers.get("Message-ID")
    references_header = headers.get("References", "")

    references = []
    if references_header:
        references.extend(references_header.split())
    if message_id_header:
        references.append(message_id_header)

    return send_email(
        to_address,
        subject,
        body,
        html_body=html_body,
        attachments=attachments,
        thread_id=message.get("threadId"),
        in_reply_to=message_id_header,
        references=references,
    )


def forward_message(
    message_id: str,
    to: str,
    body: str,
    html_body: str = None,
    attachments = None,
    include_snippet: bool = True,
) -> str:
    service = _build_service()
    message, headers = _get_message_metadata(service, message_id)

    subject = headers.get("Subject", "")
    if not subject.lower().startswith("fwd:"):
        subject = f"Fwd: {subject}".strip()

    forwarded_block = [
        "",
        "---- Forwarded message ----",
        f"From: {headers.get('From', '')}",
        f"Date: {headers.get('Date', '')}",
        f"Subject: {headers.get('Subject', '')}",
        f"To: {headers.get('To', '')}",
        "",
    ]
    if include_snippet:
        forwarded_block.append(message.get("snippet", ""))

    forwarded_text = (body or "") + "\n" + "\n".join(forwarded_block)

    forwarded_html = html_body
    if forwarded_html is not None:
        snippet = message.get("snippet", "")
        forwarded_html = forwarded_html or ""
        forwarded_html += "<hr>"
        forwarded_html += "<p><strong>Forwarded message</strong></p>"
        forwarded_html += (
            f"<p>From: {html.escape(headers.get('From', ''))}<br>"
            f"Date: {html.escape(headers.get('Date', ''))}<br>"
            f"Subject: {html.escape(headers.get('Subject', ''))}<br>"
            f"To: {html.escape(headers.get('To', ''))}</p>"
        )
        if include_snippet:
            forwarded_html += f"<pre>{html.escape(snippet)}</pre>"

    return send_email(
        to,
        subject,
        forwarded_text,
        html_body=forwarded_html,
        attachments=attachments,
        thread_id=message.get("threadId"),
    )


def list_labels() -> list:
    service = _build_service()
    result = service.users().labels().list(userId="me").execute()
    return result.get("labels", [])


def list_threads(query: str = None, max_results: int = 10, label_ids = None) -> list:
    service = _build_service()
    params = {"userId": "me", "maxResults": max_results}
    if query:
        params["q"] = query
    if label_ids:
        params["labelIds"] = label_ids

    result = service.users().threads().list(**params).execute()
    return result.get("threads", [])
