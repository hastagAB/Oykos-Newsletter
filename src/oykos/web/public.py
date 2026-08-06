"""Public subscriber surface: subscribe, confirm, preferences, unsubscribe,
feedback, archive.

Everything a reader touches lives here. All pages share the layout in
:mod:`oykos.web.design`, so the web surface matches the newsletter itself.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from oykos.config import Settings
from oykos.db.subscribers import FeedbackRepository, SubscriberRepository
from oykos.db.tables import NewsletterRow, SubscriberRow
from oykos.delivery.email_sender import send_newsletter
from oykos.models.taxonomy import TaxonomyTag
from oykos.web.design import message_page, render_fragment, render_page

logger = logging.getLogger(__name__)

router = APIRouter(tags=["public"])

MIN_RATING = 1
MAX_RATING = 5
ARCHIVE_LIMIT = 52

CONFIRMATION_SUBJECT = "Conferma la tua iscrizione a L'Essenziale in Pediatria"

# Reader-facing topic groups, mapped onto the internal taxonomy.
TOPIC_GROUPS: dict[str, tuple[str, tuple[TaxonomyTag, ...]]] = {
    "clinica": (
        "Clinica del territorio",
        (
            TaxonomyTag.RESPIRATORY,
            TaxonomyTag.GASTROENTERITIS,
            TaxonomyTag.DERMATOLOGY,
            TaxonomyTag.ALLERGOLOGY,
            TaxonomyTag.NEURO_DEVELOPMENT,
            TaxonomyTag.EMERGENCIES_TRIAGE,
        ),
    ),
    "prevenzione": (
        "Prevenzione e sorveglianza",
        (TaxonomyTag.VACCINATIONS, TaxonomyTag.SURVEILLANCE, TaxonomyTag.ANTIBIOTIC_RESISTANCE),
    ),
    "farmaci": (
        "Farmaci e sicurezza",
        (TaxonomyTag.DRUG_SAFETY, TaxonomyTag.DRUG_AUTHORIZATION, TaxonomyTag.DRUG_SHORTAGE),
    ),
    "studio": (
        "Studio e normativa",
        (TaxonomyTag.ACN_AGREEMENTS, TaxonomyTag.PRIVACY, TaxonomyTag.TELEMEDICINE),
    ),
    "diagnostica": (
        "Diagnostica, POCT e dispositivi",
        (
            TaxonomyTag.RAPID_TESTS,
            TaxonomyTag.POCT_LAB,
            TaxonomyTag.FUNCTIONAL_DIAGNOSTICS,
            TaxonomyTag.SCREENING,
            TaxonomyTag.DEVICE_SAFETY,
        ),
    ),
    "formazione": (
        "Formazione ECM ed eventi",
        (TaxonomyTag.CME_TRAINING, TaxonomyTag.CONGRESSES),
    ),
}


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


# ── Health ────────────────────────────────────────────────

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "oykos-newsletter"}


# ── Landing / subscribe ───────────────────────────────────

SENT_ONLY = ("sent",)
INCLUDING_UNSENT = ("sent", "approved", "in_review")


def _visible_statuses(settings: Settings) -> tuple[str, ...]:
    return INCLUDING_UNSENT if settings.public_show_unsent else SENT_ONLY


async def _latest_issue(session: AsyncSession, settings: Settings) -> NewsletterRow | None:
    """Most recent issue the public is allowed to see."""
    result = await session.execute(
        select(NewsletterRow)
        .where(NewsletterRow.status.in_(_visible_statuses(settings)))
        .order_by(NewsletterRow.created_at.desc())
        .limit(1),
    )
    return result.scalars().first()


LANDING_BODY = """
<div class="card">
  <p class="eyebrow">Briefing operativo settimanale</p>
  <h1>{{ brand }}</h1>
  <p class="lede">
    Per Pediatri di Libera Scelta. Ogni settimana solo ciò che è stato pubblicato in
    quella settimana: cosa cambia, perché conta nella pratica, cosa fare ora.
    Abbiamo già letto e verificato le fonti. Lettura 3-5 minuti.
  </p>
  <form method="POST" action="/subscribe">
    <div class="field">
      <label for="email">Email professionale</label>
      <input type="email" id="email" name="email" required autocomplete="email"
             placeholder="nome@esempio.it">
    </div>
    <div class="field">
      <label for="name">Nome (facoltativo)</label>
      <input type="text" id="name" name="name" autocomplete="name">
    </div>
    <button class="btn" type="submit">Iscriviti</button>
    <p class="hint">
      Doppio opt-in: riceverai una email di conferma. Puoi annullare l'iscrizione in
      qualsiasi momento con un clic. <a href="/archive">Guarda l'archivio</a>.
    </p>
  </form>
