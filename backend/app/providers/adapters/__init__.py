"""Concrete job-provider adapters."""

from app.providers.adapters.adzuna import AdzunaProvider
from app.providers.adapters.apify_linkedin import ApifyLinkedInProvider
from app.providers.adapters.apify_naukri import ApifyNaukriProvider
from app.providers.adapters.greenhouse_lever import GreenhouseLeverProvider
from app.providers.adapters.jooble import JoobleProvider
from app.providers.adapters.jsearch import JSearchProvider
from app.providers.adapters.remotive import RemotiveProvider
from app.providers.adapters.serpapi import SerpApiGoogleJobsProvider

__all__ = [
    "AdzunaProvider",
    "ApifyLinkedInProvider",
    "ApifyNaukriProvider",
    "GreenhouseLeverProvider",
    "JoobleProvider",
    "JSearchProvider",
    "RemotiveProvider",
    "SerpApiGoogleJobsProvider",
]
