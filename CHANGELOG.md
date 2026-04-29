# Changelog

All notable changes to the Oykos Newsletter Engine are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-04-29

### Added
- Full 7-phase daily pipeline: ingest, classify, score, synthesize, compose, render, send
- 12 RSS source connectors (SIP, SIN, EJP, ADC, Frontiers, Acta Paediatrica, EAP, Lancet Child, Pediatric Research, Bambino Gesu, Gaslini, UPPA)
- Azure OpenAI integration (GPT-5.2) for classification, scoring, and editorial synthesis
- 7-dimension scoring engine (PLS relevance, clinical impact, operational impact, source trust, novelty, actionability, urgency)
- Claim verification pipeline with confidence badges (high/medium/low)
- Newsletter composer with 70/30 IT/foreign ratio enforcement
- Section-based layout: top priority, clinical, regulatory, device, CME
- Professional HTML email template with gradient header, TOC, color-coded section pills, source attribution, and "Leggi tutto" links
- Plain text fallback rendering
- Gmail SMTP_SSL delivery (port 465, app passwords)
- SQLite database with SQLAlchemy 2.0 async ORM
- URL-based deduplication against DB
- `sent_at` tracking - items never repeated across newsletter issues
- Backlog fallback system: pulls from 7-28 day unsent pool when fresh candidates are sparse
- Trigger-based alert system for urgent items (AIFA, FSN, epidemic peaks)
- FastAPI review API for human-in-the-loop approval
- Structured JSON logging and quality metrics
- 127 tests (unit + integration), 90%+ coverage target
- Quality gates script (`vibe-check.ps1`): ruff lint, ruff format, pyright strict, pytest + coverage
- CLI entry point: `python -m oykos` or `oykos` console script
- Comprehensive documentation: PRD, architecture, data model, scoring, source registry