</div>

{% if issue %}
<div class="card">
  {% if issue.draft %}
  <div class="notice notice--warn">
    <strong>Anteprima di lavorazione</strong>
    Questo numero non è ancora stato approvato dalla redazione e non è stato inviato.
    I contenuti possono cambiare.
  </div>
  {% endif %}
  <p class="eyebrow">{% if issue.draft %}Numero in preparazione{% else %}Ultimo numero{% endif %}</p>
  <h2 style="margin:4px 0 6px">{{ issue.subject_line or issue.week }}</h2>
  <p class="muted" style="margin:0 0 14px">
    Settimana {{ issue.week }}{% if issue.date %} &middot; {{ issue.date }}{% endif %}
  </p>
  <iframe src="/latest/raw" title="Anteprima del numero" loading="lazy"
          style="width:100%;height:900px;border:1px solid #D6E8EC;background:#EDEEF1;"></iframe>
  <p class="hint" style="margin-top:12px">
    <a href="/archive">Tutti i numeri</a>
  </p>
</div>
{% endif %}"""


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    settings = get_settings(request)
    factory = get_session_factory(request)
    async with factory() as session:
        row = await _latest_issue(session, settings)
        issue = (
            {
                "week": row.week,
                "subject_line": row.subject_line,
                "draft": row.status != "sent",
                "date": row.created_at.strftime("%d/%m/%Y") if row.created_at else "",
            }
            if row is not None
            else None
        )

    body = render_fragment(LANDING_BODY, brand=settings.newsletter_title, issue=issue)
    # An unapproved issue must never reach a search index.
    robots = "noindex" if issue and issue["draft"] else "index"
    return HTMLResponse(render_page("Iscriviti", body, robots=robots))


@router.get("/latest/raw", response_class=HTMLResponse)
async def latest_raw(request: Request) -> HTMLResponse:
    """The rendered issue itself, for the iframe on the landing page."""
    settings = get_settings(request)
    factory = get_session_factory(request)
    async with factory() as session:
        row = await _latest_issue(session, settings)

    if row is None:
        raise HTTPException(status_code=404, detail="No issue available")
    return HTMLResponse(row.html_content, headers={"X-Robots-Tag": "noindex"})


def _confirmation_body(confirm_url: str) -> tuple[str, str]:
    html = (
        "<p>Grazie per esserti iscritto a <em>L'Essenziale in Pediatria</em>.</p>"
        f'<p><a href="{confirm_url}">Conferma la tua iscrizione</a></p>'
        "<p>Se non hai richiesto questa iscrizione, ignora questa email.</p>"
    )
    text = (
        "Grazie per esserti iscritto a L'Essenziale in Pediatria.\n\n"
        f"Conferma la tua iscrizione: {confirm_url}\n\n"
        "Se non hai richiesto questa iscrizione, ignora questa email."
    )
    return html, text


class SubscribeRequest(BaseModel):
    email: EmailStr
    name: str = ""


GENERIC_SUBSCRIBE_RESULT = {
    "status": "confirmation_sent",
    "message": "Controlla la tua email per confermare l'iscrizione.",
}


async def _register(request: Request, req: SubscribeRequest) -> None:
    """Create the subscriber if new, then email the confirmation link.

    The token is never returned to the caller: it only reaches the inbox of the
    address being subscribed, so nobody can confirm an address they do not own.
    """
    settings = get_settings(request)
    factory = get_session_factory(request)

    async with factory() as session:
        repo = SubscriberRepository(session)
        existing = await repo.get_by_email(req.email)
        if existing is not None and existing.status in {"active", "pending_confirmation"}:
            return

        row = await repo.create(email=req.email, name=req.name)
        await session.commit()
        confirm_token = row.confirm_token

    confirm_url = f"{settings.base_url.rstrip('/')}/confirm/{confirm_token}"
    html, text = _confirmation_body(confirm_url)
    if not await send_newsletter(
        settings=settings,
        to_emails=[req.email],
        subject=CONFIRMATION_SUBJECT,
        html_content=html,
        text_content=text,
    ):
        logger.error("Confirmation email could not be delivered")


@router.post("/api/subscribe")
async def subscribe_api(request: Request, req: SubscribeRequest) -> dict[str, str]:
    await _register(request, req)
    return GENERIC_SUBSCRIBE_RESULT


@router.post("/subscribe", response_class=HTMLResponse)
async def subscribe_form(
    request: Request,
    email: Annotated[EmailStr, Form()],
    name: Annotated[str, Form()] = "",
) -> HTMLResponse:
    await _register(request, SubscribeRequest(email=email, name=name))
    return HTMLResponse(
        message_page(
            "Conferma richiesta",
            "Controlla la tua email",
            "Ti abbiamo inviato un link di conferma. L'iscrizione diventa attiva solo "
            "dopo che l'hai aperto.",
        ),
    )


@router.get("/confirm/{token}", response_class=HTMLResponse)
async def confirm_subscription(request: Request, token: str) -> HTMLResponse:
    settings = get_settings(request)
    factory = get_session_factory(request)
    async with factory() as session:
        row = await SubscriberRepository(session).confirm(token)
        await session.commit()

    if row is None:
        return HTMLResponse(
            message_page(
                "Link non valido",
                "Link non valido o già utilizzato",
                "Questo link di conferma non è valido oppure è già stato usato.",
                tone="danger",
                action_url="/",
                action_label="Torna all'iscrizione",
            ),
            status_code=400,
        )

    return HTMLResponse(
        message_page(
            "Iscrizione confermata",
            "Iscrizione confermata",
            "Riceverai la prossima edizione nella tua casella. Puoi scegliere gli "
            "argomenti che ti interessano dalla pagina preferenze.",
            action_url=settings.preferences_url_for(row.unsubscribe_token),
            action_label="Imposta le preferenze",
        ),
    )


# ── Preferences ───────────────────────────────────────────

PREFERENCES_BODY = """
<div class="card">
  <p class="eyebrow">Preferenze</p>
  <h1>Cosa vuoi ricevere</h1>
  <p class="lede">
    Il briefing resta settimanale. Qui scegli gli argomenti da mettere in evidenza e se
    ricevere gli alert urgenti.
  </p>
  {% if saved %}<div class="notice notice--ok">Preferenze salvate.</div>{% endif %}
  <form method="POST" action="/preferences/{{ token }}">
    <fieldset>
      <legend>Argomenti</legend>
      <div class="check-grid">
        {% for key, label in groups %}
        <label class="check">
          <input type="checkbox" name="topics" value="{{ key }}"
                 {% if key in selected %}checked{% endif %}>
          <span>{{ label }}</span>
        </label>
        {% endfor %}
      </div>
      <p class="hint">Nessuna selezione significa "tutti gli argomenti".</p>
    </fieldset>

    <fieldset>
      <legend>Alert urgenti</legend>
      <label class="check">
        <input type="checkbox" name="alert_opt_in" value="1" {% if alert_opt_in %}checked{% endif %}>
        <span>Ricevi gli alert per eventi critici (massimo 1-2 al mese)</span>
      </label>
      <p class="hint">
        Solo eventi "hard": sicurezza farmaci AIFA, avvisi FSN sui dispositivi,
        picchi epidemici e modifiche ACN ufficiali.
      </p>
    </fieldset>

    <div class="field">
      <label for="region">Regione (facoltativo)</label>
      <input type="text" id="region" name="region" value="{{ region }}"
             placeholder="Es. Lombardia">
      <p class="hint">Usata per dare priorità agli aggiornamenti regionali.</p>
    </div>

    <div class="btn-row">
      <button class="btn" type="submit">Salva preferenze</button>
      <a class="btn btn--ghost" href="/unsubscribe/{{ token }}">Annulla iscrizione</a>
    </div>
  </form>
