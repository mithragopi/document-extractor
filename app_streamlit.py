# app_streamlit.py
import streamlit as st
import requests
import json
import pandas as pd

# --- DEBUG FLAG for Streamlit specific prints ---
DEBUG_STREAMLIT = False # Set to True to see detailed UI debug messages

FASTAPI_BASE_URL = "https://document-extractor-4llq.onrender.com"

def call_api(endpoint, method="get", json_data=None, form_data=None, files=None):
    url = f"{FASTAPI_BASE_URL}{endpoint}"
    if DEBUG_STREAMLIT:
        st.markdown(f"**DEBUG_CALL_API:** Calling `{method.upper()}` `{endpoint}`")
        if files: st.caption(f"Files: {list(files.keys()) if files else 'None'}, Form data: `{form_data}`")
        if json_data: st.caption(f"JSON data: `{json_data}`")
        if not files and not json_data and form_data : st.caption(f"Form data only: `{form_data}`")

    try:
        if method.lower() == "post":
            if files:
                response = requests.post(url, data=form_data, files=files)
            elif json_data is not None:
                response = requests.post(url, json=json_data)
            else:
                response = requests.post(url, data=form_data)
        elif method.lower() == "get":
            response = requests.get(url, params=form_data)
        else:
            st.error(f"Unsupported API method: {method}")
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Connection Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try: st.error(f"API Response Content: {e.response.json()}")
            except json.JSONDecodeError: st.error(f"API Response Content (not JSON): {e.response.text}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred in call_api: {e}")
        return None

st.set_page_config(layout="wide", page_title="Techprofuse IDP")
st.title("🚀 Techprofuse Intelligent Document Processor")

# --- Session State Initialization ---
if 'setup_extraction_result' not in st.session_state:
    st.session_state.setup_extraction_result = None
if 'agent_config_final' not in st.session_state:
    st.session_state.agent_config_final = {"fields_to_extract": [], "special_instructions": ""}
if 'agent_configured_successfully' not in st.session_state:
    st.session_state.agent_configured_successfully = False
if 'deployment_result' not in st.session_state:
    st.session_state.deployment_result = None
if 'current_doc_for_qa' not in st.session_state:
    st.session_state.current_doc_for_qa = None
if 'setup_file_bytes' not in st.session_state:
    st.session_state.setup_file_bytes = None
if 'setup_file_meta' not in st.session_state:
    st.session_state.setup_file_meta = None
if 'setup_special_instructions' not in st.session_state:
    st.session_state.setup_special_instructions = ""
if 'setup_selected_fields_for_llm' not in st.session_state: # User's current selection in multiselect
    st.session_state.setup_selected_fields_for_llm = []


tab1, tab2 = st.tabs(["⚙️ Agent Setup Stage", "🚀 Document Processing Stage"])

