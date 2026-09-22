from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from .config import Settings
from .errors import ResumeError
from .jobs import JobManager
from .models import Stage


def create_app(settings: Settings | None = None, project_generator=None) -> FastAPI:
    settings = settings or Settings.from_env()
    manager = JobManager(settings, project_generator)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        manager.sweep()
        yield
        manager.executor.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="Resume Adjuster", version="0.1.0", lifespan=lifespan)
    app.state.jobs = manager

    @app.get("/", response_class=HTMLResponse)
    def home():
        return HTML

    @app.get("/api/health")
    def health():
        return {
            "ok": True,
            "output_format": "docx",
            "generation_provider": manager.project_generator.provider_name,
            "generation_model": settings.generation_model,
        }

    @app.post("/api/jobs", status_code=202)
    async def create_job(
        resume: UploadFile = File(...),
        job_description: str = Form(...),
    ):
        if not resume.filename or not resume.filename.lower().endswith(".docx"):
            raise HTTPException(422, detail={"code": "invalid_input", "message": "Choose a .docx resume."})
        upload = await resume.read(settings.max_upload_bytes + 1)
        try:
            job = manager.create(upload, job_description)
        except ResumeError as exc:
            raise HTTPException(422, detail={"code": exc.code, "message": str(exc)}) from exc
        return job.public()

    @app.get("/api/jobs/{job_id}")
    def status(job_id: str):
        job = manager.get(job_id)
        if not job:
            raise HTTPException(404, detail={"code": "not_found", "message": "Job not found."})
        return job.public()

    @app.delete("/api/jobs/{job_id}", status_code=202)
    def cancel(job_id: str):
        if not manager.cancel(job_id):
            raise HTTPException(409, detail={"code": "not_cancellable", "message": "This job cannot be cancelled."})
        return {"id": job_id, "cancel_requested": True}

    def result_response(job_id: str):
        job = manager.get(job_id)
        if not job:
            raise HTTPException(404, detail="Job not found.")
        if job.error_code == "expired_result":
            raise HTTPException(410, detail={"code": job.error_code, "message": job.error})
        if job.stage != Stage.READY or not job.result:
            raise HTTPException(409, detail={"code": "not_ready", "message": "A validated result is not ready."})
        return FileResponse(
            job.result,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="tailored-resume.docx",
            content_disposition_type="attachment",
        )

    @app.get("/api/jobs/{job_id}/download")
    def download(job_id: str):
        return result_response(job_id)

    return app


app = create_app()

HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Resume Adjuster</title><style>
:root{font:16px system-ui;color:#17212b;background:#f4f7f9}body{margin:0}.shell{max-width:960px;margin:auto;padding:2rem}
.card{background:white;border:1px solid #d8e1e8;border-radius:12px;padding:1.5rem;box-shadow:0 5px 18px #17324d12}
label{font-weight:650;display:block;margin-top:1rem}input,textarea,button{font:inherit}input[type=file],textarea{box-sizing:border-box;width:100%;margin-top:.4rem;padding:.7rem;border:1px solid #9aaab7;border-radius:6px}textarea{min-height:12rem;resize:vertical}
button,a.button{margin-top:1rem;padding:.7rem 1rem;border:0;border-radius:6px;background:#156b8a;color:white;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block}button:disabled{opacity:.55;cursor:wait}:focus-visible{outline:3px solid #f1b24a;outline-offset:2px}
#status{margin-top:1rem;padding:.8rem;background:#edf5f8;border-radius:6px}#status.error{background:#fdecec;color:#8b2020}.actions{display:flex;gap:.7rem;flex-wrap:wrap}.help{color:#536574;font-size:.9rem}@media(max-width:600px){.shell{padding:.75rem}.card{padding:1rem}}
</style></head><body><main class="shell"><h1>Resume Adjuster</h1><div class="card">
<form id="form"><label for="resume">DOCX resume</label><input id="resume" name="resume" type="file" accept=".docx" required>
<label for="description">Job description</label><textarea id="description" name="job_description" required></textarea>
<p class="help">Existing projects are kept only when they closely match the role. OpenRouter generates other slots as visibly labeled hypothetical projects. The result is downloaded as a DOCX; pagination may vary by Word version and installed fonts.</p>
<button id="submit" type="submit">Tailor resume</button></form><div id="status" role="status" aria-live="polite">Ready.</div><div id="result" hidden><div class="actions"><a id="download" class="button">Download tailored DOCX</a><button id="retry" type="button">Start another</button></div><p id="notices"></p></div>
</div></main><script>
const form=document.querySelector('#form'), submit=document.querySelector('#submit'), statusBox=document.querySelector('#status'), result=document.querySelector('#result');let timer;
const names={queued:'Queued',validating:'Validating',tailoring:'Tailoring',writing_docx:'Writing DOCX',ready:'Ready',failed:'Failed',cancelled:'Cancelled'};
function show(text,error=false){statusBox.textContent=text;statusBox.classList.toggle('error',error)}
async function poll(id){const response=await fetch(`/api/jobs/${id}`),job=await response.json();show(names[job.stage]||job.stage,job.stage==='failed');if(job.stage==='ready'){submit.disabled=false;result.hidden=false;document.querySelector('#download').href=`/api/jobs/${id}/download`;document.querySelector('#notices').textContent=(job.notices||[]).join(' ');return}if(['failed','cancelled'].includes(job.stage)){submit.disabled=false;show(job.error||names[job.stage],true);return}timer=setTimeout(()=>poll(id),700)}
form.addEventListener('submit',async event=>{event.preventDefault();clearTimeout(timer);submit.disabled=true;result.hidden=true;show('Validating input…');try{const response=await fetch('/api/jobs',{method:'POST',body:new FormData(form)}),body=await response.json();if(!response.ok)throw new Error(body.detail?.message||'Submission failed.');poll(body.id)}catch(error){submit.disabled=false;show(error.message,true)}});
document.querySelector('#retry').addEventListener('click',()=>{result.hidden=true;show('Ready.');document.querySelector('#description').focus()});
</script></body></html>'''
