"""Minimal FastAPI page for manually testing the full Workflow A pipeline
in a browser: upload a scanned paper image, get back a regenerated
question paper + answer sheet PDF. Routes stay thin (ARCHITECTURE.md's
api/ constraint) — all real work is in api/pipeline.py's run_full_pipeline.
Not the production wizard (spec §23/§24) — no difficulty selection, no
Review Screen edit/regenerate/delete, no Workflow B. Scoped only to "click
through the pipeline once and get real PDFs back," per the user's explicit
choice of this over a CLI-only or CLI-command approach."""

from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from app.backend.api.pipeline import run_full_pipeline

app = FastAPI(title="AI Practice Paper Generator — manual test page")

_UPLOAD_DIR = Path("data/uploads")
_GENERATED_DIR = Path("data/generated")

_FORM_HTML = """<!doctype html>
<html><head><title>AI Practice Paper Generator</title></head>
<body style="font-family: sans-serif; max-width: 640px; margin: 40px auto;">
<h1>AI Practice Paper Generator — manual test</h1>
<p>Upload a scanned exam page (JPG/PNG/PDF, one page). Runs the full
Workflow A pipeline: ingest, clean, OCR, extract, regenerate 1:1
(same type, same marks, new values), render.</p>
<form action="/generate" method="post" enctype="multipart/form-data">
  <p><label>Paper image/PDF: <input type="file" name="file" required></label></p>
  <p><label>Subject: <input type="text" name="subject" value="Mathematics"></label></p>
  <p><label>Class: <input type="text" name="class_standard" value="III"></label></p>
  <p><label>Duration (minutes):
    <input type="number" name="duration_minutes" value="50"></label></p>
  <p><button type="submit">Generate</button></p>
</form>
</body></html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _FORM_HTML


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    file: UploadFile,
    subject: str = Form("Mathematics"),
    class_standard: str = Form("III"),
    duration_minutes: int = Form(50),
) -> str:
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    upload_path = _UPLOAD_DIR / Path(file.filename).name
    upload_path.write_bytes(await file.read())

    question_paper_path, answer_sheet_path = run_full_pipeline(
        upload_path,
        subject=subject,
        class_standard=class_standard,
        duration_minutes=duration_minutes,
        output_root=_GENERATED_DIR,
    )

    paper_id = question_paper_path.parent.name
    return f"""<!doctype html>
<html><head><title>Generated</title></head>
<body style="font-family: sans-serif; max-width: 640px; margin: 40px auto;">
<h1>Done</h1>
<p><a href="/download/{paper_id}/question_paper.pdf">Download question_paper.pdf</a></p>
<p><a href="/download/{paper_id}/answer_sheet.pdf">Download answer_sheet.pdf</a></p>
<p><a href="/">Generate another</a></p>
</body></html>
"""


@app.get("/download/{paper_id}/{filename}")
def download(paper_id: str, filename: str) -> FileResponse:
    safe_paper_id = Path(paper_id).name
    safe_filename = Path(filename).name
    path = _GENERATED_DIR / safe_paper_id / safe_filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(path, media_type="application/pdf", filename=safe_filename)
