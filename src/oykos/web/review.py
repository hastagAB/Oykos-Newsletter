"""Editorial review workbench.

Implements the human-in-the-loop stage of the blueprint (Section 7). Every item
in an issue requires an editor's sign-off before the issue can send; there is no
auto-approval path for medical content.

Access is gated by a shared review token. Without ``REVIEW_TOKEN`` configured the
whole router refuses to serve, so a misconfigured deployment fails closed rather
than exposing an open approval surface.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from oykos.config import Settings
from oykos.db.repository import NewsletterRepository, ReviewDecisionRepository
from oykos.models.news_item import Newsletter, NewsletterSlot, ReviewDecision
from oykos.models.taxonomy import IssueStatus, ReviewerRole
from oykos.newsletter.template import SECTION_LABELS, render_html, render_plain_text
from oykos.web.design import message_page, render_fragment, render_page

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/review", tags=["review"])

SESSION_COOKIE = "oykos_review"
VALID_DECISIONS = frozenset({"approved", "rejected", "edited"})

STATUS_TONE = {
    IssueStatus.DRAFT: "neutral",
    IssueStatus.IN_REVIEW: "warn",
    IssueStatus.APPROVED: "ok",
    IssueStatus.SENT: "ok",
}
STATUS_LABEL = {
    IssueStatus.DRAFT: "Bozza",
    IssueStatus.IN_REVIEW: "In revisione",
    IssueStatus.APPROVED: "Approvato",
    IssueStatus.SENT: "Inviato",
}
DECISION_LABEL = {
    "approved": "Approvato",
    "rejected": "Rifiutato",
    "edited": "Modificato",
}


# ── Session handling ──────────────────────────────────────

def _sign(secret: str, expires_at: int) -> str:
    return hmac.new(
        secret.encode("utf-8"), str(expires_at).encode("utf-8"), hashlib.sha256,
    ).hexdigest()


def issue_session(secret: str, ttl_hours: int) -> str:
    """Mint a signed session value. The secret itself never leaves the server."""
    expires_at = int(time.time()) + ttl_hours * 3600
    return f"{expires_at}.{_sign(secret, expires_at)}"


def session_is_valid(cookie_value: str | None, secret: str) -> bool:
    if not cookie_value or not secret:
        return False
    raw_expiry, _, signature = cookie_value.partition(".")
    if not signature:
        return False
    try:
        expires_at = int(raw_expiry)
    except ValueError:
        return False
    if expires_at < time.time():
        return False
    return hmac.compare_digest(signature, _sign(secret, expires_at))


def get_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        raise HTTPException(status_code=503, detail="App not started")
    return settings


def get_session_factory(request: Request):  # noqa: ANN201
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="App not started")
    return factory


async def require_reviewer(
    settings: Annotated[Settings, Depends(get_settings)],
    oykos_review: Annotated[str | None, Cookie()] = None,
) -> Settings:
    """Reject anything that is not a live, signed reviewer session."""
    if not settings.review_enabled:
        raise HTTPException(status_code=404, detail="Review interface disabled")
    if not session_is_valid(oykos_review, settings.review_token.get_secret_value()):
        raise HTTPException(status_code=401, detail="Sign in required")
    return settings


# ── Sign in ───────────────────────────────────────────────

LOGIN_BODY = """
<div class="card">
  <p class="eyebrow">Area riservata</p>
  <h1>Revisione editoriale</h1>
  <p class="lede">Inserisci il token di revisione per accedere alla coda dei numeri.</p>
  {% if error %}<div class="notice notice--danger">{{ error }}</div>{% endif %}
  <form method="POST" action="/review/login">
    <div class="field">
      <label for="token">Token di revisione</label>
      <input type="password" id="token" name="token" autocomplete="current-password"
             required autofocus>
    </div>
    <button class="btn" type="submit">Accedi</button>
  </form>
