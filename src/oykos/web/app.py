"""Subscriber management API - subscribe, confirm, unsubscribe, feedback, archive."""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr

from oykos.config import Settings
from oykos.db.subscribers import FeedbackRepository, SubscriberRepository
from oykos.db.tables import Base, NewsletterRow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)

app = FastAPI(title="Oykos Newsletter", version="1.0.0")

_session_factory: async_sessionmaker[AsyncSession] | None = None


@app.on_event("startup")
async def _startup() -> None:
    global _session_factory
    settings = Settings()  # type: ignore[call-arg]
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _session_factory = async_sessionmaker(engine, expire_on_commit=False)


def _get_session() -> AsyncSession:
    if _session_factory is None:
        raise RuntimeError("App not started")
    return _session_factory()


# ── Health ────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "oykos-newsletter"}


# ── Subscribe (double opt-in) ────────────────────────────

class SubscribeRequest(BaseModel):
    email: EmailStr
    name: str = ""
    referral_code: str = ""


@app.post("/api/subscribe")
async def subscribe(req: SubscribeRequest) -> dict[str, str]:
    """Step 1: Register email, send confirmation link."""
    async with _get_session() as session:
        repo = SubscriberRepository(session)
        existing = await repo.get_by_email(req.email)
        if existing and existing.status == "active":
            return {"status": "already_subscribed"}
        if existing and existing.status == "pending_confirmation":
            return {"status": "confirmation_pending", "message": "Check your email for the confirmation link."}

        referred_by = None
        if req.referral_code:
            referrer = await repo.get_by_referral_code(req.referral_code)
            if referrer:
                referred_by = referrer.subscriber_id

        row = await repo.create(email=req.email, name=req.name, referred_by=referred_by)
        await session.commit()

        settings = Settings()  # type: ignore[call-arg]
        confirm_url = f"{settings.base_url}/confirm/{row.confirm_token}"
        logger.info("Subscription request: %s - confirm URL: %s", req.email, confirm_url)

        # TODO: Send confirmation email with confirm_url
        # For now, log it - the email sending is wired in production

        return {
            "status": "confirmation_sent",
            "message": "Check your email to confirm your subscription.",
            "confirm_url": confirm_url,  # Remove in production
        }


@app.get("/confirm/{token}")
async def confirm_subscription(token: str) -> HTMLResponse:
    """Step 2: User clicks confirmation link (double opt-in complete)."""
    async with _get_session() as session:
        repo = SubscriberRepository(session)
        row = await repo.confirm(token)
        await session.commit()
        if row is None:
            return HTMLResponse(
                "<h1>Link non valido o gia confermato</h1>"
                "<p>Questo link di conferma non e valido o e gia stato utilizzato.</p>",
                status_code=400,
            )
        return HTMLResponse(
            "<h1>Iscrizione confermata!</h1>"
            "<p>Benvenuto/a nella newsletter <em>L'Essenziale in Pediatria</em>.</p>"
            "<p>Riceverai la prossima edizione nella tua casella email.</p>"
        )


# ── Unsubscribe (one-click, RFC 8058) ────────────────────

@app.get("/unsubscribe/{token}")
async def unsubscribe_page(token: str) -> HTMLResponse:
    """Show unsubscribe confirmation page."""
    return HTMLResponse(
        f'<h1>Annulla iscrizione</h1>'
        f'<p>Sei sicuro/a di voler annullare l\'iscrizione?</p>'
        f'<form method="POST" action="/unsubscribe/{token}">'
        f'<button type="submit" style="padding:10px 24px;font-size:16px;'
        f'background:#c0392b;color:#fff;border:none;border-radius:6px;cursor:pointer;">'
        f'Conferma annullamento</button></form>'
    )


@app.post("/unsubscribe/{token}")
async def unsubscribe(token: str) -> HTMLResponse:
    """Process unsubscribe (works with RFC 8058 one-click POST and browser form)."""
    async with _get_session() as session:
        repo = SubscriberRepository(session)
        row = await repo.unsubscribe(token)
        await session.commit()
        if row is None:
            return HTMLResponse(
                "<h1>Link non valido</h1><p>L'iscrizione e gia stata annullata.</p>",
                status_code=400,
            )
        return HTMLResponse(
            "<h1>Iscrizione annullata</h1>"
            "<p>Non riceverai piu la newsletter. Ci dispiace vederti andare via.</p>"
        )


# ── GDPR Right to Erasure ────────────────────────────────

class EraseRequest(BaseModel):
    email: EmailStr


@app.post("/api/erase")
async def erase_data(req: EraseRequest) -> dict[str, str]:
    """GDPR Article 17 - right to erasure."""
    async with _get_session() as session:
        repo = SubscriberRepository(session)
        deleted = await repo.delete_subscriber_data(req.email)
        await session.commit()
        if not deleted:
            raise HTTPException(status_code=404, detail="Email not found")
        return {"status": "erased", "email": req.email}


# ── Feedback micro-survey ─────────────────────────────────

class FeedbackRequest(BaseModel):
    issue_id: str
    rating: int  # 1-5
    comment: str = ""


@app.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest) -> dict[str, str]:
    if not 1 <= req.rating <= 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")
    async with _get_session() as session:
        repo = FeedbackRepository(session)
        await repo.save(issue_id=req.issue_id, rating=req.rating, comment=req.comment)
        await session.commit()
    return {"status": "received"}


