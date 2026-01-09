from fastmcp import FastMCP
import uuid
from gmail_client import send_email

mcp = FastMCP("gmail-mcp-starter")
drafts = {}

@mcp.tool()
def draft_email(to: str, subject: str, body: str) -> dict:
    draft_id = str(uuid.uuid4())
    drafts[draft_id] = {"to": to, "subject": subject, "body": body}
    return {"draft_id": draft_id, "preview": drafts[draft_id]}


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
    message_id = send_email(d["to"], d["subject"], d["body"])

    return {
        "sent": True,
        "message_id": message_id,
        "to": d["to"],
        "subject": d["subject"]
    }


if __name__ == "__main__":
    mcp.run()
