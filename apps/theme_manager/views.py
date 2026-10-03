from pathlib import Path
from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles import finders
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from .models import Theme, ThemeTemplate