</div>"""


@router.get("/login", response_class=HTMLResponse)
async def login_form(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    if not settings.review_enabled:
        raise HTTPException(status_code=404, detail="Review interface disabled")
    body = render_fragment(LOGIN_BODY, error="")
    return HTMLResponse(render_page("Accesso revisione", body, width="narrow"))


@router.post("/login", response_model=None)
async def login(
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str, Form()],
) -> HTMLResponse | RedirectResponse:
    if not settings.review_enabled:
        raise HTTPException(status_code=404, detail="Review interface disabled")

    expected = settings.review_token.get_secret_value()
    if not hmac.compare_digest(token, expected):
        logger.warning("Failed review sign-in attempt")
        body = render_fragment(LOGIN_BODY, error="Token non valido.")
        return HTMLResponse(
            render_page("Accesso revisione", body, width="narrow"), status_code=401,
        )

    response = RedirectResponse("/review", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        issue_session(expected, settings.review_session_hours),
        httponly=True,
        samesite="strict",
        secure=settings.base_url.startswith("https"),
        max_age=settings.review_session_hours * 3600,
        path="/review",
    )
    return response


@router.post("/logout")
async def logout() -> RedirectResponse:
    response = RedirectResponse("/review/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/review")
    return response


# ── Queue ─────────────────────────────────────────────────

QUEUE_BODY = """
<div class="card">
  <p class="eyebrow">Coda di revisione</p>
  <h1>Numeri da approvare</h1>
  <p class="lede">
    La revisione umana è obbligatoria sui primi 3 item, sugli item con implicazione
    prescrittiva, su privacy e normativa e sugli avvisi di sicurezza dei dispositivi.
  </p>
  <form method="POST" action="/review/logout">
    <button class="btn btn--ghost btn--sm" type="submit">Esci</button>
  </form>
</div>

<div class="card card--flush">
  <ul class="rows">
    {% for issue in issues %}
    <li>
      <a class="row-link" href="/review/{{ issue.week }}">
        <div class="row-main">
          <div class="row-title">{{ issue.subject_line or issue.week }}</div>
          <div class="row-meta">
            Settimana {{ issue.week }} &middot; {{ issue.slot_count }} item &middot;
            {{ issue.pending }} da decidere &middot; {{ issue.reading_time }} min
          </div>
        </div>
        <span class="pill pill--{{ issue.tone }}">{{ issue.label }}</span>
      </a>
    </li>
    {% else %}
    <li><div class="empty">Nessun numero in attesa di revisione.</div></li>
    {% endfor %}
  </ul>
</div>"""


def _pending_count(newsletter: Newsletter, decided: dict[str, ReviewDecision]) -> int:
    return sum(
        1
        for slot in newsletter.slots
        if slot.editorial.review.needs_human_review and str(slot.item_id) not in decided
    )


@router.get("", response_class=HTMLResponse)
async def queue(
    request: Request,
    _settings: Annotated[Settings, Depends(require_reviewer)],
) -> HTMLResponse:
    factory = get_session_factory(request)
    rows = []
    async with factory() as session:
        repo = NewsletterRepository(session)
        decisions_repo = ReviewDecisionRepository(session)
        newsletters = [
            *await repo.list_by_status(IssueStatus.IN_REVIEW),
            *await repo.list_by_status(IssueStatus.APPROVED),
            *await repo.list_by_status(IssueStatus.DRAFT),
        ]
        for newsletter in newsletters:
            decided = await decisions_repo.latest_by_item(str(newsletter.issue_id))
            rows.append(
                {
                    "week": newsletter.week,
                    "subject_line": newsletter.subject_line,
                    "slot_count": len(newsletter.slots),
                    "pending": _pending_count(newsletter, decided),
                    "reading_time": newsletter.reading_time_minutes,
                    "tone": STATUS_TONE.get(newsletter.status, "neutral"),
                    "label": STATUS_LABEL.get(newsletter.status, newsletter.status.value),
                },
            )

    body = render_fragment(QUEUE_BODY, issues=rows)
    return HTMLResponse(render_page("Coda di revisione", body, section="Revisione"))


# ── Workbench ─────────────────────────────────────────────

WORKBENCH_BODY = """
<div class="card">
  <p class="eyebrow"><a href="/review">Coda</a> / Settimana {{ n.week }}</p>
  <h1>{{ n.subject_line or n.week }}</h1>
  <p class="lede">{{ n.preheader }}</p>
  <div class="btn-row" style="margin-bottom:18px">
    <span class="pill pill--{{ status_tone }}">{{ status_label }}</span>
    <span class="muted">{{ n.slots|length }} item &middot; {{ n.metrics.italy_count }} IT /
      {{ n.metrics.foreign_count }} estero &middot; lettura {{ n.reading_time_minutes }} min</span>
  </div>
  <div style="height:8px;background:var(--line);border-radius:99px;overflow:hidden">
    <div style="height:8px;width:{{ progress }}%;background:var(--success)"></div>
  </div>
  <p class="muted" style="margin-top:8px">
    {{ decided_required }} di {{ total_required }} item obbligatori decisi.
  </p>

  {% if n.tldr %}
  <h2>Che cosa merita attenzione questa settimana</h2>
  <ul>{% for line in n.tldr %}<li>{{ line }}</li>{% endfor %}</ul>
  {% endif %}
