from django.db import transaction

from .models import URLRedirect


def register_redirect(old_path, target_url, note=""):
    old_path = URLRedirect.normalize_old_path(old_path)
    target_url = URLRedirect.normalize_target_url(target_url)
    if old_path == target_url:
        return None

    with transaction.atomic():
        # When B moves to C, previously generated A → B records become A → C.
        URLRedirect.objects.filter(
            target_url=old_path,
            is_automatic=True,
        ).exclude(old_path=target_url).update(target_url=target_url)

        redirect = URLRedirect.objects.filter(old_path=old_path).first()
        if redirect and not redirect.is_automatic:
            return redirect
        if redirect is None:
            redirect = URLRedirect(old_path=old_path, is_automatic=True)

        redirect.target_url = target_url
        redirect.status_code = URLRedirect.STATUS_PERMANENT
        redirect.is_active = True
        redirect.note = note
        redirect.save()
        return redirect


def register_localized_redirects(old_urls, new_urls, note=""):
    redirects = []
    for language, old_path in old_urls.items():
        target_url = new_urls.get(language)
        if old_path and target_url and old_path != target_url:
            redirect = register_redirect(old_path, target_url, note=note)
            if redirect:
                redirects.append(redirect)
    return redirects
