import streamlit as st
from st_supabase_connection import SupabaseConnection
import PyPDF2
from io import BytesIO
import google.generativeai as genai
import json

st.set_page_config(page_title="DIBPS SO IT Revision Hub", layout="wide", page_icon="📚")
st.title("📚 DIBPS SO IT Revision Hub")
st.caption("Login • Shared + Private PDFs • AI Summaries • Quizzes • Flashcards • Chat")

# ── Supabase connection ──────────────────────────────────────────────────────
conn = st.connection("supabase", type=SupabaseConnection)

# ── Gemini setup ─────────────────────────────────────────────────────────────
# Get your FREE key at: https://aistudio.google.com/apikey
# Then in Streamlit Cloud → Manage app → Settings → Secrets, add:
#   GEMINI_API_KEY = "AIza..."
@st.cache_resource
def get_gemini_model():
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=(
            "You are an expert study assistant for Indian government IT exam preparation. "
            "Be concise, accurate, and exam-focused."
        ),
    )

# ── PDF text extraction ──────────────────────────────────────────────────────
def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PyPDF2.PdfReader(BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)[:12000]
    except Exception as e:
        st.error(f"Could not read PDF: {e}")
        return ""

# ── Gemini helper ─────────────────────────────────────────────────────────────
def ask_gemini(prompt: str) -> str:
    model = get_gemini_model()
    response = model.generate_content(prompt)
    return response.text

def clean_json(raw: str) -> str:
    """Strip markdown fences Gemini sometimes wraps around JSON."""
    return raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

# ════════════════════════════════════════════════════════════════════════════
#  LOGIN / SIGNUP
# ════════════════════════════════════════════════════════════════════════════
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
                except Exception:
                    st.error("Invalid email or password.")

    with tab_signup:
        with st.form("signup_form"):
            email = st.text_input("Email")
            password = st.text_input("Password (min 6 chars)", type="password")
            if st.form_submit_button("Create Account"):
                try:
                    conn.auth.sign_up({"email": email, "password": password})
                    st.success("Account created! Check your email to verify, then log in.")
                except Exception as e:
                    st.error(str(e))

    st.stop()

# ════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ════════════════════════════════════════════════════════════════════════════
user = st.session_state.user
st.sidebar.success(f"👋 {user.email}")
if st.sidebar.button("Logout"):
    conn.auth.sign_out()
    st.session_state.clear()
    st.rerun()

st.header(f"Welcome, {user.email.split('@')[0]}!")

tab_shared, tab_private, tab_ai = st.tabs([
    "🌍 Shared PDFs",
    "🔒 My Private PDFs",
    "🤖 AI Tools",
])

# ── Storage helpers ───────────────────────────────────────────────────────────
def safe_download(bucket: str, path: str):
    try:
        return conn.storage.from_(bucket).download(path)
    except Exception as e:
        st.error(f"Download failed: {e}")
        return None

def safe_upload(bucket: str, path: str, data: bytes) -> bool:
    try:
        conn.storage.from_(bucket).upload(path, data)
        return True
    except Exception as e:
        if "already exists" in str(e).lower():
            st.warning(f"'{path}' already exists. Rename the file and retry.")
        else:
            st.error(f"Upload error: {e}")
        return False

# ════════════════════════════════════════════════════════════════════════════
#  SHARED PDFs
# ════════════════════════════════════════════════════════════════════════════
with tab_shared:
    st.subheader("Shared PDFs — visible to all users")

    uploaded = st.file_uploader("Upload PDF to Shared library", type="pdf", key="shared_upload")
    if uploaded:
        if safe_upload("shared-pdfs", uploaded.name, uploaded.getvalue()):
            st.success(f"✅ Uploaded: {uploaded.name}")
            st.rerun()

    try:
        files = conn.storage.from_("shared-pdfs").list() or []
    except Exception:
        files = []

    if not files:
        st.info("No shared PDFs yet. Upload one above!")
    else:
        for fi in files:
            filename = fi["name"]
            col1, col2, col3 = st.columns([4, 1, 1])
            col1.write(f"📄 {filename}")
            with col2:
                if st.button("📥 Download", key=f"dl_shared_{filename}"):
                    data = safe_download("shared-pdfs", filename)
                    if data:
                        st.download_button("Save file", data=data,
                                           file_name=filename,
                                           key=f"save_shared_{filename}")
            with col3:
                if st.button("👀 View Text", key=f"view_shared_{filename}"):
                    data = safe_download("shared-pdfs", filename)
                    if data:
                        st.text_area("Extracted text", extract_text_from_pdf(data),
                                     height=300, key=f"txt_shared_{filename}")

