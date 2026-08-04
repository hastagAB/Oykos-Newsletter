"""Taxonomy enums and value types - S003."""
from __future__ import annotations

from enum import Enum


class Tier(str, Enum):
    TIER_1_ITALY = "tier_1_italy"
    TIER_2_EUROPE = "tier_2_europe"
    TIER_3_GLOBAL = "tier_3_global"
    RADAR = "radar"


class Geo(str, Enum):
    IT = "IT"
    EU = "EU"
    GLOBAL = "GLOBAL"


class Setting(str, Enum):
    TERRITORY = "territory"
    HOSPITAL = "hospital"
    MIXED = "mixed"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DocumentType(str, Enum):
    SAFETY_COMMUNICATION = "safety_communication"
    GUIDELINE = "guideline"
    CONSENSUS = "consensus"
    SURVEILLANCE_REPORT = "surveillance_report"
    LEGAL_UPDATE = "legal_update"
    EVENT = "event"
    NEWS = "news"
    STUDY = "study"


class Section(str, Enum):
    TOP_PRIORITY = "top_priority"
    CLINICAL = "clinical"
    REGULATORY = "regulatory"
    DEVICE = "device"
    CME = "cme"


class Penalty(str, Enum):
    """Noise penalties from docs/scoring.md."""

    DUPLICATE = "duplicate"
    PAYWALL = "paywall"
    PRESS_RELEASE = "press_release"
    SINGLE_SOURCE = "single_source"


class ExclusionReason(str, Enum):
    """Why an item failed the selection gates (blueprint Section 3)."""

    NO_PLS_RELEVANCE = "no_pls_relevance"
    UNRELIABLE_SOURCE = "unreliable_source"
    NOT_ACTIONABLE = "not_actionable"
    GENERALIST_NEWS = "generalist_news"
    PREPRINT = "preprint"
    VENDOR_MARKETING = "vendor_marketing"


class ReviewerRole(str, Enum):
    MEDICAL_EDITOR = "medical_editor"
    LEGAL_EDITOR = "legal_editor"


class SourceType(str, Enum):
    RSS = "rss"
    SCRAPE = "scrape"
    API = "api"
    PDF = "pdf"


class IssueStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SENT = "sent"


class TaxonomyTag(str, Enum):
    # Clinic Territory
    RESPIRATORY = "respiratory"
    GASTROENTERITIS = "gastroenteritis"
    DERMATOLOGY = "dermatology"
    ALLERGOLOGY = "allergology"
    NEURO_DEVELOPMENT = "neuro_development"
    EMERGENCIES_TRIAGE = "emergencies_triage"
    # Prevention & Public Health
    VACCINATIONS = "vaccinations"
    SURVEILLANCE = "surveillance"
    ANTIBIOTIC_RESISTANCE = "antibiotic_resistance"
    # Medications
    DRUG_SAFETY = "drug_safety"
    DRUG_AUTHORIZATION = "drug_authorization"
    DRUG_SHORTAGE = "drug_shortage"
    # Studio & Compliance
    ACN_AGREEMENTS = "acn_agreements"
    PRIVACY = "privacy"
    TELEMEDICINE = "telemedicine"
    # Diagnostics & POCT
    RAPID_TESTS = "rapid_tests"
    POCT_LAB = "poct_lab"
    FUNCTIONAL_DIAGNOSTICS = "functional_diagnostics"
    SCREENING = "screening"
    DEVICE_SAFETY = "device_safety"
    # Training
    CME_TRAINING = "cme_training"
    CONGRESSES = "congresses"
    # Research and AI in pediatric practice
    RESEARCH_EVIDENCE = "research_evidence"
    AI_DIGITAL_HEALTH = "ai_digital_health"