with tab1:
    st.header("1. Iteratively Configure Extraction Agent")
    st.markdown("""
    **Workflow:**
    1.  Upload sample document for initial AI analysis.
    2.  Review extracted fields. Select **Primary Fields** the AI should focus on.
    3.  Provide **Special Instructions** to further guide the AI (e.g., formatting, splitting fields).
    4.  **Re-run Extraction** to see updated results. Iterate on selected fields & instructions.
    5.  **Set Final Agent Configuration** to save.
    """)
    st.markdown("---")

    st.subheader("Step 1: Upload Sample Document")
    uploaded_file_widget_setup = st.file_uploader(
        "Upload a sample document (.txt, .pdf, .png, .jpg) to analyze.",
        type=["txt", "pdf", "png", "jpg", "jpeg"],
        key="uploader_setup_main_v4" # Increment key for new version
    )

    if uploaded_file_widget_setup is not None:
        new_file_uploaded = False
        current_bytes = uploaded_file_widget_setup.getvalue() # Get bytes once
        if st.session_state.setup_file_meta is None or \
           st.session_state.setup_file_meta["name"] != uploaded_file_widget_setup.name or \
           st.session_state.setup_file_bytes != current_bytes:
            new_file_uploaded = True
        
        if new_file_uploaded:
            st.session_state.setup_file_bytes = current_bytes
            st.session_state.setup_file_meta = {"name": uploaded_file_widget_setup.name, "type": uploaded_file_widget_setup.type}
            st.session_state.setup_extraction_result = None 
            st.session_state.setup_special_instructions = "" 
            st.session_state.setup_selected_fields_for_llm = [] 
            st.success(f"File '{uploaded_file_widget_setup.name}' loaded. Click 'Perform Initial Extraction'.")

    if st.session_state.setup_file_bytes and st.session_state.setup_file_meta:
        st.write(f"Working with: `{st.session_state.setup_file_meta['name']}`")
        if st.button("🔍 Perform Initial Extraction", key="initial_extract_button_v4"):
            with st.spinner("Performing initial extraction..."):
                file_meta = st.session_state.setup_file_meta
                files_payload = {"file": (file_meta["name"], st.session_state.setup_file_bytes, file_meta["type"])}
                form_data_payload = {"special_instructions": "", "target_fields_json": json.dumps([])}
                
                result = call_api("/setup/upload_extract/", method="post", files=files_payload, form_data=form_data_payload)
                
                if DEBUG_STREAMLIT:
                    st.subheader("DEBUG: API Result from Initial Extraction")
                    st.json(result if result else {"error": "Initial API call failed"})

                if result:
                    st.session_state.setup_extraction_result = result
                    st.session_state.setup_special_instructions = "" 
                    if isinstance(result.get('extracted_data'), list):
                        st.session_state.setup_selected_fields_for_llm = sorted(list(set([ # Set to all unique, sorted new fields
                            item.get('field_name') for item in result['extracted_data']
                            if isinstance(item, dict) and item.get('field_name') and item.get('field_name') != 'N/A'
                        ])))
                    else:
                        st.session_state.setup_selected_fields_for_llm = []
                else:
                    st.session_state.setup_extraction_result = None
    st.markdown("---")

    if st.session_state.setup_extraction_result:
        st.subheader("Step 2: Review Current Extraction & Refine Iteratively")
        
        if DEBUG_STREAMLIT:
            st.write("DEBUG: `st.session_state.setup_extraction_result` (feeds table & multiselect options):")
            st.json(st.session_state.setup_extraction_result)
            st.write(f"DEBUG: `st.session_state.setup_selected_fields_for_llm` (feeds multiselect default): {st.session_state.setup_selected_fields_for_llm}")


        result_data_for_display = st.session_state.setup_extraction_result
        
        col1_disp_setup, col2_disp_setup = st.columns(2)
        with col1_disp_setup:
            st.write(f"**Analyzed File:** `{result_data_for_display.get('file_name', 'N/A')}`")
        with col2_disp_setup:
            st.write(f"**AI Summary:**"); st.info(f"{result_data_for_display.get('summary', 'N/A')}")

        st.write("**Fields Currently Extracted by AI:**")
        extracted_data_list_for_df = result_data_for_display.get('extracted_data', [])
        
        current_field_names_from_extraction = [] # For multiselect options
        if isinstance(extracted_data_list_for_df, list) and extracted_data_list_for_df:
            current_df_data = []
            for item in extracted_data_list_for_df:
                if isinstance(item, dict):
                    field_name = item.get('field_name', 'N/A')
                    current_df_data.append({"Field Name": field_name, "Extracted Value": str(item.get('field_value', 'N/A'))})
                    if field_name != 'N/A': current_field_names_from_extraction.append(field_name)
            if current_df_data:
                st.dataframe(pd.DataFrame(current_df_data), use_container_width=True, hide_index=True)
            else: st.info("No structured fields in the current extraction.")
        elif "LLMError" in str(result_data_for_display.get('summary', '')) or \
             (isinstance(extracted_data_list_for_df, list) and extracted_data_list_for_df and \
              "LLMError" in extracted_data_list_for_df[0].get("field_name","")):
             st.warning(f"Extraction Error: {result_data_for_display.get('summary', '')}")
        else: st.info("No fields currently extracted or data format is unexpected.")

        st.markdown("---")
        st.write("**A. Select Primary Fields to Guide AI:** (These will be sent to the AI)")
        
        multiselect_options = sorted(list(set(current_field_names_from_extraction)))
        
        # Current selection for multiselect (default for the widget)
        # This ensures that if the user made selections, and those fields are still available, they remain selected.
        # If previously selected fields are no longer in options, they'll be dropped by multiselect itself.
        current_multiselect_selection = [
            field for field in st.session_state.setup_selected_fields_for_llm 
            if field in multiselect_options
        ]
        # If after filtering, the selection is empty, AND there are options, default to all current options
        if not current_multiselect_selection and multiselect_options:
            current_multiselect_selection = multiselect_options


        user_selected_fields = st.multiselect( # Assign to a new variable to avoid direct modification during render
            "Choose fields from the current extraction to tell the AI to prioritize. This list will be sent with your special instructions.",
            options=multiselect_options,
            default=current_multiselect_selection, 
            key="multiselect_target_fields_v4"
        )
        # Update session state AFTER the widget has been rendered and interacted with for this run
        st.session_state.setup_selected_fields_for_llm = user_selected_fields


        st.write("**B. Provide Special Instructions for AI:** (Optional)")
        st.session_state.setup_special_instructions = st.text_area(
            "E.g., 'Split full_name into first_name and last_name', 'Format dates as MM-DD-YYYY'.",
            value=st.session_state.setup_special_instructions,
            height=150,
            key="special_instructions_input_v4"
        )

        if st.button("🔄 Re-run Extraction with Selected Fields & Instructions", key="rerun_button_v4"):
            if st.session_state.setup_file_bytes and st.session_state.setup_file_meta:
                with st.spinner("Re-running extraction..."):
                    file_meta = st.session_state.setup_file_meta
                    files_payload = {"file": (file_meta["name"], st.session_state.setup_file_bytes, file_meta["type"])}
                    
                    target_fields_to_send_on_rerun = st.session_state.setup_selected_fields_for_llm # Use current multiselect state
                    special_instructions_to_send_on_rerun = st.session_state.setup_special_instructions
                    
                    form_data_payload = {
                        "special_instructions": special_instructions_to_send_on_rerun,
                        "target_fields_json": json.dumps(target_fields_to_send_on_rerun)
                    }
                    
                    if DEBUG_STREAMLIT:
                        st.write(f"DEBUG: Re-running. Target Fields: {target_fields_to_send_on_rerun}, Instructions: '{special_instructions_to_send_on_rerun}'")
                    
                    result_rerun = call_api("/setup/upload_extract/", method="post", files=files_payload, form_data=form_data_payload)
                    
                    if DEBUG_STREAMLIT:
                        st.subheader("DEBUG: API Result from Re-run Extraction")
                        st.json(result_rerun if result_rerun else {"error": "Re-run API call failed"})

                    if result_rerun:
                        st.session_state.setup_extraction_result = result_rerun
                        
                        # Update the default selection for the multiselect based on the new results
                        # and the user's *current* selection from the multiselect widget.
                        newly_extracted_fields_from_rerun = []
                        if isinstance(result_rerun.get('extracted_data'), list):
                             newly_extracted_fields_from_rerun = [
                                item.get('field_name') for item in result_rerun['extracted_data']
                                if isinstance(item, dict) and item.get('field_name') and item.get('field_name') != 'N/A'
                            ]
                        
                        # The user_selected_fields (from widget's current state before this button press)
                        # is what we want to try and preserve if those fields still exist.
                        preserved_selections_after_rerun = [
                            f for f in user_selected_fields # Use selection *before* this re-run logic
                            if f in newly_extracted_fields_from_rerun
                        ]
                        # If nothing from previous selection is valid, default to all new fields
                        if not preserved_selections_after_rerun and newly_extracted_fields_from_rerun:
                             st.session_state.setup_selected_fields_for_llm = newly_extracted_fields_from_rerun
                        else:
                             st.session_state.setup_selected_fields_for_llm = preserved_selections_after_rerun
                        
                        st.success("Extraction re-run complete!")
                        st.rerun() 
                    else:
                        st.error("Failed to re-run extraction.")
            else:
                st.warning("No sample document loaded. Please upload and analyze first.")
        
        st.markdown("---")
        st.subheader("Step 3: Set Final Agent Configuration")
        st.caption("This saves the 'Primary Fields' selected above and current 'Special Instructions'.")
        if st.button("💾 Set Final Agent Configuration", key="set_final_config_button_v4"):
            final_selected_fields_for_config = st.session_state.setup_selected_fields_for_llm
            
            if not final_selected_fields_for_config and not st.session_state.setup_special_instructions.strip():
                st.warning("Please select at least one primary field or provide special instructions.")
            else:
                final_config_payload = {
                    "fields_to_extract": final_selected_fields_for_config,
                    "special_instructions": st.session_state.setup_special_instructions
                }
                if DEBUG_STREAMLIT:
                    st.write("DEBUG: Final config payload for /setup/configure_agent/:")
                    st.json(final_config_payload)

                response = call_api("/setup/configure_agent/", method="post", json_data=final_config_payload)
                if response:
                    st.session_state.agent_config_final = response.get("current_config", final_config_payload)
                    st.session_state.agent_configured_successfully = True
                    st.success(response.get("message", "Agent configuration finalized!"))
                    with st.expander("View Final Agent Configuration", expanded=True):
                        st.json(st.session_state.agent_config_final)
                else:
                    st.error("Failed to set final agent configuration.")

