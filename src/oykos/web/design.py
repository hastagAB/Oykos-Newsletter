"""Shared design system for every server-rendered page.

One base layout, one set of tokens, no CDN dependencies. Everything is rendered
through Jinja2 with autoescaping on, so source and subscriber content can never
inject markup.
"""
from __future__ import annotations

from jinja2 import BaseLoader, Environment
from markupsafe import Markup

_env = Environment(loader=BaseLoader(), autoescape=True)

BRAND = "L'Essenziale in Pediatria"

# Design tokens. Kept in sync with the newsletter template palette so the web
# surface and the email feel like the same product.
STYLES = """
:root {
  --ink: #12212e;
  --ink-soft: #46606f;
  --ink-faint: #7b8fa0;
  --line: #e3eaf0;
  --line-strong: #cbd8e2;
  --bg: #f4f7fa;
  --surface: #ffffff;
  --brand: #1a5276;
  --brand-dark: #0d3b66;
  --brand-tint: #eaf2f8;
  --danger: #c0392b;
  --danger-tint: #fdecea;
  --success: #1e8449;
  --success-tint: #e6f6ec;
  --warn: #b9770e;
  --warn-tint: #fdf4e3;
  --radius: 10px;
  --radius-sm: 6px;
  --shadow: 0 1px 2px rgba(16,42,66,.06), 0 8px 24px rgba(16,42,66,.08);
  --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: var(--font); font-size: 16px; line-height: 1.6;
}
a { color: var(--brand); }
a:focus-visible, button:focus-visible, input:focus-visible,
select:focus-visible, textarea:focus-visible, summary:focus-visible {
  outline: 3px solid var(--brand); outline-offset: 2px; border-radius: 3px;
}

/* Layout */
.site { max-width: 880px; margin: 0 auto; padding: 24px 20px 64px; }
.site--narrow { max-width: 560px; }
.site--wide { max-width: 1080px; }
.masthead { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }
.masthead a { text-decoration: none; }
.wordmark { font-size: 17px; font-weight: 700; color: var(--brand-dark); letter-spacing: -.01em; }
.masthead .tag { font-size: 12px; color: var(--ink-faint); text-transform: uppercase; letter-spacing: 1.4px; }
.card {
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--radius); box-shadow: var(--shadow);
  padding: 28px; margin-bottom: 20px;
}
.card--flush { padding: 0; overflow: hidden; }

/* Typography */
h1 { font-size: 26px; line-height: 1.25; margin: 0 0 8px; letter-spacing: -.02em; }
h2 { font-size: 19px; line-height: 1.3; margin: 32px 0 12px; letter-spacing: -.01em; }
h3 { font-size: 16px; margin: 0 0 6px; }
.lede { color: var(--ink-soft); margin: 0 0 24px; }
.muted { color: var(--ink-faint); font-size: 13px; }
.eyebrow {
  font-size: 11px; text-transform: uppercase; letter-spacing: 1.6px;
  color: var(--ink-faint); font-weight: 700; margin: 0 0 8px;
}

/* Forms */
.field { margin-bottom: 18px; }
label { display: block; font-size: 14px; font-weight: 600; margin-bottom: 6px; }
input[type=email], input[type=text], input[type=password], textarea, select {
  width: 100%; padding: 11px 13px; font: inherit; font-size: 15px;
  border: 1px solid var(--line-strong); border-radius: var(--radius-sm);
  background: var(--surface); color: var(--ink);
}
textarea { min-height: 96px; resize: vertical; }
.hint { font-size: 13px; color: var(--ink-faint); margin-top: 6px; }
fieldset { border: 0; padding: 0; margin: 0 0 18px; }
legend { font-size: 14px; font-weight: 600; padding: 0; margin-bottom: 10px; }
.check-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 8px; }
.check {
  display: flex; align-items: flex-start; gap: 9px; padding: 10px 12px;
  border: 1px solid var(--line); border-radius: var(--radius-sm); cursor: pointer;
  font-size: 14px; font-weight: 500; background: var(--surface);
}
.check:hover { border-color: var(--brand); background: var(--brand-tint); }
.check input { margin: 3px 0 0; flex-shrink: 0; }

/* Buttons */
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 7px;
  padding: 11px 20px; font: inherit; font-size: 15px; font-weight: 600;
  border-radius: var(--radius-sm); border: 1px solid transparent; cursor: pointer;
  text-decoration: none; background: var(--brand); color: #fff;
}
.btn:hover { background: var(--brand-dark); }
.btn[disabled] { opacity: .5; cursor: not-allowed; }
.btn--ghost { background: transparent; color: var(--brand); border-color: var(--line-strong); }
.btn--ghost:hover { background: var(--brand-tint); color: var(--brand-dark); }
.btn--danger { background: var(--danger); }
.btn--danger:hover { background: #96281b; }
.btn--sm { padding: 7px 13px; font-size: 13px; }
.btn-row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }

/* Status */
.pill {
  display: inline-block; padding: 3px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .6px;
}
.pill--ok { background: var(--success-tint); color: var(--success); }
.pill--warn { background: var(--warn-tint); color: var(--warn); }
.pill--danger { background: var(--danger-tint); color: var(--danger); }
.pill--neutral { background: var(--brand-tint); color: var(--brand); }
.notice { padding: 13px 16px; border-radius: var(--radius-sm); font-size: 14px; margin-bottom: 20px; }
.notice--ok { background: var(--success-tint); color: #14663a; }
.notice--warn { background: var(--warn-tint); color: #8a5a0b; }
.notice--danger { background: var(--danger-tint); color: #96281b; }

/* Lists */
.rows { list-style: none; margin: 0; padding: 0; }
.rows li { border-top: 1px solid var(--line); }
.rows li:first-child { border-top: 0; }
.row-link {
  display: flex; align-items: center; gap: 14px; padding: 15px 28px;
  text-decoration: none; color: inherit;
}
.row-link:hover { background: var(--brand-tint); }
.row-main { flex: 1; min-width: 0; }
.row-title { font-weight: 600; color: var(--brand-dark); }
.row-meta { font-size: 13px; color: var(--ink-faint); }
.empty { padding: 44px 28px; text-align: center; color: var(--ink-faint); }

/* Footer */
.site-foot { margin-top: 36px; font-size: 13px; color: var(--ink-faint); text-align: center; }
.site-foot a { color: var(--ink-soft); }
.disclaimer {
  margin-top: 20px; padding: 14px 16px; background: var(--surface);
  border: 1px solid var(--line); border-radius: var(--radius-sm);
  font-size: 12px; line-height: 1.6; color: var(--ink-faint); text-align: left;
}

@media (max-width: 640px) {
  .site { padding: 16px 14px 48px; }
  .card { padding: 20px; }
  .row-link { padding: 14px 20px; }
  h1 { font-size: 22px; }
}
"""

