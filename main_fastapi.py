# main_fastapi.py

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import json

# ✅ Updated import: use the new BOL-only extractor
from llm_services import extract_bill_of_lading_fields, DocumentExtract, logger

app = FastAPI(title="Techprofuse Document Processing API")

# --- CORS setup ---
origins = ["http://localhost", "http://localhost:8501"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global state ---
document_store: Dict[str, Dict[str, Any]] = {}
agent_config: Dict[str, Any] = {"fields_to_extract": [], "special_instructions": ""}


@app.post("/setup/upload_extract/", response_model=DocumentExtract)
async def setup_upload_and_extract(
    file: UploadFile = File(...),
    special_instructions: Optional[str] = Form(None),
    target_fields_json: Optional[str] = Form(None)
):
    logger.info(f"[FastAPI /setup/upload_extract/] file: {file.filename}, instructions: '{special_instructions}', target_fields_json: '{target_fields_json}'")

    if not file.filename or not file.content_type:
        raise HTTPException(status_code=400, detail="Filename and content type are required.")

    contents = await file.read()
    mime_type = file.content_type
    document_store[file.filename] = {"content": contents, "mime_type": mime_type}

    # ✅ NOTE: The BOL version ignores dynamic target_fields
    try:
        extracted_json_obj = await extract_bill_of_lading_fields(
            file_content=contents,
            file_name=file.filename,
            mime_type=mime_type
        )
        return extracted_json_obj
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"[FastAPI /setup/upload_extract/] Exception: {e} for {file.filename}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error extracting data: {str(e)}")


class AgentConfigPayload(BaseModel):
    fields_to_extract: List[str]
    special_instructions: str


@app.post("/setup/configure_agent/")
async def configure_agent_endpoint(config: AgentConfigPayload):
    global agent_config
    agent_config["fields_to_extract"] = config.fields_to_extract
    agent_config["special_instructions"] = config.special_instructions
    logger.info(f"[FastAPI /setup/configure_agent/] Agent config updated: {agent_config}")
    return {"message": "Agent configuration finalized successfully!", "current_config": agent_config}


@app.post("/deploy/process_document/", response_model=DocumentExtract)
async def deploy_process_document(file: UploadFile = File(...)):
    if not file.filename or not file.content_type:
        raise HTTPException(status_code=400, detail="Filename and content type are required.")

    contents = await file.read()
    mime_type = file.content_type
    document_store[file.filename] = {"content": contents, "mime_type": mime_type}

    try:
        processed_data = await extract_bill_of_lading_fields(
            file_content=contents,
            file_name=file.filename,
            mime_type=mime_type
        )
        return processed_data
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"[FastAPI /deploy/process_document/] Exception: {e} for {file.filename}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@app.post("/deploy/ask_question/")
async def deploy_ask_question(payload: Dict[str, str]):
    file_name = payload.get("file_name")
    question = payload.get("question")
    logger.info(f"[FastAPI /deploy/ask_question/] file: {file_name}, question: '{question}'")

    if not file_name or not question:
        raise HTTPException(status_code=400, detail="File name and question are required.")
    stored_file_data = document_store.get(file_name)
    if not stored_file_data:
        raise HTTPException(status_code=404, detail=f"Document '{file_name}' not found.")

    # 👇 Optional: Q&A is now deprecated if you removed it from llm_services.py
    return {
        "file_name": file_name,
        "question": question,
        "answer": "Q&A feature is currently disabled in the BOL-only mode."
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)