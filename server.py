import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

from gmail_client import (
    get_message as gmail_get_message,
    get_thread as gmail_get_thread,
    forward_message as forward_email_message,
    list_labels as gmail_list_labels,
    list_threads as gmail_list_threads,
    modify_message_labels as gmail_modify_labels,
    reply_to_message,
    send_email,
    trash_message as gmail_trash_message,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("gmail-mcp")

# Persistent drafts storage
DRAFTS_FILE = os.path.join(os.path.dirname(__file__), "drafts.json")


def _load_drafts() -> Dict[str, Any]:
    """Load drafts from disk."""
    if os.path.exists(DRAFTS_FILE):
        try:
            with open(DRAFTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load drafts: {e}")
    return {}


def _save_drafts(drafts: Dict[str, Any]) -> None:
    """Save drafts to disk."""
    try:
        with open(DRAFTS_FILE, "w", encoding="utf-8") as f:
            json.dump(drafts, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save drafts: {e}")


@mcp.tool()
def draft_email(
    to: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Create a draft email. Use send_draft to send it."""
    drafts = _load_drafts()
    draft_id = str(uuid.uuid4())
    drafts[draft_id] = {
        "to": to,
        "subject": subject,
        "body": body,
        "html_body": html_body,
        "attachments": attachments,
    }
    _save_drafts(drafts)
    logger.info(f"Created draft {draft_id}")
    return {"draft_id": draft_id, "preview": drafts[draft_id]}


@mcp.tool()
def draft_email_from_template(
    to: str,
    subject: str,
    template: str,
    variables: Dict[str, str],
    html_body: Optional[str] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Create a draft email using a template with variable substitution."""
    try:
        body = template.format(**variables)
    except KeyError as e:
        raise ValueError(f"Missing template variable: {e}")
    return draft_email(to, subject, body, html_body=html_body, attachments=attachments)


@mcp.tool()
def render_template(template: str, variables: Dict[str, str]) -> Dict[str, str]:
    """Render a template with variables (preview without creating draft)."""
    try:
        rendered = template.format(**variables)
    except KeyError as e:
        raise ValueError(f"Missing template variable: {e}")
    return {"rendered": rendered}


@mcp.tool()
def list_drafts() -> Dict[str, Any]:
    """List all saved drafts."""
    drafts = _load_drafts()
    return {"drafts": drafts, "count": len(drafts)}


@mcp.tool()
def delete_draft(draft_id: str) -> Dict[str, Any]:
    """Delete a draft by ID."""
    drafts = _load_drafts()
    if draft_id not in drafts:
        raise ValueError(f"Draft not found: {draft_id}")
    deleted = drafts.pop(draft_id)
    _save_drafts(drafts)
    logger.info(f"Deleted draft {draft_id}")
    return {"deleted": True, "draft_id": draft_id, "preview": deleted}


@mcp.tool()
def send_draft(draft_id: str, confirm: bool = False) -> Dict[str, Any]:
    """Send a draft email. Requires confirm=true as safety measure."""
    if not confirm:
        raise ValueError("Must pass confirm=true to send email")
    drafts = _load_drafts()
    if draft_id not in drafts:
        raise ValueError(f"Draft not found: {draft_id}")
    d = drafts[draft_id]
    message_id = send_email(
        d["to"],
        d["subject"],
        d["body"],
        html_body=d.get("html_body"),
        attachments=d.get("attachments"),
    )
    # Remove sent draft
    drafts.pop(draft_id)
    _save_drafts(drafts)
    logger.info(f"Sent draft {draft_id} as message {message_id}")
    return {"sent": True, "message_id": message_id, "to": d["to"], "subject": d["subject"]}


@mcp.tool()
def get_message(message_id: str, format: str = "full") -> Dict[str, Any]:
    """Get a single email message by ID. Format: full, metadata, or minimal."""
    return gmail_get_message(message_id, format=format)


@mcp.tool()
def get_thread(thread_id: str, format: str = "full") -> Dict[str, Any]:
    """Get an email thread with all messages. Format: full, metadata, or minimal."""
    return gmail_get_thread(thread_id, format=format)


@mcp.tool()
def reply_message(
    message_id: str,
    body: str,
    confirm: bool = False,
    html_body: Optional[str] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    to_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Reply to a message. Requires confirm=true as safety measure."""
    if not confirm:
        raise ValueError("Must pass confirm=true to send email")
    sent_id = reply_to_message(
        message_id,
        body,
        html_body=html_body,
        attachments=attachments,
        to_override=to_override,
    )
    return {"sent": True, "message_id": sent_id}


@mcp.tool()
def forward_message(
    message_id: str,
    to: str,
    body: str,
    confirm: bool = False,
    html_body: Optional[str] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    include_snippet: bool = True,
) -> Dict[str, Any]:
    """Forward a message to another recipient. Requires confirm=true as safety measure."""
    if not confirm:
        raise ValueError("Must pass confirm=true to send email")
    sent_id = forward_email_message(
        message_id,
        to,
        body,
        html_body=html_body,
        attachments=attachments,
        include_snippet=include_snippet,
    )
    return {"sent": True, "message_id": sent_id, "to": to}


@mcp.tool()
def list_labels() -> Dict[str, Any]:
    """List all Gmail labels."""
    return {"labels": gmail_list_labels()}


@mcp.tool()
def list_threads(
    query: Optional[str] = None,
    max_results: int = 10,
    label_ids: Optional[List[str]] = None,
    page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """List email threads. Use query for Gmail search syntax (e.g., 'from:me newer_than:7d')."""
    return gmail_list_threads(
        query=query,
        max_results=max_results,
        label_ids=label_ids,
        page_token=page_token,
    )


@mcp.tool()
def modify_labels(
    message_id: str,
    add_labels: Optional[List[str]] = None,
    remove_labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Add or remove labels from a message."""
    return gmail_modify_labels(message_id, add_labels=add_labels, remove_labels=remove_labels)


@mcp.tool()
def trash_message(message_id: str, confirm: bool = False) -> Dict[str, Any]:
    """Move a message to trash. Requires confirm=true as safety measure."""
    if not confirm:
        raise ValueError("Must pass confirm=true to trash message")
    return gmail_trash_message(message_id)


@mcp.tool()
def mark_as_read(message_id: str) -> Dict[str, Any]:
    """Mark a message as read by removing UNREAD label."""
    return gmail_modify_labels(message_id, remove_labels=["UNREAD"])


@mcp.tool()
def mark_as_unread(message_id: str) -> Dict[str, Any]:
    """Mark a message as unread by adding UNREAD label."""
    return gmail_modify_labels(message_id, add_labels=["UNREAD"])


if __name__ == "__main__":
    mcp.run()
