import uuid

from django.conf import settings
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone
from django.utils.translation import get_language, gettext_lazy as _


PROVIDER_CHOICES = [
    ("openai", _("OpenAI")),
    ("gemini", _("Gemini")),
    ("ollama", _("Ollama")),
    ("custom", _("Custom API")),
]

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful website AI assistant. Answer only from the provided "
    "context. If the answer is not in the context, ask the visitor to leave "
    "contact details so a specialist can help."
)

DEFAULT_PRIVACY_NOTICE = (
    "I agree that my messages and any contact details I provide may be stored "
    "to answer my request."
)

DEFAULT_PRIVACY_NOTICE_TRANSLATIONS = {
    "uk": (
        "Я погоджуюся з тим, що мої повідомлення та будь-які контактні дані, "
        "які я надаю, можуть зберігатися для відповіді на мій запит."
    ),
}


class AssistantProfile(models.Model):
    """
    Configuration for the website AI assistant.
    """

    provider_type = models.CharField(
        max_length=50,
        choices=PROVIDER_CHOICES,
        default="openai",
        verbose_name=_("Provider type"),
    )
    chat_model = models.CharField(
        max_length=100,
        default="gpt-4.1-mini",
        verbose_name=_("Chat model"),
    )
    embedding_model = models.CharField(
        max_length=100,
        default="text-embedding-3-small",
        verbose_name=_("Embedding model"),
    )
    prompt_content = models.TextField(
        default=DEFAULT_SYSTEM_PROMPT,
        verbose_name=_("Prompt text"),
    )

    temperature = models.FloatField(default=0.3, validators=[MinValueValidator(0), MaxValueValidator(2)], verbose_name=_("Temperature"))
    max_context_chunks = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(20)], verbose_name=_("Maximum context chunks"))
    min_similarity_score = models.FloatField(default=0.2, validators=[MinValueValidator(0), MaxValueValidator(1)], verbose_name=_("Minimum similarity score"))

    fallback_message = models.TextField(
        blank=True,
        default=_("I do not have enough information to answer precisely. Please leave your contact details and I will pass the question to a specialist."),
        verbose_name=_("Fallback message"),
    )

    is_enabled = models.BooleanField(default=True, verbose_name=_("Assistant enabled"))
    allow_anonymous_users = models.BooleanField(default=True, verbose_name=_("Allow anonymous users"))
    require_privacy_consent = models.BooleanField(default=True, verbose_name=_("Require privacy consent"))
    privacy_notice = models.CharField(
        max_length=500,
        default=DEFAULT_PRIVACY_NOTICE,
        verbose_name=_("Privacy notice"),
    )

    def get_privacy_notice(self):
        """Translate the built-in notice while preserving administrator overrides."""
        if self.privacy_notice == DEFAULT_PRIVACY_NOTICE:
            language = (get_language() or "").split("-", maxsplit=1)[0]
            return DEFAULT_PRIVACY_NOTICE_TRANSLATIONS.get(
                language, DEFAULT_PRIVACY_NOTICE,
            )
        return self.privacy_notice
    disabled_message = models.CharField(
        max_length=255,
        default=_("The AI assistant is temporarily unavailable."),
        verbose_name=_("Disabled message"),
    )
    error_message = models.CharField(
        max_length=255,
        default=_("The AI assistant is temporarily unavailable. Please try again later."),
        verbose_name=_("Public error message"),
    )
    rate_limit_message = models.CharField(
        max_length=255,
        default=_("You have sent too many messages. Please try again later."),
        verbose_name=_("Rate limit message"),
    )
    requests_per_minute = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1)], verbose_name=_("Requests per minute per visitor"))
    requests_per_hour = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1)], verbose_name=_("Requests per hour per visitor"))
    requests_per_day = models.PositiveIntegerField(default=100, validators=[MinValueValidator(1)], verbose_name=_("Requests per day per visitor"))
    global_requests_per_day = models.PositiveIntegerField(default=1000, validators=[MinValueValidator(1)], verbose_name=_("Global requests per day"))
    daily_token_limit = models.PositiveIntegerField(default=100000, validators=[MinValueValidator(1)], verbose_name=_("Global token limit per day"))
    monthly_token_limit = models.PositiveIntegerField(default=1000000, validators=[MinValueValidator(1)], verbose_name=_("Global token limit per month"))
    max_messages_per_session = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1)], verbose_name=_("Maximum messages per session"))
    max_message_length = models.PositiveIntegerField(default=2000, validators=[MinValueValidator(100), MaxValueValidator(12000)], verbose_name=_("Maximum message length"))
    session_lifetime_hours = models.PositiveIntegerField(default=24, validators=[MinValueValidator(1)], verbose_name=_("Session lifetime (hours)"))
    provider_timeout_seconds = models.PositiveIntegerField(default=20, validators=[MinValueValidator(1), MaxValueValidator(120)], verbose_name=_("Provider timeout (seconds)"))
    provider_max_retries = models.PositiveIntegerField(default=1, validators=[MaxValueValidator(5)], verbose_name=_("Provider retry count"))
    max_output_tokens = models.PositiveIntegerField(default=500, validators=[MinValueValidator(1)], verbose_name=_("Maximum response tokens"))
    conversation_retention_days = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1)], verbose_name=_("Conversation retention (days)"))
    store_ip_addresses = models.BooleanField(default=False, verbose_name=_("Store visitor IP addresses"))

    class Meta:
        verbose_name = _("Assistant profile")
        verbose_name_plural = _("Assistant profiles")

    def __str__(self):
        return f"Assistant profile #{self.pk}"


