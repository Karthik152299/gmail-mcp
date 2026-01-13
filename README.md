# gmail-mcp

FastMCP server for Gmail integration with support for reading, sending, drafting,
replying, forwarding emails, and managing labels.

## Installation

```bash
# Clone the repository
git clone https://github.com/Karthik152299/gmail-mcp.git
cd gmail-mcp

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Setup

1. Create a Google Cloud project and enable the Gmail API
2. Create OAuth 2.0 credentials (Desktop application)
3. Download the credentials and save as `credentials.json` in the project root
4. Run the server once to complete the OAuth flow:
   ```bash
   python server.py
   ```
5. If you modify scopes, delete `token.json` and re-authenticate

## MCP Tools

### Reading Emails
- `get_message(message_id, format?)` - Get a single email by ID
- `get_thread(thread_id, format?)` - Get an email thread with all messages
- `list_threads(query?, max_results?, label_ids?, page_token?)` - List/search threads
- `list_labels()` - List all Gmail labels

### Drafts
- `draft_email(to, subject, body, html_body?, attachments?)` - Create a draft
- `draft_email_from_template(to, subject, template, variables, ...)` - Create draft from template
- `list_drafts()` - List all saved drafts
- `delete_draft(draft_id)` - Delete a draft
- `send_draft(draft_id, confirm)` - Send a draft (requires confirm=true)

### Sending
- `reply_message(message_id, body, confirm, ...)` - Reply to a message
- `forward_message(message_id, to, body, confirm, ...)` - Forward a message

### Organization
- `modify_labels(message_id, add_labels?, remove_labels?)` - Add/remove labels
- `mark_as_read(message_id)` - Mark message as read
- `mark_as_unread(message_id)` - Mark message as unread
- `trash_message(message_id, confirm)` - Move to trash (requires confirm=true)

### Utilities
- `render_template(template, variables)` - Preview template rendering

## Examples

### Read recent emails
```json
{
  "tool": "list_threads",
  "args": {"query": "newer_than:7d", "max_results": 10}
}
```

### Read a specific message
```json
{
  "tool": "get_message",
  "args": {"message_id": "18abc123def"}
}
```

### Draft and send an email
```json
{
  "tool": "draft_email",
  "args": {
    "to": "recipient@example.com",
    "subject": "Hello",
    "body": "Plain text body",
    "html_body": "<p>HTML body</p>",
    "attachments": [{"path": "/path/to/file.pdf"}]
  }
}
```

```json
{
  "tool": "send_draft",
  "args": {"draft_id": "uuid-here", "confirm": true}
}
```

### Use a template
```json
{
  "tool": "draft_email_from_template",
  "args": {
    "to": "user@example.com",
    "subject": "Welcome",
    "template": "Hi {name}, your code is {code}",
    "variables": {"name": "Alice", "code": "12345"}
  }
}
```

### Reply to a message
```json
{
  "tool": "reply_message",
  "args": {
    "message_id": "18abc123def",
    "body": "Thanks for your email!",
    "confirm": true
  }
}
```

### Search emails
```json
{
  "tool": "list_threads",
  "args": {"query": "from:boss@company.com is:unread", "max_results": 5}
}
```

## Attachment Format

Each attachment entry supports:
- `path`: Local file path to attach
- `content_base64`: Base64-encoded file content
- `filename`: Required when using `content_base64`
- `mime_type`: Optional MIME type override

