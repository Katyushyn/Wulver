DEFAULT_COMMENT_STYLESHEET = """/* Shared styles for comment form, list and individual comments. */
.comments-system { color: #1f2937; }
.comments-title { margin: 0 0 20px; }
.comments-form, .comment-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 20px;
}
.comments-form { margin-bottom: 28px; }
.comments-field { margin-bottom: 16px; }
.comments-field label { display: block; margin-bottom: 6px; font-weight: 600; }
.comments-honeypot { position: absolute !important; left: -10000px !important; width: 1px; height: 1px; overflow: hidden; }
.comments-form textarea, .comments-form input:not([type=hidden]):not([type=submit]) {
    width: 100%;
    border: 1px solid #d1d5db;
    border-radius: 10px;
    padding: 10px 12px;
}
.comments-submit {
    border: 0;
    border-radius: 10px;
    background: #2563eb;
    color: #ffffff;
    cursor: pointer;
    padding: 10px 18px;
}
.comment-card { display: flex; gap: 14px; margin-bottom: 16px; }
.comment-avatar { width: 48px; height: 48px; flex: 0 0 48px; border-radius: 50%; object-fit: cover; }
.comment-avatar-placeholder { display: grid; place-items: center; background: #e5e7eb; }
.comment-content { min-width: 0; flex: 1; }
.comment-meta { display: flex; flex-wrap: wrap; gap: 8px 14px; margin-bottom: 8px; font-size: .875rem; color: #6b7280; }
.comment-text { overflow-wrap: anywhere; line-height: 1.6; }
.comments-empty { padding: 20px; text-align: center; color: #6b7280; }
"""

DEFAULT_COMMENT_TEXTS = {
    "en": {
        "form_title": "Leave a comment",
        "comment_label": "Comment",
        "comment_placeholder": "Write your comment…",
        "submit_text": "Post comment",
        "empty_text": "No comments yet.",
    },
    "uk": {
        "form_title": "Залишити коментар",
        "comment_label": "Коментар",
        "comment_placeholder": "Напишіть ваш коментар…",
        "submit_text": "Опублікувати коментар",
        "empty_text": "Коментарів поки немає.",
    },
}

DEFAULT_COMMENT_TEMPLATES = {
    "form": """{% load comments comment_ui %}{% comment_ui as comment_settings %}
<link rel="stylesheet" href="{% url 'comments_stylesheet' %}?v={{ comment_settings.updated_at|date:'U' }}">
<section class="comments-system comments-form-section">
    <h2 class="comments-title">{{ comment_settings.form_title }}</h2>
    <form action="{% comment_form_target %}" method="post" class="comments-form">
        {% csrf_token %}
        {% if next %}<input type="hidden" name="next" value="{{ next }}">{% else %}<input type="hidden" name="next" value="{{ request.path }}">{% endif %}
        {% for field in form %}
            {% if field.is_hidden %}{{ field }}
            {% elif field.name == "honeypot" %}<div class="comments-honeypot" aria-hidden="true">{{ field }}</div>
            {% elif field.name == "comment" %}
                <div class="comments-field{% if field.errors %} has-errors{% endif %}">
                    <label for="{{ field.id_for_label }}">{{ comment_settings.comment_label }}</label>
                    <textarea name="{{ field.name }}" id="{{ field.id_for_label }}" maxlength="3000" rows="6" placeholder="{{ comment_settings.comment_placeholder }}" required>{{ field.value|default_if_none:'' }}</textarea>
                    {{ field.errors }}
                </div>
            {% else %}
                <div class="comments-field{% if field.errors %} has-errors{% endif %}">{{ field.label_tag }}{{ field }}{{ field.errors }}</div>
            {% endif %}
        {% endfor %}
        <button type="submit" name="post" class="comments-submit">{{ comment_settings.submit_text }}</button>
    </form>
</section>""",
    "list": """{% load comment_ui %}{% comment_ui as comment_settings %}
<link rel="stylesheet" href="{% url 'comments_stylesheet' %}?v={{ comment_settings.updated_at|date:'U' }}">
<section class="comments-system comments-list" id="comments">
    {% for comment in comment_list %}
        {% include "comments/comment.html" %}
    {% empty %}
        <div class="comments-empty">{{ comment_settings.empty_text }}</div>
    {% endfor %}
</section>""",
    "comment": """<article class="comment-card" id="c{{ comment.id }}">
    {% if comment.user and comment.user.userprofile.avatar %}
        <img class="comment-avatar" src="{{ comment.user.userprofile.avatar.url }}" alt="">
    {% else %}
        <span class="comment-avatar comment-avatar-placeholder" aria-hidden="true"><i class="fas fa-user"></i></span>
    {% endif %}
    <div class="comment-content">
        <div class="comment-meta">
            <strong>{% if comment.user %}{% firstof comment.user.get_full_name comment.user.username %}{% else %}{{ comment.user_name }}{% endif %}</strong>
            <time datetime="{{ comment.submit_date|date:'c' }}">{{ comment.submit_date|date:"d.m.Y H:i" }}</time>
        </div>
        <div class="comment-text">{{ comment.comment|linebreaksbr }}</div>
    </div>
</article>""",
}
