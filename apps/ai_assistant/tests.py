import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin as django_admin
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.ai_assistant.models import (
    AssistantProfile,
    AssistantEventLog,
    ChatMessage,
    ChatSession,
    KnowledgeChunk,
    RetrievedChunk,
)
from apps.ai_assistant.admin import KnowledgeChunkAdmin
from apps.ai_assistant.services.chat import ask_assistant, prune_retrieved_chunk_logs
from apps.ai_assistant.services.providers.openai_provider import OpenAIProvider


class AiAssistantHealthTest(SimpleTestCase):
    def test_health_endpoint_returns_ok(self):
        response = self.client.get(reverse("ai_assistant:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class AiAssistantChatViewTest(TestCase):
    def setUp(self):
        self.assistant = AssistantProfile.objects.create(
            require_privacy_consent=False,
        )

    def test_chat_requires_message(self):
        response = self.client.post(
            reverse("ai_assistant:chat"),
            data=json.dumps({"message": ""}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Message is required"})

    def test_chat_is_csrf_protected(self):
        csrf_client = Client(enforce_csrf_checks=True)

        response = csrf_client.post(
            reverse("ai_assistant:chat"),
            data=json.dumps({"message": "Hello"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_chat_rejects_messages_over_configured_length(self):
        self.assistant.max_message_length = 100
        self.assistant.save()

        response = self.client.post(
            reverse("ai_assistant:chat"),
            data=json.dumps({"message": "x" * 101}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_chat_requires_configured_privacy_consent(self):
        self.assistant.require_privacy_consent = True
        self.assistant.save()

        response = self.client.post(
            reverse("ai_assistant:chat"),
            data=json.dumps({"message": "Hello"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Privacy consent is required.")

    def test_chat_uses_public_uuid_and_rejects_foreign_sessions(self):
        with patch("apps.ai_assistant.views.ask_assistant") as ask:
            def answer(**kwargs):
                return {"answer": "Hello", "session": kwargs["session"], "chunks": []}
            ask.side_effect = answer
            response = self.client.post(
                reverse("ai_assistant:chat"),
                data=json.dumps({"message": "Hello"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        public_id = response.json()["session_id"]
        session = ChatSession.objects.get(public_id=public_id)
        self.assertNotEqual(public_id, str(session.pk))

        other_client = Client()
        foreign_response = other_client.post(
            reverse("ai_assistant:chat"),
            data=json.dumps({"message": "Hijack", "session_id": public_id}),
            content_type="application/json",
        )
        self.assertEqual(foreign_response.status_code, 403)
        self.assertTrue(AssistantEventLog.objects.filter(event_type="security").exists())

    def test_chat_rate_limits_visitor_before_provider_call(self):
        self.assistant.requests_per_minute = 1
        self.assistant.save()
        session = ChatSession.objects.create(
            assistant=self.assistant,
            browser_session_key="test",
            client_hash="irrelevant",
        )
        ChatMessage.objects.create(session=session, role="user", content="First")

        with patch("apps.ai_assistant.views.ask_assistant") as ask:
            def accepted_answer(**kwargs):
                ChatMessage.objects.create(
                    session=kwargs["session"], role="user", content=kwargs["question"]
                )
                return {"answer": "OK", "session": kwargs["session"], "chunks": []}
            ask.side_effect = accepted_answer
            first = self.client.post(
                reverse("ai_assistant:chat"),
                data=json.dumps({"message": "Second"}),
                content_type="application/json",
                REMOTE_ADDR="127.0.0.1",
            )

        # The unrelated hash does not count; the accepted request establishes the real client hash.
        self.assertEqual(first.status_code, 200)
        ask.assert_called_once()
        second = self.client.post(
            reverse("ai_assistant:chat"),
            data=json.dumps({"message": "Third"}),
            content_type="application/json",
            REMOTE_ADDR="127.0.0.1",
        )
        self.assertEqual(second.status_code, 429)
        self.assertIn("Retry-After", second)

    def test_internal_errors_are_not_exposed(self):
        with patch(
            "apps.ai_assistant.views.ask_assistant",
            side_effect=RuntimeError("secret provider detail"),
        ):
            response = self.client.post(
                reverse("ai_assistant:chat"),
                data=json.dumps({"message": "Hello"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, "secret provider detail", status_code=503)


class OpenAIProviderTest(TestCase):
    @override_settings(OPENAI_API_KEY="settings-api-key")
    def test_openai_provider_uses_settings_key(self):
        assistant = AssistantProfile.objects.create(
            provider_type="openai",
            chat_model="gpt-4.1-mini",
            embedding_model="text-embedding-3-small",
        )

        with patch("apps.ai_assistant.services.providers.openai_provider.OpenAI") as openai:
            OpenAIProvider(assistant)

        self.assertEqual(openai.call_args.kwargs["api_key"], "settings-api-key")
        self.assertEqual(openai.call_args.kwargs["timeout"], 20)
        self.assertEqual(openai.call_args.kwargs["max_retries"], 1)

    @override_settings(OPENAI_API_KEY="settings-api-key")
    def test_openai_provider_limits_output_and_reports_usage(self):
        assistant = AssistantProfile.objects.create(max_output_tokens=321)
        response = SimpleNamespace(
            output_text="Safe answer",
            usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15),
        )

        with patch("apps.ai_assistant.services.providers.openai_provider.OpenAI") as openai:
            openai.return_value.responses.create.return_value = response
            result = OpenAIProvider(assistant).chat([{"role": "user", "content": "Hello"}])

        self.assertEqual(result["total_tokens"], 15)
        self.assertEqual(
            openai.return_value.responses.create.call_args.kwargs["max_output_tokens"],
            321,
        )


class AskAssistantPipelineTest(TestCase):
    def test_demo_mode_returns_response_without_provider_call(self):
        assistant = AssistantProfile.objects.create(demo_mode=True)

        with patch("apps.ai_assistant.services.chat.get_provider_client") as get_client:
            result = ask_assistant(
                question="What can Wulver do?",
                assistant=assistant,
            )

        get_client.assert_not_called()
        self.assertIn("demo mode", result["answer"].lower())
        self.assertIn("OPENAI_API_KEY", result["answer"])
        self.assertEqual(result["chunks"], [])

    def test_ask_assistant_handles_simple_messages_without_api_call(self):
        assistant = AssistantProfile.objects.create(
            provider_type="openai",
            chat_model="gpt-4.1-mini",
            embedding_model="text-embedding-3-small",
        )

        with patch("apps.ai_assistant.services.chat.get_provider_client") as get_client:
            result = ask_assistant(
                question="ти мене розумієш?",
                assistant=assistant,
            )

        get_client.assert_not_called()
        self.assertIn("Так, розумію", result["answer"])
        self.assertEqual(result["chunks"], [])

    def test_ask_assistant_uses_embedding_retrieval_and_chat_client(self):
        assistant = AssistantProfile.objects.create(
            provider_type="openai",
            chat_model="gpt-4.1-mini",
            embedding_model="text-embedding-3-small",
            prompt_content="Answer from context only.",
            min_similarity_score=0.1,
        )
        chunk = KnowledgeChunk.objects.create(
            title="AI assistant service",
            content="AI assistant answers website visitor questions.",
            priority=10,
            embedding=[1.0, 0.0],
        )

        class FakeClient:
            def embedding(self, text):
                return [1.0, 0.0]

            def chat(self, messages, temperature=0.3):
                self.messages = messages
                return {"text": "AI assistant can answer website questions."}

        fake_client = FakeClient()

        with patch(
            "apps.ai_assistant.services.chat.get_provider_client",
            return_value=fake_client,
        ):
            result = ask_assistant(
                question="What can the AI assistant do?",
                assistant=assistant,
            )

        self.assertEqual(result["answer"], "AI assistant can answer website questions.")
        self.assertEqual(result["chunks"][0]["title"], chunk.title)
        self.assertIn(chunk.content, fake_client.messages[1]["content"])
        self.assertEqual(ChatMessage.objects.filter(session=result["session"]).count(), 2)
        self.assertEqual(
            RetrievedChunk.objects.filter(message=result["assistant_message"]).count(),
            1,
        )


class BuildEmbeddingsCommandTest(TestCase):
    def test_command_processes_empty_embedding_lists(self):
        assistant = AssistantProfile.objects.create(
            provider_type="openai",
            chat_model="gpt-4.1-mini",
            embedding_model="text-embedding-3-small",
        )
        chunk = KnowledgeChunk.objects.create(
            title="AI assistant service",
            content="AI assistant answers website visitor questions.",
            is_active=True,
            embedding=[],
        )

        def fake_build_chunk_embedding(chunk_obj, assistant_obj):
            chunk_obj.embedding = [1.0, 0.0]
            chunk_obj.embedding_model = assistant_obj.embedding_model
            chunk_obj.save(
                update_fields=[
                    "embedding",
                    "embedding_model",
                ]
            )

        with patch(
            "apps.ai_assistant.management.commands.build_embeddings.build_chunk_embedding",
            side_effect=fake_build_chunk_embedding,
        ):
            call_command("build_embeddings", stdout=StringIO())

        chunk.refresh_from_db()
        self.assertEqual(chunk.embedding, [1.0, 0.0])
        self.assertEqual(chunk.embedding_model, assistant.embedding_model)


class KnowledgeChunkAdminTest(TestCase):
    def test_save_model_clears_embedding_when_content_changes(self):
        chunk = KnowledgeChunk.objects.create(
            title="AI assistant service",
            content="Old content",
            embedding=[1.0, 0.0],
            embedding_model="text-embedding-3-small",
        )
        chunk.content = "Updated content"

        admin_instance = KnowledgeChunkAdmin(KnowledgeChunk, django_admin.site)
        form = SimpleNamespace(changed_data=["content"])
        admin_instance.save_model(None, chunk, form, change=True)

        chunk.refresh_from_db()
        self.assertIsNone(chunk.embedding)
        self.assertEqual(chunk.embedding_model, "")
        self.assertIsNone(chunk.embedding_updated_at)


class RetrievedChunkPruningTest(TestCase):
    def test_prune_retrieved_chunk_logs_keeps_latest_records(self):
        assistant = AssistantProfile.objects.create()
        session = assistant.sessions.create(channel="web")
        message = ChatMessage.objects.create(
            session=session,
            role="assistant",
            content="Answer",
        )
        chunk = KnowledgeChunk.objects.create(
            title="Chunk",
            content="Knowledge",
        )

        for index in range(7):
            RetrievedChunk.objects.create(
                message=message,
                chunk=chunk,
                score=index,
                rank=index,
            )

        prune_retrieved_chunk_logs(limit=5)

        self.assertEqual(RetrievedChunk.objects.count(), 5)
        self.assertEqual(
            list(RetrievedChunk.objects.order_by("pk").values_list("rank", flat=True)),
            [2, 3, 4, 5, 6],
        )
