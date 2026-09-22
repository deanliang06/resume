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
            "supported_formats": ["docx", "latex"],
            "generation_provider": manager.project_generator.provider_name,
            "generation_model": settings.generation_model,
        }

    @app.post("/api/jobs", status_code=202)
    async def create_job(
        mode: str = Form("word"),
        skills_format: str = Form("standard"),
        resume: UploadFile | None = File(None),
        latex_source: str | None = Form(None),
        job_description: str = Form(...),
    ):
        try:
            if mode == "latex":
                job = manager.create_latex(
                    latex_source or "",
                    job_description,
                    skills_format,
                )
            elif mode == "word":
                if resume is None or not resume.filename or not resume.filename.lower().endswith(".docx"):
                    raise HTTPException(
                        422,
                        detail={"code": "invalid_input", "message": "Choose a .docx resume."},
                    )
                upload = await resume.read(settings.max_upload_bytes + 1)
                job = manager.create(upload, job_description, skills_format)
            else:
                raise HTTPException(
                    422,
                    detail={"code": "invalid_input", "message": "Choose Word or LaTeX mode."},
                )
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
        if job.output_format == "latex":
            return FileResponse(
                job.result,
                media_type="text/plain; charset=utf-8",
                filename="tailored-resume.tex",
                content_disposition_type="attachment",
            )
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
label{font-weight:650;display:block;margin-top:1rem}input,textarea,button,select{font:inherit}input[type=file],textarea,select{box-sizing:border-box;width:100%;margin-top:.4rem;padding:.7rem;border:1px solid #9aaab7;border-radius:6px}textarea{min-height:12rem;resize:vertical}#latex-source,#latex-output{font:14px ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre;tab-size:2}#latex-output{min-height:20rem;background:#f8fafb}
button,a.button{margin-top:1rem;padding:.7rem 1rem;border:0;border-radius:6px;background:#156b8a;color:white;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block}button:disabled{opacity:.55;cursor:wait}:focus-visible{outline:3px solid #f1b24a;outline-offset:2px}
#status{margin-top:1rem;padding:.8rem;background:#edf5f8;border-radius:6px}#status.error{background:#fdecec;color:#8b2020}.actions{display:flex;gap:.7rem;flex-wrap:wrap}.help{color:#536574;font-size:.9rem}[hidden]{display:none!important}@media(max-width:600px){.shell{padding:.75rem}.card{padding:1rem}}
</style></head><body><main class="shell"><h1>Resume Adjuster</h1><div class="card">
<form id="form"><label for="mode">Resume format</label><select id="mode" name="mode"><option value="word">Word (.docx)</option><option value="latex">LaTeX source</option></select>
<label for="skills-format">Technical Skills format</label><select id="skills-format" name="skills_format"><option value="standard">Languages · Libraries · Web &amp; Database · Tools/Infra</option><option value="ai_assisted">Languages · Frameworks/Libraries · Cloud/Developer Tools · AI Assisted Development</option></select>
<div id="word-input"><label for="resume">DOCX resume</label><input id="resume" name="resume" type="file" accept=".docx" required></div>
<div id="latex-input" hidden><label for="latex-source">Raw LaTeX source</label><textarea id="latex-source" name="latex_source" spellcheck="false" placeholder="Paste the complete .tex source here"></textarea><p class="help">The Projects section must use \resumeProjectHeading and \resumeItem. The existing Technical Skills rows may use either supported format.</p></div>
<label for="description">Job description</label><textarea id="description" name="job_description" required></textarea>
<p class="help">Existing projects are kept only when they closely match the role. OpenRouter generates other slots as visibly labeled hypothetical projects.</p>
<button id="submit" type="submit">Tailor resume</button></form><div id="status" role="status" aria-live="polite">Ready.</div><div id="result" hidden><div id="latex-result" hidden><label for="latex-output">Tailored LaTeX source</label><textarea id="latex-output" readonly spellcheck="false"></textarea></div><div class="actions"><a id="download" class="button">Download result</a><button id="copy" type="button" hidden>Copy LaTeX</button><button id="retry" type="button">Start another</button></div><p id="notices"></p></div>
</div></main><script>
const form=document.querySelector('#form'),mode=document.querySelector('#mode'),resume=document.querySelector('#resume'),latexSource=document.querySelector('#latex-source'),submit=document.querySelector('#submit'),statusBox=document.querySelector('#status'),result=document.querySelector('#result'),latexResult=document.querySelector('#latex-result'),latexOutput=document.querySelector('#latex-output'),copyButton=document.querySelector('#copy'),download=document.querySelector('#download');let timer;
const names={queued:'Queued',validating:'Validating',tailoring:'Tailoring',writing_docx:'Writing DOCX',ready:'Ready',failed:'Failed',cancelled:'Cancelled'};
function show(text,error=false){statusBox.textContent=text;statusBox.classList.toggle('error',error)}
function setMode(){const latex=mode.value==='latex';document.querySelector('#word-input').hidden=latex;document.querySelector('#latex-input').hidden=!latex;resume.required=!latex;latexSource.required=latex}
async function poll(id){const response=await fetch(`/api/jobs/${id}`),job=await response.json();const stage=job.stage==='writing_docx'&&job.output_format==='latex'?'Writing LaTeX':names[job.stage]||job.stage;show(stage,job.stage==='failed');if(job.stage==='ready'){submit.disabled=false;result.hidden=false;download.href=`/api/jobs/${id}/download`;download.textContent=job.output_format==='latex'?'Download .tex':'Download tailored DOCX';latexResult.hidden=job.output_format!=='latex';copyButton.hidden=job.output_format!=='latex';if(job.output_format==='latex'){const sourceResponse=await fetch(download.href);latexOutput.value=await sourceResponse.text()}document.querySelector('#notices').textContent=(job.notices||[]).join(' ');return}if(['failed','cancelled'].includes(job.stage)){submit.disabled=false;show(job.error||names[job.stage],true);return}timer=setTimeout(()=>poll(id),700)}
form.addEventListener('submit',async event=>{event.preventDefault();clearTimeout(timer);submit.disabled=true;result.hidden=true;show('Validating input…');try{const response=await fetch('/api/jobs',{method:'POST',body:new FormData(form)}),body=await response.json();if(!response.ok)throw new Error(body.detail?.message||'Submission failed.');poll(body.id)}catch(error){submit.disabled=false;show(error.message,true)}});
mode.addEventListener('change',setMode);copyButton.addEventListener('click',async()=>{await navigator.clipboard.writeText(latexOutput.value);copyButton.textContent='Copied';setTimeout(()=>copyButton.textContent='Copy LaTeX',1200)});document.querySelector('#retry').addEventListener('click',()=>{result.hidden=true;show('Ready.');document.querySelector('#description').focus()});setMode();
</script></body></html>'''