# ════════════════════════════════════════════════════════════════════════════
#  PRIVATE PDFs
# ════════════════════════════════════════════════════════════════════════════
with tab_private:
    st.subheader("My Private PDFs — only you can see these")

    uploaded_private = st.file_uploader("Upload PDF to your Private section",
                                        type="pdf", key="private_upload")
    if uploaded_private:
        path = f"{user.id}/{uploaded_private.name}"
        if safe_upload("private-pdfs", path, uploaded_private.getvalue()):
            st.success(f"✅ Uploaded to your private library: {uploaded_private.name}")
            st.rerun()

    try:
        private_files = conn.storage.from_("private-pdfs").list(f"{user.id}/") or []
    except Exception:
        private_files = []

    if not private_files:
        st.info("No private PDFs yet. Upload one above!")
    else:
        for fi in private_files:
            filename = fi["name"]
            full_path = f"{user.id}/{filename}"
            col1, col2, col3 = st.columns([4, 1, 1])
            col1.write(f"🔒 {filename}")
            with col2:
                if st.button("📥 Download", key=f"dl_priv_{filename}"):
                    data = safe_download("private-pdfs", full_path)
                    if data:
                        st.download_button("Save file", data=data,
                                           file_name=filename,
                                           key=f"save_priv_{filename}")
            with col3:
                if st.button("👀 View Text", key=f"view_priv_{filename}"):
                    data = safe_download("private-pdfs", full_path)
                    if data:
                        st.text_area("Extracted text", extract_text_from_pdf(data),
                                     height=300, key=f"txt_priv_{filename}")

