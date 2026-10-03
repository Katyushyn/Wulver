"""Central help content and template wiring for the administration site."""

from django.apps import apps
from django.contrib import admin
from django.utils.translation import gettext_lazy as _


HELP_CHANGE_LIST_TEMPLATE = "admin/help/change_list.html"
HELP_CHANGE_FORM_TEMPLATE = "admin/help/change_form.html"


def _guide(title, summary, manages, workflow, notes, extra_sections=()):
    translated_extra_sections = []
    for section in extra_sections:
        translated_section = dict(section)
        translated_section["title"] = _(section["title"])
        translated_section["items"] = tuple(_(item) for item in section["items"])
        translated_extra_sections.append(translated_section)

    return {
        "title": _(title),
        "summary": _(summary),
        "sections": (
            {
                "title": _("What can be managed here"),
                "items": tuple(_(item) for item in manages),
            },
            {
                "title": _("Recommended workflow"),
                "items": tuple(_(item) for item in workflow),
            },
            {
                "title": _("Important notes"),
                "items": tuple(_(item) for item in notes),
            },
            *translated_extra_sections,
        ),
    }


ADMIN_HELP = {
    "auth.user": _guide(
        "Users",
        "Create staff and website accounts, control access, and review account status.",
        (
            "Username, name, email address, password state and last login.",
            "Staff, active and superuser flags that determine whether a person can sign in and administer the site.",
            "Group membership and individual permissions for precise access control.",
        ),
        (
            "Create a user, enter a unique username and set a temporary strong password.",
            "Grant staff status only when admin access is required, then assign the smallest suitable group.",
            "Use Active to suspend access without deleting the account and its related content.",
        ),
        (
            "Superusers have unrestricted access; reserve this flag for trusted administrators.",
            "Do not share accounts. Separate accounts keep history and audit information meaningful.",
            "Changing or resetting a password does not reveal the previous password.",
        ),
    ),
    "auth.group": _guide(
        "Groups",
        "Build reusable permission sets for editors, moderators and other administration roles.",
        (
            "A unique group name and the Django permissions included in that role.",
            "Permissions to view, add, change or delete records for individual models.",
        ),
        (
            "Create a role named after the work it permits, such as Blog editors or Comment moderators.",
            "Select only the permissions needed for that role and save the group.",
            "Assign users to the group from the Users section instead of repeating permissions per account.",
        ),
        (
            "Delete permission can permanently remove content and should be granted sparingly.",
            "Group changes affect every member immediately.",
            "A user's individual permissions are combined with permissions inherited from groups.",
        ),
    ),
    "userprofile.personalaccounttemplate": _guide(
        "Personal account template",
        "Manage authentication appearance and the system page shown to authenticated users in one place.",
        (
            "The authentication logo shared by account pages.",
            "The stylesheet shared by sign-in, registration and other authentication pages.",
            "The complete Django template code for the personal account page.",
            "Profile details and links to email, password, connected-account and sign-out actions.",
        ),
        (
            "Configure the logo and shared authentication CSS in the Appearance section.",
            "Edit the HTML and Django template tags in the code editor.",
            "Keep {% extends \"account/_auth_layout.html\" %}, account URL names and the main block unless you intentionally replace the shared authentication layout.",
            "Save and check /account/ while signed in; use Reset to defaults to restore the original template.",
        ),
        (
            "The page is system-managed, login-protected and excluded from search indexing.",
            "Invalid template syntax automatically falls back to the default account template on the public site.",
            "Reset to defaults replaces all custom code in this field.",
        ),
    ),
    "userprofile.authenticationtemplate": _guide(
        "Authentication templates",
        "Edit the complete Django HTML templates used by account and social-authentication pages.",
        (
            "One protected record for every account, password and social-authentication template.",
            "The shared base authentication layout and complete page-level Django template code.",
        ),
        (
            "Open the required template and edit its HTML and Django tags in the code editor.",
            "Keep required form fields, CSRF tokens, URL names and template variables intact.",
            "Save and test the corresponding account flow; use Reset to defaults when the original code is needed.",
        ),
        (
            "Templates are system-managed: new records cannot be added and existing records cannot be deleted.",
            "Invalid Django template syntax is rejected when saving.",
            "Reset to defaults replaces all customized code for the selected template.",
        ),
    ),
    "userprofile.authenticationemailtemplate": _guide(
        "Authentication emails",
        "Manage the subject and body of account-related emails in every supported language.",
        (
            "Templates for verification, password reset, account notifications and other authentication events.",
            "English and Ukrainian subject lines and message bodies.",
        ),
        (
            "Select the email event, edit both language versions and preserve required template variables.",
            "Use a clear subject and explain the requested action, link lifetime and what to do if the user did not initiate it.",
            "Send or trigger a test email after editing; use Reset to defaults if the original structure is needed.",
        ),
        (
            "Removing a template variable can break links or personalized values.",
            "Never place passwords, API keys or private admin information in email templates.",
            "Reset to defaults replaces customized text for both languages.",
        ),
    ),
    "socialaccount.socialapp": _guide(
        "Social Apps",
        "Connect OAuth providers such as Google to this website.",
        (
            "Provider, application name, client ID, secret, optional key and provider-specific settings.",
            "The Sites on which the provider configuration is active.",
        ),
        (
            "Create credentials in the provider console using the callback URL required by django-allauth.",
            "Add the provider and credentials here, then attach the current Site record.",
            "Test sign-in in a private browser window before announcing the option to users.",
        ),
        (
            "Client secrets are sensitive; never copy them into templates, screenshots or public repositories.",
            "The provider's authorized domain and callback URL must match the active site domain and protocol.",
            "Do not create duplicate active configurations for the same provider and site.",
        ),
    ),
    "socialaccount.socialaccount": _guide(
        "Social Accounts",
        "Review links between local users and accounts held by external login providers.",
        (
            "Local user, provider, provider user ID, connection dates and provider metadata.",
            "Existing connections created when a visitor signs in through a social provider.",
        ),
        (
            "Use search and filters to locate a connection when diagnosing sign-in issues.",
            "Confirm the local user and provider identity before changing or removing a connection.",
            "After removal, verify that the user still has another valid way to access the account.",
        ),
        (
            "Provider metadata can contain personal information and should be handled carefully.",
            "Deleting a connection does not delete the provider account, but may prevent social sign-in.",
            "Credentials for providers belong in Social Apps, not in this section.",
        ),
    ),
    "sites.site": _guide(
        "Sites",
        "Define the canonical domain and display name used by Django's Sites framework.",
        (
            "The domain, including an optional development port, and a human-readable site name.",
            "The site identity referenced by authentication and social-provider configuration.",
        ),
        (
            "Use 127.0.0.1:8000 or localhost:8000 for local development and the real hostname in production.",
            "Keep the Site ID referenced by settings and attach it to each Social App.",
            "After changing the domain, verify login links, email links and OAuth callbacks.",
        ),
        (
            "Enter only the host and optional port here, without a path.",
            "Protocol and security behavior are configured elsewhere.",
            "Changing the primary Site can affect authentication and generated absolute links immediately.",
        ),
    ),
    "backup_manager.backupsettings": _guide(
        "Backup settings",
        "Configure where encrypted full-site backups are stored and which external filesystem paths are included.",
        (
            "The private backup directory, upload size limit, ZIP compression level and optional external paths.",
            "Automatic discovery of the project root, collected static files, media and template directories.",
        ),
        (
            "Choose an absolute backup directory outside the project and public web root.",
            "Keep compression at level 1 when low CPU usage is more important than archive size.",
            "Add only trusted absolute paths that must be restored together with the site.",
        ),
        (
            "Every backup requires a password entered at creation time; Wulver never stores that password.",
            "Losing the password makes the AES-encrypted ZIP impossible to restore.",
            "The operating-system account running Django must be able to read every included path and write to the backup directory.",
        ),
    ),
    "backup_manager.backupsnapshot": _guide(
        "Backups",
        "Create, verify, download, upload, restore and delete encrypted full-site backup snapshots.",
        (
            "Complete project files, external static/media/template roots and a database-native dump in one AES-256 ZIP.",
            "Snapshot status, source, database vendor, archive path, size, checksum, manifest and job errors.",
            "SQLite, PostgreSQL, MySQL/MariaDB and Microsoft SQL Server database adapters.",
        ),
        (
            "Create a full backup, enter and safely retain its password, then wait for Completed status.",
            "Use Verify after downloading or moving an archive and keep at least one copy away from this server.",
            "Before Restore, confirm the selected archive and password; the current files and database will be replaced.",
        ),
        (
            "Downloads are available only to superusers and ZIP files are stored outside public web directories.",
            "Deleting a backup record also permanently deletes its ZIP file.",
            "Native PostgreSQL, MySQL/MariaDB and SQL Server command-line tools must be installed on the server.",
        ),
    ),
    "theme_manager.theme": _guide(
        "Themes",
        "Register theme packages and synchronize the Django templates available inside each theme.",
        (
            "Theme name, slug, description, preview image, template map and Active status.",
            "HTML template uploads and refresh actions that discover templates in the theme folder.",
        ),
        (
            "Create a theme with a stable slug, upload or place its files, then refresh templates.",
            "Review the discovered template map and preview before activating the theme.",
            "Deactivate an unused theme only after pages, categories and articles have been moved to another active theme.",
        ),
        (
            "The slug participates in filesystem paths and should not be changed casually.",
            "Uploading untrusted template code is unsafe because Django templates execute server-side template logic.",
            "Refresh synchronizes discovery; it does not replace editorial assignments automatically.",
        ),
    ),
    "theme_manager.themetemplate": _guide(
        "Templates",
        "Configure individual theme templates, their content type and editor-specific schema.",
        (
            "Theme, template type, name, slug, Active state and article extra-fields schema.",
            "The HTML code editor and the components that may be inserted into that template.",
            "Version history used to review or restore earlier template code.",
        ),
        (
            "Choose the correct template type before assigning it to pages, categories or articles.",
            "Define extra article fields as a valid schema, then use those field names in the template.",
            "Save a working version before major edits and test the rendered public page at desktop and mobile sizes.",
        ),
        (
            "Only components assigned to this template should be offered by its code editor.",
            "Changing type or slug can invalidate existing assignments and template references.",
            "Template code can break page rendering; retain version history and avoid pasting untrusted code.",
        ),
    ),
    "theme_manager.templatecomponent": _guide(
        "Components",
        "Create reusable code snippets and control which configured modules can be inserted by the template editor.",
        (
            "Component name, category, icon, description, insertion code, AI conversion prompt, status and sort order.",
            "Links to Latest articles, Tags and Images module configurations available to module-aware components.",
        ),
        (
            "Create a clearly named component and provide valid Django-template code.",
            "For a module component, attach only the module records that should be selectable in the editor modal.",
            "Set sort order for a predictable editor palette, activate it and test insertion in a compatible template.",
        ),
        (
            "A component is an editor building block, while its linked module stores content-selection settings.",
            "Keep slugs stable because editor behavior may identify components by slug.",
            "AI prompts should describe the intended transformation without secrets or environment-specific data.",
        ),
    ),
    "core_manager.sitesettings": _guide(
        "Site settings",
        "Control the site's global identity, homepage, SEO defaults, integrations and maintenance behavior.",
        (
            "Domain, public URL, contact details, homepage and 404 template.",
            "Default metadata, preview images, favicons, social profiles, Schema.org organization/person data and robots.txt.",
            "Review integrations, analytics IDs, canonical URL parameters and maintenance mode.",
        ),
        (
            "Set the correct domain and HTTPS public URL, then select the homepage and error template.",
            "Complete global SEO and organization data before using page-level overrides.",
            "Upload generated icon variants, verify social links, and enable integrations only after credentials are configured.",
            "Use Create demo data only on a new or disposable setup and review what it creates.",
        ),
        (
            "This is a singleton setting shared by the entire site.",
            "Maintenance mode affects public availability; verify the message before enabling it.",
            "Analytics and canonical settings can affect every page and should be tested in production-like conditions.",
        ),
    ),
    "core_manager.sitemapsettings": _guide(
        "Sitemap settings",
        "Control which public content appears in XML sitemaps and how multilingual URLs are described to search engines.",
        (
            "Homepage, standalone pages, blog categories and published articles.",
            "Language versions, hreflang alternatives, priorities and response cache lifetime.",
            "The generated sitemap index and section files linked automatically from robots.txt.",
        ),
        (
            "Keep the sitemap enabled and include only content types that have useful public pages.",
            "Include translated versions after completing their localized content, then open the sitemap and inspect its URLs.",
            "Clear the sitemap cache after an unusual bulk database update that bypasses normal model saving.",
        ),
        (
            "Draft, scheduled-future and noindex content is excluded automatically.",
            "Only templates represented by published Page records are included; technical theme templates never appear.",
            "Priorities are hints rather than guarantees and do not replace strong internal linking or content quality.",
        ),
    ),
    "core_manager.page": _guide(
        "Pages",
        "Create multilingual standalone pages and assign their layout and SEO metadata.",
        (
            "English and Ukrainian title and description, slug, template and publication status.",
            "Preview image, keywords, Open Graph type, Schema.org graph, noindex and other SEO overrides.",
        ),
        (
            "Choose a page template, enter a short stable slug and complete both language tabs.",
            "Publish only after checking content, metadata, preview image and canonical behavior.",
            "Use noindex for utility or temporary pages that should not appear in search results.",
        ),
        (
            "Changing a published slug changes its URL and can break external links.",
            "Page-level SEO values override global defaults; leave fields empty when inheritance is preferred.",
            "The homepage is selected separately in Site settings.",
        ),
    ),
    "core_manager.newslettersubscription": _guide(
        "Subscriptions",
        "Review and maintain email addresses submitted through newsletter forms.",
        (
            "Subscriber email, active status, source page, IP address, browser information and timestamps.",
            "The operational list of people who requested newsletter communication.",
        ),
        (
            "Use filters to separate active and inactive subscriptions and inspect the source when diagnosing spam.",
            "Deactivate an address when consent is withdrawn while retaining only data required by your policy.",
            "Export or integrate records only through an approved consent-aware mailing workflow.",
        ),
        (
            "Email, IP address and user agent are personal data.",
            "A database record is not a substitute for consent records and unsubscribe handling.",
            "Do not reactivate a user who has opted out without renewed consent.",
        ),
    ),
    "core_manager.contactmessage": _guide(
        "Messages",
        "Process inquiries submitted through public contact forms.",
        (
            "Sender name and email, subject, message body, source URL, IP address, browser information and read state.",
            "A chronological inbox for website contact requests.",
        ),
        (
            "Open unread messages, verify context and mark them read after they enter your response workflow.",
            "Use source and technical fields to investigate abuse, not as a basis for unrelated profiling.",
            "Remove or archive messages according to the site's retention policy.",
        ),
        (
            "Messages and technical metadata may contain personal or sensitive information.",
            "Do not follow suspicious links or copy untrusted content into executable templates.",
            "Replies are sent outside this section unless a dedicated integration is added.",
        ),
    ),
    "core_manager.urllink": _guide(
        "URL links",
        "Maintain reusable links with consistent behavior and styling.",
        (
            "Link title, destination URL, new-tab and nofollow options, CSS class, icon and Active status.",
            "Reusable navigation or call-to-action destinations consumed by templates.",
        ),
        (
            "Enter a descriptive title and verify the full destination URL.",
            "Use new-tab behavior for external resources only when it improves navigation, and add nofollow when editorial policy requires it.",
            "Apply only CSS classes and icons supported by the active theme, then test the rendered link.",
        ),
        (
            "Inactive links should not be rendered but remain available for later reuse.",
            "Broken or redirected URLs reduce usability and SEO quality; review them periodically.",
            "CSS classes change presentation, not access permissions or URL safety.",
        ),
    ),
    "core_manager.urlredirect": _guide(
        "URL redirects",
        "Keep old public addresses working after pages, categories or articles change URL.",
        (
            "Old local path, target URL, 301 or 302 status, Active state and an optional note.",
            "Automatic records created after slug or article-category changes, plus redirects added manually.",
            "Hit count and last-used time for checking whether an old address is still visited.",
        ),
        (
            "Use 301 for permanent URL changes and 302 only for genuinely temporary destinations.",
            "Keep the old path local and beginning with /; the target may be local or an absolute HTTP/HTTPS URL.",
            "Review automatic entries before deleting them because external links and search results may still use the old address.",
        ),
        (
            "Redirects are checked only after the normal site returns 404, so current pages always take priority.",
            "Automatic redirect chains are collapsed when an address changes repeatedly.",
            "Disabling or deleting a redirect makes its old address return 404 again.",
        ),
    ),
    "django_comments.comment": _guide(
        "Comments",
        "Moderate comments attached to articles and other comment-enabled objects.",
        (
            "Author details, target content object, text, submission time, IP address and moderation flags.",
            "Public and removed states that control whether a comment is displayed.",
        ),
        (
            "Review recent or reported comments and confirm their target article before moderating.",
            "Clear Public to hide questionable content while it is reviewed; use Removed for content that should remain recorded but not displayed.",
            "Apply the site's moderation and retention policy consistently.",
        ),
        (
            "User email and IP address are personal data and are not shown publicly by default.",
            "Deleting a comment is permanent; moderation flags preserve context and are often preferable.",
            "Form labels and styling are configured in Comment appearance.",
        ),
    ),
    "comments_manager.commentsettings": _guide(
        "Comment appearance",
        "Customize multilingual comment-form wording and the stylesheet used by comment interfaces.",
        (
            "Form title, label, placeholder, submit button, empty-state text and CSS.",
            "English and Ukrainian versions of all visitor-facing text.",
        ),
        (
            "Complete both language tabs and keep instructions short and welcoming.",
            "Adjust CSS carefully, then test the form, list and validation states on an article.",
            "Use Reset to defaults when custom text or styles cause a problem.",
        ),
        (
            "This is a singleton configuration used by every comment-enabled page.",
            "Custom CSS can affect layout and accessibility across all comment forms.",
            "Reset to defaults replaces all customized text and styles.",
        ),
    ),
    "comments_manager.commenttemplate": _guide(
        "Comment templates",
        "Edit the Django-template fragments used to render a comment, the form and the comment list.",
        (
            "One code record for each supported comment template type.",
            "Markup and Django template tags controlling the final comment interface.",
        ),
        (
            "Choose the template type, make the smallest necessary code change and save.",
            "Test anonymous and authenticated states, validation errors and nested content on a real article.",
            "Use Reset to defaults to restore the original code if rendering fails.",
        ),
        (
            "Invalid template syntax can break every page that renders comments.",
            "Do not paste scripts or template code from untrusted sources.",
            "Text and CSS belong in Comment appearance when no structural change is required.",
        ),
    ),
    "blog_manager.blogsettings": _guide(
        "Blog settings",
        "Set fallback templates and SEO graphs used when individual blog records do not override them.",
        (
            "Default first-page category template, paginated category template and article template.",
            "Default Schema.org graphs for categories and articles.",
        ),
        (
            "Select active templates with the correct category or article type.",
            "Add valid default schema that is safe for broad reuse across the blog.",
            "Test a category and article without explicit template overrides to confirm fallback behavior.",
        ),
        (
            "This is a singleton configuration for the whole blog.",
            "Per-category and per-article assignments can override these defaults.",
            "Invalid structured data can affect all inheriting pages, so validate it before deployment.",
        ),
    ),
    "blog_manager.category": _guide(
        "Categories",
        "Build the blog hierarchy and configure category content, templates, pagination and SEO.",
        (
            "Parent relationship, multilingual title, description and introduction, slug, icon and sort order.",
            "Images, tags, first-page and paginated templates, default article template and articles per page.",
            "Noindex, metadata, preview image, canonical parameters and Schema.org overrides.",
        ),
        (
            "Create parent categories first, then add children and arrange them with the tree controls.",
            "Complete both language tabs, choose compatible templates and set the article count for pagination.",
            "Upload meaningful images and alt-related content, assign relevant tags and preview each category page.",
        ),
        (
            "Changing hierarchy or slug changes URLs for the category and may affect descendant navigation.",
            "Use plain, focused introductory content; templates decide how it is rendered.",
            "Noindex and canonical settings directly affect search-engine indexing.",
        ),
    ),
    "blog_manager.article": _guide(
        "Articles",
        "Write, translate, schedule and publish blog content with images, tags, templates and SEO data.",
        (
            "Multilingual title, introduction and body, category, author, slug, status and publication date.",
            "Main and cropped images, tags, template override and template-defined extra fields.",
            "Description, keywords, preview image, Open Graph, Schema.org, canonical parameters and noindex.",
        ),
        (
            "Choose the category and template before completing extra fields, then write both language versions.",
            "Use a stable slug, concise introduction, properly structured body and 3–5 relevant tags.",
            "Upload and verify responsive images, review metadata, then publish or schedule with the correct date.",
        ),
        (
            "Published state, workflow status and publication date all influence visibility.",
            "Changing a live slug breaks its old URL unless a redirect is created.",
            "Only mark trusted editor content safe; pasted HTML can introduce broken markup or unsafe output.",
        ),
    ),
    "blog_manager.tag": _guide(
        "Tags",
        "Maintain reusable topic labels linked to articles and categories.",
        (
            "A concise tag title and unique URL-safe slug.",
            "Labels used by article metadata, search links and configured tag modules.",
        ),
        (
            "Search for an existing synonym before creating a tag.",
            "Use a short, specific title and let the slug remain stable once published.",
            "Assign a small relevant set to each article and review unused tags periodically.",
        ),
        (
            "Near-duplicate tags fragment navigation and SEO signals.",
            "Deleting a tag removes its relationships from content and modules.",
            "Display count, order and CSS behavior are configured in Modules — Tags.",
        ),
    ),
    "blog_manager.latestarticlesmodule": _guide(
        "Modules — Latest articles",
        "Create reusable article selections that templates can insert as latest-content blocks.",
        (
            "Module name and slug, source categories, descendant inclusion, article limit, ordering and Active status.",
            "A reusable configuration selectable by compatible Latest blog articles components.",
        ),
        (
            "Choose only the categories relevant to the block and decide whether their children are included.",
            "Set a sensible article count and order, then activate the module.",
            "Attach it to a compatible Template component and insert that component into the intended templates.",
        ),
        (
            "The slug is the stable template identifier and should be unique.",
            "Inactive or unpublished articles are excluded by the rendering logic.",
            "Large counts increase page weight and reduce the meaning of a latest-content block.",
        ),
    ),
    "blog_manager.tagmodule": _guide(
        "Modules — Tags",
        "Configure reusable tag clouds or tag lists, including selection, ordering and CSS-class assignment.",
        (
            "Tag source, maximum count, ordering, comma-separated classes, class mode and Active status.",
            "Class modes for sequential, combined or random styling of returned tags.",
        ),
        (
            "Choose the source and count, then select an ordering that matches the design goal.",
            "Enter only theme-supported class names separated by commas and choose how they are applied.",
            "Save and test the module in a compatible template component across repeated page loads if random mode is used.",
        ),
        (
            "Classes are emitted into template output; use trusted CSS class names only.",
            "Random mode may produce a different visual result on each render.",
            "The module configures presentation and selection; tags themselves are managed in Tags.",
        ),
    ),
    "blog_manager.imagemodule": _guide(
        "Modules — Images",
        "Build reusable optimized image collections for template components and rotating visual blocks.",
        (
            "Module name, stable slug, display mode, returned image count, Active status and isolated storage folder.",
            "Up to 100 JPEG, PNG, WebP or AVIF uploads, with alt text, order and per-image Active state.",
            "Generated main AVIF plus 600×400 desktop and 380×253 mobile crops; originals are not retained.",
        ),
        (
            "Create and save the module, upload images, then add accurate alt text and arrange their order.",
            "Choose all, one random, daily rotation, ordered count or random count as the display mode.",
            "Open generated file links to verify processing, then attach the module to an Images Template component.",
        ),
        (
            "Limits are 25 MB per upload and 500 MB of generated files per module.",
            "Removing an image or module deletes all generated AVIF variants after save.",
            "Inactive images are never returned; responsive templates should prefer crop_mob_url and crop_url with url as fallback.",
        ),
        extra_sections=(
            {
                "title": "Template usage",
                "items": (
                    "Load the image_modules template-tag library and request the module by slug.",
                    "Each result exposes url, crop_url, crop_mob_url, alt and name.",
                ),
                "code": '{% load image_modules %}\n{% image_module "sidebar-ai-images" as module_images %}',
            },
        ),
    ),
    "ai_assistant.assistantprofile": _guide(
        "Assistant Profile",
        "Configure the AI provider, models, system instructions and retrieval thresholds used by the chat assistant.",
        (
            "Provider type, chat and embedding models, prompt, temperature, context chunk limit, similarity threshold and fallback text.",
            "The behavior shared by assistant sessions using this profile.",
        ),
        (
            "Select models supported by the configured provider credentials.",
            "Write a clear prompt defining role, scope, tone, prohibited behavior and escalation rules.",
            "Start with conservative temperature and retrieval limits, then test known questions and fallback cases.",
        ),
        (
            "API credentials belong in environment variables, never in the prompt.",
            "Changing embedding model may require rebuilding all stored embeddings.",
            "Higher temperature increases variation; lower similarity thresholds can introduce irrelevant context.",
        ),
    ),
    "ai_assistant.knowledgechunk": _guide(
        "Knowledge Chunk",
        "Manage source passages that the assistant retrieves as factual context.",
        (
            "Title, content, source URL, priority, Active state and generated embedding metadata.",
            "JSON import and bulk generation of missing embeddings.",
        ),
        (
            "Split knowledge into focused self-contained passages with descriptive titles and source URLs.",
            "Set priority only when some sources should consistently outrank others, then save and build missing embeddings.",
            "Test retrieval with representative questions and update outdated chunks at their source.",
        ),
        (
            "Only active chunks are eligible for retrieval.",
            "Editing content makes its previous embedding stale and requires regeneration.",
            "Imported or pasted text is untrusted data; review it for instructions, secrets and licensing constraints.",
        ),
    ),
    "ai_assistant.chatsession": _guide(
        "Chat Session",
        "Review complete assistant conversations and their visitor, channel and lead status.",
        (
            "Assistant profile, channel, visitor contact data, IP/user agent, lead and closed flags, and activity times.",
            "Related messages and operational context for one conversation.",
        ),
        (
            "Filter by recent activity, channel, lead or closed state and open a session to review its full sequence.",
            "Mark a session closed when no further handling is required and use Lead records for follow-up workflow.",
            "Use event logs and retrieved chunks when diagnosing an answer.",
        ),
        (
            "Conversation and contact fields may contain personal or sensitive information.",
            "Do not edit history merely to improve appearance; logs should remain reliable for diagnosis.",
            "Closing a session is an operational state and does not necessarily delete its data.",
        ),
    ),
    "ai_assistant.chatmessage": _guide(
        "Chat Message",
        "Inspect individual user and assistant messages together with model and token metadata.",
        (
            "Session, role, full content, model name, prompt/completion/total token counts and timestamp.",
            "The chronological transcript used for debugging and usage analysis.",
        ),
        (
            "Open messages from their session so surrounding context is understood.",
            "Compare assistant output with Retrieved Chunks and Event Logs when investigating quality.",
            "Use token counts to identify unusually expensive requests without exposing message data unnecessarily.",
        ),
        (
            "Messages can contain personal data, secrets or malicious instructions; treat them as untrusted content.",
            "Manual edits damage transcript integrity and should be avoided.",
            "Model output is not automatically verified even when retrieval context was used.",
        ),
    ),
    "ai_assistant.retrievedchunk": _guide(
        "Retrieved Chunk",
        "Audit which knowledge passages were supplied to an assistant response and how they ranked.",
        (
            "The assistant message, selected knowledge chunk, similarity score, rank and retrieval timestamp.",
            "Evidence for diagnosing irrelevant, missing or poorly ordered context.",
        ),
        (
            "Start from a questionable assistant message and review its retrieved chunks in rank order.",
            "Compare scores and source content, then improve the knowledge chunk or profile threshold rather than editing audit rows.",
            "Retest the same question after rebuilding embeddings or changing retrieval settings.",
        ),
        (
            "A high similarity score indicates semantic proximity, not factual correctness.",
            "These records are diagnostic history and normally should remain read-only.",
            "The source knowledge is edited in Knowledge Chunk.",
        ),
    ),
    "ai_assistant.lead": _guide(
        "Lead",
        "Manage contact requests identified or submitted during assistant conversations.",
        (
            "Related chat session, contact details, message, service interest, status and timestamps.",
            "A lightweight workflow from new inquiry through follow-up and closure.",
        ),
        (
            "Review the linked session before contacting the person so their request is understood.",
            "Update status as the lead is processed and keep service interest concise and useful.",
            "Handle follow-up in an approved communication system and retain only necessary data.",
        ),
        (
            "Name, email, phone and message are personal data and require appropriate access and retention controls.",
            "A captured lead does not automatically prove marketing consent.",
            "Do not store payment, medical or other highly sensitive data in free-text fields.",
        ),
    ),
    "ai_assistant.assistanteventlog": _guide(
        "Assistant Event Log",
        "Inspect operational events, warnings, fallbacks and provider errors emitted by the assistant.",
        (
            "Session, event type, human-readable message, structured diagnostic data and timestamp.",
            "Events for low confidence, fallback behavior, API failures and other runtime conditions.",
        ),
        (
            "Filter by event type and time, then open the related session and messages for context.",
            "Use repeated patterns to adjust provider configuration, retrieval data or error handling.",
            "Resolve the root cause before clearing or archiving operational records.",
        ),
        (
            "Diagnostic data can contain user content or provider details; restrict access accordingly.",
            "Never log API keys, passwords or authorization headers.",
            "An event explains what the system observed, but may still require reproduction to confirm the cause.",
        ),
    ),
}


def get_admin_help(opts):
    label = getattr(opts, "label_lower", "") if opts else ""
    return ADMIN_HELP.get(label)


def install_admin_help_templates(site=None):
    """Attach generic help wrappers without replacing specialized admin templates."""
    site = site or admin.site
    for label in ADMIN_HELP:
        try:
            model = apps.get_model(label)
        except LookupError:
            continue

        model_admin = site._registry.get(model)
        if model_admin is None:
            continue

        if not model_admin.change_list_template:
            model_admin.change_list_template = HELP_CHANGE_LIST_TEMPLATE
        if not model_admin.change_form_template:
            model_admin.change_form_template = HELP_CHANGE_FORM_TEMPLATE
