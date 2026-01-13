import base64
import html
import logging
import mimetypes
import os
from email.message import EmailMessage
from typing import Any, Dict, List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from gmail_auth import get_creds

logger = logging.getLogger(__name__)

_service = None


def _build_service():
    """Get cached or new Gmail API service."""
    global _service
    if _service is None:
        creds = get_creds()
        _service = build("gmail", "v1", credentials=creds)
        logger.debug("Built Gmail API service")
    return _service


def _encode_message(message: EmailMessage) -> str:
    return base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")


def _normalize_references(references: Optional[List[str]]) -> Optional[str]:
    if not references:
        return None
    if isinstance(references, str):
        return references
    return " ".join([ref for ref in references if ref])


def _add_attachments(message: EmailMessage, attachments: Optional[List[Dict[str, Any]]]) -> None:
    if not attachments:
        return
    for attachment in attachments:
        if "content_base64" in attachment:
            data = base64.b64decode(attachment["content_base64"])
            filename = attachment.get("filename")
            if not filename:
                raise ValueError("Attachment filename is required with content_base64")
            mime_type = attachment.get("mime_type") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        else:
            path = attachment.get("path")
            if not path:
                raise ValueError("Attachment must include path or content_base64")
            resolved_path = os.path.abspath(path)
            if not os.path.exists(resolved_path):
                raise FileNotFoundError(f"Attachment not found: {resolved_path}")
            with open(resolved_path, "rb") as handle:
                data = handle.read()
            filename = attachment.get("filename") or os.path.basename(resolved_path)
            mime_type = attachment.get("mime_type") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        maintype, subtype = mime_type.split("/", 1)
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)


def send_email(
    to: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    thread_id: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[List[str]] = None,
) -> str:
    """Send an email message."""
    try:
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
        payload: Dict[str, Any] = {"raw": encoded}
        if thread_id:
            payload["threadId"] = thread_id
        result = service.users().messages().send(userId="me", body=payload).execute()
        logger.info(f"Sent email to {to}, message_id={result['id']}")
        return result["id"]
    except HttpError as e:
        logger.error(f"Gmail API error sending email: {e}")
        raise


def _get_message_metadata(service, message_id: str) -> tuple:
    """Get message metadata and headers."""
    message = service.users().messages().get(
        userId="me", id=message_id, format="metadata",
        metadataHeaders=["Subject", "From", "To", "Date", "Message-ID", "References"],
    ).execute()
    headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}
    return message, headers


def get_message(message_id: str, format: str = "full") -> Dict[str, Any]:
    """Get a single message by ID."""
    try:
        service = _build_service()
        message = service.users().messages().get(userId="me", id=message_id, format=format).execute()
        result: Dict[str, Any] = {
            "id": message["id"],
            "threadId": message.get("threadId"),
            "snippet": message.get("snippet", ""),
            "labelIds": message.get("labelIds", []),
        }
        headers = {}
        payload = message.get("payload", {})
        for header in payload.get("headers", []):
            headers[header["name"]] = header["value"]
        result["headers"] = headers
        if format == "full":
            body_text = ""
            body_html = ""
            def extract_parts(part):
                nonlocal body_text, body_html
                mime_type = part.get("mimeType", "")
                body_data = part.get("body", {}).get("data")
                if body_data:
                    decoded = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
                    if mime_type == "text/plain":
                        body_text = decoded
                    elif mime_type == "text/html":
                        body_html = decoded
                for subpart in part.get("parts", []):
                    extract_parts(subpart)
            extract_parts(payload)
            result["body_text"] = body_text
            result["body_html"] = body_html
        logger.debug(f"Retrieved message {message_id}")
        return result
    except HttpError as e:
        logger.error(f"Gmail API error getting message: {e}")
        raise


def get_thread(thread_id: str, format: str = "full") -> Dict[str, Any]:
    """Get a thread with all its messages."""
    try:
        service = _build_service()
        thread = service.users().threads().get(userId="me", id=thread_id, format=format).execute()
        result: Dict[str, Any] = {"id": thread["id"], "snippet": thread.get("snippet", ""), "messages": []}
        for msg in thread.get("messages", []):
            msg_data: Dict[str, Any] = {"id": msg["id"], "snippet": msg.get("snippet", ""), "labelIds": msg.get("labelIds", [])}
            headers = {}
            payload = msg.get("payload", {})
            for header in payload.get("headers", []):
                headers[header["name"]] = header["value"]
            msg_data["headers"] = headers
            if format == "full":
                body_text = ""
                body_html = ""
                def extract_parts(part):
                    nonlocal body_text, body_html
                    mime_type = part.get("mimeType", "")
                    body_data = part.get("body", {}).get("data")
                    if body_data:
                        decoded = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
                        if mime_type == "text/plain":
                            body_text = decoded
                        elif mime_type == "text/html":
                            body_html = decoded
                    for subpart in part.get("parts", []):
                        extract_parts(subpart)
                extract_parts(payload)
                msg_data["body_text"] = body_text
                msg_data["body_html"] = body_html
            result["messages"].append(msg_data)
        logger.debug(f"Retrieved thread {thread_id}")
        return result
    except HttpError as e:
        logger.error(f"Gmail API error getting thread: {e}")
        raise


