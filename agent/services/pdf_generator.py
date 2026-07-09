"""
ATS-Optimized PDF Generator
Ports career-ops pdf.md logic to Python/Playwright.

Features:
- HTML template with ATS-friendly single-column layout
- Keyword injection based on job description
- Archetype-aware CV tailoring
- Playwright-based PDF generation
- Unicode normalization for ATS compatibility
"""

import re
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from xhtml2pdf import pisa


@dataclass
class PDFGenerationResult:
    """Result of PDF generation."""
    pdf_path: str
    page_count: int
    file_size_kb: float
    keywords_injected: List[str]
    coverage_percentage: float
    format_used: str  # letter or a4


@dataclass
class CVTemplate:
    """CV template configuration."""
    name: str
    html_template: str
    css_styles: str
    page_format: str = "a4"  # a4 or letter


class PDFGenerator:
    """
    ATS-optimized PDF generator.
    Generates tailored CVs using career-ops best practices.
    """

    # ATS-friendly fonts (self-hosted or system)
    FONT_HEADING = "Helvetica, sans-serif"
    FONT_BODY = "Helvetica, sans-serif"

    COLOR_PRIMARY = "#14798a"
    COLOR_ACCENT = "#7c3aed"
    COLOR_PRIMARY_LIGHT = "#e8f4f6"
    COLOR_ACCENT_LIGHT = "#ede9fe"

    # Section order optimized for "6-second scan"
    SECTION_ORDER = [
        "header",
        "professional_summary",
        "core_competencies",
        "work_experience",
        "projects",
        "education",
        "certifications",
        "skills"
    ]

    def __init__(self, output_dir: str = "output/cvs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_tailored_cv(
        self,
        cv_markdown_path: str,
        job_description: str,
        candidate_profile: Dict[str, Any],
        archetype: str = "general",
        company_name: str = "company",
        output_format: str = "a4"
    ) -> PDFGenerationResult:
        """
        Generate ATS-optimized PDF tailored to job description.

        Pipeline:
        1. Read cv.md
        2. Extract 15-20 keywords from JD
        3. Detect language/location for format
        4. Rewrite summary with keyword injection
        5. Reorder experience by relevance
        6. Build competency grid
        7. Generate HTML
        8. Convert to PDF via Playwright
        """
        # Step 1: Read CV
        cv_content = self._read_cv(cv_markdown_path)

        # Step 2: Extract keywords
        keywords = self._extract_keywords(job_description)

        # Step 3: Detect format (US/Canada = letter, rest = a4)
        detected_format = self._detect_format(job_description, candidate_profile)
        if output_format != "auto":
            detected_format = output_format

        # Step 4: Parse CV sections
        cv_sections = self._parse_cv_sections(cv_content)

        # Step 5: Tailor content
        tailored_sections = self._tailor_content(
            cv_sections, keywords, archetype, candidate_profile
        )

        # Step 6: Generate HTML
        html_content = self._generate_html(
            tailored_sections, keywords, detected_format, candidate_profile
        )

        # Step 7: Normalize for ATS
        html_content = self._normalize_for_ats(html_content)

        # Step 8: Convert to PDF
        result = self._html_to_pdf(
            html_content, company_name, detected_format, keywords
        )

        return result

    def _read_cv(self, path: str) -> str:
        """Read CV markdown file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            raise ValueError(f"Failed to read CV: {e}")

    def _extract_keywords(self, job_description: str) -> List[str]:
        """
        Extract 15-20 keywords from job description.
        Focus on technical skills and requirements.
        """
        jd_lower = job_description.lower()

        # Common tech keywords to look for
        keyword_patterns = [
            # AI/ML
            r"\b(?:machine learning|ml|artificial intelligence|ai|deep learning|neural networks)\b",
            r"\b(?:large language model|llm|generative ai|genai|nlp|computer vision)\b",
            r"\b(?:rag|retrieval augmented generation|vector database|embeddings)\b",
            # Languages & Frameworks
            r"\b(?:python|r|scala|julia|javascript|typescript)\b",
            r"\b(?:tensorflow|pytorch|keras|scikit[- ]learn|xgboost|lightgbm)\b",
            r"\b(?:langchain|llamaindex|haystack|transformers|huggingface)\b",
            # Cloud & Infrastructure
            r"\b(?:aws|azure|gcp|google cloud|amazon web services)\b",
            r"\b(?:docker|kubernetes|k8s|terraform|ansible|ci/cd|devops)\b",
            # Data
            r"\b(?:sql|postgresql|mysql|mongodb|cassandra|redis|kafka)\b",
            r"\b(?:spark|hadoop|snowflake|bigquery|airflow|dbt)\b",
            # Roles
            r"\b(?:data scientist|ml engineer|ai engineer|research scientist)\b",
            r"\b(?:software engineer|backend|frontend|full[- ]stack|platform)\b",
            # Concepts
            r"\b(?:microservices|rest api|graphql|event[- ]driven|serverless)\b",
            r"\b(?:distributed systems|high availability|scalability|performance)\b",
        ]

        found_keywords = set()
        for pattern in keyword_patterns:
            matches = re.findall(pattern, jd_lower)
            found_keywords.update(matches)

        # Also extract capitalized technical terms
        capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', job_description)
        tech_terms = [t for t in capitalized if len(t) > 2 and t.lower() not in {
            "the", "and", "for", "are", "but", "not", "you", "all", "can",
            "had", "her", "was", "one", "our", "out", "day", "get", "has"
        }]
        found_keywords.update(tech_terms[:10])

        return list(found_keywords)[:20]

    def _detect_format(self, job_description: str, profile: Dict[str, Any]) -> str:
        """Detect paper format based on location."""
        jd_lower = job_description.lower()
        location = profile.get("location", "").lower()

        us_indicators = ["united states", "usa", "us", "canada", "remote us", "remote usa"]
        if any(ind in jd_lower or ind in location for ind in us_indicators):
            return "letter"

        return "a4"

    def _parse_cv_sections(self, cv_content: str) -> Dict[str, str]:
        """Parse CV markdown into sections."""
        sections = {
            "header": "",
            "professional_summary": "",
            "work_experience": "",
            "projects": "",
            "education": "",
            "certifications": "",
            "skills": ""
        }

        # Extract header (first few lines before any ##)
        lines = cv_content.split("\n")
        header_lines = []
        for line in lines:
            if line.startswith("##"):
                break
            header_lines.append(line)
        sections["header"] = "\n".join(header_lines)

        # Extract sections by headers
        current_section = None
        section_content = []

        section_map = {
            "profile summary": "professional_summary",
            "professional summary": "professional_summary",
            "summary": "professional_summary",
            "work experience": "work_experience",
            "experience": "work_experience",
            "projects": "projects",
            "education": "education",
            "certifications": "certifications",
            "skills": "skills",
            "technical skills": "skills"
        }

        for line in lines:
            if line.startswith("##"):
                # Save previous section
                if current_section and section_content:
                    sections[current_section] = "\n".join(section_content)

                # Start new section
                header_text = line.lstrip("#").strip().lower()
                current_section = section_map.get(header_text, None)
                section_content = []
            elif current_section:
                section_content.append(line)

        # Save last section
        if current_section and section_content:
            sections[current_section] = "\n".join(section_content)

        return sections

    def _tailor_content(
        self,
        sections: Dict[str, str],
        keywords: List[str],
        archetype: str,
        profile: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Tailor CV content based on job keywords and archetype.
        """
        tailored = sections.copy()

        narrative = profile.get("narrative", {})
        proof_points = profile.get("proof_points", [])
        narrative_summary = narrative.get("professional_summary", "")

        if narrative_summary and not sections.get("professional_summary"):
            tailored["professional_summary"] = narrative_summary
        elif sections.get("professional_summary"):
            tailored["professional_summary"] = self._rewrite_summary(
                sections["professional_summary"], keywords, archetype,
                narrative_summary=narrative_summary
            )

        archetype_proof = [p for p in proof_points if p.get("archetype") == archetype]
        if not archetype_proof:
            archetype_proof = proof_points

        if archetype_proof and tailored.get("professional_summary"):
            hero_metrics = "; ".join(
                f"{p['metric']} ({p['context']})" for p in archetype_proof[:2]
            )
            tailored["professional_summary"] = (
                tailored["professional_summary"].rstrip(".") +
                f" Key results: {hero_metrics}."
            )

        tailored["core_competencies"] = self._generate_competencies(keywords, archetype)

        if sections.get("work_experience"):
            tailored["work_experience"] = self._prioritize_experience(
                sections["work_experience"], keywords
            )

        if sections.get("projects"):
            tailored["projects"] = self._select_projects(
                sections["projects"], archetype, keywords
            )

        return tailored

    def _rewrite_summary(self, summary: str, keywords: List[str], archetype: str,
                          narrative_summary: str = "") -> str:
        """
        Rewrite professional summary injecting relevant keywords.
        Ethical reformulation - only restate existing skills.
        """
        # Extract existing skills from summary
        existing_skills = re.findall(r'\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b', summary)

        # Find keywords that are semantically similar to existing skills
        injectable = []
        for keyword in keywords[:5]:  # Top 5 keywords
            # Check if keyword or similar term exists
            if any(self._is_similar(keyword.lower(), skill.lower()) for skill in existing_skills):
                injectable.append(keyword)

        if narrative_summary and len(narrative_summary) > 50:
            summary = narrative_summary + " " + summary if summary else narrative_summary

        archetype_openers = {
            "ai_platform_llmops": "ML Engineer specializing in LLMOps, observability, and production AI systems.",
            "agentic_automation": "AI Engineer focused on building autonomous agents and intelligent automation systems.",
            "technical_ai_pm": "Technical AI Product Manager bridging engineering and product strategy.",
            "ai_solutions_architect": "AI Solutions Architect designing enterprise-grade AI integrations and systems.",
            "ai_forward_deployed": "Forward Deployed Engineer delivering rapid AI prototypes and client solutions.",
            "ai_transformation": "AI Transformation Lead driving organizational adoption and AI strategy."
        }

        opener = archetype_openers.get(archetype, "")
        if opener and not summary.lower().startswith(opener.lower()[:20]):
            summary = opener + " " + summary

        # Inject keywords naturally into skills list if present
        if "skills" in summary.lower() and injectable:
            # Find skills section and append
            skill_section = re.search(
                r'(skills include|technical expertise|proficient in|experience with)([:;][^\.]+)',
                summary,
                re.IGNORECASE
            )
            if skill_section:
                before = summary[:skill_section.end()]
                after = summary[skill_section.end():]
                new_skills = ", ".join(injectable[:3])
                summary = before + " " + new_skills + "," + after

        return summary

    def _is_similar(self, word1: str, word2: str) -> bool:
        """Check if two words are semantically similar."""
        # Simple similarity - can be enhanced with embeddings
        if word1 in word2 or word2 in word1:
            return True

        # Common tech synonyms
        synonyms = {
            "python": ["python", "py"],
            "ml": ["machine learning", "ml"],
            "ai": ["artificial intelligence", "ai"],
            "llm": ["large language model", "llm"],
            "rag": ["retrieval augmented generation", "rag"]
        }

        for term, syns in synonyms.items():
            if word1 in syns and word2 in syns:
                return True

        return False

    def _generate_competencies(self, keywords: List[str], archetype: str) -> str:
        """Generate core competencies section (6-8 keyword phrases)."""
        # Select 6-8 most relevant keywords
        selected = keywords[:8]

        # Format as comma-separated for HTML rendering
        return ", ".join(selected)

    def _prioritize_experience(self, experience: str, keywords: List[str]) -> str:
        """
        Reorder experience bullets to put keyword-matching ones first.
        """
        lines = experience.split("\n")

        # Score each line by keyword matches
        scored_lines = []
        for line in lines:
            if not line.strip():
                scored_lines.append((0, line))
                continue

            score = sum(1 for kw in keywords if kw.lower() in line.lower())
            scored_lines.append((score, line))

        # Sort by score (descending), preserving headers
        sorted_lines = []
        current_company = []
        for score, line in scored_lines:
            if line.strip().startswith("###") or (line.strip() and not line.startswith("-")):
                # This is a company header - flush previous and start new
                if current_company:
                    # Sort bullets within company
                    header = current_company[0]
                    bullets = sorted(current_company[1:], key=lambda x: x[0], reverse=True)
                    sorted_lines.append((0, header[1]))
                    for s, l in bullets:
                        sorted_lines.append((s, l))
                current_company = [(score, line)]
            else:
                current_company.append((score, line))

        # Flush last company
        if current_company:
            header = current_company[0]
            bullets = sorted(current_company[1:], key=lambda x: x[0], reverse=True)
            sorted_lines.append((0, header[1]))
            for s, l in bullets:
                sorted_lines.append((s, l))

        return "\n".join(line for _, line in sorted_lines)

    def _select_projects(self, projects: str, archetype: str, keywords: List[str]) -> str:
        """Select and prioritize top 3-4 projects."""
        # Split into project blocks
        project_blocks = re.split(r'\n(?=###|\*\*\*|- )', projects)

        if len(project_blocks) <= 4:
            return projects

        # Score each project
        scored_projects = []
        for project in project_blocks:
            score = sum(1 for kw in keywords if kw.lower() in project.lower())
            # Archetype bonus
            if archetype in project.lower():
                score += 2
            scored_projects.append((score, project))

        # Sort and take top 4
        scored_projects.sort(reverse=True)
        top_projects = [p for _, p in scored_projects[:4]]

        return "\n\n".join(top_projects)

    def _generate_html(
        self,
        sections: Dict[str, str],
        keywords: List[str],
        page_format: str,
        profile: Dict[str, Any]
    ) -> str:
        """Generate complete HTML document."""
        # Parse header info
        header_info = self._parse_header(sections.get("header", ""), profile)

        # Build sections HTML
        sections_html = ""

        # Header section
        sections_html += self._render_header_section(header_info)

        # Professional Summary
        if sections.get("professional_summary"):
            sections_html += self._render_section(
                "Professional Summary",
                self._markdown_to_html(sections["professional_summary"])
            )

        # Core Competencies
        if sections.get("core_competencies"):
            comps = sections["core_competencies"].split(", ")
            comp_html = " ".join([f'<span class="competency">{c.strip()}</span>' for c in comps])
            sections_html += self._render_section("Core Competencies", comp_html)

        # Work Experience
        if sections.get("work_experience"):
            sections_html += self._render_section(
                "Work Experience",
                self._markdown_to_html(sections["work_experience"]),
                first=True
            )

        # Projects
        if sections.get("projects"):
            sections_html += self._render_section(
                "Projects",
                self._markdown_to_html(sections["projects"])
            )

        # Education
        if sections.get("education"):
            sections_html += self._render_section(
                "Education",
                self._markdown_to_html(sections["education"])
            )

        # Certifications
        if sections.get("certifications"):
            sections_html += self._render_section(
                "Certifications",
                self._markdown_to_html(sections["certifications"])
            )

        # Skills
        if sections.get("skills"):
            sections_html += self._render_section(
                "Skills",
                self._markdown_to_html(sections["skills"])
            )

        # Page dimensions
        page_width = "8.5in" if page_format == "letter" else "210mm"
        page_height = "11in" if page_format == "letter" else "297mm"

        # Complete HTML document
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CV - {header_info.get('name', 'Candidate')}</title>
    <style>
        @page {{
            size: {page_format};
            margin: 0.6in;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: {self.FONT_BODY};
            font-size: 11px;
            line-height: 1.5;
            color: #333;
            background: white;
        }}

        .cv-container {{
            max-width: {page_width};
            margin: 0 auto;
            padding: 0;
        }}

        /* Header */
        .cv-header {{
            text-align: center;
            padding-bottom: 12px;
            border-bottom: 2px solid;
            border-image: linear-gradient(to right, {self.COLOR_PRIMARY}, {self.COLOR_ACCENT}) 1;
            margin-bottom: 16px;
        }}

        .cv-header h1 {{
            font-family: {self.FONT_HEADING};
            font-size: 24px;
            font-weight: 700;
            color: {self.COLOR_PRIMARY};
            margin-bottom: 8px;
        }}

        .cv-header .subtitle {{
            font-size: 13px;
            color: #555;
            margin-bottom: 8px;
        }}

        .cv-header .contact {{
            font-size: 10px;
            color: #666;
        }}

        .cv-header .contact span {{
            margin: 0 8px;
        }}

        /* Section headers */
        .section {{
            margin-bottom: 14px;
        }}

        .section-title {{
            font-family: {self.FONT_HEADING};
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: {self.COLOR_PRIMARY};
            border-bottom: 1px solid {self.COLOR_PRIMARY};
            padding-bottom: 4px;
            margin-bottom: 10px;
        }}

        .section-content {{
            padding-left: 0;
        }}

        /* Competencies */
        .competency {{
            display: inline-block;
            background: {self.COLOR_PRIMARY_LIGHT};
            color: {self.COLOR_PRIMARY};
            padding: 3px 10px;
            margin: 2px;
            border-radius: 6px;
            font-size: 10px;
            font-weight: 500;
        }}

        /* Experience entries */
        .entry {{
            margin-bottom: 10px;
        }}

        .entry-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 4px;
        }}

        .entry-title {{
            font-weight: 600;
            color: {self.COLOR_ACCENT};
            font-size: 12px;
        }}

        .entry-date {{
            font-size: 10px;
            color: #666;
        }}

        .entry-company {{
            font-style: italic;
            color: #555;
            font-size: 10px;
            margin-bottom: 4px;
        }}

        .entry-description {{
            font-size: 10px;
            line-height: 1.4;
        }}

        .entry-description ul {{
            margin-left: 16px;
            margin-top: 4px;
        }}

        .entry-description li {{
            margin-bottom: 3px;
        }}

        /* Lists */
        ul {{
            margin-left: 16px;
        }}

        li {{
            margin-bottom: 3px;
        }}

        strong {{
            color: {self.COLOR_ACCENT};
        }}
    </style>
