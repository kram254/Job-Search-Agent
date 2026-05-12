"""
Portal Scanner - 3-Level Discovery Strategy (career-ops inspired)

Level 1: Playwright Direct (Primary) - Real-time scraping of careers pages
Level 2: Greenhouse API (Complementary) - Structured JSON for Greenhouse boards
Level 3: WebSearch (Discovery) - Broad search for new companies/roles
"""

import json
import re
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

# Assuming these imports exist in the project
from ..browser.playwright_wrapper import BrowserWrapper
from ..tracker.logger import Logger


class ScanLevel(Enum):
    """Scan strategy levels."""
    PLAYWRIGHT_DIRECT = "playwright"      # Level 1 - Most reliable
    GREENHOUSE_API = "greenhouse_api"     # Level 2 - Fast, structured
    WEBSEARCH = "websearch"               # Level 3 - Broad discovery


@dataclass
class JobListing:
    """Discovered job listing."""
    title: str
    company: str
    url: str
    location: str = ""
    description: str = ""
    detected_via: ScanLevel = ScanLevel.PLAYWRIGHT_DIRECT
    scan_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = True
    score: float = 0.0


@dataclass
class ScanResult:
    """Complete scan result."""
    listings: List[JobListing] = field(default_factory=list)
    total_found: int = 0
    added_to_pipeline: int = 0
    filtered_out: int = 0
    duplicates_skipped: int = 0
    expired_skipped: int = 0
    scan_duration_seconds: float = 0.0


@dataclass
class CompanyConfig:
    """Configuration for a tracked company."""
    name: str
    careers_url: str = ""
    api_url: str = ""  # For Greenhouse API
    scan_method: str = "playwright"
    scan_query: str = ""
    notes: str = ""
    enabled: bool = True
    platform: str = ""  # greenhouse, ashby, lever, custom


@dataclass
class TitleFilter:
    """Title filtering configuration."""
    positive: List[str] = field(default_factory=list)
    negative: List[str] = field(default_factory=list)
    seniority_boost: List[str] = field(default_factory=list)