</div>"""


def _render_preferences(token: str, row: SubscriberRow, *, saved: bool = False) -> str:
    body = render_fragment(
        PREFERENCES_BODY,
        token=token,
        groups=[(key, label) for key, (label, _) in TOPIC_GROUPS.items()],
        selected=set(row.topics or []),
        alert_opt_in=row.alert_opt_in,
        region=row.region or "",
        saved=saved,
    )
    return render_page("Preferenze", body, width="narrow")


@router.get("/preferences/{token}", response_class=HTMLResponse)
async def preferences_page(request: Request, token: str) -> HTMLResponse:
    factory = get_session_factory(request)
    async with factory() as session:
        row = await SubscriberRepository(session).get_by_unsubscribe_token(token)

    if row is None:
        raise HTTPException(status_code=404, detail="Unknown preferences link")
    return HTMLResponse(_render_preferences(token, row))


@router.post("/preferences/{token}", response_class=HTMLResponse)
async def save_preferences(
    request: Request,
    token: str,
    topics: Annotated[list[str] | None, Form()] = None,
    alert_opt_in: Annotated[str, Form()] = "",
    region: Annotated[str, Form()] = "",
) -> HTMLResponse:
    valid = [t for t in (topics or []) if t in TOPIC_GROUPS]
    factory = get_session_factory(request)
    async with factory() as session:
        row = await SubscriberRepository(session).update_preferences(
            token=token,
            topics=valid,
            alert_opt_in=bool(alert_opt_in),
            region=region.strip()[:40],
        )
        await session.commit()

    if row is None:
        raise HTTPException(status_code=404, detail="Unknown preferences link")
    return HTMLResponse(_render_preferences(token, row, saved=True))


@router.get("/preferences", response_class=HTMLResponse)
async def preferences_help() -> HTMLResponse:
    """Landing for the generic footer link, which carries no token."""
    return HTMLResponse(
        message_page(
            "Preferenze",
            "Apri il link personale",
            "Il link alle preferenze è personale e si trova in fondo a ogni numero "
            "della newsletter. Aprilo da lì per gestire argomenti e alert.",
            tone="warn",
            action_url="/archive",
            action_label="Vai all'archivio",
        ),
    )


# ── Unsubscribe (RFC 8058 one-click) ──────────────────────

UNSUBSCRIBE_BODY = """
<div class="card">
  <h1>Annulla iscrizione</h1>
  <p class="lede">
    Non riceverai più il briefing settimanale. Se ti interessa solo ridurre il volume,
    puoi invece disattivare gli alert dalle preferenze.
  </p>
  <div class="btn-row">
    <form method="POST" action="/unsubscribe/{{ token }}">
      <button class="btn btn--danger" type="submit">Conferma annullamento</button>
    </form>
    <a class="btn btn--ghost" href="/preferences/{{ token }}">Gestisci le preferenze</a>
  </div>
