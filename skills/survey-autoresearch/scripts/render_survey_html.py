#!/usr/bin/env python3
"""Render a survey candidate markdown file to a reusable light-themed HTML page."""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "assets" / "survey_template.html"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip().lower()).strip("-")
    return slug or "section"


def ref_id(value: str) -> str:
    return "ref-" + slugify(value)


def render_inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>', escaped)
    escaped = re.sub(
        r"\[@([A-Za-z0-9_:\-]+)\]",
        lambda m: f'<a class="citation-link" href="#{ref_id(m.group(1))}">[{html.escape(m.group(1))}]</a>',
        escaped,
    )
    escaped = re.sub(
        r"(?<![A-Za-z0-9_:\-])@([A-Za-z0-9_:\-]+)",
        lambda m: f'<a class="citation-link" href="#{ref_id(m.group(1))}">@{html.escape(m.group(1))}</a>',
        escaped,
    )
    escaped = re.sub(
        r"\b([Pp]\d{3})\b",
        lambda m: f'<a class="citation-link" href="#{ref_id(m.group(1))}">{html.escape(m.group(1))}</a>',
        escaped,
    )
    return escaped


def render_table(lines: list[str]) -> str:
    rows = []
    for raw in lines:
        cells = [render_inline(cell.strip()) for cell in raw.strip().strip("|").split("|")]
        rows.append(cells)
    if len(rows) < 2:
        return ""
    header = "".join(f"<th>{cell}</th>" for cell in rows[0])
    body_rows = rows[2:] if re.match(r"^\s*:?-{3,}:?\s*$", rows[1][0] if rows[1] else "") else rows[1:]
    body = "\n".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in body_rows)
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def render_markdown(markdown: str) -> tuple[str, list[dict]]:
    html_parts: list[str] = []
    headings: list[dict] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    table_lines: list[str] = []
    in_code = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            html_parts.append(f"<p>{render_inline(' '.join(paragraph).strip())}</p>")
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            html_parts.append("<ul>" + "".join(f"<li>{item}</li>" for item in list_items) + "</ul>")
            list_items = []

    def flush_table() -> None:
        nonlocal table_lines
        if table_lines:
            html_parts.append(render_table(table_lines))
            table_lines = []

    for line in markdown.splitlines():
        if line.strip().startswith("```"):
            flush_paragraph()
            flush_list()
            flush_table()
            if in_code:
                html_parts.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        heading = re.match(r"^(#{1,4})\s+(.+?)\s*$", line)
        if heading:
            flush_paragraph()
            flush_list()
            flush_table()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            section_id = slugify(title)
            headings.append({"level": level, "title": title, "id": section_id})
            html_parts.append(f'<h{level} id="{section_id}">{render_inline(title)}</h{level}>')
            continue
        if line.strip().startswith("|") and line.strip().endswith("|"):
            flush_paragraph()
            flush_list()
            table_lines.append(line)
            continue
        flush_table()
        bullet = re.match(r"^\s*[-*]\s+(.+)$", line)
        if bullet:
            flush_paragraph()
            list_items.append(render_inline(bullet.group(1).strip()))
            continue
        if not line.strip():
            flush_paragraph()
            flush_list()
            continue
        flush_list()
        paragraph.append(line.strip())

    flush_paragraph()
    flush_list()
    flush_table()
    if in_code:
        html_parts.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    return "\n".join(part for part in html_parts if part), headings


def parse_bibtex(path: Path) -> list[dict]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    entries = []
    for match in re.finditer(r"@\w+\s*\{\s*([^,]+),([\s\S]*?)(?=^\s*@|\Z)", text, flags=re.MULTILINE):
        key = match.group(1).strip()
        body = match.group(2)
        entry = {"paper_id": key, "citation_key": key}
        for field in ["title", "author", "year", "venue", "journal", "booktitle", "url", "doi", "arxiv"]:
            found = re.search(field + r"\s*=\s*[\{\"]([^}\"]+)[}\"]", body, flags=re.IGNORECASE)
            if found:
                entry[field] = found.group(1).strip()
        entries.append(entry)
    return entries


