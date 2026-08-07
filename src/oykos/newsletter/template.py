"""HTML template rendering for newsletter - S023."""
from __future__ import annotations

from jinja2 import BaseLoader, Environment

from oykos.models.news_item import Newsletter

MIN_READING_MINUTES = 6

# Oykomed brand palette, taken from oykomed.it.
BRAND_TEAL = "#008484"
BRAND_TEAL_DARK = "#006B6B"
BRAND_PINK = "#D1427C"
BRAND_NAVY = "#0F2B5B"
BRAND_RUST = "#C42E00"
TINT = "#EEF6F8"
TINT_BORDER = "#D6E8EC"

# The logo is teal on a transparent background, so it only reads on a light
# surface - hence the white masthead. Most clients block images by default, so
# nothing in the header depends on it loading.
LOGO_URL = "https://oykomed.it/_next/static/media/logo-sm.abbdf224.png"
LOGO_ALT = "Oykos by Oykomed"

# Standard closing call to action, on every issue.
CTA_TITLE = "Inizia a risparmiare 1 ora al giorno nella tua attività pediatrica"
CTA_SUBTITLE = (
    "Oykos raccoglie, verifica e traduce in azioni ciò che cambia davvero per un "
    "Pediatra di Libera Scelta. Scopri come funziona."
)
CTA_BUTTON = "Scopri Oykos"
CTA_URL = "https://oykomed.it"

