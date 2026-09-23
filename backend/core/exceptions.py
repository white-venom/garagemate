import logging

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class Conflict(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with the current state of the resource."
    default_code = "conflict"


def _first_message(data):
    """Dig out the first human readable message from DRF's nested error data."""
    if isinstance(data, dict):
        for value in data.values():
            message = _first_message(value)
            if message:
                return message
    elif isinstance(data, list):
        for value in data:
            message = _first_message(value)
            if message:
                return message
    elif data:
        return str(data)
    return ""


def api_exception_handler(exc, context):
    """
    Wrap every error in the same shape so the frontend only has to handle one format:

        {"error": {"code": "...", "message": "...", "fields": {...}}}
    """
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()
    elif isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(getattr(exc, "message_dict", exc.messages))

    response = exception_handler(exc, context)

    if response is None:
        view = context.get("view")
        logger.exception("Unhandled error in %s", view.__class__.__name__ if view else "unknown view", exc_info=exc)
        return Response(
            {"error": {"code": "server_error", "message": "Something went wrong on our side. Please try again."}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, exceptions.ValidationError):
        fields = response.data if isinstance(response.data, dict) else {"non_field_errors": response.data}
        error = {
            "code": "validation_error",
            "message": _first_message(fields) or "Invalid input.",
            "fields": fields,
        }
    else:
        codes = exc.get_codes() if isinstance(exc, exceptions.APIException) else None
        error = {
            "code": codes if isinstance(codes, str) else getattr(exc, "default_code", "error"),
            "message": _first_message(response.data),
        }
        if isinstance(exc, exceptions.Throttled) and exc.wait:
            error["retry_after"] = int(exc.wait)

    response.data = {"error": error}
    return response
