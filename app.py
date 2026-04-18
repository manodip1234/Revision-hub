import streamlit as st
from st_supabase_connection import SupabaseConnection
import PyPDF2
from io import BytesIO

st.set_page_config(page_title="DIBPS SO IT Revision Hub", layout="wide", page_icon="📚")
st.title("📚 DIBPS SO IT Revision Hub")
st.caption("Login • Shared + Private PDFs • Mobile friendly • 100% Free")

# Connect to Supabase
conn = st.connection("supabase", type=SupabaseConnection)

# ====================== LOGIN ======================
if "user" not in st.session_state:
    st.subheader("🔑 Login to your Revision Hub")
    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                try:
                    res = conn.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.user = res.user
                    st.success(f"Welcome {res.user.email}!")
                    st.rerun()
                except Exception as e:
                    st.error("Invalid email or password")

    with tab_signup:
        with st.form("signup_form"):
            email = st.text_input("Email (use your Gmail or any)")
            password = st.text_input("Password (min 6 characters)", type="password")
            if st.form_submit_button("Create Account"):
                try:
                    res = conn.auth.sign_up({"email": email, "password": password})
                    st.success("Account created! Check your email for verification (or ask admin to confirm).")
                except Exception as e:
                    st.error(str(e))

    st.stop()  # Don't show anything else until logged in

# ====================== LOGGED IN ======================
user = st.session_state.user
st.sidebar.success(f"👋 {user.email}")
if st.sidebar.button("Logout"):
    conn.auth.sign_out()
    st.session_state.clear()
    st.rerun()

st.header(f"Welcome back, {user.email.split('@')[0]}!")

tab_shared, tab_private = st.tabs(["🌍 Shared PDFs (visible to all 3 of you)", "🔒 My Private PDFs (only you can see)"])

# Helper to extract text
def extract_text_from_pdf(file_bytes):
    reader = PyPDF2.PdfReader(BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text[:15000]  # limit for display

# ====================== SHARED SECTION ======================
with tab_shared:
    st.subheader("Shared PDFs")
    uploaded = st.file_uploader("Upload new PDF to Shared library", type="pdf", key="shared_upload")
    if uploaded:
        try:
            file_bytes = uploaded.getvalue()
            filename = uploaded.name
            # Upload to shared bucket
            conn.storage.from_("shared-pdfs").upload(filename, file_bytes)
            st.success(f"✅ Uploaded to Shared: {filename}")
            st.rerun()
        except Exception as e:
            if "already exists" in str(e):
                st.warning("File with same name already exists in Shared.")
            else:
                st.error(str(e))

    # List shared PDFs
    try:
        files = conn.storage.from_("shared-pdfs").list()
        if files:
            for file_info in files:
                filename = file_info["name"]
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    st.write(f"📄 {filename}")
                with col2:
                    if st.button("📥 Download", key=f"dl_shared_{filename}"):
                        url = conn.storage.from_("shared-pdfs").get_public_url(filename)
                        st.download_button("Download now", "", file_name=filename, key=f"dl2_shared_{filename}")
                with col3:
                    if st.button("👀 View Text", key=f"view_shared_{filename}"):
                        bytes_data = conn.storage.from_("shared-pdfs").download(filename)
                        text = extract_text_from_pdf(bytes_data)
                        st.text_area("Extracted text", text, height=400)
        else:
            st.info("No shared PDFs yet. Upload one above!")
    except:
        st.info("Shared library is empty.")

# ====================== PRIVATE SECTION ======================
with tab_private:
    st.subheader("My Private PDFs")
    uploaded_private = st.file_uploader("Upload new PDF to your Private section", type="pdf", key="private_upload")
    if uploaded_private:
        try:
            file_bytes = uploaded_private.getvalue()
            filename = uploaded_private.name
            path = f"{user.id}/{filename}"   # private path per user
            conn.storage.from_("private-pdfs").upload(path, file_bytes)
            st.success(f"✅ Uploaded to your Private: {filename}")
            st.rerun()
        except Exception as e:
            st.error(str(e))

    # List private PDFs
    try:
        private_files = conn.storage.from_("private-pdfs").list(f"{user.id}/")
        if private_files:
            for file_info in private_files:
                filename = file_info["name"]
                full_path = f"{user.id}/{filename}"
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    st.write(f"🔒 {filename}")
                with col2:
                    if st.button("📥 Download", key=f"dl_priv_{filename}"):
                        bytes_data = conn.storage.from_("private-pdfs").download(full_path)
                        st.download_button("Download now", bytes_data, file_name=filename, key=f"dl2_priv_{filename}")
                with col3:
                    if st.button("👀 View Text", key=f"view_priv_{filename}"):
                        bytes_data = conn.storage.from_("private-pdfs").download(full_path)
                        text = extract_text_from_pdf(bytes_data)
                        st.text_area("Extracted text", text, height=400)
        else:
            st.info("No private PDFs yet. Upload one above!")
    except:
        st.info("Your private library is empty.")

st.caption("✅ Hosted free on Streamlit Cloud • Data stored securely in Supabase • You + your 2 friends only")
