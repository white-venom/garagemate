import re

from rest_framework.exceptions import ValidationError

CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def get_client_id(request):
    """
    There are no user accounts. The frontend generates a random id once, stores
    it in localStorage and sends it with every request, so a browser only sees
    its own conversations and uploads.

    Accepted as the X-Client-Id header, or client_id in the body / query string.
    """
    body = request.data if hasattr(request.data, "get") else {}
    client_id = (
        request.headers.get("X-Client-Id")
        or body.get("client_id")
        or request.query_params.get("client_id")
        or ""
    )
    client_id = str(client_id).strip()
    if not client_id:
        raise ValidationError({"client_id": "client_id is required (X-Client-Id header or client_id field)."})
    if not CLIENT_ID_RE.match(client_id):
        raise ValidationError({"client_id": "client_id must be 8-64 characters: letters, numbers or dashes."})
    return client_id
