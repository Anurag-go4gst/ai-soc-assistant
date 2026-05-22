export function SplTracePanel() {
  return (
    <section className="panel">
      <h2>SPL Trace Panel</h2>
      <code>index=auth earliest=-15m latest=now | stats count by user</code>
    </section>
  );
}
