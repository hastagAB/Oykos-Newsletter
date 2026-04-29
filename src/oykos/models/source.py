"""Source registry model and whitelist - S002."""
from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field

from oykos.models.taxonomy import SourceType, TaxonomyTag, Tier


class FetchConfig(BaseModel):
    timeout_seconds: int = 30
    max_items: int = 20
    custom_headers: dict[str, str] = Field(default_factory=dict)


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
    """Build the complete source registry from the whitelist."""
    fc_scrape = FetchConfig(timeout_seconds=45, max_items=10)
    fc_rss = FetchConfig(timeout_seconds=30, max_items=20)
    fc_api = FetchConfig(timeout_seconds=30, max_items=50)

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
        Source(key="sicupp", name="SICuPP Guidelines Commentate", url="https://sicupp.org/category/linee-guida-commentate/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[], fetch_config=fc_scrape),
        Source(key="sipps", name="SIPPS", url="https://www.sipps.it/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[], fetch_config=fc_scrape),
        Source(key="agenas_ecm", name="Agenas ECM Events", url="https://ape.agenas.it/Tools/Eventi.aspx", source_type=SourceType.API, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[TaxonomyTag.CME_TRAINING], fetch_config=fc_api),
        Source(key="ecm_portal", name="ECM Commission Portal", url="https://ecm.agenas.it/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[TaxonomyTag.CME_TRAINING], fetch_config=fc_scrape),
        Source(key="garante_privacy", name="Garante Privacy", url="https://www.garanteprivacy.it/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=5, country="IT", category_hints=[TaxonomyTag.PRIVACY], fetch_config=fc_scrape),
        Source(key="choosing_wisely_it", name="Choosing Wisely Italy", url="https://choosingwiselyitaly.org/progetto/", source_type=SourceType.SCRAPE, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[], fetch_config=fc_scrape),
        Source(key="sin_neonatologia", name="SIN (Neonatologia)", url="https://www.neonatologia.it/feed/", source_type=SourceType.RSS, tier=Tier.TIER_1_ITALY, reliability=4, country="IT", category_hints=[], fetch_config=fc_rss),
        # --- Tier 2: European ---
        Source(key="ecdc_cdtr", name="ECDC Weekly Threats Report", url="https://www.ecdc.europa.eu/en/publications-and-data/monitoring/weekly-threats-reports", source_type=SourceType.SCRAPE, tier=Tier.TIER_2_EUROPE, reliability=5, country="EU", category_hints=[TaxonomyTag.SURVEILLANCE], fetch_config=fc_scrape),
        Source(key="ema_news", name="EMA News", url="https://www.ema.europa.eu/en/news", source_type=SourceType.SCRAPE, tier=Tier.TIER_2_EUROPE, reliability=5, country="EU", category_hints=[TaxonomyTag.DRUG_SAFETY, TaxonomyTag.DRUG_AUTHORIZATION], fetch_config=fc_scrape),
        Source(key="ejped", name="European Journal of Pediatrics", url="https://link.springer.com/search.rss?facet-journal-id=431&facet-content-type=Article", source_type=SourceType.RSS, tier=Tier.TIER_2_EUROPE, reliability=3, country="EU", category_hints=[], fetch_config=fc_rss),
        Source(key="adc_bmj", name="Archives of Disease in Childhood", url="https://adc.bmj.com/rss/current.xml", source_type=SourceType.RSS, tier=Tier.TIER_2_EUROPE, reliability=3, country="EU", category_hints=[], fetch_config=fc_rss),
        Source(key="frontiers_ped", name="Frontiers in Pediatrics", url="https://www.frontiersin.org/journals/pediatrics/rss", source_type=SourceType.RSS, tier=Tier.TIER_2_EUROPE, reliability=3, country="EU", category_hints=[], fetch_config=fc_rss),
        Source(key="acta_paed", name="Acta Paediatrica", url="https://rss.onlinelibrary.wiley.com/feed/16512227/most-recent", source_type=SourceType.RSS, tier=Tier.TIER_2_EUROPE, reliability=3, country="EU", category_hints=[], fetch_config=fc_rss),
        Source(key="eap", name="European Academy of Paediatrics", url="https://www.eapaediatrics.eu/feed/", source_type=SourceType.RSS, tier=Tier.TIER_2_EUROPE, reliability=4, country="EU", category_hints=[], fetch_config=fc_rss),
        # --- Tier 3: Global ---
        Source(key="aap_guidelines", name="AAP Clinical Practice Guidelines", url="https://publications.aap.org/collection/523/Clinical-Practice-Guidelines", source_type=SourceType.SCRAPE, tier=Tier.TIER_3_GLOBAL, reliability=3, country="US", category_hints=[], fetch_config=fc_scrape),
        Source(key="aap_news", name="AAP News", url="https://publications.aap.org/rss/site_154/48.xml", source_type=SourceType.RSS, tier=Tier.TIER_3_GLOBAL, reliability=3, country="US", category_hints=[], fetch_config=fc_rss),
        Source(key="jama_ped", name="JAMA Pediatrics", url="https://jamanetwork.com/rss/site_16/116.xml", source_type=SourceType.RSS, tier=Tier.TIER_3_GLOBAL, reliability=3, country="US", category_hints=[], fetch_config=fc_rss),
        Source(key="lancet_child", name="Lancet Child & Adolescent Health", url="https://www.thelancet.com/rssfeed/lanchi_current.xml", source_type=SourceType.RSS, tier=Tier.TIER_3_GLOBAL, reliability=3, country="UK", category_hints=[], fetch_config=fc_rss),
        Source(key="bmc_ped", name="BMC Pediatrics", url="https://bmcpediatr.biomedcentral.com/articles/most-recent/rss.xml", source_type=SourceType.RSS, tier=Tier.TIER_3_GLOBAL, reliability=3, country="UK", category_hints=[], fetch_config=fc_rss),
        Source(key="ped_research", name="Pediatric Research", url="https://www.nature.com/pr.rss", source_type=SourceType.RSS, tier=Tier.TIER_3_GLOBAL, reliability=3, country="UK", category_hints=[], fetch_config=fc_rss),
        Source(key="who", name="WHO Publications", url="https://www.who.int/", source_type=SourceType.SCRAPE, tier=Tier.TIER_3_GLOBAL, reliability=5, country="GLOBAL", category_hints=[], fetch_config=fc_scrape),
        # --- Radar ---
        Source(key="bambino_gesu", name="Ospedale Bambino Gesu", url="https://www.ospedalebambinogesu.it/rss", source_type=SourceType.RSS, tier=Tier.RADAR, reliability=2, country="IT", category_hints=[], fetch_config=fc_rss),
        Source(key="meyer", name="Ospedale Meyer", url="https://www.meyer.it/index.php?format=feed&type=rss", source_type=SourceType.RSS, tier=Tier.RADAR, reliability=2, country="IT", category_hints=[], fetch_config=fc_rss),
        Source(key="gaslini", name="Ospedale Gaslini", url="https://www.gaslini.org/feed/", source_type=SourceType.RSS, tier=Tier.RADAR, reliability=2, country="IT", category_hints=[], fetch_config=fc_rss),
        Source(key="medico_pediatra", name="Il Medico Pediatra", url="https://www.ilmedicopediatra-rivistafimp.it/enewsletter/", source_type=SourceType.SCRAPE, tier=Tier.RADAR, reliability=1, country="IT", category_hints=[], fetch_config=fc_scrape),
        Source(key="uppa", name="UPPA", url="https://www.uppa.it/feed/", source_type=SourceType.RSS, tier=Tier.RADAR, reliability=1, country="IT", category_hints=[], fetch_config=fc_rss),
        Source(key="medico_bambino", name="Medico e Bambino", url="https://www.medicoebambino.com/rss.php", source_type=SourceType.RSS, tier=Tier.RADAR, reliability=2, country="IT", category_hints=[], fetch_config=fc_rss),
    ]

    return {s.key: s for s in sources}


@lru_cache(maxsize=1)
def get_source_registry() -> dict[str, Source]:
    """Return the singleton source registry."""
    return _build_registry()
