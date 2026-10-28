from __future__ import annotations

import json
from typing import Any, Callable

from backend.artifacts.filesystem import ArtifactRun
from backend.pipelines.authorship import add_author_credit
from backend.pipelines.common import (
    PipelineError,
    PipelineResult,
    extract_fenced_or_raw,
    format_citations,
    format_log,
)
from backend.pipelines.html_to_pdf import (
    A4_PAGE,
    ConvertError,
    HtmlToPdfConverter,
)
from backend.providers.base import (
    ModelProviderError,
    TextGenerationProvider,
    TextGenerationRequest,
)
from backend.timing import RunTimingRecorder, measure_stage


DEPLOYMENT_REPORT_INSTRUCTIONS = """\
For the BA3073 take-home assignment, "From AI Agent to Cloud Service", write an
evidence-led technical deployment report. Apply these requirements when the task
requests this assignment report; preserve the requested topic for other essays.

Structure and page budget (maximum 20 A4 pages including all front matter,
screenshots, references, and appendices; aim for 12-16 pages):
1. Title, supplied student identity, date, and a concise executive summary.
   Omit identity details that were not supplied.
2. System architecture: browser /ui/ -> Nginx HTTPS and proxy access control ->
   FastAPI:14242 -> SQLite and workspace bind mounts; the backend calls a
   Qwen-compatible API and Playwright/Chromium renders self-contained HTML to PDF.
   Explain source -> Dockerfile -> Linux image -> local test -> Alibaba Cloud ACR
   -> ECS pull/run -> domain, including what each component does.
3. Task 1 (40 marks): local Docker build and launch, health and UI verification,
   local-ui-check.txt, and a browser screenshot with its address bar visible.
   Explain the improvements made to essay_html.py instructions and how they
   improve structure, clarity, technical accuracy, and evidence use. Describe
   generating this report through the deployed AI Learning Assistant.
4. Task 2 (40 marks): actual Linux image architecture/tag/digest when supplied,
   ACR push/pull, ECS OS and deployment commands, data/workspace persistence,
   Docker health/port mapping, and ecs-docker-check.txt. Explain the temporary
   14242:14242 mapping and security-group restriction to the student's public
   IP /32. Include the ECS public-IP /ui/ browser screenshot and address bar.
5. Task 3 (20 marks): actual domain and DNS A record, Nginx reverse proxy,
   Certbot certificate and renewal verification, HTTP-to-HTTPS redirect, and
   separate reverse-proxy access control such as Basic Authentication.
   Explain that proxy authentication and the application's BNBU login are
   independent. Include the supplied HTTPS domain URL and a screenshot of
   successful access after the proxy check with its address bar visible.
   Record unauthenticated rejection and authenticated success separately.
   Explain removal of the public 14242 rule and binding the backend to
   127.0.0.1:14242 behind Nginx, with inbound 80/443 allowed as required.
6. Verification and troubleshooting: concise evidence matrix (requirement,
   procedure, observed result, evidence filename/figure), actual errors and
   resolutions, and restart-persistence checks when performed. Distinguish
   an HTTP 200 check from browser rendering and real model/PDF generation.
7. Security, costs, limitations, and improvements: weak teaching auth, HTTPS,
   least-privilege SSH/firewalls, encrypted personal API keys and the separate
   master key, private shared-secret file, backups, certificate renewal,
   synchronous generation/timeouts, rate limits, and monitoring. Explain ECS,
   storage, network, domain, and model-token cost drivers; use measured/account
   figures only when supplied, otherwise describe costs without inventing prices.
8. Conclusion, references to supplied/verified sources, and a compact submission
   checklist: report, whole-project GitHub URL, local-ui-check.txt, and
   ecs-docker-check.txt. Exclude secrets, data/, workspace/, and dependencies
   from the source-code submission.

Evidence and writing rules:
- Ground every completed-action claim in supplied logs, configuration, run
  metadata, or screenshots. Never invent an ECS IP, domain, repository URL,
  image digest, command output, certificate, test result, cost, or screenshot.
- If evidence is absent, label it "Not verified" or "Pending evidence" and
  state exactly what is needed. A proposed command is not proof it was run.
- Give each real screenshot a numbered figure caption explaining what it proves
  and its source filename. Preserve the browser address bar. Embed image bytes
  as data URIs only if supplied; never manufacture a screenshot or use a local
  path as though the renderer could access it. If only a filename is supplied,
  identify the missing image explicitly instead of making a broken <img>.
- Never reproduce API keys, passwords, bearer tokens, private keys, raw secret
  files, or account billing details. Redact sensitive parts of evidence.
- Write clear, concise technical prose in the requested language. Explain why
  commands/settings are needed, distinguish host/container ports and local/ECS
  execution, and separate observed outcomes from proposed improvements.
- Use short command excerpts, tables, and inline SVG architecture diagrams where
  useful. Use readable 10.5-11pt body text and compact captions; prevent split
  figures and table rows with print break controls. Avoid giant code dumps,
  excessive forced page breaks, clipped content, and tiny fonts. The final PDF
  page count must be checked after rendering; do not claim a count without it.
"""