# ════════════════════════════════════════════════════════════════════════════
#  AI TOOLS
# ════════════════════════════════════════════════════════════════════════════
with tab_ai:
    st.subheader("🤖 AI-Powered Revision Tools")

    all_files = []
    try:
        for fi in (conn.storage.from_("shared-pdfs").list() or []):
            all_files.append({"label": f"[Shared] {fi['name']}",
                               "bucket": "shared-pdfs", "path": fi["name"]})
    except Exception:
        pass
    try:
        for fi in (conn.storage.from_("private-pdfs").list(f"{user.id}/") or []):
            all_files.append({"label": f"[Private] {fi['name']}",
                               "bucket": "private-pdfs",
                               "path": f"{user.id}/{fi['name']}"})
    except Exception:
        pass

    if not all_files:
        st.info("Upload PDFs in the Shared or Private tabs first, then come back here.")
        st.stop()

    selected_label = st.selectbox("Choose a PDF to work with",
                                  options=[f["label"] for f in all_files])
    selected = next(f for f in all_files if f["label"] == selected_label)

    # Cache extracted text so we don't re-download on every button click
    cache_key = f"text_{selected['bucket']}_{selected['path']}"
    if cache_key not in st.session_state:
        with st.spinner("Reading PDF…"):
            data = safe_download(selected["bucket"], selected["path"])
            st.session_state[cache_key] = extract_text_from_pdf(data) if data else ""

    pdf_text = st.session_state[cache_key]

    if not pdf_text.strip():
        st.warning("Could not extract text (PDF may be scanned/image-based).")
        st.stop()

    ai_tab1, ai_tab2, ai_tab3, ai_tab4 = st.tabs(
        ["📝 Summarize", "❓ Quiz me", "🃏 Flashcards", "💬 Chat with PDF"]
    )

    # ── Summarize ────────────────────────────────────────────────────────────
    with ai_tab1:
        if st.button("Generate Summary", type="primary"):
            with st.spinner("Summarizing…"):
                summary = ask_gemini(
                    "Summarize this document for exam revision:\n"
                    "1. Write a 3-sentence overview\n"
                    "2. List key topics as bullet points\n"
                    "3. State the top 3 facts to memorize for the exam\n\n"
                    f"Document:\n{pdf_text}"
                )
            st.markdown(summary)

    # ── Quiz ─────────────────────────────────────────────────────────────────
    with ai_tab2:
        num_q = st.slider("Number of questions", 3, 10, 5)
        if st.button("Generate Quiz", type="primary"):
            with st.spinner("Creating questions…"):
                raw = ask_gemini(
                    f"Create {num_q} multiple-choice questions from this document.\n"
                    "Return a JSON array ONLY — no markdown fences, no explanation:\n"
                    '[{"q":"question text","options":["A","B","C","D"],"answer":0}]\n'
                    "answer = 0-based index of the correct option.\n\n"
                    f"Document:\n{pdf_text}"
                )
            try:
                questions = json.loads(clean_json(raw))
                st.session_state["quiz"] = questions
            except json.JSONDecodeError:
                st.error("Could not parse quiz. Try again.")
                st.code(raw)

        if "quiz" in st.session_state:
            st.divider()
            for i, q in enumerate(st.session_state["quiz"]):
                st.markdown(f"**Q{i+1}. {q['q']}**")
                choice = st.radio("Pick an answer", options=q["options"],
                                  key=f"quiz_q{i}", index=None,
                                  label_visibility="collapsed")
                if choice is not None:
                    if q["options"].index(choice) == q["answer"]:
                        st.success("✅ Correct!")
                    else:
                        st.error(f"❌ Wrong. Correct answer: {q['options'][q['answer']]}")
                st.write("")

    # ── Flashcards ───────────────────────────────────────────────────────────
    with ai_tab3:
        num_cards = st.slider("Number of flashcards", 5, 20, 10)
        if st.button("Generate Flashcards", type="primary"):
            with st.spinner("Making flashcards…"):
                raw = ask_gemini(
                    f"Create {num_cards} flashcards from this document.\n"
                    "Return a JSON array ONLY — no markdown fences, no explanation:\n"
                    '[{"front":"term or question","back":"definition or answer"}]\n\n'
                    f"Document:\n{pdf_text}"
                )
            try:
                cards = json.loads(clean_json(raw))
                st.session_state["flashcards"] = cards
            except json.JSONDecodeError:
                st.error("Could not parse flashcards. Try again.")

        if "flashcards" in st.session_state:
            st.divider()
            cols = st.columns(2)
            for i, card in enumerate(st.session_state["flashcards"]):
                with cols[i % 2]:
                    with st.expander(f"🃏 {card['front']}"):
                        st.info(card["back"])

    # ── Chat with PDF ────────────────────────────────────────────────────────
    with ai_tab4:
        st.caption("Ask anything about this PDF. Chat history is kept for your session.")

        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []

        # Start a Gemini chat session primed with the PDF text
        if "gemini_chat" not in st.session_state:
            model = get_gemini_model()
            chat = model.start_chat(history=[])
            chat.send_message(
                f"I will ask you questions about this document. Use it as your reference:\n\n{pdf_text}"
            )
            st.session_state["gemini_chat"] = chat

        for msg in st.session_state["chat_history"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("Ask a question about this PDF…"):
            st.session_state["chat_history"].append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Thinking…"):
                    response = st.session_state["gemini_chat"].send_message(prompt)
                    answer = response.text
                st.markdown(answer)

            st.session_state["chat_history"].append({"role": "assistant", "content": answer})

        if st.button("Clear chat history"):
            st.session_state.pop("chat_history", None)
            st.session_state.pop("gemini_chat", None)
            st.rerun()

st.divider()
st.caption("✅ Hosted free on Streamlit Cloud · Data in Supabase · AI by Google Gemini")
