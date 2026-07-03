from __future__ import annotations

import logging
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.config.settings import get_settings
from app.utils.logging_config import configure_logging
from app.services.file_service import (
    load_dataframe,
    detect_email_column,
    build_output_dataframe,
    write_output_xlsx,
    NoEmailColumnFoundError,
    MultipleEmailColumnsError,
)
from app.workers.batch_processor import process_emails_batch
from app.dns import resolver as dns_resolver

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Enterprise-grade offline email validation (syntax, DNS/MX, disposable, "
    "role-based, risk scoring). No SMTP mailbox verification is performed - see /docs "
    "and the README for the mailbox-verification limitation.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_JOBS_DIR = Path(tempfile.gettempdir()) / "email_validator_jobs"
_JOBS_DIR.mkdir(exist_ok=True)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "dns_cache": dns_resolver.cache_stats()}


@app.post("/inspect-columns")
async def inspect_columns(file: UploadFile = File(...)) -> dict:
    """Upload a file and get back its column names, so a UI can let the
    user pick the email column when auto-detection is ambiguous."""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".csv", ".xlsx", ".xlsm"):
        raise HTTPException(400, "Only .csv and .xlsx files are supported")

    tmp_path = _JOBS_DIR / f"{uuid.uuid4().hex}{suffix}"
    with open(tmp_path, "wb") as fh:
        shutil.copyfileobj(file.file, fh)

    try:
        df = load_dataframe(tmp_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Could not read file: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    columns = list(df.columns)
    try:
        detected = detect_email_column(columns)
        candidates = [detected]
    except MultipleEmailColumnsError as exc:
        detected = None
        candidates = exc.candidates
    except NoEmailColumnFoundError:
        detected = None
        candidates = []

    return {
        "columns": columns,
        "detected_email_column": detected,
        "candidate_email_columns": candidates,
        "row_count": len(df),
    }


@app.post("/validate")
async def validate_file(
    file: UploadFile = File(...),
    email_column: Optional[str] = Form(None),
    check_dns: bool = Form(True),
    deep_dns_checks: bool = Form(True),
):
    """Upload a CSV/XLSX, validate every email, return an XLSX with
    validation results appended as new columns."""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".csv", ".xlsx", ".xlsm"):
        raise HTTPException(400, "Only .csv and .xlsx files are supported")

    job_id = uuid.uuid4().hex
    input_path = _JOBS_DIR / f"{job_id}{suffix}"
    output_path = _JOBS_DIR / f"{job_id}_validated.xlsx"

    with open(input_path, "wb") as fh:
        shutil.copyfileobj(file.file, fh)

    try:
        df = load_dataframe(input_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Could not read file: {exc}") from exc

    if len(df) > settings.max_upload_rows:
        raise HTTPException(
            413, f"File has {len(df)} rows, exceeding max of {settings.max_upload_rows}"
        )

    try:
        column = detect_email_column(list(df.columns), preferred=email_column)
    except MultipleEmailColumnsError as exc:
        raise HTTPException(
            422,
            f"Multiple possible email columns found: {exc.candidates}. "
            "Re-submit with 'email_column' set to one of these.",
        ) from exc
    except NoEmailColumnFoundError as exc:
        raise HTTPException(422, str(exc)) from exc

    # Some users paste row-like strings into a single cell, e.g.
    #   email@example.com | Name | https://example.com
    # In that case, validate only the left-most token.
    def _extract_email_cell(value: str) -> str:
        raw = (value or "").strip()
        if "|" in raw:
            raw = raw.split("|", 1)[0].strip()
        return raw

    emails = [
        _extract_email_cell(v) for v in df[column].fillna("").astype(str).tolist()
    ]

    logger.info("Validating %d emails from column '%s' (job=%s)", len(emails), column, job_id)
    results, summary = process_emails_batch(
        emails, check_dns=check_dns, deep_dns_checks=deep_dns_checks
    )

    output_df = build_output_dataframe(df, column, results)
    write_output_xlsx(output_df, output_path)

    input_path.unlink(missing_ok=True)

    return FileResponse(
        path=output_path,
        filename=f"validated_{Path(file.filename).stem}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "X-Total-Rows": str(summary.total_rows),
            "X-Valid-Count": str(summary.valid_count),
            "X-Invalid-Count": str(summary.invalid_count),
            "X-Elapsed-Seconds": str(summary.elapsed_seconds),
        },
    )


