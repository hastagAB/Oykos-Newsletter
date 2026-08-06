"""Render a sample issue to HTML so the template can be reviewed without an LLM.

The copy here is fixed sample text, not generated content. This is for checking
layout, sections, the closing CTA and the footer - not for judging editorial
quality. Run it with:

    python scripts/preview_newsletter.py

It writes ``preview.html`` and opens it in the default browser.
"""
from __future__ import annotations

import webbrowser
from datetime import UTC, datetime
from pathlib import Path

from oykos.models.news_item import (
    Citation,
    Classification,
    ContentBlock,
    EditorialBlock,
    KeyPassage,
    NewsItem,
    ScoringBlock,
    SourceRef,
    Subscores,
)
from oykos.models.taxonomy import Confidence, DocumentType, Geo, TaxonomyTag
from oykos.newsletter.composer import compose_newsletter
from oykos.newsletter.template import render_html, render_plain_text

WEEK = "2026-W32"
# Only items published in the issue week ship, so the samples carry that date.
PUBLISHED = datetime.fromisocalendar(2026, 32, 3).replace(tzinfo=UTC)
OUTPUT = Path("preview.html")

# What kind of source each item is, and what it does not let us conclude.
SOURCE_NOTES: dict[TaxonomyTag, str] = {
    TaxonomyTag.DRUG_SAFETY: "Fonte primaria. Comunicazione istituzionale AIFA.",
    TaxonomyTag.VACCINATIONS: "Fonte primaria. Circolare ministeriale.",
    TaxonomyTag.RESPIRATORY: "Società scientifica. Raccomandazione nazionale.",
    TaxonomyTag.ACN_AGREEMENTS: "Fonte istituzionale. Testo integrale non accessibile.",
    TaxonomyTag.RAPID_TESTS: "Documento associativo. Raccomandazione di appropriatezza.",
    TaxonomyTag.DRUG_AUTHORIZATION: "Fonte primaria. Comunicazione EMA.",
    TaxonomyTag.SURVEILLANCE: "Fonte istituzionale. Bollettino di sorveglianza.",
    TaxonomyTag.PRIVACY: "Fonte primaria. Provvedimento del Garante.",
    TaxonomyTag.AI_DIGITAL_HEALTH: "Fonte secondaria. Studio prospettico, non linea guida.",
    TaxonomyTag.CME_TRAINING: "Fonte istituzionale. Segnalazione di evento formativo.",
}

# (title, source, geo, tag, headline, why it matters, actions, score)
SAMPLES: list[tuple[str, str, Geo, TaxonomyTag, str, str, list[str], float]] = [
    (
        "Ritiro lotti di amoxicillina sospensione orale",
        "AIFA", Geo.IT, TaxonomyTag.DRUG_SAFETY,
        "Verificare i lotti di amoxicillina in armadio",
        "Il ritiro riguarda tre lotti di uso pediatrico frequente. Le famiglie "
        "possono presentarsi in studio con la confezione richiamata.",
        ["Controllare i lotti in studio", "Informare le famiglie con terapia in corso"],
        95.0,
    ),
    (
        "Aggiornamento calendario vaccinale: richiamo esavalente",
        "Ministero della Salute", Geo.IT, TaxonomyTag.VACCINATIONS,
        "Cambia la finestra del richiamo esavalente",
        "La finestra si sposta di quattro settimane. Incide sulla programmazione "
        "degli appuntamenti già fissati per l'autunno.",
        ["Rivedere gli appuntamenti di settembre", "Aggiornare il promemoria ai genitori"],
        91.0,
    ),
    (
        "Nuove raccomandazioni sulla bronchiolite nel lattante",
        "SIP", Geo.IT, TaxonomyTag.RESPIRATORY,
        "La saturimetria domiciliare non è più raccomandata di routine",
        "La raccomandazione riduce gli invii impropri al pronto soccorso e "
        "cambia il messaggio da dare ai genitori in fase acuta.",
        ["Aggiornare il counselling ai genitori", "Rivedere i criteri di invio in PS"],
        88.0,
    ),
    (
        "Accordo collettivo nazionale: nuove indennità informatiche",
        "SISAC", Geo.IT, TaxonomyTag.ACN_AGREEMENTS,
        "Nuova indennità per il fascicolo sanitario elettronico",
        "Riguarda direttamente la remunerazione dei PLS convenzionati e "
        "richiede un adempimento entro fine trimestre.",
        ["Verificare i requisiti di adesione", "Contattare il proprio sindacato"],
        84.0,
    ),
    (
        "Test rapidi per streptococco: criteri di appropriatezza",
        "Choosing Wisely Italy", Geo.IT, TaxonomyTag.RAPID_TESTS,
        "Non eseguire il test rapido sotto i 3 anni",
        "L'uso non selettivo genera falsi positivi e terapie antibiotiche "
        "evitabili. Il documento definisce quando il test non va fatto.",
        ["Applicare lo score clinico prima del test", "Rivedere le scorte in studio"],
        80.0,
    ),
    (
        "EMA: nuova formulazione pediatrica autorizzata",
        "EMA", Geo.EU, TaxonomyTag.DRUG_AUTHORIZATION,
        "Disponibile una formulazione senza eccipienti a rischio",
        "Rilevante per i bambini con allergie note agli eccipienti. "
        "La disponibilità in Italia è attesa nei prossimi mesi.",
        ["Annotare l'alternativa per i pazienti allergici"],
        78.0,
    ),
    (
        "ECDC: aumento dei casi di pertosse in Europa",
        "ECDC", Geo.EU, TaxonomyTag.SURVEILLANCE,
        "Soglia di sospetto più bassa per la tosse persistente",
        "L'incremento europeo anticipa di norma quello italiano di alcune "
        "settimane. Utile alzare l'attenzione diagnostica ora.",
        ["Considerare la pertosse nella tosse oltre 2 settimane"],
        75.0,
    ),
    (
        "Garante privacy: uso di applicazioni di messaggistica con le famiglie",
        "Garante Privacy", Geo.IT, TaxonomyTag.PRIVACY,
        "Chiarite le condizioni per i gruppi WhatsApp con i genitori",
        "Molti studi usano gruppi di messaggistica senza base giuridica "
        "esplicita. Il provvedimento indica cosa serve per essere in regola.",
        [
            "Verificare l'informativa consegnata",
            "Separare i canali clinici da quelli organizzativi",
        ],
        72.0,
    ),
    (
        "npj Digital Medicine: triage assistito da IA in pediatria territoriale",
        "npj Digital Medicine", Geo.EU, TaxonomyTag.AI_DIGITAL_HEALTH,
        "Il triage assistito riduce il tempo per visita di circa 6 minuti",
        "Studio prospettico su 12 ambulatori. Il beneficio si concentra "
        "sulla raccolta anamnestica, non sulla decisione clinica.",
        ["Valutare l'impatto sulla propria agenda"],
        70.0,
    ),
    (
        "Corso ECM: gestione dell'asma in età pediatrica",
        "AGENAS", Geo.IT, TaxonomyTag.CME_TRAINING,
        "18 crediti ECM, iscrizioni aperte fino al 30 settembre",
        "Copre l'aggiornamento GINA 2026 con casi clinici territoriali.",
        ["Iscriversi entro il 30 settembre"],
        62.0,
    ),
]