def best_url(paper: dict) -> str:
    for key in ["doi_url", "arxiv_url", "openreview_url", "publisher_url", "url", "source_url", "dblp_url", "semantic_scholar_url"]:
        value = str(paper.get(key) or "").strip()
        if value.startswith("http"):
            return value
    doi = str(paper.get("doi") or "").strip()
    if doi:
        return doi if doi.startswith("http") else f"https://doi.org/{doi}"
    arxiv = str(paper.get("arxiv_id") or paper.get("arxiv") or "").strip()
    if arxiv:
        return arxiv if arxiv.startswith("http") else f"https://arxiv.org/abs/{arxiv}"
    sources = paper.get("verified_sources") or []
    if isinstance(sources, list):
        for item in sources:
            if isinstance(item, str) and item.startswith("http"):
                return item
            if isinstance(item, dict):
                value = str(item.get("url") or item.get("source_url") or "").strip()
                if value.startswith("http"):
                    return value
    return ""


def merge_references(papers: list[dict], bib_entries: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for entry in bib_entries:
        key = str(entry.get("paper_id") or entry.get("citation_key") or entry.get("title") or "").strip()
        if key:
            merged[key] = dict(entry)
    for paper in papers:
        key = str(paper.get("paper_id") or paper.get("citation_key") or paper.get("title") or "").strip()
        if not key:
            continue
        current = merged.get(key, {})
        current.update({k: v for k, v in paper.items() if v not in (None, "", [])})
        merged[key] = current
    return list(merged.values())


def render_references(references: list[dict]) -> str:
    if not references:
        return '<div class="reference-item">No cited paper metadata was available.</div>'
    items = []
    for paper in references:
        title = str(paper.get("title") or paper.get("paper_id") or "Untitled paper")
        keys = [
            str(paper.get("paper_id") or "").strip(),
            str(paper.get("citation_key") or "").strip(),
            str(paper.get("bibtex_key") or "").strip(),
        ]
        anchor_key = next((key for key in keys if key), title)
        authors = paper.get("authors") or paper.get("author") or ""
        if isinstance(authors, list):
            authors = ", ".join(str(author) for author in authors[:8])
        year = str(paper.get("year") or "")
        venue = str(paper.get("venue") or paper.get("journal") or paper.get("booktitle") or paper.get("venue_status") or "")
        url = best_url(paper)
        title_html = f'<a href="{html.escape(url, quote=True)}">{html.escape(title)}</a>' if url else html.escape(title)
        limited = "" if url else '<span class="source-limited">source-limited</span>'
        meta = " · ".join(part for part in [str(authors), year, venue] if part)
        items.append(
            f'<div class="reference-item" id="{html.escape(ref_id(anchor_key), quote=True)}">'
            f'<div class="reference-title">{title_html}{limited}</div>'
            f'<div class="reference-meta">{html.escape(meta)}</div>'
            '</div>'
        )
    return "\n".join(items)


def render_toc(headings: list[dict]) -> str:
    links = []
    for heading in headings:
        if heading["level"] <= 3:
            indent = " style=\"padding-left: 12px\"" if heading["level"] == 3 else ""
            links.append(f'<a href="#{heading["id"]}"{indent}>{html.escape(heading["title"])}</a>')
    return "\n".join(links) or '<a href="#references">References</a>'


def render_survey_html(
    task_dir: Path,
    template_path: Path = DEFAULT_TEMPLATE,
    markdown_name: str = "survey_candidate.md",
    output_name: str = "survey_candidate.html",
) -> Path:
    state = task_dir / "state"
    outputs = task_dir / "outputs"
    markdown_path = outputs / markdown_name
    output_path = outputs / output_name
    markdown = markdown_path.read_text(encoding="utf-8")
    content, headings = render_markdown(markdown)
    title = headings[0]["title"] if headings else "Survey"
    subtitle = "Generated survey article with cited paper links"
    references = merge_references(read_jsonl(state / "papers.jsonl"), parse_bibtex(outputs / "references.bib"))
    template = template_path.read_text(encoding="utf-8")
    html_text = (
        template
        .replace("{{title}}", html.escape(title))
        .replace("{{subtitle}}", html.escape(f"{subtitle} · {datetime.now(timezone.utc).date().isoformat()}"))
        .replace("{{toc}}", render_toc(headings))
        .replace("{{content}}", content)
        .replace("{{references}}", render_references(references))
    )
    output_path.write_text(html_text, encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--markdown-name", default="survey_candidate.md")
    parser.add_argument("--output-name", default="survey_candidate.html")
    args = parser.parse_args()
    print(render_survey_html(args.task_dir, args.template, args.markdown_name, args.output_name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