# --- Tab 2: Document Processing Stage ---
with tab2:
    st.header("2. Process Documents with Configured Agent")
    if not st.session_state.agent_configured_successfully:
        st.warning("➡️ Please set the final agent configuration in the 'Agent Setup Stage' first.")
    else: # ... (Tab 2 logic remains mostly the same, using st.session_state.agent_config_final) ...
        st.success("✅ Agent is configured and ready.")
        with st.expander("View Current Agent Configuration"):
            st.json(st.session_state.agent_config_final) # Display the final saved config

        uploaded_file_deploy = st.file_uploader(
            "Upload a document for processing by the agent",
            type=["txt", "pdf", "png", "jpg", "jpeg"], key="deploy_uploader_main_v4"
        )
        if uploaded_file_deploy is not None:
            if st.button("Process Document with Agent", key="deploy_process_button_main_v4"):
                with st.spinner("Processing document..."):
                    files_payload = {"file": (uploaded_file_deploy.name, uploaded_file_deploy.getvalue(), uploaded_file_deploy.type)}
                    result = call_api("/deploy/process_document/", method="post", files=files_payload)
                    if result:
                        st.session_state.deployment_result = result
                        st.session_state.current_doc_for_qa = {"file_name": uploaded_file_deploy.name}
                    else: st.session_state.deployment_result = None
        if st.session_state.deployment_result:
            st.markdown("---")
            st.subheader("Processed Document Results")
            deploy_data = st.session_state.deployment_result
            col_res1_d, col_res2_d = st.columns(2)
            with col_res1_d: st.write(f"**Processed File:** `{deploy_data.get('file_name', 'N/A')}`")
            with col_res2_d: st.write(f"**AI Summary:**"); st.info(f"{deploy_data.get('summary', 'N/A')}")
            st.write("**Data Extracted by Agent:**")
            deploy_extracted_data_list = deploy_data.get('extracted_data', [])
            if isinstance(deploy_extracted_data_list, list) and deploy_extracted_data_list:
                df_deploy_display_data = []
                for item in deploy_extracted_data_list:
                    if isinstance(item, dict):
                         df_deploy_display_data.append({"Field Name": item.get('field_name', 'N/A'), "Extracted Value": str(item.get('field_value', 'N/A'))})
                if df_deploy_display_data: st.dataframe(pd.DataFrame(df_deploy_display_data), use_container_width=True, hide_index=True)
                else: st.info("No structured fields extracted by the agent.")
            elif "LLMError" in str(deploy_data.get('summary', '')) or (isinstance(deploy_extracted_data_list, list) and deploy_extracted_data_list and "LLMError" in deploy_extracted_data_list[0].get("field_name","")):
                 st.warning(f"Extraction Error: {deploy_data.get('summary', '')}")
            else: st.info("No data extracted by the agent or data format is unexpected.")
            st.markdown("---")
            st.subheader(f"Ask Questions about '{deploy_data.get('file_name', 'this document')}'")
            if st.session_state.current_doc_for_qa and st.session_state.current_doc_for_qa.get('file_name') == deploy_data.get('file_name'):
                question_deploy = st.text_input("Your question:", key="deploy_qa_input_main_v4")
                if st.button("Ask Question", key="deploy_qa_button_main_v4"):
                    if question_deploy:
                        with st.spinner("Getting answer..."):
                            payload = {"file_name": st.session_state.current_doc_for_qa['file_name'], "question": question_deploy}
                            answer_response = call_api("/deploy/ask_question/", method="post", json_data=payload)
                            if answer_response: st.info(f"**Answer:** {answer_response.get('answer', 'No answer received.')}")
                    else: st.warning("Please enter a question.")
            elif uploaded_file_deploy: st.info("Process the document first to enable Q&A for it.")


st.sidebar.info( # Keep sidebar as is
    """
    **Techprofuse Intelligent Document Processor**
    ---
    **How to Use:**
    1.  **Agent Setup Stage:**
        * Upload sample document. Review initial AI extraction.
        * Select primary fields from the extraction.
        * Provide 'Special Instructions' to refine. 'Re-run Extraction' to iterate.
        * 'Set Final Agent Configuration' with your chosen fields and instructions.
    2.  **Document Processing Stage:**
        * Upload documents for the configured agent.
        * Review extracted data and ask questions.
    ---
    **Run Locally:**
    1. `GOOGLE_API_KEY` in `.env`.
    2. FastAPI: `uvicorn main_fastapi:app --reload --port 8000`
    3. Streamlit: `streamlit run app_streamlit.py`
    """
)