def _build_items() -> list[NewsItem]:
    items: list[NewsItem] = []
    for title, source, geo, tag, headline, why, actions, score in SAMPLES:
        items.append(
            NewsItem(
                source=SourceRef(
                    key=source.lower().replace(" ", "_"),
                    name=source,
                    source_type="rss",
                    country="IT" if geo is Geo.IT else "EU",
                    reliability_tier=5,
                ),
                content=ContentBlock(
                    title=title,
                    canonical_url=f"https://esempio.it/{tag.value}",
                    published_at=PUBLISHED,
                    raw_text=why,
                    document_type=DocumentType.GUIDELINE,
                    key_passages=[
                        KeyPassage(
                            quote=why,
                            url=f"https://esempio.it/{tag.value}",
                        ),
                    ],
                ),
                classification=Classification(geo=geo, taxonomy_tags=[tag]),
                scoring=ScoringBlock(
                    score_total=score,
                    subscores=Subscores(
                        pls_relevance=5,
                        clinical_impact=4,
                        operational_impact=4,
                        source_trust=5,
                        novelty=4,
                        actionability=4,
                        urgency=3,
                    ),
                ),
                editorial=EditorialBlock(
                    source_note=SOURCE_NOTES.get(tag, ""),
                    headline_operational=headline,
                    why_it_matters=why,
                    what_to_do=actions[:1],
                    summary=why,
                    confidence=Confidence.HIGH,
                    citations=[
                        Citation(
                            claim_id=headline,
                            source_url=f"https://esempio.it/{tag.value}",
                        ),
                    ],
                ),
            ),
        )
    return items


def main() -> None:
    newsletter = compose_newsletter(_build_items(), WEEK)
    newsletter.subject_line = "Amoxicillina ritirata, cambia il richiamo esavalente"
    newsletter.preheader = "10 aggiornamenti operativi per la settimana"
    newsletter.public_url = "https://oykomed.it/briefing-2026-w32"

    OUTPUT.write_text(
        render_html(
            newsletter,
            unsubscribe_url="https://oykomed.it/unsubscribe/esempio",
            preferences_url="https://oykomed.it/preferences/esempio",
            archive_url="https://oykomed.it/archive",
        ),
        encoding="utf-8",
    )

    plain = render_plain_text(newsletter)
    print(f"Sections rendered : {len({slot.section for slot in newsletter.slots})}")  # noqa: T201
    print(f"Items rendered    : {len(newsletter.slots)}")  # noqa: T201
    print(f"Plain text length : {len(plain)} chars")  # noqa: T201
    print(f"Written           : {OUTPUT.resolve()}")  # noqa: T201
    webbrowser.open(OUTPUT.resolve().as_uri())


if __name__ == "__main__":
    main()
