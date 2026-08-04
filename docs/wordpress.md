# WordPress Publishing

Every issue is published as a WordPress post **before** the email is delivered.
That ordering is the whole point: the email footer carries a "Leggi online" link,
and the link has to resolve by the time the message lands.

Implemented in `src/oykos/delivery/wordpress.py`, called from
`oykos.pipeline.weekly.deliver_and_finalize`, which is shared by the scheduled
`oykos send` run and the "Approva e invia ora" button in the review workbench, so
both paths finalise identically.

---

## What gets posted

`build_post_payload` maps the issue onto the core `/wp-json/wp/v2/posts` schema:

| WordPress field | Source |
|-----------------|--------|
| `title` | `Newsletter.subject_line`, falling back to `"{NEWSLETTER_TITLE} - {week}"` |
| `slug` | `briefing-{week}` lowercased, e.g. `briefing-2026-w31` |
| `content` | `Newsletter.html_content` - the same HTML the email carries |
| `excerpt` | `Newsletter.preheader` |
| `status` | `WORDPRESS_STATUS` |
| `categories` | `[WORDPRESS_CATEGORY_ID]`, omitted entirely when the ID is `0` |

On `201 Created` the `link` from the response is stored on
`Newsletter.public_url` and in the `public_url` column of the `newsletters`
table, then the email is rendered with the "Leggi online" link in the footer and
at the end of the plain text part.

---

## Setup

### 1. Create an Application Password

WordPress 5.6+ ships Application Passwords in core. Nothing to install.

1. Log in to WordPress as the account that should own the posts.
2. Go to **Users > Profile** (or **Users > All Users > {user}**).
3. Scroll to **Application Passwords**, name it (for example `oykos-newsletter`)
   and click **Add New Application Password**.
4. Copy the generated value. It is shown once.

The feature only appears over HTTPS. On a plain-HTTP site the section is hidden
and you will need TLS before going further.

This is **not** your WordPress login password. The account password will be
rejected by the REST API.

### 2. Configure

```env
# Site root. No trailing slash, no /wp-json suffix.
WORDPRESS_URL=https://oykomed.it
WORDPRESS_USER=your-wp-username
# The Application Password. Spaces in the generated value are fine.
WORDPRESS_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
# "publish" goes live immediately, "draft" stages it for a human.
WORDPRESS_STATUS=publish
# Optional category ID. 0 uses the site default.
WORDPRESS_CATEGORY_ID=0
```

Publishing is enabled only when `WORDPRESS_URL`, `WORDPRESS_USER` and
`WORDPRESS_APP_PASSWORD` are **all** set (`Settings.wordpress_enabled`). Leave
`WORDPRESS_URL` empty and `publish_issue` returns immediately; the pipeline
composes, review-gates and sends email exactly as before, just without the
online link.

### 3. Verify

Set `WORDPRESS_STATUS=draft` for the first run. The post appears in the
WordPress admin without going public, so you can check the rendering before
switching to `publish`.

---

## Failure behaviour

Publishing never blocks delivery. `publish_issue` returns an empty string and
logs on:

- transport failure or timeout (30s, `httpx.HTTPError`)
- any response status other than `201`, with the first 300 characters of the
  body logged so the WordPress error code is visible

`Newsletter.public_url` then stays empty and the template simply omits the
"Leggi online" link. The issue still ships.

---

## Troubleshooting

| Symptom | Cause |
|---------|-------|
| `401` with `incorrect_password` | Using the account password instead of an Application Password |
| No Application Passwords section in the profile | Site is not served over HTTPS, or WordPress is older than 5.6 |
| `403` with `rest_cannot_create` | The user's role cannot publish posts. Use an Editor or Administrator |
| `404` on `/wp-json/` | REST API disabled by a plugin, or permalinks set to "Plain" |
| `401` and the header never arrives | Some Apache configurations drop the `Authorization` header. Add `SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1` |
| Post created but empty | `Newsletter.html_content` was empty; the issue was never rendered |

## Moving off WordPress

`publish_issue` returns a URL string and nothing else in the pipeline depends on
WordPress. To publish somewhere else, replace that one function and keep the
signature `(Settings, Newsletter) -> str`, returning an empty string on failure.