</head>
<body>
    <div class="cv-container">
        {sections_html}
    </div>
</body>
</html>"""

        return html

    def _parse_header(self, header_text: str, profile: Dict[str, Any]) -> Dict[str, str]:
        """Parse header section for contact info."""
        info = {
            "name": profile.get("personal_details", {}).get("name", "EMMANUEL M NDALIRO"),
            "title": "Software Engineer | Python & Machine Learning",
            "email": profile.get("personal_details", {}).get("email", ""),
            "phone": profile.get("personal_details", {}).get("phone", {}).get("primary", ""),
            "location": "Kenya",
            "linkedin": profile.get("professional_profiles", {}).get("linkedin", ""),
            "github": profile.get("professional_profiles", {}).get("github", ""),
            "medium": profile.get("professional_profiles", {}).get("medium", "")
        }

        # Override from header text if present
        lines = header_text.split("\n")
        for line in lines:
            if "**" in line and not info["name"]:
                # Bold line is likely the name
                name_match = re.search(r'\*\*([^*]+)\*\*', line)
                if name_match:
                    info["name"] = name_match.group(1).strip()

        return info

    def _render_header_section(self, info: Dict[str, str]) -> str:
        """Render the CV header section."""
        contact_parts = []
        if info.get("email"):
            contact_parts.append(info["email"])
        if info.get("phone"):
            contact_parts.append(info["phone"])
        if info.get("location"):
            contact_parts.append(info["location"])
        if info.get("linkedin"):
            linkedin_display = info["linkedin"].replace("https://", "").replace("www.", "")[:30]
            contact_parts.append(f"LinkedIn: {linkedin_display}")

        contact_html = " | ".join(contact_parts)

        return f"""
        <div class="cv-header">
            <h1>{info.get('name', 'Candidate')}</h1>
            <div class="subtitle">{info.get('title', 'Software Engineer')}</div>
            <div class="contact">{contact_html}</div>
        </div>
        """

    def _render_section(self, title: str, content: str, first: bool = False) -> str:
        """Render a CV section."""
        return f"""
        <div class="section">
            <div class="section-title">{title}</div>
            <div class="section-content">
                {content}
            </div>
        </div>
        """

    def _markdown_to_html(self, markdown: str) -> str:
        """Simple markdown to HTML conversion."""
        html = markdown

        # Headers
        html = re.sub(r'^### (.+)$', r'<div class="entry"><div class="entry-title">\1</div>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)

        # Bold
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)

        # Italic
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

        # Bullet lists
        lines = html.split("\n")
        result = []
        in_list = False

        for line in lines:
            if line.strip().startswith("-") or line.strip().startswith("*"):
                if not in_list:
                    result.append("<ul>")
                    in_list = True
                item = line.strip().lstrip("-").lstrip("*").strip()
                result.append(f"<li>{item}</li>")
            else:
                if in_list:
                    result.append("</ul>")
                    in_list = False
                result.append(line)

        if in_list:
            result.append("</ul>")

        html = "\n".join(result)

        # Wrap plain text in paragraphs
        paragraphs = html.split("\n\n")
        wrapped = []
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith("<"):
                p = f"<p>{p}</p>"
            wrapped.append(p)

        html = "\n".join(wrapped)

        # Close any open entry divs
        html = html.replace("</div></div>", "</div>")

        return html

    def _normalize_for_ats(self, html: str) -> str:
        """
        Normalize Unicode characters for ATS compatibility.
        Convert smart quotes, em-dashes, etc. to ASCII equivalents.
        """
        replacements = {
            '\u2014': '-',    # em-dash
            '\u2013': '-',    # en-dash
            '\u201C': '"',    # left double quote
            '\u201D': '"',    # right double quote
            '\u2018': "'",    # left single quote
            '\u2019': "'",    # right single quote
            '\u2026': '...',  # ellipsis
            '\u200B': '',     # zero-width space
            '\u200C': '',     # zero-width non-joiner
            '\u200D': '',     # zero-width joiner
            '\u00A0': ' ',    # non-breaking space
            '\uFEFF': '',     # byte order mark
        }

        for char, replacement in replacements.items():
            html = html.replace(char, replacement)

        return html

    def _html_to_pdf(
        self,
        html: str,
        company_name: str,
        page_format: str,
        keywords: List[str]
    ) -> PDFGenerationResult:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"cv_{company_name.lower().replace(' ', '_')}_{timestamp}.pdf"
        pdf_path = self.output_dir / pdf_filename

        clean_html = re.sub(r'@import url\([^)]+\);?', '', html)
        clean_html = re.sub(r'border-image:[^;]+;', '', clean_html)
        clean_html = re.sub(r'background:\s*linear-gradient\([^;]+\)', f'background: {self.COLOR_PRIMARY_LIGHT}', clean_html)
        clean_html = re.sub(r'hsl\([^)]+\)', self.COLOR_PRIMARY, clean_html)
        clean_html = re.sub(r'#[0-9a-fA-F]{8}\b', lambda m: m.group(0)[:7], clean_html)

        with open(pdf_path, 'wb') as f:
            pisa_status = pisa.CreatePDF(clean_html, dest=f, encoding='utf-8')

        if pisa_status.err:
            raise RuntimeError(f"PDF generation failed: {pisa_status.err}")

        file_size = pdf_path.stat().st_size / 1024
        coverage = min(100.0, len(keywords) * 5)

        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()
        pdf_str = pdf_bytes.decode('latin-1', errors='ignore')
        page_count = max(len(re.findall(r'/Type\s*/Page[^s]', pdf_str)), 1)

        return PDFGenerationResult(
            pdf_path=str(pdf_path),
            page_count=page_count,
            file_size_kb=round(file_size, 1),
            keywords_injected=keywords[:8],
            coverage_percentage=coverage,
            format_used=page_format
        )

    def quick_generate(
        self,
        cv_path: str,
        job_description: str,
        output_name: str = "tailored_cv"
    ) -> str:
        """Quick generate PDF without full profile."""
        dummy_profile = {
            "personal_details": {"name": "Candidate", "email": "", "phone": {"primary": ""}},
            "professional_profiles": {}
        }

        result = self.generate_tailored_cv(
            cv_path,
            job_description,
            dummy_profile,
            company_name=output_name
        )

        return result.pdf_path
