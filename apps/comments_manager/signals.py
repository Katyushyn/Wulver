from datetime import timedelta

from django.dispatch import receiver
from django.utils import timezone
from django_comments import signals
from django_comments.models import Comment

from .models import CommentSettings


@receiver(signals.comment_will_be_posted, dispatch_uid="comments_manager_enforce_posting_policy")
def enforce_comment_posting_policy(sender, comment, request, **kwargs):
    settings = CommentSettings.get_solo()
    user = getattr(request, "user", None)
    is_authenticated = bool(user and user.is_authenticated)

    if not settings.allow_anonymous_comments and not is_authenticated:
        return False

    since = timezone.now() - timedelta(minutes=settings.rate_limit_window_minutes)
    recent_comments = Comment.objects.filter(submit_date__gte=since)

    if is_authenticated and recent_comments.filter(user=user).count() >= settings.rate_limit_count:
        return False

    ip_address = getattr(comment, "ip_address", None)
    if ip_address and recent_comments.filter(ip_address=ip_address).count() >= settings.rate_limit_count:
        return False

    if settings.publication_mode == CommentSettings.PublicationMode.MODERATION:
        comment.is_public = False

    return True
