APP_NAME = "Genis Email Hub"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["Mail.Read", "Mail.Send", "Mail.ReadWrite", "User.Read"]
DEFAULT_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
AUTHORITY = "https://login.microsoftonline.com/common"
POLL_INTERVAL_MS = 30000
HTTP_CONNECT_TIMEOUT_SEC = 10
HTTP_READ_TIMEOUT_SEC = 45
HTTP_GET_RETRIES = 1

FOLDER_DISPLAY = {
    "inbox": "Inbox",
    "sentitems": "Sent",
    "drafts": "Drafts",
    "archive": "Archive",
    "deleteditems": "Deleted",
    "junkemail": "Junk",
}