</div>"""


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe_page(token: str) -> HTMLResponse:
    body = render_fragment(UNSUBSCRIBE_BODY, token=token)
    return HTMLResponse(render_page("Annulla iscrizione", body, width="narrow"))


@router.post("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe(request: Request, token: str) -> HTMLResponse:
    factory = get_session_factory(request)
    async with factory() as session:
        row = await SubscriberRepository(session).unsubscribe(token)
        await session.commit()

    if row is None:
        return HTMLResponse(
            message_page(
                "Link non valido",
                "Iscrizione già annullata",
                "Questo link non è valido oppure l'iscrizione era già stata annullata.",
                tone="warn",
            ),
            status_code=400,
        )

    return HTMLResponse(
        message_page(
            "Iscrizione annullata",
            "Iscrizione annullata",
            "Non riceverai più la newsletter. Se cambi idea puoi iscriverti di nuovo "
            "in qualsiasi momento.",
            action_url="/",
            action_label="Iscriviti di nuovo",
        ),
    )


# ── Feedback ──────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    issue_id: str
    rating: int = Field(ge=MIN_RATING, le=MAX_RATING)
    comment: str = ""
    too_long: bool = False
    too_many_devices: bool = False
    not_relevant: bool = False


FEEDBACK_BODY = """
<div class="card">
  <p class="eyebrow">Micro-survey</p>
  <h1>Quanto ti è stata utile questa edizione?</h1>
  {% if saved %}
  <div class="notice notice--ok">Grazie, il feedback è stato registrato.</div>
  {% else %}
  <form method="POST" action="/feedback/{{ issue_id }}">
    <fieldset>
      <legend>Valutazione</legend>
      <div class="check-grid">
        {% for value, label in ratings %}
        <label class="check">
          <input type="radio" name="rating" value="{{ value }}" required>
          <span>{{ value }} - {{ label }}</span>
        </label>
        {% endfor %}
      </div>
    </fieldset>
    <fieldset>
      <legend>Cosa non ha funzionato (facoltativo)</legend>
      <div class="check-grid">
        <label class="check">
          <input type="checkbox" name="too_long" value="1"><span>Troppo lungo</span>
        </label>
        <label class="check">
          <input type="checkbox" name="too_many_devices" value="1">
          <span>Troppi dispositivi/test</span>
        </label>
        <label class="check">
          <input type="checkbox" name="not_relevant" value="1">
          <span>Poco rilevante per il mio studio</span>
        </label>
      </div>
    </fieldset>
    <div class="field">
      <label for="comment">Commento (facoltativo)</label>
      <textarea id="comment" name="comment"></textarea>
    </div>
    <button class="btn" type="submit">Invia feedback</button>
  </form>
  {% endif %}