class PortalScanner:
    """
    3-Level job discovery scanner.
    Ports career-ops scan.md logic to Python/Playwright.
    """

    # Platform URL patterns
    PLATFORM_PATTERNS = {
        "greenhouse": [
            r"job-boards\.greenhouse\.io/(?P<slug>[^/]+)",
            r"boards\.greenhouse\.io/(?P<slug>[^/]+)",
            r"job-boards\.eu\.greenhouse\.io/(?P<slug>[^/]+)"
        ],
        "ashby": [
            r"jobs\.ashbyhq\.com/(?P<slug>[^/]+)"
        ],
        "lever": [
            r"jobs\.lever\.co/(?P<slug>[^/]+)"
        ],
        "workday": [
            r"\.wd\d+\.myworkdayjobs\.com"
        ],
        "custom": []
    }

    def __init__(
        self,
        browser: BrowserWrapper,
        config_path: str = "config/portals.yml",
        history_path: str = "data/scan_history.json",
        logger: Optional[Logger] = None
    ):
        self.browser = browser
        self.config_path = Path(config_path)
        self.history_path = Path(history_path)
        self.logger = logger or Logger()

        self.companies: List[CompanyConfig] = []
        self.title_filter: TitleFilter = TitleFilter()
        self.search_queries: List[Dict[str, Any]] = []

        self._load_config()
        self._scan_history: List[str] = self._load_history()

    def _load_config(self) -> None:
        """Load portal configuration from YAML."""
        if not self.config_path.exists():
            self.logger.warning(f"Portal config not found: {self.config_path}")
            self._create_default_config()
            return

        try:
            import yaml
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)

            # Load tracked companies
            for company_data in config.get("tracked_companies", []):
                self.companies.append(CompanyConfig(
                    name=company_data.get("name", ""),
                    careers_url=company_data.get("careers_url", ""),
                    api_url=company_data.get("api", ""),
                    scan_method=company_data.get("scan_method", "playwright"),
                    scan_query=company_data.get("scan_query", ""),
                    notes=company_data.get("notes", ""),
                    enabled=company_data.get("enabled", True),
                    platform=self._detect_platform(company_data.get("careers_url", ""))
                ))

            # Load title filter
            filter_config = config.get("title_filter", {})
            self.title_filter = TitleFilter(
                positive=filter_config.get("positive", []),
                negative=filter_config.get("negative", []),
                seniority_boost=filter_config.get("seniority_boost", [])
            )

            # Load search queries
            self.search_queries = config.get("search_queries", [])

        except Exception as e:
            self.logger.error(f"Failed to load portal config: {e}")
            self._create_default_config()

    def _create_default_config(self) -> None:
        """Create default Kenyan market portal configuration."""
        self.companies = [
            # Kenyan Tech Companies
            CompanyConfig(
                name="Andela",
                careers_url="https://www.andela.com/join-andela/",
                enabled=True,
                platform="custom"
            ),
            CompanyConfig(
                name="Cellulant",
                careers_url="https://cellulant.com/careers/",
                enabled=True,
                platform="custom"
            ),
            CompanyConfig(
                name="M-KOPA",
                careers_url="https://www.m-kopa.com/about/careers/",
                enabled=True,
                platform="custom"
            ),
            CompanyConfig(
                name="SafeBoda",
                careers_url="https://safeboda.com/careers",
                enabled=True,
                platform="custom"
            ),
            CompanyConfig(
                name="Twiga Foods",
                careers_url="https://twiga.com/careers",
                enabled=True,
                platform="custom"
            ),
            CompanyConfig(
                name="Sendy",
                careers_url="https://www.sendyit.com/careers",
                enabled=True,
                platform="custom"
            ),
            CompanyConfig(
                name="Kobo360",
                careers_url="https://kobo360.com/careers",
                enabled=True,
                platform="custom"
            ),
            CompanyConfig(
                name="Lipa Payments",
                careers_url="https://lipapayments.com/careers",
                enabled=True,
                platform="custom"
            ),
            # Remote-friendly AI Companies
            CompanyConfig(
                name="Anthropic",
                careers_url="https://job-boards.greenhouse.io/anthropic",
                api_url="https://boards-api.greenhouse.io/v1/boards/anthropic/jobs",
                enabled=True,
                platform="greenhouse"
            ),
            CompanyConfig(
                name="OpenAI",
                careers_url="https://openai.com/careers",
                scan_method="websearch",
                scan_query="site:openai.com/careers remote",
                enabled=True,
                platform="custom"
            ),
            CompanyConfig(
                name="LangChain",
                careers_url="https://jobs.ashbyhq.com/langchain",
                enabled=True,
                platform="ashby"
            ),
        ]

        self.title_filter = TitleFilter(
            positive=[
                # AI/ML Roles
                "AI", "ML", "Machine Learning", "LLM", "Agent", "Agentic",
                "Generative AI", "NLP", "Computer Vision", "Deep Learning",
                "MLOps", "LLMOps", "AI Engineer", "ML Engineer",
                "Data Scientist", "Data Engineer", "AI Product",
                # Software Engineering
                "Software Engineer", "Backend", "Frontend", "Full Stack",
                "DevOps", "Platform Engineer", "SRE",
                # Seniority
                "Senior", "Staff", "Principal", "Lead", "Head"
            ],
            negative=[
                "Intern", "Junior", "Entry Level", "Associate",
                ".NET", "Java", "PHP", "Ruby on Rails",
                "Salesforce", "SAP", "Oracle EBS",
                "Blockchain", "Web3", "Crypto",
                "Embedded", "Firmware", "Hardware"
            ],
            seniority_boost=["Senior", "Staff", "Principal", "Lead", "Head", "Director"]
        )

        self._save_default_config()

    def _save_default_config(self) -> None:
        """Save default configuration to YAML."""
        try:
            import yaml
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            config = {
                "title_filter": {
                    "positive": self.title_filter.positive,
                    "negative": self.title_filter.negative,
                    "seniority_boost": self.title_filter.seniority_boost
                },
                "tracked_companies": [
                    {
                        "name": c.name,
                        "careers_url": c.careers_url,
                        "api": c.api_url,
                        "scan_method": c.scan_method,
                        "scan_query": c.scan_query,
                        "notes": c.notes,
                        "enabled": c.enabled
                    }
                    for c in self.companies
                ],
                "search_queries": [
                    {
                        "name": "Kenyan Tech - AI/ML",
                        "query": 'site:andela.com OR site:cellulant.com OR site:m-kopa.com "AI" OR "Machine Learning" OR "Data Science"',
                        "enabled": True
                    },
                    {
                        "name": "Remote AI - Africa",
                        "query": '"AI Engineer" OR "ML Engineer" remote Africa OR Kenya OR Nigeria OR South Africa',
                        "enabled": True
                    },
                    {
                        "name": "Greenhouse - AI Roles",
                        "query": 'site:boards.greenhouse.io "AI" OR "LLM" OR "Machine Learning" remote',
                        "enabled": True
                    },
                    {
                        "name": "Ashby - AI/ML",
                        "query": 'site:jobs.ashbyhq.com "AI" OR "ML" OR "Data"',
                        "enabled": True
                    }
                ]
            }

            with open(self.config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False)

        except Exception as e:
            self.logger.error(f"Failed to save default config: {e}")

    def _load_history(self) -> List[str]:
        """Load scan history (URLs already seen)."""
        if not self.history_path.exists():
            return []

        try:
            with open(self.history_path, "r") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load scan history: {e}")
            return []

    def _save_history(self) -> None:
        """Save scan history."""
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_path, "w") as f:
                json.dump(self._scan_history, f)
        except Exception as e:
            self.logger.error(f"Failed to save scan history: {e}")

    def _detect_platform(self, url: str) -> str:
        """Detect ATS platform from URL."""
        for platform, patterns in self.PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return platform
        return "custom"

    def _extract_slug(self, url: str, platform: str) -> Optional[str]:
        """Extract company slug from platform URL."""
        patterns = self.PLATFORM_PATTERNS.get(platform, [])
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group("slug")
        return None

    async def scan(self) -> ScanResult:
        """
        Execute 3-level scan strategy.
        Returns aggregated results.
        """
        start_time = datetime.now()
        all_listings: List[JobListing] = []

        self.logger.info("Starting 3-level portal scan...")

        # Level 1: Playwright Direct (Primary - Most Reliable)
        level1_results = await self._level1_playwright_scan()
        all_listings.extend(level1_results)
        self.logger.info(f"Level 1 (Playwright): {len(level1_results)} listings")

        # Level 2: Greenhouse API (Complementary - Fast Structured)
        level2_results = await self._level2_greenhouse_api_scan()
        all_listings.extend(level2_results)
        self.logger.info(f"Level 2 (Greenhouse API): {len(level2_results)} listings")

        # Level 3: WebSearch (Discovery - Broad)
        level3_results = await self._level3_websearch_scan()
        all_listings.extend(level3_results)
        self.logger.info(f"Level 3 (WebSearch): {len(level3_results)} listings")

        # Deduplicate
        deduped_listings = self._deduplicate_listings(all_listings)

        # Filter by title
        filtered_listings, filtered_count = self._filter_by_title(deduped_listings)

        # Skip already seen
        new_listings, dup_count = self._skip_seen(filtered_listings)

        # Verify liveness for WebSearch results
        verified_listings, expired_count = await self._verify_liveness(new_listings)

        # Update history
        for listing in verified_listings:
            self._scan_history.append(listing.url)
        self._save_history()

        duration = (datetime.now() - start_time).total_seconds()

        return ScanResult(
            listings=verified_listings,
            total_found=len(all_listings),
            added_to_pipeline=len(verified_listings),
            filtered_out=filtered_count,
            duplicates_skipped=dup_count,
            expired_skipped=expired_count,
            scan_duration_seconds=duration
        )

    async def _level1_playwright_scan(self) -> List[JobListing]:
        """
        Level 1: Direct Playwright scraping of careers pages.
        Most reliable - sees pages in real-time.
        """
        listings = []
        enabled_companies = [c for c in self.companies if c.enabled and c.careers_url]

        # Process in batches of 3 for parallelization
        batch_size = 3
        for i in range(0, len(enabled_companies), batch_size):
            batch = enabled_companies[i:i + batch_size]
            tasks = [self._scrape_company(c) for c in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for company, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    self.logger.warning(f"Failed to scrape {company.name}: {result}")
                elif result:
                    listings.extend(result)

        return listings

    async def _scrape_company(self, company: CompanyConfig) -> List[JobListing]:
        """Scrape a single company's careers page."""
        listings = []

        try:
            # Navigate to careers page
            await self.browser.navigate(company.careers_url)

            # Platform-specific scraping logic
            if company.platform == "greenhouse":
                listings = await self._scrape_greenhouse(company)
            elif company.platform == "ashby":
                listings = await self._scrape_ashby(company)
            elif company.platform == "lever":
                listings = await self._scrape_lever(company)
            else:
                listings = await self._scrape_generic(company)

        except Exception as e:
            self.logger.error(f"Error scraping {company.name}: {e}")
            # Try fallback query if available
            if company.scan_query:
                return await self._fallback_websearch(company)

        return listings

    async def _scrape_greenhouse(self, company: CompanyConfig) -> List[JobListing]:
        """Scrape Greenhouse ATS."""
        listings = []

        # Try to get jobs from page
        try:
            # Wait for job listings to load
            await self.browser.page.wait_for_selector(".opening", timeout=5000)

            # Extract job data
            jobs = await self.browser.page.eval_on_selector_all(
                ".opening",
                """elements => elements.map(el => ({
                    title: el.querySelector('a')?.textContent?.trim() || '',
                    url: el.querySelector('a')?.href || '',
                    location: el.querySelector('.location')?.textContent?.trim() || ''
                }))"""
            )

            for job in jobs:
                if job.get("title") and job.get("url"):
                    listings.append(JobListing(
                        title=job["title"],
                        company=company.name,
                        url=job["url"],
                        location=job.get("location", ""),
                        detected_via=ScanLevel.PLAYWRIGHT_DIRECT
                    ))

        except Exception as e:
            self.logger.warning(f"Greenhouse scraping failed for {company.name}: {e}")

        return listings

    async def _scrape_ashby(self, company: CompanyConfig) -> List[JobListing]:
        """Scrape Ashby ATS."""
        listings = []

        try:
            # Ashby uses React - wait for job cards
            await self.browser.page.wait_for_selector("[data-testid='job-card']", timeout=5000)

            jobs = await self.browser.page.eval_on_selector_all(
                "[data-testid='job-card']",
                """elements => elements.map(el => ({
                    title: el.querySelector('h3')?.textContent?.trim() || '',
                    url: el.querySelector('a')?.href || '',
                    location: el.querySelector('[data-testid="location"]')?.textContent?.trim() || ''
                }))"""
            )

            for job in jobs:
                if job.get("title") and job.get("url"):
                    listings.append(JobListing(
                        title=job["title"],
                        company=company.name,
                        url=job["url"],
                        location=job.get("location", ""),
                        detected_via=ScanLevel.PLAYWRIGHT_DIRECT
                    ))

        except Exception as e:
            self.logger.warning(f"Ashby scraping failed for {company.name}: {e}")

        return listings

    async def _scrape_lever(self, company: CompanyConfig) -> List[JobListing]:
        """Scrape Lever ATS."""
        listings = []

        try:
            await self.browser.page.wait_for_selector(".posting", timeout=5000)

            jobs = await self.browser.page.eval_on_selector_all(
                ".posting",
                """elements => elements.map(el => ({
                    title: el.querySelector('.posting-title')?.textContent?.trim() || '',
                    url: el.querySelector('a')?.href || '',
                    location: el.querySelector('.location')?.textContent?.trim() || ''
                }))"""
            )

            for job in jobs:
                if job.get("title") and job.get("url"):
                    listings.append(JobListing(
                        title=job["title"],
                        company=company.name,
                        url=job["url"],
                        location=job.get("location", ""),
                        detected_via=ScanLevel.PLAYWRIGHT_DIRECT
                    ))

        except Exception as e:
            self.logger.warning(f"Lever scraping failed for {company.name}: {e}")

        return listings

    async def _scrape_generic(self, company: CompanyConfig) -> List[JobListing]:
        """Generic scraper for custom careers pages."""
        listings = []

        try:
            # Common selectors for job listings
            selectors = [
                "a[href*='job']", "a[href*='career']",
                ".job-listing", ".career-item",
                "[class*='job']", "[class*='opening']"
            ]

            # Try to find job links
            for selector in selectors:
                try:
                    elements = await self.browser.page.query_selector_all(selector)
                    for el in elements[:10]:  # Limit to first 10
                        text = await el.text_content()
                        href = await el.get_attribute("href")
                        if text and href and any(kw in text.lower() for kw in ["engineer", "developer", "manager", "analyst"]):
                            full_url = href if href.startswith("http") else f"{company.careers_url.rstrip('/')}/{href.lstrip('/')}"
                            listings.append(JobListing(
                                title=text.strip()[:100],
                                company=company.name,
                                url=full_url,
                                detected_via=ScanLevel.PLAYWRIGHT_DIRECT
                            ))
                except:
                    continue

        except Exception as e:
            self.logger.warning(f"Generic scraping failed for {company.name}: {e}")

        return listings

    async def _level2_greenhouse_api_scan(self) -> List[JobListing]:
        """
        Level 2: Structured API scan for Greenhouse, Ashby, Lever, and BambooHR.
        """
        listings = []
        import requests

        api_companies = [
            c for c in self.companies
            if c.enabled and c.platform in ("greenhouse", "ashby", "lever", "bamboohr")
        ]

        for company in api_companies:
            try:
                if company.platform == "greenhouse" and company.api_url:
                    response = requests.get(company.api_url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        for job in data.get("jobs", []):
                            listings.append(JobListing(
                                title=job.get("title", ""),
                                company=company.name,
                                url=job.get("absolute_url", ""),
                                location=job.get("location", {}).get("name", ""),
                                detected_via=ScanLevel.GREENHOUSE_API
                            ))

                elif company.platform == "ashby":
                    from agent.platforms.ashby import AshbyHandler
                    slug = AshbyHandler.extract_slug(company.careers_url)
                    if slug:
                        handler = AshbyHandler()
                        postings = handler.fetch_jobs(slug)
                        for posting in postings:
                            url = posting.get("externalLink") or f"https://jobs.ashbyhq.com/{slug}/{posting.get('id', '')}"
                            listings.append(JobListing(
                                title=posting.get("title", ""),
                                company=company.name,
                                url=url,
                                location=posting.get("locationName", ""),
                                description=posting.get("descriptionPlain", "")[:500],
                                detected_via=ScanLevel.GREENHOUSE_API
                            ))

                elif company.platform == "lever":
                    import re
                    match = re.search(r'jobs\.lever\.co/([^/?#]+)', company.careers_url)
                    if match:
                        lever_slug = match.group(1)
                        lever_url = f"https://api.lever.co/v0/postings/{lever_slug}?mode=json"
                        response = requests.get(lever_url, timeout=10)
                        if response.status_code == 200:
                            for job in response.json():
                                listings.append(JobListing(
                                    title=job.get("text", ""),
                                    company=company.name,
                                    url=job.get("hostedUrl", job.get("applyUrl", "")),
                                    location=job.get("categories", {}).get("location", ""),
                                    detected_via=ScanLevel.GREENHOUSE_API
                                ))

                elif company.platform == "bamboohr":
                    import re
                    match = re.search(r'([^/.]+)\.bamboohr\.com', company.careers_url)
                    if match:
                        bhr_slug = match.group(1)
                        bhr_url = f"https://{bhr_slug}.bamboohr.com/careers/list"
                        response = requests.get(bhr_url, timeout=10, headers={"Accept": "application/json"})
                        if response.status_code == 200:
                            data = response.json()
                            for job in data.get("result", []):
                                listings.append(JobListing(
                                    title=job.get("jobOpeningName", ""),
                                    company=company.name,
                                    url=f"https://{bhr_slug}.bamboohr.com/careers/{job.get('id', '')}",
                                    location=job.get("location", {}).get("name", ""),
                                    detected_via=ScanLevel.GREENHOUSE_API
                                ))

            except Exception as e:
                self.logger.warning(f"Level 2 API scan failed for {company.name} ({company.platform}): {e}")

        return listings

    async def _level3_websearch_scan(self) -> List[JobListing]:
        """
        Level 3: WebSearch for broad discovery.
        May return stale results - requires liveness verification.
        """
        listings = []

        # In a real implementation, this would use a search API
        # For now, return empty - placeholder for WebSearch integration
        self.logger.info("Level 3 (WebSearch) - Placeholder for search API integration")

        return listings

    async def _fallback_websearch(self, company: CompanyConfig) -> List[JobListing]:
        """Fallback to WebSearch when direct scraping fails."""
        self.logger.info(f"Using WebSearch fallback for {company.name}")
        return []

    def _deduplicate_listings(self, listings: List[JobListing]) -> List[JobListing]:
        """Remove duplicate listings by URL."""
        seen_urls = set()
        unique = []

        for listing in listings:
            url_normalized = listing.url.split("?")[0].rstrip("/")
            if url_normalized not in seen_urls:
                seen_urls.add(url_normalized)
                unique.append(listing)

        return unique

    def _filter_by_title(self, listings: List[JobListing]) -> Tuple[List[JobListing], int]:
        """
        Filter listings by title keywords.
        At least 1 positive must match, 0 negative must match.
        """
        filtered = []
        rejected = 0

        for listing in listings:
            title_lower = listing.title.lower()

            # Check positive filters
            has_positive = any(
                keyword.lower() in title_lower
                for keyword in self.title_filter.positive
            )

            # Check negative filters
            has_negative = any(
                keyword.lower() in title_lower
                for keyword in self.title_filter.negative
            )

            if has_positive and not has_negative:
                # Calculate relevance score
                score = sum(
                    1 for kw in self.title_filter.positive
                    if kw.lower() in title_lower
                )
                # Seniority boost
                if any(sb.lower() in title_lower for sb in self.title_filter.seniority_boost):
                    score += 0.5

                listing.score = min(score, 5.0)
                filtered.append(listing)
            else:
                rejected += 1

        return filtered, rejected

    def _skip_seen(self, listings: List[JobListing]) -> Tuple[List[JobListing], int]:
        """Skip listings already in history."""
        new_listings = []
        duplicates = 0

        for listing in listings:
            url_normalized = listing.url.split("?")[0].rstrip("/")
            if url_normalized not in self._scan_history:
                new_listings.append(listing)
            else:
                duplicates += 1

        return new_listings, duplicates

    async def _verify_liveness(self, listings: List[JobListing]) -> Tuple[List[JobListing], int]:
        """
        Verify job is still active using LivenessChecker.
        WebSearch results are always checked; Level 1/2 results are spot-checked.
        """
        from agent.scanner.liveness_checker import LivenessChecker
        checker = LivenessChecker(timeout=8)

        verified = []
        expired = 0

        for listing in listings:
            if listing.detected_via != ScanLevel.WEBSEARCH:
                listing.is_active = True
                verified.append(listing)
                continue

            try:
                is_live, reason = checker.check(listing.url)
                if is_live:
                    listing.is_active = True
                    verified.append(listing)
                else:
                    self.logger.info(f"Expired listing ({reason}): {listing.url[:80]}")
                    expired += 1
            except Exception:
                expired += 1

        return verified, expired

    def get_scan_summary(self, result: ScanResult) -> str:
        """Generate human-readable scan summary."""
        lines = [
            f"Portal Scan Summary - {datetime.now().strftime('%Y-%m-%d')}",
            "=" * 50,
            f"Total found: {result.total_found}",
            f"Added to pipeline: {result.added_to_pipeline}",
            f"Filtered out: {result.filtered_out}",
            f"Duplicates skipped: {result.duplicates_skipped}",
            f"Expired skipped: {result.expired_skipped}",
            f"Duration: {result.scan_duration_seconds:.1f}s",
            "",
            "New Listings:",
        ]

        for listing in result.listings[:10]:  # Show first 10
            lines.append(f"  • {listing.company} | {listing.title} | Score: {listing.score:.1f}")

        if len(result.listings) > 10:
            lines.append(f"  ... and {len(result.listings) - 10} more")

        return "\n".join(lines)

    def export_to_jobs_raw(self, result: ScanResult, output_path: str = "data/jobs_raw.json") -> None:
        """Export scan results to jobs_raw.json format."""
        output_file = Path(output_path)

        # Load existing jobs
        existing_jobs = []
        if output_file.exists():
            try:
                with open(output_file, "r") as f:
                    existing_jobs = json.load(f)
            except:
                pass

        # Convert listings to jobs_raw format
        new_jobs = []
        for listing in result.listings:
            job_id = f"scan_{abs(hash(listing.url)) % 10000000000}"
            new_jobs.append({
                "id": job_id,
                "title": listing.title,
                "company": listing.company,
                "location": listing.location,
                "description": f"Discovered via {listing.detected_via.value}",
                "applyUrl": listing.url,
                "source": listing.detected_via.value,
                "datePosted": listing.scan_timestamp,
                "url": listing.url
            })

        # Merge and deduplicate
        all_urls = {j.get("url", j.get("applyUrl", "")) for j in existing_jobs}
        for job in new_jobs:
            if job.get("url") not in all_urls:
                existing_jobs.append(job)

        # Save
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(existing_jobs, f, indent=2)

        self.logger.info(f"Exported {len(new_jobs)} new jobs to {output_path}")
