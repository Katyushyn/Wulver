from django.http import HttpResponse
from django.views.decorators.http import require_GET

from .models import CommentSettings


@require_GET
def comments_stylesheet(request):
    response = HttpResponse(
        CommentSettings.get_solo().stylesheet,
        content_type="text/css; charset=utf-8",
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response
