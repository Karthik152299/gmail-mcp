from fastmcp import FastMCP
import uuid
from gmail_client import (
    send_email,
    reply_to_message,
    forward_message as forward_email_message,
    list_labels as gmail_list_labels,
    list_threads as gmail_list_threads,
)

mcp = FastMCP("gmail-mcp-starter")
drafts = {}


@mcp.tool()
def draft_email(
    to: str,
    subject: str,
    body: str,
    html_body: str = None,
    attachments = None,
) -> dict:
    draft_id = str(uuid.uuid4())
    drafts[draft_id] = {
        "to": to,
        "subject": subject,
        "body": body,
        "html_body": html_body,
        "attachments": attachments,
    }
    return {"draft_id": draft_id, "preview": drafts[draft_id]}


@mcp.tool()
def draft_email_from_template(
    to: str,
    subject: str,
    template: str,
    variables: dict,
    html_body: str = None,
    attachments = None,
) -> dict:
    body = template.format(**variables)
    return draft_email(
        to,
        subject,
        body,
        html_body=html_body,
        attachments=attachments,
    )


@mcp.tool()
def render_template(template: str, variables: dict) -> dict:
    rendered = template.format(**variables)
    return {"rendered": rendered}


@mcp.tool()
def list_drafts() -> dict:
    return {"drafts": drafts}


@mcp.tool()
def delete_draft(draft_id: str) -> dict:
    if draft_id not in drafts:
        raise ValueError("Draft not found")

    deleted = drafts.pop(draft_id)
    return {"deleted": True, "draft_id": draft_id, "preview": deleted}


@mcp.tool()
def send_draft(draft_id: str, confirm: bool = False) -> dict:
    if not confirm:
        raise ValueError("Must pass confirm=true to send email")

    if draft_id not in drafts:
        raise ValueError("Draft not found")

    d = drafts[draft_id]
    message_id = send_email(
        d["to"],
        d["subject"],
        d["body"],
        html_body=d.get("html_body"),
        attachments=d.get("attachments"),
    )

    return {
        "sent": True,
        "message_id": message_id,
        "to": d["to"],
        "subject": d["subject"],
    }


@mcp.tool()
def reply_message(
    message_id: str,
    body: str,
    confirm: bool = False,
    html_body: str = None,
    attachments = None,
    to_override: str = None,
) -> dict:
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
    html_body: str = None,
    attachments = None,
    include_snippet: bool = True,
) -> dict:
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
def list_labels() -> dict:
    return {"labels": gmail_list_labels()}


@mcp.tool()
def list_threads(
    query: str = None,
    max_results: int = 10,
    label_ids = None,
) -> dict:
    return {
        "threads": gmail_list_threads(
            query=query,
            max_results=max_results,
            label_ids=label_ids,
        )
    }


if __name__ == "__main__":
    mcp.run()