</div>

{% for item in items %}
<div class="card" id="item-{{ item.position }}">
  <div class="btn-row" style="justify-content:space-between;margin-bottom:10px">
    <div class="btn-row">
      <span class="pill pill--neutral">{{ item.position }}. {{ item.section_label }}</span>
      <span class="pill pill--{{ item.confidence_tone }}">Affidabilità {{ item.confidence }}</span>
      {% if item.needs_review %}
      <span class="pill pill--warn">Revisione: {{ item.review_reason }}</span>
      {% endif %}
    </div>
    {% if item.decision %}
    <span class="pill pill--{{ item.decision_tone }}">{{ item.decision_label }}</span>
    {% endif %}
  </div>

  {% if item.unsupported %}
  <div class="notice notice--danger">
    Claim non supportati dalle fonti:
    <ul style="margin:6px 0 0">{% for c in item.unsupported %}<li>{{ c }}</li>{% endfor %}</ul>
  </div>
  {% endif %}

  {% if item.note %}<p class="eyebrow" style="color:#008484">{{ item.note }}</p>{% endif %}
  <h3>{{ item.headline }}</h3>
  <p class="lede" style="margin-bottom:12px">{{ item.why }}</p>

  {% if item.actions %}
  <p class="eyebrow">Implicazione pratica</p>
  <ol>{% for a in item.actions %}<li>{{ a }}</li>{% endfor %}</ol>
  {% endif %}

  {% if item.summary %}<p>{{ item.summary }}</p>{% endif %}

  {% if item.sources %}
  <p class="eyebrow">Fonti</p>
  <ul>
    {% for s in item.sources %}
    <li><a href="{{ s.url }}" target="_blank" rel="noopener noreferrer">{{ s.label }}</a></li>
    {% endfor %}
  </ul>
  {% endif %}

  {% if editable %}
  <form method="POST" action="/review/{{ n.week }}/items/{{ item.item_id }}" class="btn-row"
        style="margin-top:16px">
    <input type="hidden" name="decision" value="approved">
    <button class="btn btn--sm" type="submit">Approva</button>
  </form>

  <details style="margin-top:12px">
    <summary class="muted" style="cursor:pointer">Modifica o rifiuta</summary>
    <form method="POST" action="/review/{{ n.week }}/items/{{ item.item_id }}"
          style="margin-top:14px">
      <div class="field">
        <label for="h-{{ item.position }}">Titolo (max 90 caratteri)</label>
        <input type="text" id="h-{{ item.position }}" name="headline"
               maxlength="90" value="{{ item.headline }}">
      </div>
      <div class="field">
        <label for="e-{{ item.position }}">Cosa emerge (apri con il dato, non con "Questo studio...")</label>
        <textarea id="e-{{ item.position }}" name="what_emerges"
                  style="min-height:60px">{{ item.emerges }}</textarea>
      </div>
      <div class="field">
        <label for="w-{{ item.position }}">Perché può contare per il PLS</label>
        <textarea id="w-{{ item.position }}" name="why_it_matters"
                  style="min-height:60px">{{ item.why }}</textarea>
      </div>
      <div class="field">
        <label for="a-{{ item.position }}">Implicazione pratica (vuoto se non esiste)</label>
        <textarea id="a-{{ item.position }}" name="what_to_do">{{ item.actions_text }}</textarea>
      </div>
      <div class="field">
        <label for="s-{{ item.position }}">Dettaglio clinico</label>
        <textarea id="s-{{ item.position }}" name="summary">{{ item.summary }}</textarea>
      </div>
      <div class="field">
        <label for="n-{{ item.position }}">Note di revisione</label>
        <input type="text" id="n-{{ item.position }}" name="notes"
               placeholder="Motivazione della modifica o del rifiuto">
      </div>
      <div class="btn-row">
        <button class="btn btn--sm" type="submit" name="decision" value="edited">
          Salva modifiche
        </button>
        <button class="btn btn--sm btn--danger" type="submit" name="decision" value="rejected">
          Rifiuta ed escludi
        </button>
      </div>
    </form>
  </details>
  {% endif %}
