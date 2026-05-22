export function AlertList() {
  return (
    <section className="panel tall">
      <h2>Alert List</h2>
      <div className="listItem critical">Failed login spike from VPN segment</div>
      <div className="listItem warning">Database pool exhaustion signal</div>
      <div className="listItem info">OT telemetry anomaly candidate</div>
    </section>
  );
}