# Table-based HTML email. Email clients (Outlook in particular, which renders
# with the Word engine) do not support flexbox, gradients, CSS counters or
# pseudo-elements, so the layout uses nested tables and explicit values.
NEWSLETTER_TEMPLATE = """<!DOCTYPE html>
<html lang="it" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="format-detection" content="telephone=no">
<title>{{ title }} - {{ week }}</title>
<!--[if mso]>
<noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript>
<![endif]-->
<style>
body, table, td, p, a, li, h1, h2, h3 { -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }
table { border-collapse: collapse !important; mso-table-lspace: 0pt; mso-table-rspace: 0pt; }
img { border: 0; outline: none; text-decoration: none; -ms-interpolation-mode: bicubic; }
body { margin: 0 !important; padding: 0 !important; width: 100% !important; }
a { color: #008484; }
.serif { font-family: Georgia, 'Times New Roman', Times, serif; }
.sans { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
.preheader { display: none !important; visibility: hidden; opacity: 0; color: transparent;
             height: 0; width: 0; max-height: 0; max-width: 0; overflow: hidden; mso-hide: all; }
a.plain, a.plain:visited { text-decoration: none; }
@media screen and (max-width: 620px) {
  .container { width: 100% !important; }
  .pad { padding-left: 22px !important; padding-right: 22px !important; }
  .h-title { font-size: 25px !important; }
  .i-title { font-size: 19px !important; }
  .stack { display: block !important; width: 100% !important; text-align: left !important; }
  .stack-gap { padding-top: 10px !important; }
}
@media (prefers-color-scheme: dark) {
  .darkbg { background-color: #ffffff !important; }
}
</style>
</head>
<body style="margin:0;padding:0;background-color:#EDEEF1;">
<div class="preheader">{{ preheader }}</div>

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#EDEEF1" style="background-color:#EDEEF1;">
<tr><td align="center" style="padding:28px 12px;">

<table role="presentation" class="container darkbg" width="600" cellpadding="0" cellspacing="0" border="0" bgcolor="#FFFFFF" style="width:600px;max-width:600px;background-color:#FFFFFF;">

  <!-- Masthead -->
  <tr>
    <td class="pad" bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:30px 40px 24px;">
      <img src="{{ logo_url }}" alt="{{ logo_alt }}" width="132" height="59"
           style="display:block;border:0;outline:none;width:132px;height:59px;margin:0 0 20px;">
      <p class="sans" style="margin:0 0 12px;font-size:10px;letter-spacing:2.6px;text-transform:uppercase;color:#008484;font-weight:700;">
        Briefing operativo per PLS
      </p>
      <h1 class="serif h-title" style="margin:0;font-size:30px;line-height:1.22;font-weight:400;color:#0F2B5B;letter-spacing:-0.2px;">
        {{ title }}
      </h1>
      <p class="sans" style="margin:14px 0 0;font-size:12px;color:#64748B;letter-spacing:0.4px;">
        Settimana {{ week }} &nbsp;&middot;&nbsp; lettura {{ reading_time }} minuti
      </p>
    </td>
  </tr>

  <!-- Accent rule -->
  <tr><td bgcolor="#008484" style="background-color:#008484;font-size:0;line-height:0;height:3px;">&nbsp;</td></tr>

  <!-- What is really changing -->
  {% if tldr %}
  <tr>
    <td class="pad" bgcolor="#EEF6F8" style="background-color:#EEF6F8;padding:24px 40px;border-bottom:1px solid #D6E8EC;">
      <p class="sans" style="margin:0 0 12px;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#006B6B;font-weight:700;">
        Cosa cambia davvero questa settimana
      </p>
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
        {% for line in tldr %}
        <tr>
          <td valign="top" style="padding:3px 10px 3px 0;font-size:14px;line-height:1.6;color:#D1427C;">&bull;</td>
          <td valign="top" class="sans" style="padding:3px 0;font-size:14px;line-height:1.62;color:#1E293B;">{{ line }}</td>
        </tr>
        {% endfor %}
      </table>
    </td>
  </tr>
  {% endif %}

  <!-- In this issue -->
  {% if slots %}
  <tr>
    <td class="pad" style="padding:24px 40px 20px;border-bottom:1px solid #E7E9ED;">
      <p class="sans" style="margin:0 0 12px;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#8B95A3;font-weight:700;">
        In questo numero
      </p>
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
        {% for slot in slots %}
        <tr>
          <td valign="top" class="sans" style="padding:5px 12px 5px 0;font-size:12px;line-height:1.5;color:#008484;font-weight:700;width:22px;">
            {{ "%02d"|format(slot.position) }}
          </td>
          <td valign="top" class="sans" style="padding:5px 0;font-size:13.5px;line-height:1.5;color:#1E293B;">
            <a href="#item-{{ slot.position }}" class="plain" style="color:#1E293B;text-decoration:none;">{{ slot.editorial.headline_operational | truncate(78, true, '...') }}</a>
            <span style="color:#94A3B8;font-size:11.5px;">&nbsp;&middot;&nbsp;{{ section_labels.get(slot.section.value, slot.section.value) }}</span>
          </td>
        </tr>
        {% endfor %}
      </table>
    </td>
  </tr>
  {% endif %}

  <!-- Items -->
  {% set ns = namespace(section='') %}
  {% for slot in slots %}
  {% if slot.section.value != ns.section %}
  {% set ns.section = slot.section.value %}
  <tr>
    <td class="pad" style="padding:30px 40px 0;">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
        <tr>
          <td valign="middle" class="sans" style="font-size:10px;letter-spacing:2.2px;text-transform:uppercase;font-weight:700;color:{{ section_colors.get(slot.section.value, '#12263F') }};white-space:nowrap;padding-right:14px;">
            {{ section_labels.get(slot.section.value, slot.section.value) }}
          </td>
          <td valign="middle" style="width:100%;border-top:1px solid #E7E9ED;font-size:0;line-height:0;">&nbsp;</td>
        </tr>
      </table>
    </td>
  </tr>
  {% endif %}

  <tr>
    <td class="pad" id="item-{{ slot.position }}" style="padding:22px 40px 26px;border-bottom:1px solid #F0F2F5;">

      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
        <tr>
          <td valign="top" class="serif" style="width:34px;padding:2px 14px 0 0;font-size:22px;line-height:1;color:#9CCBCB;font-weight:400;">
            {{ "%02d"|format(slot.position) }}
          </td>
          <td valign="top">
            <h3 class="serif i-title" style="margin:0 0 12px;font-size:21px;line-height:1.32;font-weight:400;color:#0F2B5B;letter-spacing:-0.1px;">
              {{ slot.editorial.headline_operational or "Titolo non disponibile" }}
            </h3>

            {% if slot.editorial.why_it_matters %}
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:0 0 16px;">
              <tr>
                <td width="3" bgcolor="#008484" style="background-color:#008484;font-size:0;line-height:0;width:3px;">&nbsp;</td>
                <td class="sans" style="padding:2px 0 2px 15px;font-size:14.5px;line-height:1.68;color:#334155;">
                  {{ slot.editorial.why_it_matters }}
                </td>
              </tr>
            </table>
            {% endif %}

            {% if slot.editorial.what_to_do %}
            <p class="sans" style="margin:0 0 9px;font-size:10px;letter-spacing:1.6px;text-transform:uppercase;color:#8B95A3;font-weight:700;">
              Cosa fare ora
            </p>
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:0 0 16px;">
              {% for action in slot.editorial.what_to_do %}
              <tr>
                <td valign="top" style="width:3px;" bgcolor="#D1427C">&nbsp;</td>
                <td valign="top" class="sans" style="padding:4px 0 4px 12px;font-size:14.5px;line-height:1.6;color:#1E293B;font-weight:600;">{{ action }}</td>
              </tr>
              {% endfor %}
            </table>
            {% endif %}

            {% if slot.position == 1 and slot.editorial.summary %}
            <p class="sans" style="margin:0 0 16px;font-size:14px;line-height:1.68;color:#5A6472;">{{ slot.editorial.summary }}</p>
            {% endif %}

            {% if slot.position == 1 and slot.evidence_quote %}
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:0 0 18px;">
              <tr>
                <td bgcolor="#F6FAFB" style="background-color:#F6FAFB;padding:16px 18px;border-left:3px solid #D1427C;">
                  <p class="serif" style="margin:0 0 8px;font-size:15.5px;line-height:1.6;color:#0F2B5B;font-style:italic;">
                    &ldquo;{{ slot.evidence_quote }}&rdquo;
                  </p>
                  <p class="sans" style="margin:0;font-size:10.5px;letter-spacing:1.2px;text-transform:uppercase;color:#7B96A0;font-weight:700;">
                    {{ slot.source_name }}
                  </p>
                </td>
              </tr>
            </table>
            {% endif %}

            {% if slot.source_links %}
            <p class="sans" style="margin:0 0 6px;font-size:10px;letter-spacing:1.6px;text-transform:uppercase;color:#8B95A3;font-weight:700;">Fonti</p>
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:0 0 14px;">
              {% for link in slot.source_links %}
              <tr>
                <td class="sans" style="padding:2px 0;font-size:13px;line-height:1.55;">
                  <a href="{{ link.url }}" target="_blank" rel="noopener noreferrer" style="color:#008484;text-decoration:underline;">{{ link.label }}</a>
                </td>
              </tr>
              {% endfor %}
            </table>
            {% endif %}

            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-top:1px solid #F0F2F5;margin-top:4px;">
              <tr>
                <td valign="middle" class="stack sans" style="padding:12px 0 0;font-size:11px;color:#8B95A3;">
                  {% if slot.editorial.source_note %}{{ slot.editorial.source_note }}
                  {% elif slot.source_name %}{{ slot.source_name }}{% endif %}
                </td>
                {% if slot.source_url %}
                <td valign="middle" align="right" class="stack stack-gap" style="padding:12px 0 0;">
                  {% if slot.access_limited %}
                  <span class="sans" style="font-size:10.5px;letter-spacing:0.6px;color:#B45309;font-weight:700;">ACCESSO RISERVATO AI SOCI</span>
                  <span style="color:#C3C9D2;">&nbsp;&middot;&nbsp;</span>
                  {% endif %}
                  <a href="{{ slot.source_url }}" target="_blank" rel="noopener noreferrer" class="sans plain" style="font-size:12px;font-weight:700;color:#008484;text-decoration:none;white-space:nowrap;">
                    Consulta il testo integrale &rarr;
                  </a>
                </td>
                {% endif %}
              </tr>
            </table>

          </td>
        </tr>
      </table>

    </td>
  </tr>
  {% endfor %}

  <!-- Call to action -->
  <tr>
    <td class="pad" style="padding:32px 40px 36px;">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" bgcolor="#008484" style="background-color:#008484;">
        <tr>
          <td align="center" style="padding:32px 30px;">
            <p class="serif" style="margin:0 0 10px;font-size:21px;line-height:1.35;color:#FFFFFF;font-weight:400;">
              {{ cta_title }}
            </p>
            <p class="sans" style="margin:0 0 22px;font-size:13.5px;line-height:1.65;color:#CDE7E7;">
              {{ cta_subtitle }}
            </p>
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center">
              <tr>
                <td bgcolor="#D1427C" style="background-color:#D1427C;">
                  <a href="{{ cta_url }}" target="_blank" rel="noopener noreferrer" class="sans plain"
                     style="display:inline-block;padding:14px 34px;font-size:14px;font-weight:700;color:#FFFFFF;text-decoration:none;letter-spacing:0.4px;">
                    {{ cta_button }}
                  </a>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Footer -->
  <tr>
    <td class="pad" bgcolor="#EEF6F8" style="background-color:#EEF6F8;padding:28px 40px 32px;border-top:1px solid #D6E8EC;">
      <img src="{{ logo_url }}" alt="{{ logo_alt }}" width="106" height="48"
           style="display:block;border:0;outline:none;width:106px;height:48px;margin:0 0 14px;">
      <p class="sans" style="margin:0 0 16px;font-size:11.5px;color:#64748B;">{{ title }} &middot; Briefing settimanale per Pediatri di Libera Scelta</p>
      <p class="sans" style="margin:0 0 14px;font-size:12px;line-height:1.9;color:#64748B;">
        {% if public_url %}<a href="{{ public_url }}" style="color:#008484;text-decoration:none;">Leggi online</a>
        <span style="color:#A9C7CD;">&nbsp;&middot;&nbsp;</span>{% endif %}
        <a href="{{ preferences_url }}" style="color:#008484;text-decoration:none;">Preferenze</a>
        <span style="color:#A9C7CD;">&nbsp;&middot;&nbsp;</span>
        <a href="{{ archive_url }}" style="color:#008484;text-decoration:none;">Archivio</a>
        <span style="color:#A9C7CD;">&nbsp;&middot;&nbsp;</span>
        <a href="{{ unsubscribe_url }}" style="color:#008484;text-decoration:none;">Annulla iscrizione</a>
      </p>
      <p class="sans" style="margin:0 0 14px;font-size:11px;line-height:1.6;color:#8FA3AD;">
        Ricevi questa email perché ti sei iscritto e hai confermato l'indirizzo.
      </p>
      <p class="sans" style="margin:0;font-size:10.5px;line-height:1.65;color:#7B8F99;background-color:#FFFFFF;padding:12px 14px;">
        {{ disclaimer }}
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""

SECTION_LABELS = {
    "top_priority": "Priorità della settimana",
    "clinical": "Clinica del territorio",
    "regulatory": "Normativa e organizzazione",
    "device": "Test, POCT e dispositivi",
    "cme": "Formazione ECM ed eventi",
}

SECTION_COLORS = {
    "top_priority": BRAND_RUST,
    "clinical": BRAND_TEAL,
    "regulatory": BRAND_NAVY,
    "device": BRAND_TEAL_DARK,
    "cme": BRAND_PINK,
}

CONFIDENCE_COLORS = {
    "high": BRAND_TEAL,
    "medium": "#B45309",
    "low": BRAND_RUST,
}


DISCLAIMER = (
    "Informazione professionale destinata a medici. Non sostituisce le linee guida "
    "locali, la valutazione clinica del singolo caso né la consultazione della fonte "
    "primaria. Le implicazioni operative sono redazionali e distinte da quanto "
    "affermato dalla fonte."
)


def render_html(
    newsletter: Newsletter,
    title: str = "L'Essenziale in Pediatria",
    unsubscribe_url: str = "#",
    preferences_url: str = "#",
    archive_url: str = "#",
    cta_url: str = CTA_URL,
    logo_url: str = LOGO_URL,
    preheader: str = "",
    cta_title: str = "",
) -> str:
    """Render the newsletter as HTML email.

    The "Leggi online" link is driven by ``newsletter.public_url``, which the
    pipeline sets by publishing to WordPress *before* delivering. If publishing
    failed the field stays empty and the link is simply omitted.
    """
    env = Environment(loader=BaseLoader(), autoescape=True)
    template = env.from_string(NEWSLETTER_TEMPLATE)
    return template.render(
        title=title,
        week=newsletter.week,
        slots=newsletter.slots,
        section_labels=SECTION_LABELS,
        tldr=newsletter.tldr,
        preheader=preheader or newsletter.preheader,
        reading_time=newsletter.reading_time_minutes or MIN_READING_MINUTES,
        unsubscribe_url=unsubscribe_url,
        preferences_url=preferences_url,
        archive_url=archive_url,
        public_url=newsletter.public_url,
        section_colors=SECTION_COLORS,
        confidence_colors=CONFIDENCE_COLORS,
        logo_url=logo_url,
        logo_alt=LOGO_ALT,
        cta_title=cta_title or CTA_TITLE,
        cta_subtitle=CTA_SUBTITLE,
        cta_button=CTA_BUTTON,
        cta_url=cta_url,
        disclaimer=DISCLAIMER,
    )


def render_plain_text(
    newsletter: Newsletter,
    title: str = "L'Essenziale in Pediatria",
    unsubscribe_url: str = "",
    preferences_url: str = "",
    cta_url: str = CTA_URL,
    cta_title: str = "",
) -> str:
    """Render the newsletter as plain text fallback."""
    reading_time = newsletter.reading_time_minutes or MIN_READING_MINUTES
    lines = [
        f"{title} - Settimana {newsletter.week}",
        f"Tempo di lettura stimato: {reading_time} minuti",
        "=" * 60,
    ]

    if newsletter.tldr:
        lines.extend(["", "COSA CAMBIA DAVVERO QUESTA SETTIMANA", ""])
        lines.extend(f"  - {line}" for line in newsletter.tldr)

    current_section = ""
    for slot in newsletter.slots:
        section = slot.section.value
        if section != current_section:
            current_section = section
            lines.extend(["", f"--- {SECTION_LABELS.get(section, section)} ---", ""])

        ed = slot.editorial
        lines.append(f"{slot.position}. {ed.headline_operational or 'N/A'}")
        if ed.why_it_matters:
            lines.append(f"   In pratica: {ed.why_it_matters}")
        if ed.what_to_do:
            lines.append("   Cosa fare ora:")
            lines.extend(f"     {i}. {action}" for i, action in enumerate(ed.what_to_do, 1))
        # Only the week's priority gets the extended treatment.
        if slot.position == 1 and ed.summary:
            lines.append(f"   {ed.summary}")
        if slot.position == 1 and slot.evidence_quote:
            lines.append(f'   "{slot.evidence_quote}" - {slot.source_name}')

        if slot.source_links:
            lines.append("   Fonti:")
            lines.extend(f"     - {link.label}: {link.url}" for link in slot.source_links)
        elif slot.source_url:
            lines.append(f"   Fonte: {slot.source_name} - {slot.source_url}")

        if ed.source_note:
            lines.append(f"   {ed.source_note}")
        if slot.access_limited:
            lines.append("   [Accesso riservato ai soci]")
        lines.append("")

    lines.extend(["", "-" * 60, cta_title or CTA_TITLE, CTA_SUBTITLE, cta_url, "", DISCLAIMER])
    if newsletter.public_url:
        lines.append(f"Leggi online: {newsletter.public_url}")
    if preferences_url:
        lines.append(f"Preferenze: {preferences_url}")
    if unsubscribe_url:
        lines.append(f"Annulla iscrizione: {unsubscribe_url}")

    return "\n".join(lines)
