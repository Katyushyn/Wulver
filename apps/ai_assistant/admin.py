import json

from django import forms
from django.contrib import admin, messages
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from apps.core_manager.admin_mixins import SingletonAdminMixin

from .models import (
    AssistantEventLog,
    AssistantProfile,
    ChatMessage,
    ChatSession,
    KnowledgeChunk,
    Lead,
    RetrievedChunk,
)
from .services.embeddings import build_chunk_embedding


class ChunkImportForm(forms.Form):
    json_file = forms.FileField(label=_("JSON file with chunks"))


@admin.register(AssistantProfile)
class AssistantProfileAdmin(SingletonAdminMixin, ModelAdmin):
    list_display = (
        "provider_type",
        "chat_model",
        "embedding_model",
        "temperature",
        "max_context_chunks",
    )
    list_filter = ("provider_type",)
    search_fields = (
        "prompt_content",
        "fallback_message",
        "chat_model",
        "embedding_model",
    )

    fieldsets = (
        (_("Provider"), {
            "fields": (
                "provider_type",
                "chat_model",
                "embedding_model",
            )
        }),
        (_("Prompt"), {
            "fields": (
                "prompt_content",
            )
        }),
        (_("Model behavior"), {
            "fields": (
                "temperature",
                "max_context_chunks",
                "min_similarity_score",
            )
        }),
        (_("Fallback"), {
            "fields": (
                "fallback_message",
            )
        }),
        (_("Access and privacy"), {
            "fields": (
                "is_enabled",
                "allow_anonymous_users",
                "require_privacy_consent",
                "privacy_notice",
                "store_ip_addresses",
                "conversation_retention_days",
            )
        }),
        (_("Request limits"), {
            "fields": (
                "requests_per_minute",
                "requests_per_hour",
                "requests_per_day",
                "global_requests_per_day",
                "daily_token_limit",
                "monthly_token_limit",
                "max_messages_per_session",
                "max_message_length",
                "session_lifetime_hours",
            )
        }),
        (_("Provider safety"), {
            "fields": (
                "provider_timeout_seconds",
                "provider_max_retries",
                "max_output_tokens",
            )
        }),
        (_("Public messages"), {
            "fields": (
                "disabled_message",
                "error_message",
                "rate_limit_message",
            )
        }),
    )

    def changelist_view(self, request, extra_context=None):
        assistant = AssistantProfile.objects.order_by("pk").first()

        if assistant:
            return redirect(
                reverse(
                    "admin:ai_assistant_assistantprofile_change",
                    args=[assistant.pk],
                )
            )

        return redirect("admin:ai_assistant_assistantprofile_add")


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(ModelAdmin):
    change_list_template = "admin/ai_assistant/knowledgechunk/change_list.html"

    list_display = (
        "title",
        "priority",
        "is_active",
        "has_embedding",
        "embedding_model",
        "embedding_updated_at",
    )
    list_filter = (
        "is_active",
        "embedding_model",
    )
    search_fields = (
        "title",
        "content",
        "source_url",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "embedding_updated_at",
    )

    fieldsets = (
        (_("General"), {
            "fields": (
                "title",
                "content",
                "source_url",
            )
        }),
        (_("Search and priority"), {
            "fields": (
                "priority",
                "is_active",
            )
        }),
        (_("Embedding"), {
            "fields": (
                "embedding",
                "embedding_model",
                "embedding_updated_at",
            )
        }),
        (_("Dates"), {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

    def has_embedding(self, obj):
        return bool(obj.embedding)

    has_embedding.boolean = True
    has_embedding.short_description = _("Has embedding")

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                "import-json/",
                self.admin_site.admin_view(self.import_json_view),
                name="ai_assistant_import_chunks_json",
            ),
            path(
                "build-missing-embeddings/",
                self.admin_site.admin_view(self.build_missing_embeddings_view),
                name="ai_assistant_build_missing_embeddings",
            ),
        ]

        return custom_urls + urls

    def save_model(self, request, obj, form, change):
        if change and form.changed_data:
            content_changed = bool({"title", "content"} & set(form.changed_data))

            if content_changed:
                obj.embedding = None
                obj.embedding_model = ""
                obj.embedding_updated_at = None

        super().save_model(request, obj, form, change)

    def build_missing_embeddings_view(self, request):
        assistant = AssistantProfile.objects.order_by("pk").first()

        if not assistant:
            messages.error(request, _("No AssistantProfile found"))
            return redirect("..")

        chunks = KnowledgeChunk.objects.filter(
            is_active=True,
        ).filter(
            Q(embedding__isnull=True) |
            Q(embedding=[])
        )

        processed = 0
        failed = 0

        for chunk in chunks:
            try:
                build_chunk_embedding(chunk, assistant)
                processed += 1
            except Exception as e:
                failed += 1
                messages.error(
                    request,
                    _("Embedding failed for %(title)s: %(error)s") % {
                        "title": chunk.title,
                        "error": e,
                    },
                )

        if processed:
            messages.success(
                request,
                _("Embeddings rebuilt: %(processed)s") % {
                    "processed": processed,
                },
            )

        if failed:
            messages.warning(
                request,
                _("Embedding failures: %(failed)s") % {
                    "failed": failed,
                },
            )

        if not processed and not failed:
            messages.info(request, _("No missing embeddings found"))

        return redirect("..")

    def import_json_view(self, request):
        if request.method == "POST":
            form = ChunkImportForm(request.POST, request.FILES)

            if form.is_valid():
                uploaded_file = form.cleaned_data["json_file"]

                try:
                    data = json.load(uploaded_file)

                    if not isinstance(data, list):
                        raise ValueError("Invalid JSON format")

                    created = 0
                    updated = 0

                    for item in data:
                        if "title" not in item or "content" not in item:
                            raise ValueError(
                                _("Each chunk must contain title and content fields")
                            )

                        existing_chunk = KnowledgeChunk.objects.filter(
                            title=item["title"],
                        ).first()

                        defaults = {
                            "content": item["content"],
                            "source_url": item.get("source_url", ""),
                            "priority": item.get("priority", 5),
                            "is_active": item.get("is_active", True),
                        }

                        if (
                            existing_chunk
                            and (
                                existing_chunk.title != item["title"]
                                or existing_chunk.content != item["content"]
                            )
                        ):
                            defaults.update({
                                "embedding": None,
                                "embedding_model": "",
                                "embedding_updated_at": None,
                            })

                        chunk, was_created = KnowledgeChunk.objects.update_or_create(
                            title=item["title"],
                            defaults=defaults,
                        )

                        if was_created:
                            created += 1
                        else:
                            updated += 1

                    messages.success(
                        request,
                        _("Import completed. Created: %(created)s, updated: %(updated)s") % {
                            "created": created,
                            "updated": updated,
                        },
                    )

                    return redirect("..")

                except Exception as e:
                    messages.error(request, _("Import error: %(error)s") % {
                        "error": e,
                    })

        else:
            form = ChunkImportForm()

        context = {
            **self.admin_site.each_context(request),
            "title": _("Import chunks from JSON"),
            "form": form,
        }

        return render(
            request,
            "admin/ai_assistant/knowledgechunk/import_json.html",
            context,
        )


class ChatMessageInline(TabularInline):
    model = ChatMessage
    extra = 0
    fields = (
        "role",
        "content",
        "model_name",
        "total_tokens",
        "created_at",
    )
    readonly_fields = (
        "role",
        "content",
        "model_name",
        "total_tokens",
        "created_at",
    )
    can_delete = False
    show_change_link = True


@admin.register(ChatSession)
class ChatSessionAdmin(ModelAdmin):
    list_display = (
        "id",
        "channel_link",
        "user_name",
        "user_email",
        "user_phone",
        "is_lead",
        "is_closed",
        "created_at",
        "last_message_at",
    )
    list_filter = (
        "channel",
        "is_lead",
        "is_closed",
    )
    exclude = ("assistant",)
    search_fields = (
        "user_name",
        "user_email",
        "user_phone",
        "ip_address",
        "user_agent",
    )
    readonly_fields = (
        "created_at",
        "last_message_at",
    )
    inlines = (ChatMessageInline,)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))

        if obj and "channel" not in readonly_fields:
            readonly_fields.append("channel")

        return readonly_fields

    def save_model(self, request, obj, form, change):
        if not obj.assistant_id:
            obj.assistant = AssistantProfile.objects.order_by("pk").first()

        super().save_model(request, obj, form, change)

    def channel_link(self, obj):
        url = reverse(
            "admin:ai_assistant_chatsession_change",
            args=[obj.pk],
        )

        return format_html('<a href="{}">{}</a>', url, obj.get_channel_display())

    channel_link.short_description = _("Channel")
    channel_link.admin_order_field = "channel"


