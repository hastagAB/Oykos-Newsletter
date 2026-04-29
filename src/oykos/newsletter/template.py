"""HTML template rendering for newsletter - S023."""
from __future__ import annotations

from jinja2 import Environment, BaseLoader

from oykos.models.news_item import Newsletter

# Minimal responsive HTML email template
NEWSLETTER_TEMPLATE = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }} - {{ week }}</title>
<style>
/* Reset */
body, table, td, p, a, li { -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }
body { margin: 0; padding: 0; width: 100% !important; }
img { border: 0; outline: none; text-decoration: none; }

/* Base */
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background: #f0f2f5; color: #1a1a2e; line-height: 1.6; }
.wrapper { width: 100%; background: #f0f2f5; padding: 24px 0; }
.container { max-width: 640px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }

/* Header */
.header { background: linear-gradient(135deg, #0d3b66 0%, #1a5276 60%, #2471a3 100%); color: #ffffff; padding: 32px 32px 28px; }
.header-logo { font-size: 13px; text-transform: uppercase; letter-spacing: 2.5px; opacity: 0.7; margin-bottom: 8px; }
.header h1 { margin: 0; font-size: 26px; font-weight: 700; line-height: 1.2; }
.header .week-badge { display: inline-block; background: rgba(255,255,255,0.18); padding: 4px 14px; border-radius: 20px; font-size: 13px; margin-top: 12px; letter-spacing: 0.5px; }

/* TOC */
.toc { padding: 20px 32px; background: #f8f9fb; border-bottom: 1px solid #e8ecf1; }
.toc-title { font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #6b7b8d; margin: 0 0 10px 0; font-weight: 600; }
.toc-list { margin: 0; padding: 0; list-style: none; }
.toc-list li { padding: 3px 0; }
.toc-list a { color: #1a5276; font-size: 13px; text-decoration: none; border-bottom: 1px dotted #b0c4d8; }
.toc-list a:hover { border-bottom-style: solid; }
.toc-section { font-size: 11px; color: #8899aa; margin-left: 6px; }

/* Section headers */
.section-header { padding: 14px 32px 10px; margin-top: 8px; }
.section-header-inner { display: inline-block; font-size: 11px; text-transform: uppercase; letter-spacing: 2px; font-weight: 700; color: #ffffff; background: #1a5276; padding: 5px 16px; border-radius: 4px; }
.section-header-top .section-header-inner { background: #c0392b; }
.section-header-clinical .section-header-inner { background: #1a5276; }
.section-header-regulatory .section-header-inner { background: #7d3c98; }
.section-header-device .section-header-inner { background: #117a65; }
.section-header-cme .section-header-inner { background: #b9770e; }

/* Items */
.item { padding: 24px 32px; border-bottom: 1px solid #f0f2f5; }
.item:last-child { border-bottom: none; }
.item-number { display: inline-block; width: 24px; height: 24px; background: #eaf2f8; color: #1a5276; font-size: 12px; font-weight: 700; text-align: center; line-height: 24px; border-radius: 50%; margin-right: 8px; vertical-align: middle; }
.item h3 { margin: 0 0 10px 0; font-size: 17px; font-weight: 700; color: #1a1a2e; line-height: 1.35; }
.item .why { color: #3d4f5f; font-size: 14px; line-height: 1.65; margin: 0 0 16px 0; padding: 12px 16px; background: #f8f9fb; border-left: 3px solid #d5dde5; border-radius: 0 6px 6px 0; }
.actions-title { font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #6b7b8d; font-weight: 600; margin: 0 0 8px 0; }
.item .actions { margin: 0 0 16px 0; padding: 0; list-style: none; counter-reset: action-counter; }
.item .actions li { position: relative; padding: 6px 0 6px 28px; font-size: 14px; line-height: 1.55; color: #2c3e50; counter-increment: action-counter; }
.item .actions li::before { content: counter(action-counter); position: absolute; left: 0; top: 7px; width: 20px; height: 20px; background: #eaf2f8; color: #1a5276; font-size: 11px; font-weight: 700; text-align: center; line-height: 20px; border-radius: 50%; }

/* Meta row */
.item-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-top: 14px; padding-top: 12px; border-top: 1px solid #f0f2f5; }
.confidence { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
.confidence-high { background: #d5f5e3; color: #1e8449; }
.confidence-medium { background: #fef3e2; color: #b9770e; }
.confidence-low { background: #fce4e4; color: #c0392b; }
.source-tag { font-size: 12px; color: #6b7b8d; }
.source-tag a { color: #6b7b8d; text-decoration: none; }
.read-more { display: inline-block; font-size: 13px; font-weight: 600; color: #1a5276; text-decoration: none; padding: 5px 16px; border: 1.5px solid #1a5276; border-radius: 6px; margin-left: auto; transition: all 0.2s; }
.read-more:hover { background: #1a5276; color: #ffffff; }

/* Footer */
.footer { padding: 28px 32px; text-align: center; background: #f8f9fb; }
.footer-brand { font-size: 15px; font-weight: 600; color: #1a5276; margin-bottom: 4px; }
.footer-sub { font-size: 12px; color: #8899aa; margin: 4px 0; line-height: 1.5; }
.footer a { color: #1a5276; text-decoration: none; }
.footer a:hover { text-decoration: underline; }
.footer-divider { width: 40px; height: 2px; background: #d5dde5; margin: 16px auto; border: none; }

/* Responsive */
@media (max-width: 640px) {
  .container { width: 100% !important; border-radius: 0 !important; }
  .item, .header, .section-header, .footer, .toc { padding-left: 20px !important; padding-right: 20px !important; }
  .item-meta { flex-direction: column; align-items: flex-start; }
  .read-more { margin-left: 0 !important; margin-top: 8px; }
}
</style>
</head>
<body>
<div class="wrapper">
<div class="container">
  <!-- Header -->
  <div class="header">
    <div class="header-logo">Newsletter Pediatrica</div>
    <h1>{{ title }}</h1>
    <span class="week-badge">Settimana {{ week }}</span>
  </div>

  <!-- Table of Contents -->
  {% if slots %}
  <div class="toc">
    <p class="toc-title">In questo numero</p>
    <ul class="toc-list">
      {% for slot in slots %}
      <li>
        <a href="#item-{{ slot.position }}">{{ slot.editorial.headline_operational | truncate(80, true, '...') }}</a>
        <span class="toc-section">{{ section_labels.get(slot.section.value, slot.section.value) }}</span>
      </li>
      {% endfor %}
    </ul>
  </div>
  {% endif %}

  <!-- Content -->
  {% set current_section = namespace(value='') %}
  {% for slot in slots %}
  {% if slot.section.value != current_section.value %}
  {% set current_section.value = slot.section.value %}
  <div class="section-header section-header-{{ slot.section.value }}">
    <span class="section-header-inner">{{ section_labels.get(slot.section.value, slot.section.value) }}</span>
  </div>
  {% endif %}

  <div class="item" id="item-{{ slot.position }}">
    <h3><span class="item-number">{{ slot.position }}</span>{{ slot.editorial.headline_operational or "Titolo non disponibile" }}</h3>

    {% if slot.editorial.why_it_matters %}
    <div class="why">{{ slot.editorial.why_it_matters }}</div>
    {% endif %}

    {% if slot.editorial.what_to_do %}
    <p class="actions-title">Cosa fare</p>
    <ol class="actions">
      {% for action in slot.editorial.what_to_do %}
      <li>{{ action }}</li>
      {% endfor %}
    </ol>
    {% endif %}

    <div class="item-meta">
      <span class="confidence confidence-{{ slot.editorial.confidence.value }}">{{ slot.editorial.confidence.value | upper }}</span>
      {% if slot.source_name %}
      <span class="source-tag">Fonte: {{ slot.source_name }}</span>
      {% endif %}
      {% if slot.source_url %}
      <a href="{{ slot.source_url }}" class="read-more" target="_blank" rel="noopener">Leggi tutto &rarr;</a>
      {% endif %}
    </div>
  </div>
  {% endfor %}

  <!-- Footer -->
  <div class="footer">
    <p class="footer-brand">{{ title }}</p>
    <p class="footer-sub">Newsletter settimanale per Pediatri di Libera Scelta</p>
    <hr class="footer-divider">
    <p class="footer-sub">Ricevi questa email perche sei iscritto alla newsletter.</p>
    <p class="footer-sub"><a href="{{ unsubscribe_url }}">Annulla iscrizione</a></p>
  </div>
</div>
</div>
</body>
</html>"""

SECTION_LABELS = {
    "top_priority": "Priorita del giorno",
    "clinical": "Clinica",
    "regulatory": "Normativa e Convenzione",
    "device": "Diagnostica e Dispositivi",
    "cme": "Formazione ECM",
}


def render_html(
    newsletter: Newsletter,
    title: str = "L'Essenziale in Pediatria",
    unsubscribe_url: str = "#",
) -> str:
    """Render the newsletter as HTML email."""
    env = Environment(loader=BaseLoader(), autoescape=True)
    template = env.from_string(NEWSLETTER_TEMPLATE)
    return template.render(
        title=title,
        week=newsletter.week,
        slots=newsletter.slots,
        section_labels=SECTION_LABELS,
        unsubscribe_url=unsubscribe_url,
    )


def render_plain_text(newsletter: Newsletter, title: str = "L'Essenziale in Pediatria") -> str:
    """Render the newsletter as plain text fallback."""
    lines = [f"{title} - Settimana {newsletter.week}", "=" * 60, ""]
    current_section = ""

    for slot in newsletter.slots:
        section = slot.section.value
        if section != current_section:
            current_section = section
            label = SECTION_LABELS.get(section, section)
            lines.extend(["", f"--- {label} ---", ""])

        ed = slot.editorial
        lines.append(f"{slot.position}. {ed.headline_operational or 'N/A'}")
        if ed.why_it_matters:
            lines.append(f"   {ed.why_it_matters}")
        for i, action in enumerate(ed.what_to_do, 1):
            lines.append(f"   {i}. {action}")
        meta_parts = [f"[{ed.confidence.value.upper()}]"]
        if slot.source_name:
            meta_parts.append(f"Fonte: {slot.source_name}")
        if slot.source_url:
            meta_parts.append(f"Leggi tutto: {slot.source_url}")
        lines.append(f"   {' | '.join(meta_parts)}")
        lines.append("")

    return "\n".join(lines)