def reply_to_message(message_id: str, body: str, html_body: Optional[str] = None,
                     attachments: Optional[List[Dict[str, Any]]] = None, to_override: Optional[str] = None) -> str:
    """Reply to a message."""
    try:
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
        references: List[str] = []
        if references_header:
            references.extend(references_header.split())
        if message_id_header:
            references.append(message_id_header)
        return send_email(to_address, subject, body, html_body=html_body, attachments=attachments,
                         thread_id=message.get("threadId"), in_reply_to=message_id_header, references=references)
    except HttpError as e:
        logger.error(f"Gmail API error replying: {e}")
        raise


def forward_message(message_id: str, to: str, body: str, html_body: Optional[str] = None,
                   attachments: Optional[List[Dict[str, Any]]] = None, include_snippet: bool = True) -> str:
    """Forward a message."""
    try:
        service = _build_service()
        message, headers = _get_message_metadata(service, message_id)
        subject = headers.get("Subject", "")
        if not subject.lower().startswith("fwd:"):
            subject = f"Fwd: {subject}".strip()
        forwarded_block = ["", "---- Forwarded message ----",
            f"From: {headers.get('From', '')}", f"Date: {headers.get('Date', '')}",
            f"Subject: {headers.get('Subject', '')}", f"To: {headers.get('To', '')}", ""]
        if include_snippet:
            forwarded_block.append(message.get("snippet", ""))
        forwarded_text = (body or "") + "\n" + "\n".join(forwarded_block)
        forwarded_html = html_body
        if forwarded_html is not None:
            snippet = message.get("snippet", "")
            forwarded_html = forwarded_html or ""
            forwarded_html += "<hr><p><strong>Forwarded message</strong></p>"
            forwarded_html += f"<p>From: {html.escape(headers.get('From', ''))}<br>"
            forwarded_html += f"Date: {html.escape(headers.get('Date', ''))}<br>"
            forwarded_html += f"Subject: {html.escape(headers.get('Subject', ''))}<br>"
            forwarded_html += f"To: {html.escape(headers.get('To', ''))}</p>"
            if include_snippet:
                forwarded_html += f"<pre>{html.escape(snippet)}</pre>"
        return send_email(to, subject, forwarded_text, html_body=forwarded_html,
                         attachments=attachments, thread_id=message.get("threadId"))
    except HttpError as e:
        logger.error(f"Gmail API error forwarding: {e}")
        raise


def list_labels() -> List[Dict[str, Any]]:
    """List all Gmail labels."""
    try:
        service = _build_service()
        result = service.users().labels().list(userId="me").execute()
        labels = result.get("labels", [])
        logger.debug(f"Listed {len(labels)} labels")
        return labels
    except HttpError as e:
        logger.error(f"Gmail API error listing labels: {e}")
        raise


def list_threads(query: Optional[str] = None, max_results: int = 10,
                label_ids: Optional[List[str]] = None, page_token: Optional[str] = None) -> Dict[str, Any]:
    """List threads with optional filtering."""
    try:
        service = _build_service()
        params: Dict[str, Any] = {"userId": "me", "maxResults": max_results}
        if query:
            params["q"] = query
        if label_ids:
            params["labelIds"] = label_ids
        if page_token:
            params["pageToken"] = page_token
        result = service.users().threads().list(**params).execute()
        threads = result.get("threads", [])
        logger.debug(f"Listed {len(threads)} threads")
        response: Dict[str, Any] = {"threads": threads}
        if "nextPageToken" in result:
            response["nextPageToken"] = result["nextPageToken"]
        return response
    except HttpError as e:
        logger.error(f"Gmail API error listing threads: {e}")
        raise


def modify_message_labels(message_id: str, add_labels: Optional[List[str]] = None,
                         remove_labels: Optional[List[str]] = None) -> Dict[str, Any]:
    """Add or remove labels from a message."""
    try:
        service = _build_service()
        body: Dict[str, Any] = {}
        if add_labels:
            body["addLabelIds"] = add_labels
        if remove_labels:
            body["removeLabelIds"] = remove_labels
        result = service.users().messages().modify(userId="me", id=message_id, body=body).execute()
        logger.info(f"Modified labels on message {message_id}")
        return result
    except HttpError as e:
        logger.error(f"Gmail API error modifying labels: {e}")
        raise


def trash_message(message_id: str) -> Dict[str, Any]:
    """Move a message to trash."""
    try:
        service = _build_service()
        result = service.users().messages().trash(userId="me", id=message_id).execute()
        logger.info(f"Trashed message {message_id}")
        return result
    except HttpError as e:
        logger.error(f"Gmail API error trashing message: {e}")
        raise
