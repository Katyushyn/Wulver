"""app URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse, HttpResponseNotFound
from django.conf.urls.i18n import i18n_patterns
from django.contrib.auth.views import *
from django.contrib.auth import views as auth_views
# from pages.views import robots_txt
from apps.core_manager import views as core_views
from apps.core_manager import sitemaps as core_sitemaps
from apps.comments_manager import views as comments_views
from apps.userprofile import views as userprofile_views

# sitemaps = {
#     'pages': StaticViewSitemap,
#     'category': CategorySitemap,
#     'article': ArticleSitemap,
#     'article': ArticleSitemap,
#     'template': TemplateSitemap,
# }

urlpatterns = [
    # path('ckeditor/', include('ckeditor_uploader.urls')),
    path("sitemap.xml", core_sitemaps.sitemap_index, name="sitemap-index"),
    path("sitemap.xsl", core_sitemaps.sitemap_stylesheet, name="sitemap-stylesheet"),
    path(
        "sitemaps/<str:section>.xml",
        core_sitemaps.sitemap_section,
        name="sitemap-section",
    ),
    path('i18n/', include('django.conf.urls.i18n')),
    path('rosetta/', include('rosetta.urls')),
    path("comments/", include("django_comments.urls")),
    path("theme-manager/", include("apps.theme_manager.urls")),
    path("ai-assistant/", include("apps.ai_assistant.urls", namespace="ai_assistant")),
    path("favicon.ico", core_views.favicon_ico, name="favicon_ico"),
    path("favicon.png", core_views.favicon_png, name="favicon_png"),
    path("apple-touch-icon.png", core_views.apple_touch_icon, name="apple_touch_icon"),
    path("robots.txt", core_views.robots_txt, name="robots_txt"),
    path("authentication.css", userprofile_views.authentication_stylesheet, name="authentication_stylesheet"),
    path("comments.css", comments_views.comments_stylesheet, name="comments_stylesheet"),
]
urlpatterns += i18n_patterns(
    path("admin/", admin.site.urls),
    prefix_default_language=False,
)
urlpatterns += i18n_patterns(
    path('accounts/', include('allauth.urls')),
    path('account/', userprofile_views.personal_account, name='personal_account'),
    path('register/reset-password/', auth_views.PasswordResetView.as_view(), name='reset_password'),
    path('register/reset-password-sent/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('register/reset-password-form/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('register/reset-password-complete/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('', include('apps.core_manager.urls', namespace='core_manager')),
    path('', include('apps.blog_manager.urls', namespace='blog')),
    prefix_default_language=False  # hide prefix whit original language
)

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
elif settings.SERVE_MEDIA_LOCALLY:
    # Local testing only: replace this with Nginx, Caddy, or object storage in production.
    urlpatterns += [
        path(
            "media/<path:path>",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]

handler404 = "apps.core_manager.views.page_not_found"
