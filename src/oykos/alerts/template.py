"""Alert email template - S033."""
from __future__ import annotations

from jinja2 import Environment, BaseLoader

from oykos.alerts.triggers import AlertLevel
from oykos.models.news_item import EditorialBlock

ALERT_TEMPLATE = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ level_label }} - {{ headline }}</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }
.container { max-width: 600px; margin: 0 auto; background: #ffffff; }
.header { background: {{ level_color }}; color: #ffffff; padding: 20px 24px; }
.header h1 { margin: 0; font-size: 20px; }
.header .badge { font-size: 12px; opacity: 0.9; text-transform: uppercase; letter-spacing: 1px; }
.body { padding: 24px; }
.body h2 { font-size: 18px; color: #1a1a1a; margin: 0 0 12px 0; }
.body .why { color: #333; font-size: 14px; line-height: 1.5; }
.body .actions { margin: 16px 0; padding-left: 20px; }
.body .actions li { font-size: 14px; line-height: 1.6; color: #1a5276; }
.footer { padding: 16px 24px; font-size: 11px; color: #888; background: #f5f5f5; text-align: center; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="badge">{{ level_label }}</div>
    <h1>Oykos Alert</h1>
  </div>
  <div class="body">
    <h2>{{ headline }}</h2>
    {% if why_it_matters %}
    <p class="why">{{ why_it_matters }}</p>
    {% endif %}
    {% if what_to_do %}
    <ul class="actions">
      {% for action in what_to_do %}
      <li>{{ action }}</li>
      {% endfor %}
    </ul>
    {% endif %}
    {% if summary %}
    <p style="font-size: 13px; color: #555;">{{ summary }}</p>
    {% endif %}
  </div>
  <div class="footer">
    <p>Questo alert e stato generato automaticamente da Oykos Newsletter Engine.</p>
  </div>
</div>
</body>
</html>"""

LEVEL_CONFIG = {
    AlertLevel.CRITICAL: {"label": "ALLERTA CRITICA", "color": "#c0392b"},
    AlertLevel.HIGH: {"label": "ALLERTA ALTA", "color": "#e67e22"},
    AlertLevel.MEDIUM: {"label": "AVVISO", "color": "#2980b9"},
}


def render_alert_html(level: AlertLevel, editorial: EditorialBlock) -> str:
    """Render an alert email from editorial content."""
    config = LEVEL_CONFIG[level]
    env = Environment(loader=BaseLoader(), autoescape=True)
    template = env.from_string(ALERT_TEMPLATE)
    return template.render(
        level_label=config["label"],
        level_color=config["color"],
        headline=editorial.headline_operational,
        why_it_matters=editorial.why_it_matters,
        what_to_do=editorial.what_to_do,
        summary=editorial.summary,
    )


def render_alert_text(level: AlertLevel, editorial: EditorialBlock) -> str:
    """Render alert as plain text."""
    config = LEVEL_CONFIG[level]
    lines = [
        f"[{config['label']}] Oykos Alert",
        "=" * 40,
        "",
        editorial.headline_operational,
        "",
    ]
    if editorial.why_it_matters:
        lines.extend([editorial.why_it_matters, ""])
    if editorial.what_to_do:
        lines.append("Cosa fare:")
        for action in editorial.what_to_do:
            lines.append(f"  - {action}")
        lines.append("")
    if editorial.summary:
        lines.extend([editorial.summary, ""])
    return "\n".join(lines)
