DEFAULT_TEMPLATE_COMPONENTS = [
    {
        "name": "Latest blog articles",
        "slug": "latest-blog-articles",
        "category": "Content",
        "icon": "dynamic_feed",
        "sort_order": 5,
        "description": "Reusable latest blog articles block using latest_blog_articles context.",
        "code": """{% load i18n comments %}
{% if latest_blog_articles %}
    {% for article in latest_blog_articles %}
        <div class="col-12 mb-4">
            <article>
                <div class="card bg-primary border-light shadow-soft">
                    {% if article.img_crop or article.img_crop_mob %}
                        <a href="{% url 'blog:post' category_slug=article.category.slug post_slug=article.slug %}"
                           aria-label="{% trans 'Featured image' %} {{ article.title }}">
                            <picture>
                                {% if article.img_crop_mob %}
                                    <source media="(max-width: 767px)"
                                            srcset="{{ article.img_crop_mob.url }}"
                                            type="image/avif">
                                {% elif article.img_crop %}
                                    <source media="(max-width: 767px)"
                                            srcset="{{ article.img_crop.url }}"
                                            type="image/avif">
                                {% endif %}
                                {% if article.img_crop %}
                                    <source media="(min-width: 768px)"
                                            srcset="{{ article.img_crop.url }}"
                                            type="image/avif">
                                    <img src="{{ article.img_crop.url }}"
                                         alt="{% trans 'Featured image' %} {{ article.title }}"
                                         style="aspect-ratio: 508 / 338; height: auto; object-fit: cover;"
                                         class="card-img-top rounded-top"
                                         {% if forloop.first %}fetchpriority="high"{% else %}loading="lazy" fetchpriority="low"{% endif %}>
                                {% endif %}
                            </picture>
                        </a>
                    {% endif %}
                    <div class="card-body">
                        <div class="media d-flex align-items-center justify-content-between">
                            <div class="post-group">
                                <a href="{% url 'blog:category' category_slug=article.category.slug %}"
                                   class="badge badge-secondary">
                                    {{ article.category.title }}
                                </a>
                            </div>
                            <div class="d-flex align-items-center">
                                <span class="small">
                                    <span class="far fa-calendar-alt mr-2"></span>
                                    {{ article.publish|date:"d.m.Y" }}
                                </span>
                            </div>
                        </div>
                        <a href="{% url 'blog:post' category_slug=article.category.slug post_slug=article.slug %}">
                            <h2 class="h5 card-title mt-3">{{ article.title }}</h2>
                        </a>
                        <p class="card-text">{{ article.intro|safe }}</p>
                        <a href="{% url 'blog:post' category_slug=article.category.slug post_slug=article.slug %}"
                           class="btn btn-primary btn-sm mr-3">
                            <i class="fas fa-book mr-2"></i>
                            {% trans "Read more" %}
                        </a>
                        <a href="{% url 'blog:post' category_slug=article.category.slug post_slug=article.slug %}#comments"
                           class="small"
                           aria-label="{% trans 'Go to comments: ' %}{{ article.title }}">
                            <span class="far fa-comments mr-2"></span>
                            {% get_comment_count for article as comment_count %}
                            {{ comment_count }}
                        </a>
                    </div>
                </div>
            </article>
        </div>
    {% endfor %}
{% endif %}""",
        "ai_conversion_prompt": """Convert the selected article/card/list markup into a reusable latest blog articles block.
- Preserve the selected outer wrappers, grid columns, card/list structure, CSS classes, icons, image wrappers, aria attributes, data attributes, and visual layout.
- Use the context variable latest_blog_articles. Never use articles for this module, because articles may already be the current blog category listing.
- Wrap the repeated markup in {% if latest_blog_articles %} and {% for article in latest_blog_articles %}.
- Use article.title for titles, article.intro|safe for intro/excerpt text, article.publish|date:"d.m.Y" for dates, article.category.title for category labels, and article.category.slug plus article.slug for URLs.
- Use {% url 'blog:post' category_slug=article.category.slug post_slug=article.slug %} for article links.
- Use {% url 'blog:category' category_slug=article.category.slug %} for category links when category links exist in the selected markup.
- If the selected markup contains images, render article.img_crop_mob and article.img_crop with a picture/img fallback while preserving selected image classes.
- If the selected markup contains comments, include {% load comments %} and use {% get_comment_count for article as comment_count %}.
- If the selected markup contains translated labels, include {% load i18n %} and use {% trans %} for static labels.
- Do not change the main category page variable articles.
- Return only the converted template fragment.""",
    },
    {
        "name": "External reviews carousel",
        "slug": "external-reviews-carousel",
        "category": "Content",
        "icon": "reviews",
        "sort_order": 6,
        "description": "Reusable carousel for external reviews from GitHub and future providers.",
        "code": """{% load i18n %}
{% if external_reviews %}
    <section class="external-reviews">
        <h2>{% trans "Reviews" %}</h2>
        <div id="ExternalReviewsCarousel" class="carousel slide" data-ride="carousel">
            <ol class="carousel-indicators">
                {% for review in external_reviews %}
                    <li data-target="#ExternalReviewsCarousel"
                        data-slide-to="{{ forloop.counter0 }}"
                        class="{% if forloop.first %}active{% endif %}">
                    </li>
                {% endfor %}
            </ol>
            <div class="carousel-inner">
                {% for review in external_reviews %}
                    <div class="carousel-item {% if forloop.first %}active{% endif %} text-center">
                        {% if review.logo_url %}
                            <img src="{{ review.logo_url }}"
                                 alt="{% trans 'Organisation:' %} {{ review.display_name }}"
                                 loading="lazy">
                        {% elif review.avatar_url %}
                            <img src="{{ review.avatar_url }}"
                                 alt="{{ review.author }}"
                                 loading="lazy">
                        {% endif %}
                        {% if review.stars %}
                            <div aria-label="{{ review.rating }} / 5">{{ review.stars }}</div>
                        {% endif %}
                        <blockquote>{{ review.text }}</blockquote>
                        <div>
                            {% if review.url %}
                                <a href="{{ review.url }}" target="_blank" rel="noopener noreferrer">
                                    {{ review.display_name }}
                                </a>
                            {% else %}
                                {{ review.display_name }}
                            {% endif %}
                            {% if review.created_at %}
                                <span>{{ review.created_at|date:"d.m.Y" }}</span>
                            {% endif %}
                        </div>
                    </div>
                {% endfor %}
            </div>
        </div>
    </section>
{% endif %}""",
        "ai_conversion_prompt": """Convert the selected static testimonials/reviews block into a dynamic external reviews block.
- Preserve the selected outer wrapper, carousel/list/card structure, CSS classes, icons, image wrappers, aria attributes, data attributes, and layout.
- Use the context variable external_reviews.
- Wrap the repeated markup in {% if external_reviews %} and {% for review in external_reviews %}.
- Use review.text for review text, review.display_name for organization/person display name, review.author for author, review.created_at|date:"d.m.Y" for dates, review.stars for prepared star text, and review.rating for rating labels.
- Render review.logo_url first, then review.avatar_url as fallback. Do not use {% static %} for external review images.
- If the selected markup has carousel indicators, generate them with forloop.counter0 and mark only forloop.first as active.
- If the selected markup has a source link, use review.url with target="_blank" and rel="noopener noreferrer".
- Do not output external review text with |safe.
- Return only the converted template fragment.""",
    },
    {
        "name": "Tags",
        "slug": "tags-cloud",
        "category": "Content",
        "icon": "sell",
        "sort_order": 7,
        "description": "Reusable tags block configured by a Blog manager tag module.",
        "code": """{% if module_tags %}
    <div class="tags-cloud">
        {% for item in module_tags %}
            <a href="{% url 'core_manager:search' %}?tag={{ item.slug }}"
               class="{{ item.css_class }} my-1">
                {{ item.title }}
            </a>
        {% endfor %}
    </div>
{% endif %}""",
        "ai_conversion_prompt": """Convert the selected static tag links/list into a dynamic tags cloud block.
- Preserve the selected outer wrapper, link classes, spacing classes, icons, aria attributes, and layout.
- Use the context variable module_tags prepared by the selected Tags module.
- Wrap the repeated tag item in {% if module_tags %} and {% for item in module_tags %}.
- Use {% url 'core_manager:search' %}?tag={{ item.slug }} for tag links unless the selected markup already uses a compatible search URL.
- Use item.title for visible tag text and item.css_class for module-configured CSS classes.
- Return only the converted template fragment.""",
    },
    {
        "name": "Images",
        "slug": "images",
        "category": "Content",
        "icon": "imagesmode",
        "sort_order": 8,
        "description": "Reusable image block configured by an Images module.",
        "code": """{% if module_images %}
    <div class="module-images">
        {% for image in module_images %}
            <picture>
                {% if image.crop_mob_url %}
                    <source media="(max-width: 767px)" srcset="{{ image.crop_mob_url }}" type="image/avif">
                {% endif %}
                {% if image.crop_url %}
                    <source media="(min-width: 768px)" srcset="{{ image.crop_url }}" type="image/avif">
                {% endif %}
                <img src="{% firstof image.crop_url image.url %}"
                     alt="{{ image.alt }}"
                     loading="lazy">
            </picture>
        {% endfor %}
    </div>
{% endif %}""",
        "ai_conversion_prompt": """Convert the selected static image or image list into a dynamic Images module block.
- Preserve the selected wrappers, image classes, picture elements, spacing, loading and accessibility attributes.
- Use the context variable module_images prepared by the selected Images module.
- Wrap repeated image markup in {% if module_images %} and {% for image in module_images %}.
- Prefer image.crop_mob_url below 768 px and image.crop_url from 768 px using a picture element.
- Use image.url as the fallback for legacy module images, image.alt for alt text, and image.name when a file name is needed.
- Do not use {% static %} for module image URLs.
- Return only the converted template fragment.""",
    },
    {
        "name": "Blog category list",
        "slug": "blog-category-children",
        "category": "Navigation",
        "icon": "account_tree",
        "sort_order": 10,
        "description": "Converts selected list markup into blog category links.",
        "code": """{% load blog_categories %}
{% get_blog_category_children category.id as child_categories %}
<ul>
    {% for child_category in child_categories %}
        <li>
            <a href="{% url 'blog:category' category_slug=child_category.slug %}">
                {{ child_category.title }}
            </a>
        </li>
    {% endfor %}
</ul>""",
        "ai_conversion_prompt": """Convert the selected list/navigation markup into a dynamic list of direct child blog categories.
- Preserve the selected block's outer wrapper, list container, item wrapper, anchor classes, icons, spans, aria attributes, data attributes, dropdown hooks, and layout.
- Use {% load blog_categories %}.
- Use {% get_blog_category_children SELECTED_CATEGORY_ID as child_categories %}; replace SELECTED_CATEGORY_ID with the selected parent blog category id from the runtime context.
- Loop with {% for child_category in child_categories %} and render one selected list item per child category.
- Use {% url 'blog:category' category_slug=child_category.slug %} for links.
- Use child_category.title for visible category text.
- If the selected item contains an icon, preserve the icon markup. If using category-provided icons, use child_category.icon only as a fallback and keep the original icon classes.
- Keep static headings or wrapper labels that identify the parent category.
- Do not render grandchildren unless the selected markup explicitly contains nested child lists.
- Return only the converted template fragment.""",
    },
    {
        "name": "Breadcrumbs",
        "slug": "breadcrumbs",
        "category": "Navigation",
        "icon": "conversion_path",
        "sort_order": 20,
        "description": "Accessible breadcrumbs with automatic current title fallback.",
        "code": """{% firstof title page_title object.title article.title category.name "Current page" as title %}
<nav class="breadcrumbs" aria-label="Breadcrumb">
    <ol>
        <li><a href="/">Home</a></li>
        {% if category %}
            <li><a href="{{ category.get_absolute_url }}">{{ category.name }}</a></li>
        {% endif %}
        <li aria-current="page">{{ title }}</li>
    </ol>
</nav>""",
        "ai_conversion_prompt": """Convert the selected breadcrumb markup into a dynamic Django breadcrumb.
- Preserve the selected outer wrappers, classes, icons, separators, aria attributes, and list structure.
- Use title as the current page title, with safe fallbacks where useful.
- If a category object appears to be available, include a category link using category.get_absolute_url and category.name.
- Keep Home as a link to "/".
- Do not invent unrelated navigation items.""",
    },
    {
        "name": "Previous article",
        "slug": "previous-article",
        "category": "Navigation",
        "icon": "keyboard_double_arrow_left",
        "sort_order": 40,
        "description": "Button linking to the previous article prepared by the article detail view.",
        "code": """{% load i18n %}
{% if prev_article %}
    <a href="{% url 'blog:post' category_slug=prev_article.category.slug post_slug=prev_article.slug %}"
       class="btn btn-primary w-100 d-flex align-items-center justify-content-start">
        <i class="fas fa-angle-double-left mr-2" aria-hidden="true"></i>
        <span>{% trans "Previous template" %}: {{ prev_article.title }}</span>
    </a>
{% endif %}""",
        "ai_conversion_prompt": """Convert the selected previous-article link or button into a dynamic Django article navigation button.
- Preserve the selected wrapper, button classes, alignment, icons, spans, aria attributes, and layout.
- Use the context variable prev_article.
- Wrap the complete button in {% if prev_article %}.
- Build the URL with {% url 'blog:post' category_slug=prev_article.category.slug post_slug=prev_article.slug %}.
- Use prev_article.title for the visible article title.
- Keep translated static labels with {% load i18n %} and {% trans %}.
- Do not include next_article markup.
- Return only the converted template fragment.""",
    },
    {
        "name": "Next article",
        "slug": "next-article",
        "category": "Navigation",
        "icon": "keyboard_double_arrow_right",
        "sort_order": 41,
        "description": "Button linking to the next article prepared by the article detail view.",
        "code": """{% load i18n %}
{% if next_article %}
    <a href="{% url 'blog:post' category_slug=next_article.category.slug post_slug=next_article.slug %}"
       class="btn btn-primary w-100 d-flex align-items-center justify-content-end">
        <span>{% trans "Next template" %}: {{ next_article.title }}</span>
        <i class="fas fa-angle-double-right ml-2" aria-hidden="true"></i>
    </a>
{% endif %}""",
        "ai_conversion_prompt": """Convert the selected next-article link or button into a dynamic Django article navigation button.
- Preserve the selected wrapper, button classes, alignment, icons, spans, aria attributes, and layout.
- Use the context variable next_article.
- Wrap the complete button in {% if next_article %}.
- Build the URL with {% url 'blog:post' category_slug=next_article.category.slug post_slug=next_article.slug %}.
- Use next_article.title for the visible article title.
- Keep translated static labels with {% load i18n %} and {% trans %}.
- Do not include prev_article markup.
- Return only the converted template fragment.""",
    },
    {
        "name": "Language switcher",
        "slug": "language-switcher",
        "category": "Navigation",
        "icon": "translate",
        "sort_order": 30,
        "description": "Language links generated automatically from settings.LANGUAGES.",
        "code": """{% if language_urls %}
    <nav class="language-switcher" aria-label="Language switcher">
        {% for language in language_urls %}
            <a href="{{ language.url }}"{% if language.is_active %} class="active"{% endif %}>{{ language.code|upper }}</a>
        {% endfor %}
    </nav>
{% endif %}""",
        "ai_conversion_prompt": """Convert selected language switcher HTML into working Django language links.
- Preserve wrappers, classes, icons, labels, aria attributes, ids, and layout.
- Loop over the language_urls context variable.
- Each language item contains code, name, url, and is_active.
- Use language.url for href and language.is_active for active classes.
- Never leave language href values as "#".
- Return only the converted template fragment.""",
    },
    {
        "name": "Pagination",
        "slug": "pagination",
        "category": "Content",
        "icon": "keyboard_double_arrow_right",
        "sort_order": 10,
        "description": "Reusable pagination for Django Page objects named page_obj.",
        "code": """{% load i18n pagination %}
{% if page_obj and page_obj.paginator.num_pages > 1 %}
    {% elided_page_range page_obj as page_numbers %}
    <nav class="pagination-wrap" aria-label="{% trans 'Pagination' %}">
        <ul class="pagination">
            {% if page_obj.has_previous %}
                <li><a href="?page={{ page_obj.previous_page_number }}" rel="prev">{% trans "Previous" %}</a></li>
            {% endif %}

            {% for page_number in page_numbers %}
                {% if page_number == page_obj.paginator.ELLIPSIS %}
                    <li class="disabled"><span>{{ page_number }}</span></li>
                {% else %}
                    <li>
                        {% if page_number == page_obj.number %}
                            <span class="active" aria-current="page">{{ page_number }}</span>
                        {% else %}
                            <a href="?page={{ page_number }}">{{ page_number }}</a>
                        {% endif %}
                    </li>
                {% endif %}
            {% endfor %}

            {% if page_obj.has_next %}
                <li><a href="?page={{ page_obj.next_page_number }}" rel="next">{% trans "Next" %}</a></li>
            {% endif %}
        </ul>
    </nav>
{% endif %}""",
        "ai_conversion_prompt": """Convert the selected pagination markup into Django pagination using page_obj.
- Preserve wrappers, classes, icons, aria attributes, rel attributes, and visual structure.
- Load i18n and pagination, then use elided_page_range to build page_numbers.
- Use page_obj.has_previous, page_obj.previous_page_number, page_obj.number, page_obj.has_next, and page_obj.next_page_number.
- Render paginator.ELLIPSIS as disabled text without a link.
- Wrap the result in an if that only renders when page_obj exists and page_obj.paginator.num_pages > 1.
- Keep the current page active state in the same visual style as the selected markup.""",
    },
    {
        "name": "Subscription form",
        "slug": "subscription",
        "category": "Forms",
        "icon": "mark_email_read",
        "sort_order": 10,
        "description": "Newsletter block with CSRF token and message states ready for backend wiring.",
        "code": """<div class="footer-newsletter">
    <div class="container">
        <h4>Subscribe to our newsletter</h4>
        <p>Receive the latest news and updates.</p>
        <form action="{% url 'core_manager:newsletter_subscribe' %}" method="post" class="php-email-form">
            <input type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true" style="position:absolute;left:-10000px">
            {% csrf_token %}
            <div class="newsletter-form">
                <input type="email" name="email" placeholder="Email address" required>
                <input type="submit" value="Subscribe">
            </div>
            <div class="loading">Loading</div>
            <div class="error-message"></div>
            <div class="sent-message">Your subscription request has been sent. Thank you!</div>
        </form>
    </div>
</div>""",
        "ai_conversion_prompt": """Convert the selected subscription/newsletter form into a working CMS subscription form.
- Preserve wrappers, classes, fields, loading/error/sent message containers, icons, and layout.
- Set the form action to {% url 'core_manager:newsletter_subscribe' %}.
- Keep method="post" and include {% csrf_token %} inside the form.
- Ensure the email input has name="email", type="email", and required.
- Keep compatibility with BootstrapMade php-email-form behavior if those classes are present.""",
    },
    {
        "name": "Contact form",
        "slug": "contact-form",
        "category": "Forms",
        "icon": "contact_mail",
        "sort_order": 20,
        "description": "Contact form layout with name, email, subject, message, CSRF and template-friendly states.",
        "code": """<form action="{% url 'core_manager:contact_send' %}" method="post" class="php-email-form">
    {% csrf_token %}
    <div style="position:absolute; left:-9999px;" aria-hidden="true">
        <label>Website <input type="text" name="website" tabindex="-1" autocomplete="off"></label>
    </div>
    <div class="row gy-4">
        <div class="col-md-6">
            <input type="text" name="name" class="form-control" placeholder="Your name" required>
        </div>
        <div class="col-md-6">
            <input type="email" name="email" class="form-control" placeholder="Your email" required>
        </div>
        <div class="col-md-12">
            <input type="text" name="subject" class="form-control" placeholder="Subject" required>
        </div>
        <div class="col-md-12">
            <textarea name="message" class="form-control" rows="6" placeholder="Message" required></textarea>
        </div>
        <div class="col-md-12 text-center">
            <div class="loading">Loading</div>
            <div class="error-message"></div>
            <div class="sent-message">Your message has been sent. Thank you!</div>
            <button type="submit">Send Message</button>
        </div>
    </div>
</form>""",
        "ai_conversion_prompt": """Convert the selected contact form into a working CMS contact form.
- Preserve wrappers, classes, fields, loading/error/sent message containers, icons, and layout.
- Set the form action to {% url 'core_manager:contact_send' %}.
- Keep method="post" and include {% csrf_token %} inside the form.
- Ensure fields use name="name", name="email", name="subject", and name="message".
- Ensure the email field has type="email" and required.
- Add a hidden honeypot field named website inside the form, positioned off-screen, unless it already exists.
- Keep compatibility with BootstrapMade php-email-form behavior if those classes are present.""",
    },
    {
        "name": "Django comments",
        "slug": "comments",
        "category": "Content",
        "icon": "comment",
        "sort_order": 20,
        "description": "Comment count, list and form for django-contrib-comments using object, article, or page context.",
        "code": """{% load comments %}
{% if object %}
    {% get_comment_count for object as comment_count %}
    <section class="comments">
        <h3>{{ comment_count }} Comment{{ comment_count|pluralize }}</h3>
        {% render_comment_list for object %}
        {% render_comment_form for object %}
    </section>
{% elif article %}
    {% get_comment_count for article as comment_count %}
    <section class="comments">
        <h3>{{ comment_count }} Comment{{ comment_count|pluralize }}</h3>
        {% render_comment_list for article %}
        {% render_comment_form for article %}
    </section>
{% elif page %}
    {% get_comment_count for page as comment_count %}
    <section class="comments">
        <h3>{{ comment_count }} Comment{{ comment_count|pluralize }}</h3>
        {% render_comment_list for page %}
        {% render_comment_form for page %}
    </section>
{% endif %}""",
        "ai_conversion_prompt": """Convert the selected comments/comment-form markup into django-contrib-comments markup.
- Preserve the selected visual section wrapper, classes, headings, and layout as much as possible.
- Include {% load comments %}.
- Do not use {% firstof ... as comment_object %}; django-comments needs a real model instance, not a rendered string.
- Use explicit branches for object, article, and page.
- In each branch, use get_comment_count, render_comment_list, and render_comment_form for the actual object in that branch.
- Keep existing comment section classes where possible.""",
    },
    {
        "name": "Authentication controls",
        "slug": "authentication-controls",
        "category": "Authentication",
        "icon": "login",
        "sort_order": 10,
        "description": "One Bootstrap user button that opens sign-in or the configured personal information page.",
        "code": """{% load i18n authentication_controls %}
{% authentication_button_url as authentication_url %}
<a href="{{ authentication_url }}"
   class="authentication-button btn btn-outline-primary"
   aria-label="{% if user.is_authenticated %}{% trans 'Personal information' %}{% else %}{% trans 'Sign in' %}{% endif %}"
   title="{% if user.is_authenticated %}{% trans 'Personal information' %}{% else %}{% trans 'Sign in' %}{% endif %}">
    <i class="fas fa-user" aria-hidden="true"></i>
    <span class="sr-only">
        {% if user.is_authenticated %}{% trans "Personal information" %}{% else %}{% trans "Sign in" %}{% endif %}
    </span>
</a>""",
        "ai_conversion_prompt": """Convert the selected account button into the Wulver authentication button.
- Preserve the selected button wrapper, Bootstrap classes, Font Awesome user icon, sizing, aria attributes, and visual layout.
- Include {% load i18n authentication_controls %}.
- Resolve the destination with {% authentication_button_url as authentication_url %} and use {{ authentication_url }} as href.
- Render one button only, using user.is_authenticated only to switch its accessible Sign in / Personal information label.
- Keep a Font Awesome user icon and an accessible visually hidden label.
- Do not create custom authentication endpoints or forms.
- Return only the converted template fragment.""",
    },
]
