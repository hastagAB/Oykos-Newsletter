"""Source registry model and whitelist - S002."""
from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field

from oykos.models.taxonomy import SourceType, TaxonomyTag, Tier


class FetchConfig(BaseModel):
    timeout_seconds: int = 30
    max_items: int = 20
    custom_headers: dict[str, str] = Field(default_factory=dict)
    # Controlled-scraping hints. Empty values fall back to generic heuristics.
    link_selector: str = ""
    content_selector: str = ""
    url_must_contain: str = ""


class Source(BaseModel):
    key: str
    name: str
    url: str
    source_type: SourceType
    tier: Tier
    reliability: int = Field(ge=0, le=5)
    country: str
    category_hints: list[TaxonomyTag] = Field(default_factory=list)
    enabled: bool = True
    fetch_config: FetchConfig = Field(default_factory=FetchConfig)

    @property
    def is_italian(self) -> bool:
        return self.tier == Tier.TIER_1_ITALY


def _build_registry() -> dict[str, Source]:
    """Build the complete source registry from the whitelist (docs/sources.md)."""
    fc_scrape = FetchConfig(timeout_seconds=45, max_items=10)
    fc_rss = FetchConfig(timeout_seconds=30, max_items=20)
    fc_ecm = FetchConfig(timeout_seconds=45, max_items=15)

    sources: list[Source] = [
        # --- Tier 1: Italian Institutional ---
        Source(key="min_salute_pnpv", name="Ministry - PNPV/Vaccinations", url="https://www.salute.gov.it/new/it/tema/vaccinazioni/piano-nazionale-prevenzione-vaccinale/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=5, country="IT", category_hints=[TaxonomyTag.VACCINATIONS], fetch_config=fc_scrape),
        Source(key="respivirnet", name="RespiVirNet (ISS)", url="https://www.salute.gov.it/new/it/tema/influenza/sistema-di-sorveglianza-respivirnet/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=5, country="IT", category_hints=[TaxonomyTag.SURVEILLANCE, TaxonomyTag.RESPIRATORY], fetch_config=fc_scrape),
        Source(key="min_salute_fsn", name="Ministry - Device Safety (FSN)", url="https://www.salute.gov.it/new/it/avvisi/avvisi-di-sicurezza-sui-dispositivi-medici/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=5, country="IT", category_hints=[TaxonomyTag.DEVICE_SAFETY], fetch_config=fc_scrape),
        Source(key="min_salute_dm_db", name="Ministry - Device Database", url="https://www.salute.gov.it/new/it/banche-dati/banca-dati-nazionale-dei-dispositivi-medici/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=5, country="IT", category_hints=[TaxonomyTag.DEVICE_SAFETY], fetch_config=fc_scrape),
        Source(key="iss_epicentro", name="ISS/EpiCentro Influenza", url="https://www.epicentro.iss.it/influenza/bollettini", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=5, country="IT", category_hints=[TaxonomyTag.SURVEILLANCE, TaxonomyTag.RESPIRATORY], fetch_config=fc_scrape),
        Source(key="iss_abr", name="ISS - Antibiotic Resistance", url="https://www.epicentro.iss.it/antibiotico-resistenza/documentazione-italia", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=5, country="IT", category_hints=[TaxonomyTag.ANTIBIOTIC_RESISTANCE], fetch_config=fc_scrape),
        Source(key="aifa_safety", name="AIFA Safety Communications", url="https://www.aifa.gov.it/comunicazioni-di-sicurezza", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=5, country="IT", category_hints=[TaxonomyTag.DRUG_SAFETY], fetch_config=fc_scrape),
        Source(key="sisac_acn", name="SISAC - ACN Publications", url="https://www.sisac.info/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=5, country="IT", category_hints=[TaxonomyTag.ACN_AGREEMENTS], fetch_config=fc_scrape),
        Source(key="sip", name="SIP (Societa Italiana di Pediatria)", url="https://sip.it/feed/", source_type=SourceType.RSS, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[], fetch_config=fc_rss),
        Source(key="sip_guidelines", name="SIP Guidelines", url="https://sip.it/sezione/formazione-e-aggiornamento/linee-guida/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[], fetch_config=fc_scrape),
        Source(key="fimp", name="FIMP Nazionale", url="https://www.fimp.pro/feed/", source_type=SourceType.RSS, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[TaxonomyTag.CONGRESSES], fetch_config=fc_rss),
        Source(key="fimp_events", name="FIMP Events/Congresses", url="https://www.fimp.pro/eventi/eventi-in-presenza/prossimi-eventi", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[TaxonomyTag.CONGRESSES], fetch_config=fc_scrape),
        Source(key="fimp_calendar", name="FIMP Event Calendar", url="https://www.fimp.pro/eventi/calendario-eventi", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[TaxonomyTag.CONGRESSES], fetch_config=fc_scrape),
        Source(key="sicupp", name="SICuPP Guidelines Commentate", url="https://sicupp.org/category/linee-guida-commentate/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[], fetch_config=FetchConfig(max_items=20)),
        Source(key="sipps", name="SIPPS", url="https://www.sipps.it/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[], fetch_config=fc_scrape),
        Source(key="agenas_ecm", name="Agenas ECM Events", url="https://ape.agenas.it/Tools/Eventi.aspx", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[TaxonomyTag.CME_TRAINING], fetch_config=fc_ecm),
        Source(key="ecm_portal", name="ECM Commission Portal", url="https://ecm.agenas.it/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[TaxonomyTag.CME_TRAINING], fetch_config=fc_scrape),
        Source(key="garante_privacy", name="Garante Privacy", url="https://www.garanteprivacy.it/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=5, country="IT", category_hints=[TaxonomyTag.PRIVACY], fetch_config=fc_scrape),
        Source(key="choosing_wisely_it", name="Choosing Wisely Italy", url="https://choosingwiselyitaly.org/progetto/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[], fetch_config=fc_scrape),
        Source(key="sin_neonatologia", name="SIN (Neonatologia)", url="https://www.neonatologia.it/feed/", source_type=SourceType.RSS, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[], fetch_config=fc_rss),
        Source(key="min_salute_segnalazioni", name="Ministry - Device Incident Reporting", url="https://www.salute.gov.it/new/it/tema/dispositivi-medici/sistema-di-segnalazione-i-dispositivi-medici/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=5, country="IT", category_hints=[TaxonomyTag.DEVICE_SAFETY], fetch_config=fc_scrape),
        Source(key="min_salute_ivdr", name="Ministry - IVD Performance Studies (IVDR)", url="https://www.salute.gov.it/new/it/tema/dispositivi-medici/studi-delle-prestazioni-dei-dispositivi-medico-diagnostici-vitro/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=5, country="IT", category_hints=[TaxonomyTag.POCT_LAB, TaxonomyTag.RAPID_TESTS], fetch_config=fc_scrape),
        Source(key="agenas_hta", name="Agenas - HTA Medical Devices", url="https://www.agenas.gov.it/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[TaxonomyTag.DEVICE_SAFETY], fetch_config=fc_scrape),
        # --- Tier 1: Italian regional (operational changes for affiliated PLS) ---
        Source(key="regione_lombardia", name="Regione Lombardia - Sanita", url="https://www.regione.lombardia.it/wps/portal/istituzionale/HP/servizi-e-informazioni/cittadini/salute-e-prevenzione", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[TaxonomyTag.ACN_AGREEMENTS], fetch_config=fc_scrape),
        Source(key="regione_veneto", name="Regione Veneto - Sanita", url="https://www.regione.veneto.it/web/sanita", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[TaxonomyTag.ACN_AGREEMENTS], fetch_config=fc_scrape),
        Source(key="regione_umbria", name="Regione Umbria - Salute", url="https://www.regione.umbria.it/salute", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[TaxonomyTag.ACN_AGREEMENTS], fetch_config=fc_scrape),
        # --- Tier 2: European ---
        Source(key="ecdc_cdtr", name="ECDC Weekly Threats Report", url="https://www.ecdc.europa.eu/en/publications-and-data/monitoring/weekly-threats-reports", source_type=SourceType.SCRAPE, tier=Tier.TIER_2_EUROPE, reliability=5, country="EU", category_hints=[TaxonomyTag.SURVEILLANCE], fetch_config=fc_scrape),
        Source(key="ema_news", name="EMA News", url="https://www.ema.europa.eu/en/news", source_type=SourceType.SCRAPE, tier=Tier.TIER_2_EUROPE, reliability=5, country="EU", category_hints=[TaxonomyTag.DRUG_SAFETY, TaxonomyTag.DRUG_AUTHORIZATION], fetch_config=fc_scrape),
        Source(key="ejped", name="European Journal of Pediatrics", url="https://link.springer.com/search.rss?facet-journal-id=431&facet-content-type=Article", source_type=SourceType.RSS, tier=Tier.TIER_2_EUROPE, reliability=3, country="EU", category_hints=[], fetch_config=fc_rss),
        Source(key="adc_bmj", name="Archives of Disease in Childhood", url="https://adc.bmj.com/rss/current.xml", source_type=SourceType.RSS, tier=Tier.TIER_2_EUROPE, reliability=3, country="EU", category_hints=[], fetch_config=fc_rss),
        Source(key="frontiers_ped", name="Frontiers in Pediatrics", url="https://www.frontiersin.org/journals/pediatrics/rss", source_type=SourceType.RSS, tier=Tier.TIER_2_EUROPE, reliability=3, country="EU", category_hints=[], fetch_config=fc_rss),
        Source(key="acta_paed", name="Acta Paediatrica", url="https://rss.onlinelibrary.wiley.com/feed/16512227/most-recent", source_type=SourceType.RSS, tier=Tier.TIER_2_EUROPE, reliability=3, country="EU", category_hints=[], fetch_config=fc_rss),
        Source(key="eap", name="European Academy of Paediatrics", url="https://www.eapaediatrics.eu/feed/", source_type=SourceType.RSS, tier=Tier.TIER_2_EUROPE, reliability=4, country="EU", category_hints=[], fetch_config=fc_rss),
        # --- Tier 3: Global ---
        Source(key="aap_guidelines", name="AAP Clinical Practice Guidelines", url="https://publications.aap.org/collection/523/Clinical-Practice-Guidelines", source_type=SourceType.SCRAPE, tier=Tier.TIER_3_GLOBAL, reliability=4, country="US", category_hints=[], fetch_config=fc_scrape),
        # Pediatrics, JAMA Pediatrics and AAP News all return 403/404 to
        # automated clients (verified 2026-08-07). Europe PMC indexes the same
        # journals and serves a documented API, so the peer-reviewed literature
        # the editorial feedback asks for arrives through this one connector.
        Source(key="europe_pmc", name="Europe PMC - Pediatric Evidence", url="https://www.ebi.ac.uk/europepmc/webservices/rest/search", source_type=SourceType.API, tier=Tier.TIER_3_GLOBAL, reliability=4, country="GLOBAL", category_hints=[TaxonomyTag.RESEARCH_EVIDENCE], fetch_config=FetchConfig(timeout_seconds=45, max_items=25)),
        Source(key="lancet_child", name="Lancet Child & Adolescent Health", url="https://www.thelancet.com/rssfeed/lanchi_current.xml", source_type=SourceType.RSS, tier=Tier.TIER_3_GLOBAL, reliability=4, country="UK", category_hints=[], fetch_config=fc_rss),
        Source(key="bmc_ped", name="BMC Pediatrics", url="https://bmcpediatr.biomedcentral.com/articles/most-recent/rss.xml", source_type=SourceType.RSS, tier=Tier.TIER_3_GLOBAL, reliability=3, country="UK", category_hints=[], fetch_config=fc_rss),
        Source(key="ped_research", name="Pediatric Research", url="https://www.nature.com/pr.rss", source_type=SourceType.RSS, tier=Tier.TIER_3_GLOBAL, reliability=3, country="UK", category_hints=[], fetch_config=fc_rss),
        Source(key="who_news", name="WHO News", url="https://www.who.int/rss-feeds/news-english.xml", source_type=SourceType.RSS, tier=Tier.TIER_3_GLOBAL, reliability=5, country="GLOBAL", category_hints=[], fetch_config=fc_rss),
        Source(key="nice_guidance", name="NICE Guidance", url="https://www.nice.org.uk/guidance/published?ndt=Guidance", source_type=SourceType.SCRAPE, tier=Tier.TIER_3_GLOBAL, reliability=3, country="UK", category_hints=[], fetch_config=fc_scrape),
        # --- Tier 3: high-impact research and AI in clinical practice ---
        Source(key="nature_medicine", name="Nature Medicine", url="https://www.nature.com/nm.rss", source_type=SourceType.RSS, tier=Tier.TIER_3_GLOBAL, reliability=3, country="UK", category_hints=[TaxonomyTag.RESEARCH_EVIDENCE], fetch_config=fc_rss),
        Source(key="npj_digital_medicine", name="npj Digital Medicine", url="https://www.nature.com/npjdigitalmed.rss", source_type=SourceType.RSS, tier=Tier.TIER_3_GLOBAL, reliability=3, country="UK", category_hints=[TaxonomyTag.AI_DIGITAL_HEALTH], fetch_config=fc_rss),
        Source(key="lancet_digital_health", name="Lancet Digital Health", url="https://www.thelancet.com/rssfeed/landig_current.xml", source_type=SourceType.RSS, tier=Tier.TIER_3_GLOBAL, reliability=3, country="UK", category_hints=[TaxonomyTag.AI_DIGITAL_HEALTH], fetch_config=fc_rss),
        # --- Radar ---
        Source(key="bambino_gesu", name="Ospedale Bambino Gesu", url="https://www.ospedalebambinogesu.it/rss", source_type=SourceType.RSS, tier=Tier.RADAR, reliability=2, country="IT", category_hints=[], fetch_config=fc_rss),
        Source(key="meyer", name="Ospedale Meyer", url="https://www.meyer.it/index.php?format=feed&type=rss", source_type=SourceType.RSS, tier=Tier.RADAR, reliability=2, country="IT", category_hints=[], fetch_config=fc_rss),
        Source(key="gaslini", name="Ospedale Gaslini", url="https://www.gaslini.org/feed/", source_type=SourceType.RSS, tier=Tier.RADAR, reliability=2, country="IT", category_hints=[], fetch_config=fc_rss),
        Source(key="medico_pediatra", name="Il Medico Pediatra", url="https://www.ilmedicopediatra-rivistafimp.it/enewsletter/", source_type=SourceType.SCRAPE, tier=Tier.RADAR, reliability=1, country="IT", category_hints=[], fetch_config=fc_scrape),
        Source(key="uppa", name="UPPA", url="https://www.uppa.it/feed/", source_type=SourceType.RSS, tier=Tier.RADAR, reliability=1, country="IT", category_hints=[], fetch_config=fc_rss),
        Source(key="medico_bambino", name="Medico e Bambino", url="https://www.medicoebambino.com/rss.php", source_type=SourceType.RSS, tier=Tier.RADAR, reliability=2, country="IT", category_hints=[], fetch_config=fc_rss),
        # Health-policy daily. Secondary press, so reliability 3: it clears the
        # reliability gate but most of its volume is filtered out as generalist
        # news. It earns its place on ACN, LEA and regional items a PLS must act on.
        Source(key="quotidiano_sanita", name="Quotidiano Sanita", url="https://www.quotidianosanita.it/feed/", source_type=SourceType.RSS, tier=Tier.TIER_1_ITALY, reliability=3, country="IT", category_hints=[TaxonomyTag.ACN_AGREEMENTS], fetch_config=fc_rss),
    ]

    return {s.key: s for s in sources}


@lru_cache(maxsize=1)
def get_source_registry() -> dict[str, Source]:
    """Return the singleton source registry."""
    return _build_registry()
