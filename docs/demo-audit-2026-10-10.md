# Story demo data audit — 2026-10-10

Read-only inspection of the current demo database and templates. No demo content was changed.

## Verified

- 24 articles, 7 categories (Blog and 6 children), 33 tags, 14 comments, 4 users.
- 38 English page requests returned expected HTTP statuses; five Ukrainian page requests returned 200.
- No missing images were found in the rendered English pages; all ThemeTemplate files exist.
- All articles have tags; no future-dated articles were found.
- Sitemap and robots.txt respond successfully; robots.txt includes Sitemap.
- Production 404 returns 404 and noindex, nofollow.

## Findings before release

1. About and Contacts contain Latin placeholder text. Article author biography is a shared placeholder, and its technical tagline does not fit all demo authors.
2. Profile shows Kevin Anderson and hard-coded counters (147 articles, 13 awards, 25 followers), while Featured Articles uses the administrator's articles. About has invented experience/project counters.
3. Contacts contains a demonstration address, email and phone, plus a New York map. Mark these as demo details or connect appropriate settings.
4. All configured social links lead to platform homepages, not actual profiles. These are placeholders rather than broken links.
5. Three Home advertising banners link to #. Supply appropriate demo destinations or remove the links.
6. Ukrainian titles are absent for all 24 articles, 7 categories and 4 pages. Ukrainian routes work but show English fallback content; several template headings remain English.
7. Page descriptions need review; at least Home is empty. Generic titles such as Home and Profile also need editorial review.
8. Tag modules emit Bootstrap 4 class names (badge-dark, badge-secondary and badge-md/lg) that need visual verification with the Bootstrap 5 Story theme.
9. The 404 template is standalone with copied header/footer rather than the current shared includes. It emits an empty canonical link in production; it should omit the element entirely.
10. Categories in Header/Blog sidebar reference parent ID 1. Demo import must resolve identifiers reliably or preserve mappings; profile/comment modules also require seeded slugs and relationships.
11. Admin still uses the known demo password. Public installation must create credentials interactively; do not export the administrator's password hash in demo data.
12. Admin-managed comment templates are stored in the current database, and avatars/media are separate assets. A reproducible demo installer must include these along with modules, relationships and settings. No dedicated Story demo-install command was identified.

## Scope limits

No browser visual inspection, external link availability checks, license review, public deployment, email delivery test or clean-install test was performed in this audit.
