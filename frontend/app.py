import streamlit as st
import requests
from pathlib import Path
import json
from datetime import datetime
import pandas as pd
import time

# API Configuration
API_BASE_URL = "http://localhost:8000"

# Page Configuration
st.set_page_config(
    page_title="Autonomous QA Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Helper Functions
def check_api_health():
    """Check if API is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def upload_support_documents(files):
    """Upload support documents to API"""
    files_data = [("files", (file.name, file, file.type)) for file in files]
    response = requests.post(f"{API_BASE_URL}/upload/support-documents", files=files_data)
    return response.json()


def upload_html_file(file):
    """Upload HTML file to API"""
    files_data = {"file": (file.name, file, "text/html")}
    response = requests.post(f"{API_BASE_URL}/upload/html", files=files_data)
    return response.json()


def build_knowledge_base():
    """Build knowledge base"""
    response = requests.post(f"{API_BASE_URL}/knowledge-base/build")
    return response.json()


def generate_test_cases(query, num_cases=10):
    """Generate test cases"""
    data = {"query": query, "num_cases": num_cases}
    response = requests.post(f"{API_BASE_URL}/test-cases/generate", json=data)
    return response.json()


def generate_selenium_script(test_case, html_content, browser="chrome"):
    """Generate Selenium script"""
    data = {
        "test_case": test_case,
        "html_content": html_content,
        "browser": browser
    }
    response = requests.post(f"{API_BASE_URL}/selenium-script/generate", json=data)
    return response.json()


def list_documents():
    """List uploaded documents"""
    response = requests.get(f"{API_BASE_URL}/documents/list")
    return response.json()


def clear_documents():
    """Clear all documents"""
    response = requests.delete(f"{API_BASE_URL}/documents/clear")
    return response.json()


# Initialize Session State
if 'kb_built' not in st.session_state:
    st.session_state.kb_built = False
if 'test_cases' not in st.session_state:
    st.session_state.test_cases = []
if 'selected_test_case' not in st.session_state:
    st.session_state.selected_test_case = None
if 'html_content' not in st.session_state:
    st.session_state.html_content = ""
if 'uploaded_docs' not in st.session_state:
    st.session_state.uploaded_docs = []


# Main App
def main():
    # Header
    st.markdown('<h1 class="main-header">🤖 Autonomous QA Agent</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Intelligent Test Case & Selenium Script Generation</p>', unsafe_allow_html=True)
    
    # Check API health
    if not check_api_health():
        st.error("⚠️ Backend API is not running. Please start the FastAPI server.")
        st.code("uvicorn backend.main:app --reload --port 8000")
        return
    
    # Sidebar
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/test-results.png", width=80)
        st.title("Navigation")
        
        page = st.radio(
            "Select Page",
            ["📤 Upload & Build KB", "🧪 Generate Test Cases", "🔧 Generate Scripts", "📊 Dashboard"],
            label_visibility="collapsed"
        )
        
        st.divider()
        
        # Quick Stats
        st.subheader("Quick Stats")
        try:
            docs = list_documents()
            st.metric("Support Docs", len(docs.get('support_documents', [])))
            st.metric("HTML Files", len(docs.get('html_files', [])))
            st.metric("KB Status", "✅ Built" if st.session_state.kb_built else "❌ Not Built")
        except:
            pass
        
        st.divider()
        
        # Clear button
        if st.button("🗑️ Clear All Data", use_container_width=True):
            if st.session_state.kb_built:
                with st.spinner("Clearing data..."):
                    clear_documents()
                    st.session_state.kb_built = False
                    st.session_state.test_cases = []
                    st.session_state.selected_test_case = None
                    st.success("All data cleared!")
                    st.rerun()
    
    # Page Routing
    if page == "📤 Upload & Build KB":
        show_upload_page()
    elif page == "🧪 Generate Test Cases":
        show_test_case_page()
    elif page == "🔧 Generate Scripts":
        show_script_generation_page()
    elif page == "📊 Dashboard":
        show_dashboard()


def show_upload_page():
    """Upload documents and build knowledge base"""
    st.header("📤 Document Upload & Knowledge Base")
    
    tab1, tab2, tab3 = st.tabs(["📄 Support Documents", "🌐 HTML File", "🏗️ Build KB"])
    
    # Tab 1: Upload Support Documents
    with tab1:
        st.subheader("Upload Support Documents")
        st.info("📋 Upload project documentation: specifications, UI/UX guides, API docs, etc.")
        
        support_files = st.file_uploader(
            "Choose files",
            type=['md', 'txt', 'json', 'pdf', 'docx'],
            accept_multiple_files=True,
            key="support_uploader"
        )
        
        if support_files:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{len(support_files)} file(s) selected:**")
                for file in support_files:
                    st.write(f"- {file.name} ({file.size / 1024:.1f} KB)")
            
            with col2:
                if st.button("Upload Documents", type="primary", use_container_width=True):
                    with st.spinner("Uploading documents..."):
                        try:
                            result = upload_support_documents(support_files)
                            st.session_state.uploaded_docs = result['files']
                            st.success(f"✅ {result['message']}")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
    
    # Tab 2: Upload HTML
    with tab2:
        st.subheader("Upload Target HTML File")
        st.info("🌐 Upload the HTML file of the web application to test")
        
        html_file = st.file_uploader(
            "Choose HTML file",
            type=['html'],
            key="html_uploader"
        )
        
        if html_file:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**File:** {html_file.name} ({html_file.size / 1024:.1f} KB)")
                
                # Preview HTML
                with st.expander("Preview HTML Structure"):
                    html_content = html_file.read().decode('utf-8')
                    st.code(html_content[:1000] + "..." if len(html_content) > 1000 else html_content, language='html')
                    html_file.seek(0)  # Reset file pointer
            
            with col2:
                if st.button("Upload HTML", type="primary", use_container_width=True):
                    with st.spinner("Uploading HTML..."):
                        try:
                            result = upload_html_file(html_file)
                            st.session_state.html_content = html_file.read().decode('utf-8')
                            st.success(f"✅ {result['message']}")
                            st.info(f"Found {result.get('elements_count', 0)} elements and {result.get('forms_count', 0)} forms")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
    
    # Tab 3: Build Knowledge Base
    with tab3:
        st.subheader("Build Knowledge Base")
        
        try:
            docs = list_documents()
            total_docs = len(docs.get('support_documents', [])) + len(docs.get('html_files', []))
            
            if total_docs == 0:
                st.warning("⚠️ Please upload documents before building the knowledge base.")
            else:
                st.success(f"✅ {total_docs} document(s) ready to process")
                
                # Show uploaded files
                with st.expander("View Uploaded Documents"):
                    if docs.get('support_documents'):
                        st.write("**Support Documents:**")
                        for doc in docs['support_documents']:
                            st.write(f"- {doc['filename']}")
                    
                    if docs.get('html_files'):
                        st.write("**HTML Files:**")
                        for doc in docs['html_files']:
                            st.write(f"- {doc['filename']}")
                
                st.divider()
                
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if st.button("🏗️ Build Knowledge Base", type="primary", use_container_width=True):
                        with st.spinner("Building knowledge base... This may take a minute."):
                            try:
                                progress_bar = st.progress(0)
                                status_text = st.empty()
                                
                                status_text.text("Parsing documents...")
                                progress_bar.progress(25)
                                time.sleep(0.5)
                                
                                status_text.text("Generating embeddings...")
                                progress_bar.progress(50)
                                
                                result = build_knowledge_base()
                                
                                status_text.text("Storing in vector database...")
                                progress_bar.progress(75)
                                time.sleep(0.5)
                                
                                progress_bar.progress(100)
                                status_text.text("Complete!")
                                
                                st.session_state.kb_built = True
                                
                                st.balloons()
                                
                                st.success("✅ Knowledge Base Built Successfully!")
                                
                                # Show stats
                                col_a, col_b, col_c = st.columns(3)
                                with col_a:
                                    st.metric("Documents", result['total_documents'])
                                with col_b:
                                    st.metric("Chunks", result['total_chunks'])
                                with col_c:
                                    st.metric("Status", "Ready ✅")
                                
                                st.info("🎉 You can now generate test cases!")
                                
                            except Exception as e:
                                st.error(f"❌ Error building knowledge base: {str(e)}")
                                progress_bar.empty()
                                status_text.empty()
        
        except Exception as e:
            st.error(f"❌ Error checking documents: {str(e)}")


def show_test_case_page():
    """Generate test cases page"""
    st.header("🧪 Test Case Generation")
    
    if not st.session_state.kb_built:
        st.warning("⚠️ Please build the knowledge base first in the 'Upload & Build KB' page.")
        return
    
    st.success("✅ Knowledge base is ready!")
    
    # Query input
    st.subheader("What would you like to test?")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        query = st.text_area(
            "Enter your test requirements:",
            placeholder="Example: Generate test cases for the discount code feature including positive and negative scenarios",
            height=100,
            key="test_query"
        )
    
    with col2:
        num_cases = st.number_input("Number of test cases:", min_value=1, max_value=20, value=5)
    
    if st.button("🚀 Generate Test Cases", type="primary", use_container_width=True):
        if not query:
            st.warning("Please enter a test query.")
            return
        
        with st.spinner("Generating test cases..."):
            try:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                status_text.text("Searching knowledge base...")
                progress_bar.progress(33)
                time.sleep(0.5)
                
                status_text.text("Generating test scenarios...")
                progress_bar.progress(66)
                
                result = generate_test_cases(query, num_cases)
                
                progress_bar.progress(100)
                status_text.text("Complete!")
                time.sleep(0.5)
                progress_bar.empty()
                status_text.empty()
                
                st.session_state.test_cases = result['test_cases']
                
                st.success(f"✅ Generated {result['total_cases']} test case(s)")
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                return
    
    # Display test cases
    if st.session_state.test_cases:
        st.divider()
        st.subheader(f"📋 Generated Test Cases ({len(st.session_state.test_cases)})")
        
        for idx, test_case in enumerate(st.session_state.test_cases):
            with st.expander(f"**{test_case['test_id']}** - {test_case['test_scenario']}", expanded=(idx == 0)):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown(f"**Feature:** {test_case['feature']}")
                    st.markdown(f"**Type:** `{test_case['test_type']}`")
                    st.markdown(f"**Priority:** `{test_case['priority']}`")
                    
                    if test_case.get('preconditions'):
                        st.markdown(f"**Preconditions:** {test_case['preconditions']}")
                    
                    st.markdown("**Test Steps:**")
                    for i, step in enumerate(test_case['test_steps'], 1):
                        st.markdown(f"{i}. {step}")
                    
                    st.markdown(f"**Expected Result:** {test_case['expected_result']}")
                    
                    st.markdown("**Grounded In:**")
                    for source in test_case['grounded_in']:
                        st.markdown(f"- 📄 {source}")
                
                with col2:
                    if st.button(f"Generate Script", key=f"script_btn_{idx}", use_container_width=True):
                        st.session_state.selected_test_case = test_case
                        st.success("✅ Test case selected! Go to 'Generate Scripts' page.")
        
        # Export options
        st.divider()
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Export as JSON
            json_data = json.dumps(st.session_state.test_cases, indent=2)
            st.download_button(
                label="📥 Download as JSON",
                data=json_data,
                file_name=f"test_cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
        
        with col2:
            # Export as CSV
            df = pd.DataFrame(st.session_state.test_cases)
            csv_data = df.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv_data,
                file_name=f"test_cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )


def show_script_generation_page():
    """Generate Selenium scripts page"""
    st.header("🔧 Selenium Script Generation")
    
    if not st.session_state.kb_built:
        st.warning("⚠️ Please build the knowledge base first.")
        return
    
    if not st.session_state.test_cases:
        st.warning("⚠️ Please generate test cases first.")
        return
    
    # Select test case
    st.subheader("Select Test Case")
    
    test_case_options = [
        f"{tc['test_id']} - {tc['test_scenario']}"
        for tc in st.session_state.test_cases
    ]
    
    selected_option = st.selectbox("Choose a test case:", test_case_options)
    selected_idx = test_case_options.index(selected_option)
    selected_test_case = st.session_state.test_cases[selected_idx]
    
    # Show test case details
    with st.expander("📋 Test Case Details", expanded=True):
        st.json(selected_test_case)
    
    # Browser selection
    browser = st.selectbox("Select Browser:", ["chrome", "firefox", "edge"])
    
    # Generate button
    if st.button("🚀 Generate Selenium Script", type="primary", use_container_width=True):
        if not st.session_state.html_content:
            st.error("❌ HTML content not found. Please upload HTML file.")
            return
        
        with st.spinner("Generating Selenium script..."):
            try:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                status_text.text("Analyzing test case...")
                progress_bar.progress(25)
                time.sleep(0.5)
                
                status_text.text("Extracting HTML selectors...")
                progress_bar.progress(50)
                time.sleep(0.5)
                
                status_text.text("Generating Python code...")
                progress_bar.progress(75)
                
                result = generate_selenium_script(
                    selected_test_case,
                    st.session_state.html_content,
                    browser
                )
                
                progress_bar.progress(100)
                status_text.text("Complete!")
                time.sleep(0.5)
                progress_bar.empty()
                status_text.empty()
                
                st.success("✅ Selenium script generated successfully!")
                
                # Display script
                st.subheader("📝 Generated Script")
                st.code(result['script'], language='python')
                
                # Selectors used
                if result.get('selectors_used'):
                    with st.expander("🎯 Selectors Used"):
                        for selector in result['selectors_used']:
                            st.code(selector)
                
                # Explanation
                if result.get('explanation'):
                    with st.expander("💡 Script Explanation"):
                        st.write(result['explanation'])
                
                # Download button
                st.download_button(
                    label="📥 Download Script",
                    data=result['script'],
                    file_name=f"{selected_test_case['test_id']}_selenium_script.py",
                    mime="text/x-python",
                    use_container_width=True
                )
                
            except Exception as e:
                st.error(f"❌ Error generating script: {str(e)}")


def show_dashboard():
    """Dashboard with statistics"""
    st.header("📊 Dashboard")
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    try:
        docs = list_documents()
        
        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Support Docs", len(docs.get('support_documents', [])))
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("HTML Files", len(docs.get('html_files', [])))
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Test Cases", len(st.session_state.test_cases))
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col4:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            kb_status = "Built ✅" if st.session_state.kb_built else "Not Built ❌"
            st.metric("KB Status", kb_status)
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.divider()
        
        # Documents table
        if docs.get('support_documents') or docs.get('html_files'):
            st.subheader("📄 Uploaded Documents")
            
            all_docs = docs.get('support_documents', []) + docs.get('html_files', [])
            df = pd.DataFrame(all_docs)
            df['size_kb'] = df['size'] / 1024
            st.dataframe(df[['filename', 'type', 'size_kb']], use_container_width=True)
        
        # Test cases summary
        if st.session_state.test_cases:
            st.divider()
            st.subheader("🧪 Test Cases Summary")
            
            df_tests = pd.DataFrame(st.session_state.test_cases)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**By Type:**")
                type_counts = df_tests['test_type'].value_counts()
                st.bar_chart(type_counts)
            
            with col2:
                st.write("**By Priority:**")
                priority_counts = df_tests['priority'].value_counts()
                st.bar_chart(priority_counts)
    
    except Exception as e:
        st.error(f"Error loading dashboard: {str(e)}")


if __name__ == "__main__":
    main()