class KnowledgeChunk(models.Model):
    title = models.CharField(max_length=255, verbose_name=_("Title"))

    content = models.TextField(verbose_name=_("Content"))
    source_url = models.CharField(max_length=500, blank=True, verbose_name=_("Source URL"))

    priority = models.IntegerField(default=5, verbose_name=_("Priority"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    embedding = models.JSONField(null=True, blank=True, verbose_name=_("Embedding"))
    embedding_model = models.CharField(max_length=100, blank=True, verbose_name=_("Embedding model"))
    embedding_updated_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Embedding updated at"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated at"))

    class Meta:
        verbose_name = _("Knowledge chunk")
        verbose_name_plural = _("Knowledge chunks")

    def mark_embedding_updated(self, model_name: str = ""):
        self.embedding_model = model_name
        self.embedding_updated_at = timezone.now()
        self.save(update_fields=["embedding_model", "embedding_updated_at"])

    def __str__(self):
        return self.title


class ChatSession(models.Model):
    CHANNEL_CHOICES = [
        ("web", _("Web Chat")),
        ("telegram", _("Telegram")),
        ("api", _("API")),
    ]

    assistant = models.ForeignKey(
        AssistantProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
        verbose_name=_("Assistant"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    browser_session_key = models.CharField(max_length=40, blank=True, db_index=True, editable=False)
    client_hash = models.CharField(max_length=64, blank=True, db_index=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_chat_sessions",
        editable=False,
        verbose_name=_("User"),
    )

    channel = models.CharField(max_length=50, choices=CHANNEL_CHOICES, default="web", verbose_name=_("Channel"))

    user_name = models.CharField(max_length=255, blank=True, verbose_name=_("User name"))
    user_email = models.EmailField(blank=True, verbose_name=_("User email"))
    user_phone = models.CharField(max_length=50, blank=True, verbose_name=_("User phone"))

    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name=_("IP address"))
    user_agent = models.TextField(blank=True, verbose_name=_("User agent"))

    is_lead = models.BooleanField(default=False, verbose_name=_("Is lead"))
    is_closed = models.BooleanField(default=False, verbose_name=_("Closed"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))
    last_message_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Last message at"))

    class Meta:
        verbose_name = _("Chat session")
        verbose_name_plural = _("Chat sessions")

    def __str__(self):
        return f"Session #{self.id} ({self.channel})"


class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ("user", _("User")),
        ("assistant", _("Assistant")),
        ("system", _("System")),
    ]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages", verbose_name=_("Session"))
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name=_("Role"))
    content = models.TextField(verbose_name=_("Content"))
    model_name = models.CharField(max_length=100, blank=True, verbose_name=_("Model"))

    prompt_tokens = models.IntegerField(null=True, blank=True, verbose_name=_("Prompt tokens"))
    completion_tokens = models.IntegerField(null=True, blank=True, verbose_name=_("Completion tokens"))
    total_tokens = models.IntegerField(null=True, blank=True, verbose_name=_("Total tokens"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))

    class Meta:
        verbose_name = _("Chat message")
        verbose_name_plural = _("Chat messages")

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class RetrievedChunk(models.Model):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name="retrieved_chunks", verbose_name=_("Message"))

    chunk = models.ForeignKey(
        KnowledgeChunk,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Chunk"),
    )

    score = models.FloatField(default=0, verbose_name=_("Score"))
    rank = models.IntegerField(default=0, verbose_name=_("Rank"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))

    class Meta:
        verbose_name = _("Retrieved chunk")
        verbose_name_plural = _("Retrieved chunks")

    def __str__(self):
        return f"Chunk #{self.chunk_id} score={self.score}"


class Lead(models.Model):
    STATUS_CHOICES = [
        ("new", _("New")),
        ("contacted", _("Contacted")),
        ("qualified", _("Qualified")),
        ("lost", _("Lost")),
        ("won", _("Won")),
    ]

    session = models.OneToOneField(
        ChatSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead",
        verbose_name=_("Session"),
    )

    name = models.CharField(max_length=255, blank=True, verbose_name=_("Name"))
    email = models.EmailField(blank=True, verbose_name=_("Email"))
    phone = models.CharField(max_length=50, blank=True, verbose_name=_("Phone"))

    message = models.TextField(blank=True, verbose_name=_("Message"))
    service_interest = models.CharField(max_length=100, blank=True, verbose_name=_("Service interest"))

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="new", verbose_name=_("Status"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated at"))

    class Meta:
        verbose_name = _("Lead")
        verbose_name_plural = _("Leads")

    def __str__(self):
        return self.name or self.email or f"Lead #{self.id}"


class AssistantEventLog(models.Model):
    EVENT_TYPES = [
        ("info", _("Info")),
        ("warning", _("Warning")),
        ("error", _("Error")),
        ("fallback", _("Fallback")),
        ("api_error", _("API Error")),
        ("low_confidence", _("Low Confidence")),
        ("rate_limit", _("Rate limit")),
        ("security", _("Security")),
    ]

    session = models.ForeignKey(ChatSession, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Session"))

    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, verbose_name=_("Event type"))
    message = models.TextField(verbose_name=_("Message"))
    data = models.JSONField(null=True, blank=True, verbose_name=_("Data"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))

    class Meta:
        verbose_name = _("AI assistant log")
        verbose_name_plural = _("AI assistant logs")

    def __str__(self):
        return f"{self.event_type}: {self.message[:50]}"