@app.get("/feedback/{issue_id}")
async def feedback_page(issue_id: str) -> HTMLResponse:
    """One-click feedback page embedded in newsletter footer."""
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8"><title>Feedback</title>
<style>body{{font-family:sans-serif;max-width:500px;margin:40px auto;text-align:center}}
.stars{{font-size:40px;cursor:pointer}}.star{{color:#ddd;transition:color .2s}}
.star:hover,.star.active{{color:#f1c40f}}
button{{padding:10px 32px;font-size:16px;background:#1a5276;color:#fff;border:none;border-radius:6px;cursor:pointer;margin-top:16px}}
textarea{{width:100%;padding:8px;margin-top:12px;border:1px solid #ddd;border-radius:6px;font-size:14px}}</style></head>
<body><h2>Come valuti questa edizione?</h2>
<div class="stars" id="stars">
  <span class="star" data-v="1">&#9733;</span>
  <span class="star" data-v="2">&#9733;</span>
  <span class="star" data-v="3">&#9733;</span>
  <span class="star" data-v="4">&#9733;</span>
  <span class="star" data-v="5">&#9733;</span>
</div>
<textarea id="comment" rows="3" placeholder="Commento (opzionale)"></textarea>
<br><button onclick="send()">Invia</button>
<p id="msg"></p>
<script>
let rating=0;
document.querySelectorAll('.star').forEach(s=>{{
  s.onclick=()=>{{rating=+s.dataset.v;
    document.querySelectorAll('.star').forEach(x=>x.classList.toggle('active',+x.dataset.v<=rating))}}}});
async function send(){{
  if(!rating){{document.getElementById('msg').textContent='Seleziona una valutazione';return}}
  const r=await fetch('/api/feedback',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{issue_id:'{issue_id}',rating,comment:document.getElementById('comment').value}})}});
  document.getElementById('msg').textContent=r.ok?'Grazie per il feedback!':'Errore, riprova.'}}
</script></body></html>""")


# ── Public Archive ────────────────────────────────────────

@app.get("/archive")
async def archive_list() -> HTMLResponse:
    """Public page listing all sent newsletters."""
    async with _get_session() as session:
        stmt = (
            select(NewsletterRow)
            .where(NewsletterRow.status == "sent")
            .order_by(NewsletterRow.created_at.desc())
            .limit(52)
        )
        result = await session.execute(stmt)
        newsletters = result.scalars().all()

    items_html = ""
    for nl in newsletters:
        date_str = nl.created_at.strftime("%d %B %Y") if nl.created_at else ""
        items_html += (
            f'<li style="padding:8px 0;border-bottom:1px solid #eee">'
            f'<a href="/archive/{nl.week}" style="color:#1a5276;text-decoration:none;font-weight:600">'
            f'{nl.subject_line or nl.week}</a>'
            f'<span style="color:#888;margin-left:12px;font-size:13px">{date_str}</span></li>'
        )

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8"><title>Archivio Newsletter</title>
<style>body{{font-family:sans-serif;max-width:700px;margin:40px auto;padding:0 20px}}
h1{{color:#1a5276}}ul{{list-style:none;padding:0}}</style></head>
<body><h1>Archivio - L'Essenziale in Pediatria</h1>
<p style="color:#666">Tutte le edizioni passate della newsletter.</p>
<ul>{items_html or '<li>Nessuna newsletter pubblicata ancora.</li>'}</ul>
</body></html>""")


@app.get("/archive/{week}")
async def archive_issue(week: str) -> HTMLResponse:
    """Serve a past newsletter as a public web page."""
    async with _get_session() as session:
        stmt = select(NewsletterRow).where(NewsletterRow.week == week, NewsletterRow.status == "sent")
        result = await session.execute(stmt)
        nl = result.scalar_one_or_none()
    if nl is None:
        raise HTTPException(status_code=404, detail="Newsletter not found")
    return HTMLResponse(nl.html_content)


# ── Referral ──────────────────────────────────────────────

@app.get("/refer/{referral_code}")
async def referral_landing(referral_code: str) -> HTMLResponse:
    """Landing page for referred visitors."""
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8"><title>Iscriviti alla Newsletter</title>
<style>body{{font-family:sans-serif;max-width:500px;margin:40px auto;text-align:center}}
input{{padding:10px;font-size:16px;border:1px solid #ddd;border-radius:6px;width:80%;margin:8px 0}}
button{{padding:10px 32px;font-size:16px;background:#1a5276;color:#fff;border:none;border-radius:6px;cursor:pointer}}</style></head>
<body><h1>L'Essenziale in Pediatria</h1>
<p>Un collega ti ha invitato a iscriverti alla newsletter settimanale per Pediatri di Libera Scelta.</p>
<input type="email" id="email" placeholder="La tua email">
<input type="text" id="name" placeholder="Nome (opzionale)">
<br><button onclick="sub()">Iscriviti</button><p id="msg"></p>
<script>async function sub(){{
  const r=await fetch('/api/subscribe',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{email:document.getElementById('email').value,
      name:document.getElementById('name').value,referral_code:'{referral_code}'}})}});
  const d=await r.json();document.getElementById('msg').textContent=d.message||d.status}}</script>
</body></html>""")
