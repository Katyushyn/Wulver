from django.urls import path

from . import views

app_name = "core_manager"

urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.search, name="search"),
    path("newsletter/subscribe/", views.newsletter_subscribe, name="newsletter_subscribe"),
    path("newsletter/confirm/<str:token>/", views.newsletter_confirm, name="newsletter_confirm"),
    path("contact/send/", views.contact_send, name="contact_send"),
    path("<slug:category_slug>/<slug:item_slug>/", views.item_detail, name="item_detail"),
    path("<slug:slug>/", views.slug_detail, name="slug_detail"),
]