@app.post("/validate-single")
async def validate_single(email: str = Query(...), check_dns: bool = Query(True)):
    from app.services.validation_service import validate_single_email

    result = validate_single_email(email, check_dns=check_dns)
    return JSONResponse(result.to_flat_dict())


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _INDEX_HTML


_INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Email Validator</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 720px;
         margin: 60px auto; padding: 0 20px; }
  h1 { font-size: 1.6rem; }
  #drop { border: 2px dashed #888; border-radius: 12px; padding: 48px 24px;
          text-align: center; cursor: pointer; transition: 0.2s; }
  #drop.drag { border-color: #4472C4; background: rgba(68,114,196,0.08); }
  #status { margin-top: 20px; font-size: 0.95rem; }
  progress { width: 100%; height: 10px; margin-top: 12px; }
  button { background: #4472C4; color: white; border: none; padding: 10px 18px;
           border-radius: 8px; cursor: pointer; font-size: 0.95rem; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .opts { margin: 16px 0; font-size: 0.9rem; }
  a.download { display: inline-block; margin-top: 12px; }
  code { background: rgba(127,127,127,0.15); padding: 2px 6px; border-radius: 4px; }
</style>
</head>
<body>
  <h1>📧 Email Validation Service</h1>
  <p>Upload a CSV or XLSX file with an email column. Get back an XLSX with
     detailed validation, risk scoring, and deliverability signals appended.</p>

  <div id="drop">
    <p>Drag &amp; drop a .csv or .xlsx file here, or click to browse</p>
    <input type="file" id="fileInput" accept=".csv,.xlsx" style="display:none">
  </div>

  <div class="opts">
    <label><input type="checkbox" id="checkDns" checked> Perform DNS/MX lookups</label><br>
    <label><input type="checkbox" id="deepDns" checked> Deep checks (SPF/DMARC/DKIM indicator)</label>
  </div>

  <div id="status"></div>

  <p style="margin-top:40px;font-size:0.8rem;opacity:0.7">
    Note: this tool never claims a mailbox exists. Without SMTP verification,
    results distinguish <code>Domain/MX valid</code> from
    <code>MAILBOX_UNKNOWN</code> - see README for details.
  </p>

<script>
const drop = document.getElementById('drop');
const fileInput = document.getElementById('fileInput');
const statusEl = document.getElementById('status');

drop.addEventListener('click', () => fileInput.click());
drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('drag'); });
drop.addEventListener('dragleave', () => drop.classList.remove('drag'));
drop.addEventListener('drop', e => {
  e.preventDefault();
  drop.classList.remove('drag');
  if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', () => {
  if (fileInput.files.length) uploadFile(fileInput.files[0]);
});

async function uploadFile(file) {
  statusEl.innerHTML = `Uploading <b>${file.name}</b>...`;
  const form = new FormData();
  form.append('file', file);
  form.append('check_dns', document.getElementById('checkDns').checked);
  form.append('deep_dns_checks', document.getElementById('deepDns').checked);

  try {
    const resp = await fetch('/validate', { method: 'POST', body: form });
    if (resp.status === 422) {
      const err = await resp.json();
      statusEl.innerHTML = `<span style="color:#c33">${err.detail}</span>`;
      return;
    }
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({detail: resp.statusText}));
      statusEl.innerHTML = `<span style="color:#c33">Error: ${err.detail}</span>`;
      return;
    }
    const blob = await resp.blob();
    const total = resp.headers.get('X-Total-Rows');
    const valid = resp.headers.get('X-Valid-Count');
    const invalid = resp.headers.get('X-Invalid-Count');
    const elapsed = resp.headers.get('X-Elapsed-Seconds');
    const url = URL.createObjectURL(blob);
    statusEl.innerHTML = `
      Done. ${total} rows processed in ${elapsed}s
      (${valid} valid, ${invalid} invalid).<br>
      <a class="download" href="${url}" download="validated_${file.name.replace(/\\.[^/.]+$/, '')}.xlsx">
        <button>Download validated_${file.name}.xlsx</button>
      </a>`;
  } catch (err) {
    statusEl.innerHTML = `<span style="color:#c33">Upload failed: ${err}</span>`;
  }
}
</script>
</body>
</html>
"""