class RetrievedChunkInline(TabularInline):
    model = RetrievedChunk
    extra = 0
    fields = (
        "chunk",
        "score",
        "rank",
        "created_at",
    )
    readonly_fields = (
        "chunk",
        "score",
        "rank",
        "created_at",
    )
    can_delete = False
    show_change_link = True


@admin.register(ChatMessage)
class ChatMessageAdmin(ModelAdmin):
    list_display = (
        "id",
        "session",
        "role",
        "short_content",
        "model_name",
        "total_tokens",
        "created_at",
    )
    list_filter = (
        "role",
        "model_name",
        "created_at",
    )
    search_fields = (
        "content",
        "session__user_name",
        "session__user_email",
    )
    readonly_fields = (
        "created_at",
    )
    inlines = (RetrievedChunkInline,)

    def short_content(self, obj):
        return obj.content[:80]

    short_content.short_description = _("Content")


@admin.register(RetrievedChunk)
class RetrievedChunkAdmin(ModelAdmin):
    list_display = (
        "id",
        "message",
        "chunk",
        "score",
        "rank",
        "created_at",
    )
    list_filter = (
        "rank",
        "created_at",
    )
    search_fields = (
        "chunk__title",
        "chunk__content",
        "message__content",
    )
    readonly_fields = (
        "created_at",
    )


@admin.register(Lead)
class LeadAdmin(ModelAdmin):
    list_display = (
        "id",
        "name",
        "email",
        "phone",
        "service_interest",
        "status",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "status",
        "service_interest",
        "created_at",
    )
    search_fields = (
        "name",
        "email",
        "phone",
        "message",
        "service_interest",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(AssistantEventLog)
class AssistantEventLogAdmin(ModelAdmin):
    list_display = (
        "id",
        "event_type",
        "session",
        "short_message",
        "created_at",
    )
    list_filter = (
        "event_type",
        "created_at",
    )
    search_fields = (
        "message",
        "data",
    )
    readonly_fields = (
        "created_at",
    )

    def short_message(self, obj):
        return obj.message[:100]

    short_message.short_description = _("Message")
