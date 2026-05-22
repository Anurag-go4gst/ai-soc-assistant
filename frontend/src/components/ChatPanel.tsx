export function ChatPanel() {
  return (
    <section className="panel tall">
      <h2>Chat Panel</h2>
      <div className="message analyst">Summarize the current alert and recommended triage path.</div>
      <div className="message assistant">Placeholder assistant response. LangGraph and LLM logic are not connected.</div>
      <textarea placeholder="Ask a triage question..." />
    </section>
  );
}
