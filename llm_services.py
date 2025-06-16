# llm_services.py

import os
import json
import logging
from typing import List, Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field

import google.generativeai as genai
import google.generativeai.types as glm

# --- Logging and API Setup ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(name)s: %(message)s')
logger = logging.getLogger(__name__)
DEBUG = True

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise EnvironmentError("Missing GOOGLE_API_KEY in environment variables.")
genai.configure(api_key=api_key)

# --- Pydantic Schema ---
class ExtractedField(BaseModel):
    field_name: str
    field_value: Any

class DocumentExtract(BaseModel):
    file_name: str
    extracted_data: List[ExtractedField]
    summary: str

# --- Gemini Model Setup ---
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash-latest",
    safety_settings={
        glm.HarmCategory.HARM_CATEGORY_HARASSMENT: glm.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        glm.HarmCategory.HARM_CATEGORY_HATE_SPEECH: glm.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        glm.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: glm.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        glm.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: glm.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    }
)

# --- BOL Fields and Descriptions ---
BOL_TARGET_FIELDS = [
    "BOL Number", "Carrier Name", "Shipper Name", "Consignee Name", "Notify Party",
    "Port of Loading", "Port of Discharge", "Vessel Name", "Date of Issue",
    "Description of Goods", "Freight Class", "Declared Value", "Hazardous Material Information", "Signature"
]

BOL_FIELD_DESCRIPTIONS = """
- BOL Number: Unique identifier for the Bill of Lading.
- Carrier Name: Shipping or trucking company transporting the goods.
- Shipper Name: Name/address of the sender.
- Consignee Name: Name/address of the receiver.
- Notify Party: Contact to be informed on arrival, if different from consignee.
- Port of Loading: Where cargo is loaded.
- Port of Discharge: Where cargo is unloaded.
- Vessel Name: Name of the ship or vehicle.
- Date of Issue: Creation date of the document.
- Description of Goods: Contents, quantity, weight, packaging.
- Freight Class: Shipping classification.
- Declared Value: Insurance value of goods.
- Hazardous Material Information: Hazmat status.
- Signature: Set to "Signed" if a signature is found; omit if not found.
"""

# --- Prompt Template ---
extraction_prompt_text_template = """
You are a specialized Bill of Lading (BOL) extraction AI. Your task is to extract ONLY the fields listed below.

Document: {file_name}

{additional_context}

EXTRACT ONLY THESE FIELDS:
- {target_fields}

INSTRUCTIONS:
- Use EXACT field names from the list above.
- If a field is not present, omit it.
- If a signature is visible, set "Signature" to "Signed".
- Return a JSON with fields 'file_name', 'extracted_data' (list of field_name/value), and 'summary'.

{field_descriptions}
"""

# --- Extraction Function ---
async def extract_bill_of_lading_fields(
    file_content: bytes,
    file_name: str,
    mime_type: str
) -> DocumentExtract:
    logger.info("Extracting BOL fields from document...")

    additional_context = ""
    if mime_type == "text/plain":
        try:
            decoded_text = file_content.decode('utf-8')
            additional_context = f"Document content:\n{decoded_text}"
        except UnicodeDecodeError:
            raise ValueError("Invalid UTF-8 text file.")

    prompt_text = extraction_prompt_text_template.format(
        file_name=file_name,
        additional_context=additional_context,
        target_fields=", ".join(BOL_TARGET_FIELDS),
        field_descriptions=BOL_FIELD_DESCRIPTIONS
    )

    prompt_parts = [prompt_text]
    if mime_type != "text/plain":
        prompt_parts.append({"inline_data": {"mime_type": mime_type, "data": file_content}})

    generation_config = glm.GenerationConfig(
        response_mime_type="application/json",
        response_schema=DocumentExtract
    )

    try:
        response = await model.generate_content_async(
            contents=prompt_parts,
            generation_config=generation_config
        )
        json_string = response.candidates[0].content.parts[0].text
        data_dict = json.loads(json_string)

        if 'file_name' not in data_dict:
            data_dict['file_name'] = file_name

        return DocumentExtract.model_validate(data_dict)

    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=DEBUG)
        return DocumentExtract(
            file_name=file_name,
            extracted_data=[ExtractedField(field_name="Error", field_value=str(e))],
            summary="Extraction failed due to an internal error."
        )