_BASE = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="{{ robots }}">
<title>{{ title }} - {{ brand }}</title>
<style>{{ styles }}</style>
</head>
<body>
<div class="site {{ width_class }}">
  <header class="masthead">
    <a href="/"><span class="wordmark">{{ brand }}</span></a>
    {% if section %}<span class="tag">{{ section }}</span>{% endif %}
  </header>
  <main>
{{ body }}
  </main>
  <footer class="site-foot">
    {% if show_disclaimer %}<p class="disclaimer">{{ disclaimer }}</p>{% endif %}
  </footer>
</div>
</body>
</html>"""

DISCLAIMER = (
    "Informazione professionale destinata a medici. Non sostituisce le linee guida "
    "locali, la valutazione clinica del singolo caso né la consultazione della fonte "
    "primaria."
)

WIDTHS = {"narrow": "site--narrow", "default": "", "wide": "site--wide"}


def render_page(
    title: str,
    body_html: str,
    *,
    section: str = "",
    width: str = "default",
    show_disclaimer: bool = True,
    robots: str = "noindex",
) -> str:
    """Wrap pre-rendered body markup in the shared layout.

    ``body_html`` must come from :func:`render_fragment`, which escapes every
    interpolated value. It is marked safe here so the layout does not escape it
    a second time; never pass raw user input to this function.
    """
    template = _env.from_string(_BASE)
    return template.render(
        title=title,
        brand=BRAND,
        # Both values are authored in this module, never derived from input.
        styles=Markup(STYLES),  # noqa: S704
        body=Markup(body_html),  # noqa: S704
        section=section,
        width_class=WIDTHS.get(width, ""),
        show_disclaimer=show_disclaimer,
        disclaimer=DISCLAIMER,
        robots=robots,
    ) + "\n"


def render_fragment(template_source: str, **context: object) -> str:
    """Render a body fragment with autoescaping on."""
    return _env.from_string(template_source).render(**context)


def message_page(
    title: str,
    heading: str,
    message: str,
    *,
    tone: str = "ok",
    action_url: str = "",
    action_label: str = "",
) -> str:
    """A single-purpose confirmation or error page."""
    body = render_fragment(
        """
    <div class="card">
      <div class="notice notice--{{ tone }}">{{ heading }}</div>
      <p class="lede">{{ message }}</p>
      {% if action_url %}
      <a class="btn" href="{{ action_url }}">{{ action_label }}</a>
      {% endif %}
    </div>""",
        heading=heading,
        message=message,
        tone=tone,
        action_url=action_url,
        action_label=action_label,
    )
    return render_page(title, body, width="narrow")