def run_essay_html_pipeline(
    *,
    artifact_run: ArtifactRun,
    model_profile: dict[str, Any],
    model_provider: TextGenerationProvider,
    pdf_converter: HtmlToPdfConverter,
    task_text: str,
    context_bundle: str,
    output_preference: str | None,
    options: dict[str, Any] | None,
    search: dict[str, Any],
    max_output_tokens: int,
    emit_event: Callable[[str, str], None] | None = None,
    timing: RunTimingRecorder | None = None,
) -> PipelineResult:
    log_lines = [
        "Pipeline: essay_html",
        f"Output preference: {output_preference or 'pdf'}",
        "Stage: generate_source",
    ]
    system_prompt, user_prompt = build_essay_html_prompt(
        task_text=task_text,
        context_bundle=context_bundle,
        options=options or {},
        search=search,
    )
    if emit_event:
        emit_event("generate_source", "Generating essay HTML source")

    try:
        with measure_stage(timing, "provider_generation"):
            raw_output = model_provider.generate_text(
                TextGenerationRequest(
                    profile=model_profile,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_output_tokens=max_output_tokens,
                    temperature=0.2,
                )
            )
    except ModelProviderError as exc:
        raise PipelineError(
            exc.code,
            exc.message,
            stage="generate_source",
            log_lines=log_lines,
        ) from exc
    except Exception as exc:
        raise PipelineError(
            "provider_unavailable",
            "The model provider request failed.",
            stage="generate_source",
            log_lines=log_lines,
        ) from exc

    source = extract_fenced_or_raw(raw_output, accepted_languages={"html", "htm"})
    source = add_author_credit(source.strip()) + "\n"
    html_path = artifact_run.write_output(
        "main.html",
        source,
        kind="source",
        media_type="text/html",
    )
    log_lines.extend(["Output: output/main.html", "Stage: convert_pdf"])
    if emit_event:
        emit_event("convert_pdf", "Converting essay HTML to PDF")

    pdf_path = artifact_run.run_dir / "output" / "main.pdf"
    try:
        with measure_stage(timing, "convert_pdf"):
            convert_result = pdf_converter.convert(
                html_path=html_path,
                pdf_path=pdf_path,
                page_config=A4_PAGE,
            )
    except ConvertError as exc:
        artifact_run.write_log("convert.log", exc.log_text)
        raise PipelineError(
            "convert_failed",
            exc.message,
            stage="convert_pdf",
            log_lines=log_lines,
        ) from exc
    except Exception as exc:
        artifact_run.write_log(
            "convert.log",
            "HTML-to-PDF converter raised an unexpected error.\n",
        )
        raise PipelineError(
            "convert_failed",
            "HTML-to-PDF conversion failed.",
            stage="convert_pdf",
            log_lines=log_lines,
        ) from exc

    artifact_run.write_log("convert.log", convert_result.log_text)
    artifact_run.write_output(
        "main.pdf",
        convert_result.pdf_path.read_bytes(),
        kind="pdf",
        media_type="application/pdf",
    )
    log_lines.extend(["Convert: pdf_ok", "Output: output/main.pdf"])
    return PipelineResult(log_text=format_log(log_lines))


def build_essay_html_prompt(
    *,
    task_text: str,
    context_bundle: str,
    options: dict[str, Any],
    search: dict[str, Any],
) -> tuple[str, str]:
    system_prompt = (
        "You are an expert teaching assistant writing complete academic essay and "
        "report deliverables as self-contained HTML documents. Return only the "
        "requested HTML source, with no surrounding explanation."
    )
    output_instruction = (
        "Return one complete self-contained HTML document. It must start with "
        "<!doctype html> and include <html>, <head>, and <body>. Include all CSS "
        "inside a <style> element: use a readable serif academic print layout, "
        "clear heading hierarchy, careful paragraph spacing, and CSS "
        "@page { size: A4; margin: 20mm; }. Do not use external stylesheet links, "
        "remote images, or remote HTTP(S) assets. If mathematical notation is "
        "needed, include inline KaTeX-compatible markup and any needed minimal "
        "KaTeX styling inline in the document; do not fetch KaTeX from a CDN at "
        "render time. Use inline SVG or CSS for diagrams. Cite any provided web "
        "sources in a References section using ordinary HTML. Do not wrap the "
        "answer in Markdown fences."
    )
    user_prompt = "\n\n".join(
        [
            "[Assignment Task]\n" + task_text.strip(),
            "[Prepared Context]\n" + context_bundle.strip(),
            "[Search Citations]\n" + format_citations(search),
            "[Options]\n" + json.dumps(options, sort_keys=True),
            "[BA3073 Deployment Report Instructions]\n" + DEPLOYMENT_REPORT_INSTRUCTIONS,
            "[Output Contract]\n" + output_instruction,
        ]
    )
    return system_prompt, user_prompt
