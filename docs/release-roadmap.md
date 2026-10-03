# WULVER Corporate — release roadmap

## Product direction

WULVER starts as a focused CMS for corporate websites. Optional capabilities
such as catalog, commerce, AI, events, booking, and advanced forms will be
distributed as installable modules rather than bundled into every project.

The first public release must provide a small, stable core that can build:

- corporate and service websites;
- landing pages;
- portfolios and personal websites;
- blogs and information portals.

## Core scope

- Core Manager and site settings;
- Theme Manager, templates, components, and theme assets;
- pages and homepage selection;
- blog, categories, articles, tags, article images, and content modules;
- localization and Rosetta;
- SEO metadata, Open Graph, Schema.org, canonical rules, sitemap, robots, and redirects;
- contact messages and newsletter subscriptions;
- users, profiles, and base authentication;
- backup and restore;
- production, security, image-processing, and static-file configuration.

## Optional module direction

- `wulver-ai`;
- `wulver-catalog`;
- `wulver-commerce` (depends on catalog);
- `wulver-comments`;
- `wulver-events`;
- `wulver-booking`;
- `wulver-forms`.

Prepared distributions such as WULVER Corporate, WULVER Catalog, and WULVER
Commerce must remain profiles composed from one core and optional modules, not
independent forks of the project.

## Release steps

### 1. Remove legacy website data — complete

Completed:

- removed old articles, categories, tags, pages, themes, and templates;
- removed legacy uploaded media;
- removed generated `staticfiles`;
- removed the previous project-specific frontend theme;
- created a fresh database and local administrator.
- removed the previous project-specific reviews repository from fresh site settings and its model default;
- regenerated localization catalogs without deleted project-specific template strings;
- replaced remaining legacy project identifiers in active system code;
- confirmed no old-site assets or content remain outside Git history;
- ran Django checks and the full test suite.

Completion criteria:

- clean database contains only required singleton defaults and the local administrator;
- `media` and generated `staticfiles` are empty;
- active source, translations, defaults, and documentation contain no legacy project branding;
- Django checks and tests pass.

### 2. Define core and module boundaries

- document mandatory core applications;
- identify optional applications and their dependencies;
- define a module manifest and compatibility rules;
- ensure the core does not import optional modules directly;
- support enabling modules through configuration before building a web installer.

### 3. Extract the first optional module

- use AI Assistant as the first architecture test;
- package its models, URLs, templates, static assets, admin menu, and migrations;
- verify installation, disabling, upgrading, and removal behavior;
- use the resulting contract for future modules.

### 4. Create a neutral corporate demo

- add one redistribution-safe corporate theme;
- provide homepage, about, services, contacts, blog, article, search, and 404 templates;
- create neutral multilingual demo content and images;
- verify responsive layout, accessibility, SEO, and PageSpeed behavior.

### 5. Build clean initialization

- rename and repair the WULVER initialization command;
- create required singleton settings and built-in template components;
- support a clean database without shipping user accounts or sessions;
- document migrations, administrator creation, static collection, and first start;
- verify installation on a clean machine or container.

### 6. Product documentation

- create README, license, installation guide, theme-development guide, and module guide;
- document environment variables and production deployment;
- describe backup, restore, upgrade, and rollback procedures;
- prepare concise admin instructions and an initial video walkthrough.

### 7. Versioning and release engineering

- introduce an explicit WULVER version;
- maintain a changelog and compatibility policy;
- add release checks and a clean build process;
- define safe update and migration procedures;
- publish the first corporate release only after clean-install verification.

### 8. Post-release modules

- Catalog;
- Commerce on top of Catalog;
- AI / WULVER Developer;
- Forms;
- Events and Booking;
- optional module installer and module catalog in the admin interface.
