DEFAULT_PERSONAL_ACCOUNT_TEMPLATE = r'''{% extends "account/_auth_layout.html" %}
{% load i18n %}

{% block auth_card_class %}auth-card--account{% endblock %}

{% block main %}
<section class="account-dashboard">
    <header class="account-profile">
        {% if user.avatar_url %}
            <img src="{{ user.avatar_url }}" class="account-avatar" width="112" height="112" alt="{% trans 'Profile picture' %}">
        {% else %}
            <span class="account-avatar-placeholder" aria-hidden="true">👤</span>
        {% endif %}
        <h1>{% if user.get_full_name %}{{ user.get_full_name }}{% else %}{{ user.username }}{% endif %}</h1>
        <p>{{ user.email|default:user.username }}</p>
    </header>

    <div class="account-intro">
        <h2>{% trans "Your account" %}</h2>
        <p>{% trans "Manage your personal information, email addresses, password, and connected accounts." %}</p>
    </div>

    <div class="account-grid">
        <article class="account-panel">
            <div class="account-panel__heading">
                <span class="account-panel__icon" aria-hidden="true">👤</span>
                <div>
                    <h2>{% trans "Personal information" %}</h2>
                    <p>{% trans "Review the basic information associated with your account." %}</p>
                </div>
            </div>
            <dl>
                <dt>{% trans "Username" %}</dt>
                <dd>{{ user.username }}</dd>
                <dt>{% trans "Full name" %}</dt>
                <dd>{{ user.get_full_name|default:"—" }}</dd>
            </dl>
        </article>

        <article class="account-panel">
            <div class="account-panel__heading">
                <span class="account-panel__icon" aria-hidden="true">✉</span>
                <div>
                    <h2>{% trans "Email addresses" %}</h2>
                    <p>{% trans "Add, verify, remove, or choose your primary email address." %}</p>
                </div>
            </div>
            <a href="{% url 'account_email' %}" class="btn btn-primary btn-block">{% trans "Manage email addresses" %}</a>
        </article>

        <article class="account-panel">
            <div class="account-panel__heading">
                <span class="account-panel__icon" aria-hidden="true">🔒</span>
                <div>
                    <h2>{% trans "Password and security" %}</h2>
                    <p>{% trans "Keep your account secure by updating or setting a password." %}</p>
                </div>
            </div>
            {% if user.has_usable_password %}
                <a href="{% url 'account_change_password' %}" class="btn btn-primary btn-block">{% trans "Change password" %}</a>
            {% else %}
                <a href="{% url 'account_set_password' %}" class="btn btn-primary btn-block">{% trans "Set password" %}</a>
            {% endif %}
        </article>

        <article class="account-panel">
            <div class="account-panel__heading">
                <span class="account-panel__icon" aria-hidden="true">🔗</span>
                <div>
                    <h2>{% trans "Connected accounts" %}</h2>
                    <p>{% trans "Connect or disconnect social accounts used to sign in." %}</p>
                </div>
            </div>
            <a href="{% url 'socialaccount_connections' %}" class="btn btn-primary btn-block">{% trans "Manage connected accounts" %}</a>
        </article>
    </div>

    <div class="account-actions">
        <a href="{% url 'account_logout' %}" class="btn btn-primary">{% trans "Sign out" %}</a>
    </div>
</section>
{% endblock %}
'''