</div>"""

RATING_LABELS = [
    (1, "Per niente utile"),
    (2, "Poco utile"),
    (3, "Nella media"),
    (4, "Utile"),
    (5, "Molto utile"),
]


@router.get("/feedback/{issue_id}", response_class=HTMLResponse)
async def feedback_page(issue_id: str) -> HTMLResponse:
    body = render_fragment(
        FEEDBACK_BODY, issue_id=issue_id, ratings=RATING_LABELS, saved=False,
    )
    return HTMLResponse(render_page("Feedback", body, width="narrow"))


async def _store_feedback(request: Request, req: FeedbackRequest) -> None:
    factory = get_session_factory(request)
    async with factory() as session:
        await FeedbackRepository(session).save(
            issue_id=req.issue_id,
            rating=req.rating,
            comment=req.comment,
            too_long=req.too_long,
            too_many_devices=req.too_many_devices,
            not_relevant=req.not_relevant,
        )
        await session.commit()


@router.post("/api/feedback")
async def submit_feedback_api(request: Request, req: FeedbackRequest) -> dict[str, str]:
    await _store_feedback(request, req)
    return {"status": "received"}


@router.post("/feedback/{issue_id}", response_class=HTMLResponse)
async def submit_feedback_form(
    request: Request,
    issue_id: str,
    rating: Annotated[int, Form()],
    comment: Annotated[str, Form()] = "",
    too_long: Annotated[str, Form()] = "",
    too_many_devices: Annotated[str, Form()] = "",
    not_relevant: Annotated[str, Form()] = "",
) -> HTMLResponse:
    if not MIN_RATING <= rating <= MAX_RATING:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")

    await _store_feedback(
        request,
        FeedbackRequest(
            issue_id=issue_id,
            rating=rating,
            comment=comment,
            too_long=bool(too_long),
            too_many_devices=bool(too_many_devices),
            not_relevant=bool(not_relevant),
        ),
    )
    body = render_fragment(
        FEEDBACK_BODY, issue_id=issue_id, ratings=RATING_LABELS, saved=True,
    )
    return HTMLResponse(render_page("Feedback", body, width="narrow"))


# ── GDPR erasure ──────────────────────────────────────────

class EraseRequest(BaseModel):
    email: EmailStr


@router.post("/api/erase")
async def erase_data(request: Request, req: EraseRequest) -> dict[str, str]:
    """GDPR Article 17 - right to erasure."""
    factory = get_session_factory(request)
    async with factory() as session:
        deleted = await SubscriberRepository(session).delete_subscriber_data(req.email)
        await session.commit()

    if not deleted:
        raise HTTPException(status_code=404, detail="Email not found")
    return {"status": "erased", "email": req.email}


# ── Archive ───────────────────────────────────────────────

ARCHIVE_BODY = """
<div class="card card--flush">
  <ul class="rows">
    {% for issue in issues %}
    <li>
      <a class="row-link" href="/archive/{{ issue.week }}">
        <div class="row-main">
          <div class="row-title">{{ issue.subject_line or issue.week }}</div>
          <div class="row-meta">{{ issue.date }} &middot; settimana {{ issue.week }}</div>
        </div>
        <span class="muted">Leggi &rarr;</span>
      </a>
    </li>
    {% else %}
    <li><div class="empty">Nessuna edizione pubblicata finora.</div></li>
    {% endfor %}
  </ul>
