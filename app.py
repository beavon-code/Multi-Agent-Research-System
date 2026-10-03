 
import time
from datetime import datetime
 
import streamlit as st
 
from src.agents.agents import build_search_agent, build_reader_agent, writer_chain, critic_chain
 
 
# --------------------------------------------------------------------------- #
# Page setup
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="Research Agent", page_icon="🔎", layout="wide")
 
st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; max-width: 1100px;}
      .step-label {font-size: 0.8rem; text-transform: uppercase; letter-spacing: .08em; opacity: .6;}
    </style>
    """,
    unsafe_allow_html=True,
)
 
if "history" not in st.session_state:
    st.session_state.history = []      # list of {"topic", "time", "state", "timings"}
if "current" not in st.session_state:
    st.session_state.current = None
 
 
def as_text(result) -> str:
    """Chains may return a str or an AIMessage — normalise to text."""
    return getattr(result, "content", result) if result is not None else ""
 
 
# --------------------------------------------------------------------------- #
# Pipeline (same steps as run_research_pipeline, with live UI updates)
# --------------------------------------------------------------------------- #
def run_pipeline_with_ui(topic: str, snippet_chars: int) -> dict:
    state, timings = {}, {}
    progress = st.progress(0, text="Starting…")
 
    def step(n, label, icon):
        progress.progress((n - 1) / 4, text=f"Step {n}/4 — {label}")
        return st.status(f"{icon} Step {n}: {label}", expanded=False), time.perf_counter()
 
    # 1. Search
    box, t0 = step(1, "Search agent is finding sources…", "🌐")
    with box:
        search_agent = build_search_agent()
        result = search_agent.invoke({
            "messages": [("user", f"Find recent, reliable and detailed information about: {topic}")]
        })
        state["search_results"] = result["messages"][-1].content
        st.markdown(state["search_results"])
    timings["search"] = time.perf_counter() - t0
    box.update(label=f"🌐 Step 1: Search complete ({timings['search']:.1f}s)", state="complete")
 
    # 2. Read / scrape
    box, t0 = step(2, "Reader agent is scraping the best source…", "📖")
    with box:
        reader_agent = build_reader_agent()
        result = reader_agent.invoke({
            "messages": [("user",
                          f"Based on the following search results about '{topic}', "
                          f"pick the most relevant URL and scrape it for deeper content.\n\n"
                          f"Search results:\n{state['search_results'][:snippet_chars]}")]
        })
        state["scraped_content"] = result["messages"][-1].content
        st.markdown(state["scraped_content"])
    timings["reader"] = time.perf_counter() - t0
    box.update(label=f"📖 Step 2: Scraping complete ({timings['reader']:.1f}s)", state="complete")
 
    # 3. Write
    box, t0 = step(3, "Writer is drafting the report…", "✍️")
    with box:
        research_combined = (
            f"SEARCH RESULTS:\n{state['search_results']}\n\n"
            f"DETAILED SCRAPED CONTENT:\n{state['scraped_content']}"
        )
        state["report"] = as_text(writer_chain.invoke({"topic": topic, "research": research_combined}))
        st.caption("Draft ready — see the Report tab below.")
    timings["writer"] = time.perf_counter() - t0
    box.update(label=f"✍️ Step 3: Report drafted ({timings['writer']:.1f}s)", state="complete")
 
    # 4. Critique
    box, t0 = step(4, "Critic is reviewing the report…", "🧐")
    with box:
        state["feedback"] = as_text(critic_chain.invoke({"report": state["report"]}))
        st.caption("Review ready — see the Critic Feedback tab below.")
    timings["critic"] = time.perf_counter() - t0
    box.update(label=f"🧐 Step 4: Review complete ({timings['critic']:.1f}s)", state="complete")
 
    progress.progress(1.0, text=f"Done in {sum(timings.values()):.1f}s")
    return {"state": state, "timings": timings}
 
 
# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("⚙️ Settings")
    snippet_chars = st.slider(
        "Search text passed to reader (chars)", 400, 4000, 800, step=200,
        help="How much of the search results the reader agent sees when choosing a URL.",
    )
 
    st.divider()
    st.header("🕘 History")
    if not st.session_state.history:
        st.caption("No runs yet.")
    for i, run in enumerate(reversed(st.session_state.history)):
        if st.button(f"{run['topic'][:40]}  ·  {run['time']}", key=f"hist_{i}", use_container_width=True):
            st.session_state.current = run
    if st.session_state.history and st.button("Clear history", type="secondary"):
        st.session_state.history, st.session_state.current = [], None
        st.rerun()
 
 
# --------------------------------------------------------------------------- #
# Main area
# --------------------------------------------------------------------------- #
st.title("🔎 AI Research Assistant")
st.caption("Search → Read → Write → Critique, powered by LangChain agents.")
 
with st.form("research_form"):
    topic = st.text_input("Research topic", placeholder="e.g. Latest advances in solid-state batteries")
    submitted = st.form_submit_button("Run research", type="primary", use_container_width=True)
 
if submitted:
    if not topic.strip():
        st.warning("Please enter a topic.")
    else:
        try:
            with st.container(border=True):
                st.markdown('<div class="step-label">Pipeline progress</div>', unsafe_allow_html=True)
                run = run_pipeline_with_ui(topic.strip(), snippet_chars)
            run.update(topic=topic.strip(), time=datetime.now().strftime("%H:%M"))
            st.session_state.history.append(run)
            st.session_state.current = run
        except Exception as exc:
            st.error(f"The pipeline failed: {exc}")
            st.exception(exc)
 
# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #
run = st.session_state.current
if run:
    state, timings = run["state"], run["timings"]
    st.subheader(f"Results: {run['topic']}")
 
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total time", f"{sum(timings.values()):.1f}s")
    c2.metric("Report words", len(state["report"].split()))
    c3.metric("Sources (chars)", f"{len(state['search_results']):,}")
    c4.metric("Scraped (chars)", f"{len(state['scraped_content']):,}")
 
    tab_report, tab_feedback, tab_search, tab_scraped = st.tabs(
        ["📄 Report", "🧐 Critic Feedback", "🌐 Search Results", "📖 Scraped Content"]
    )
    with tab_report:
        st.markdown(state["report"])
    with tab_feedback:
        st.markdown(state["feedback"])
    with tab_search:
        st.markdown(state["search_results"])
    with tab_scraped:
        st.markdown(state["scraped_content"])
 
    slug = "".join(ch if ch.isalnum() else "_" for ch in run["topic"])[:50]
    full_md = (
        f"# Research Report: {run['topic']}\n\n{state['report']}\n\n---\n\n"
        f"## Critic Feedback\n\n{state['feedback']}\n"
    )
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Download report (.md)", full_md, file_name=f"{slug}_report.md",
                       mime="text/markdown", use_container_width=True)
    d2.download_button("⬇️ Download everything (.md)",
                       full_md + f"\n---\n\n## Search Results\n\n{state['search_results']}\n\n"
                                 f"## Scraped Content\n\n{state['scraped_content']}\n",
                       file_name=f"{slug}_full.md", mime="text/markdown", use_container_width=True)
elif not submitted:
    st.info("Enter a topic above and click **Run research** to start.")
 