</div>
{% endfor %}

{% if editable %}
<div class="card">
  <h2 style="margin-top:0">Chiudi la revisione</h2>
  {% if blocking %}
  <div class="notice notice--warn">
    Mancano {{ blocking }} decisioni obbligatorie prima di poter approvare il numero.
  </div>
  {% else %}
  <div class="notice notice--ok">Tutti gli item obbligatori sono stati decisi.</div>
  {% endif %}
  <div class="btn-row">
    <form method="POST" action="/review/{{ n.week }}/approve">
      <button class="btn" type="submit" {% if blocking %}disabled{% endif %}>
        Approva il numero
      </button>
    </form>
    <form method="POST" action="/review/{{ n.week }}/send">
      <button class="btn btn--ghost" type="submit" {% if blocking %}disabled{% endif %}>
        Approva e invia ora
      </button>
    </form>
  </div>
</div>
{% endif %}"""

CONFIDENCE_TONE = {"high": "ok", "medium": "warn", "low": "danger"}


def _slot_view(slot: NewsletterSlot, decision: ReviewDecision | None) -> dict[str, object]:
    return {
        "position": slot.position,
        "item_id": str(slot.item_id),
        "section_label": SECTION_LABELS.get(slot.section.value, slot.section.value),
        "confidence": slot.editorial.confidence.value.upper(),
        "confidence_tone": CONFIDENCE_TONE.get(slot.editorial.confidence.value, "neutral"),
        "needs_review": slot.editorial.review.needs_human_review,
        "review_reason": slot.editorial.review.review_reason or "campionamento",
        "unsupported": slot.editorial.unsupported_claims,
        "note": slot.editorial.source_note,
        "headline": slot.editorial.headline_operational,
        "emerges": slot.editorial.what_emerges,
        "why": slot.editorial.why_it_matters,
        "actions": slot.editorial.what_to_do,
        "actions_text": "\n".join(slot.editorial.what_to_do),
        "summary": slot.editorial.summary,
        "sources": slot.source_links,
        "decision": decision.status if decision else "",
        "decision_label": DECISION_LABEL.get(decision.status, "") if decision else "",
        "decision_tone": {
            "approved": "ok", "rejected": "danger", "edited": "neutral",
        }.get(decision.status, "neutral") if decision else "neutral",
    }


async def _load(request: Request, week: str) -> tuple[Newsletter, dict[str, ReviewDecision]]:
    factory = get_session_factory(request)
    async with factory() as session:
        newsletter = await NewsletterRepository(session).get_by_week(week)
        if newsletter is None:
            raise HTTPException(status_code=404, detail="Newsletter not found")
        decided = await ReviewDecisionRepository(session).latest_by_item(
            str(newsletter.issue_id),
        )
    return newsletter, decided


@router.get("/{week}", response_class=HTMLResponse)
async def workbench(
    request: Request,
    week: str,
    _settings: Annotated[Settings, Depends(require_reviewer)],
) -> HTMLResponse:
    newsletter, decided = await _load(request, week)

    required = [s for s in newsletter.slots if s.editorial.review.needs_human_review]
    blocking = _pending_count(newsletter, decided)
    total_required = len(required)
    progress = 100 if not total_required else round(
        (total_required - blocking) / total_required * 100,
    )

    body = render_fragment(
        WORKBENCH_BODY,
        n=newsletter,
        items=[
            _slot_view(slot, decided.get(str(slot.item_id))) for slot in newsletter.slots
        ],
        status_tone=STATUS_TONE.get(newsletter.status, "neutral"),
        status_label=STATUS_LABEL.get(newsletter.status, newsletter.status.value),
        blocking=blocking,
        total_required=total_required,
        decided_required=total_required - blocking,
        progress=progress,
        editable=newsletter.status
        in {IssueStatus.DRAFT, IssueStatus.IN_REVIEW, IssueStatus.APPROVED},
    )
    return HTMLResponse(
        render_page(f"Revisione {week}", body, section="Revisione", width="wide"),
    )


@router.post("/{week}/items/{item_id}")
async def decide_item(
    request: Request,
    week: str,
    item_id: str,
    settings: Annotated[Settings, Depends(require_reviewer)],
    decision: Annotated[str, Form()],
    headline: Annotated[str, Form()] = "",
    why_it_matters: Annotated[str, Form()] = "",
    what_emerges: Annotated[str, Form()] = "",
    what_to_do: Annotated[str, Form()] = "",
    summary: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
) -> RedirectResponse:
    """Record an approve / reject / edit decision for a single item."""
    if decision not in VALID_DECISIONS:
        raise HTTPException(status_code=400, detail="Invalid decision")

    factory = get_session_factory(request)
    async with factory() as session:
        repo = NewsletterRepository(session)
        newsletter = await repo.get_by_week(week)
        if newsletter is None:
            raise HTTPException(status_code=404, detail="Newsletter not found")

        slot = next((s for s in newsletter.slots if str(s.item_id) == item_id), None)
        if slot is None:
            raise HTTPException(status_code=404, detail="Item not found")

        edits: dict[str, str] = {}
        if decision == "edited":
            if headline.strip() and headline.strip() != slot.editorial.headline_operational:
                edits["headline_operational"] = headline.strip()
                slot.editorial.headline_operational = headline.strip()
            if why_it_matters.strip() and why_it_matters.strip() != slot.editorial.why_it_matters:
                edits["why_it_matters"] = why_it_matters.strip()
                slot.editorial.why_it_matters = why_it_matters.strip()
            if what_emerges.strip() and what_emerges.strip() != slot.editorial.what_emerges:
                edits["what_emerges"] = what_emerges.strip()
                slot.editorial.what_emerges = what_emerges.strip()
            actions = [line.strip() for line in what_to_do.splitlines() if line.strip()]
            if actions and actions != slot.editorial.what_to_do:
                edits["what_to_do"] = "\n".join(actions)
                slot.editorial.what_to_do = actions
            if summary.strip() and summary.strip() != slot.editorial.summary:
                edits["summary"] = summary.strip()
                slot.editorial.summary = summary.strip()

        if decision == "rejected":
            newsletter.slots = [s for s in newsletter.slots if str(s.item_id) != item_id]
            for position, remaining in enumerate(newsletter.slots, start=1):
                remaining.position = position
        else:
            slot.editorial.review.review_status = "approved"

        await repo.update_slots(str(newsletter.issue_id), newsletter.slots)
        await ReviewDecisionRepository(session).save(
            ReviewDecision(
                item_id=UUID(item_id),
                issue_id=newsletter.issue_id,
                reviewer_role=slot.editorial.review.reviewer_role
                or ReviewerRole.MEDICAL_EDITOR.value,
                status=decision,
                edits=edits or None,
                notes=notes.strip() or None,
            ),
        )
        await _rerender(repo, newsletter, settings)
        await session.commit()

    logger.info("Review decision %s on item %s (issue %s)", decision, item_id, week)
    return RedirectResponse(f"/review/{week}", status_code=303)


async def _rerender(
    repo: NewsletterRepository,
    newsletter: Newsletter,
    settings: Settings,
) -> None:
    """Re-render the issue so edits are reflected in what actually ships."""
    html = render_html(
        newsletter,
        settings.newsletter_title,
        unsubscribe_url=f"{settings.base_url.rstrip('/')}/unsubscribe/preview",
        preferences_url=settings.preferences_url,
        archive_url=settings.archive_url,
        cta_url=settings.cta_url,
        logo_url=settings.logo_url,
    )
    text = render_plain_text(
        newsletter,
        settings.newsletter_title,
        preferences_url=settings.preferences_url,
        cta_url=settings.cta_url,
    )
    await repo.update_rendered(str(newsletter.issue_id), html, text)


async def _guard_complete(request: Request, week: str) -> Newsletter:
    newsletter, decided = await _load(request, week)
    if _pending_count(newsletter, decided):
        raise HTTPException(status_code=409, detail="Items still awaiting review")
    if not newsletter.slots:
        raise HTTPException(status_code=409, detail="Every item was rejected")
    return newsletter


@router.post("/{week}/approve", response_class=HTMLResponse)
async def approve_issue(
    request: Request,
    week: str,
    _settings: Annotated[Settings, Depends(require_reviewer)],
) -> HTMLResponse:
    newsletter = await _guard_complete(request, week)

    factory = get_session_factory(request)
    async with factory() as session:
        await NewsletterRepository(session).mark_approved(
            str(newsletter.issue_id), ReviewerRole.MEDICAL_EDITOR.value,
        )
        await session.commit()

    logger.info("Issue %s approved", week)
    return HTMLResponse(
        message_page(
            "Numero approvato",
            "Numero approvato",
            "Il numero è pronto. Verrà inviato al prossimo run di consegna, "
            "oppure puoi inviarlo subito dalla pagina di revisione.",
            action_url=f"/review/{week}",
            action_label="Torna al numero",
        ),
    )


@router.post("/{week}/send", response_class=HTMLResponse)
async def approve_and_send(
    request: Request,
    week: str,
    settings: Annotated[Settings, Depends(require_reviewer)],
) -> HTMLResponse:
    """Approve and deliver immediately."""
    from oykos.pipeline.weekly import deliver_and_finalize  # noqa: PLC0415 (import cycle)

    newsletter = await _guard_complete(request, week)

    factory = get_session_factory(request)
    async with factory() as session:
        repo = NewsletterRepository(session)
        await repo.mark_approved(str(newsletter.issue_id), ReviewerRole.MEDICAL_EDITOR.value)
        delivered = await deliver_and_finalize(newsletter, settings, session)
        await session.commit()

    if not delivered:
        return HTMLResponse(
            message_page(
                "Invio non riuscito",
                "Invio non riuscito",
                "Il numero resta approvato ma la consegna non è andata a buon fine. "
                "Controlla i log e la configurazione SMTP.",
                tone="danger",
                action_url=f"/review/{week}",
                action_label="Torna al numero",
            ),
            status_code=502,
        )

    logger.info("Issue %s approved and sent", week)
    return HTMLResponse(
        message_page(
            "Numero inviato",
            "Numero inviato",
            "La newsletter è stata consegnata agli iscritti confermati.",
            action_url="/review",
            action_label="Torna alla coda",
        ),
    )
