from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("<slug:category_slug>/", views.BlogCategoryView.as_view(), name="category"),
    path("<slug:category_slug>/<slug:post_slug>/", views.Article.as_view(), name="post"),
]