</div>"""


@router.get("/archive", response_class=HTMLResponse)
async def archive_list(request: Request) -> HTMLResponse:
    settings = get_settings(request)
    stmt = (
        select(NewsletterRow)
        .where(NewsletterRow.status.in_(_visible_statuses(settings)))
        .order_by(NewsletterRow.created_at.desc())
        .limit(ARCHIVE_LIMIT)
    )

    factory = get_session_factory(request)
    async with factory() as session:
        result = await session.execute(stmt)
        issues = [
            {
                "week": row.week,
                "subject_line": row.subject_line,
                "date": row.created_at.strftime("%d/%m/%Y") if row.created_at else "",
            }
            for row in result.scalars().all()
        ]

    body = render_fragment(ARCHIVE_BODY, issues=issues)
    return HTMLResponse(render_page("Archivio", body, robots="index"))


@router.get("/archive/{week}", response_class=HTMLResponse)
async def archive_issue(request: Request, week: str) -> HTMLResponse:
    settings = get_settings(request)
    factory = get_session_factory(request)
    async with factory() as session:
        result = await session.execute(
            select(NewsletterRow).where(
                NewsletterRow.week == week,
                NewsletterRow.status.in_(_visible_statuses(settings)),
            ),
        )
        row = result.scalars().first()

    if row is None:
        raise HTTPException(status_code=404, detail="Newsletter not found")
    headers = {"X-Robots-Tag": "noindex"} if row.status != "sent" else {}
    return HTMLResponse(row.html_content, headers=headers)


@router.get("/unsubscribe/preview", response_class=HTMLResponse)
async def unsubscribe_preview() -> RedirectResponse:
    """Placeholder link used when rendering an issue for review."""
    return RedirectResponse("/preferences", status_code=307)
