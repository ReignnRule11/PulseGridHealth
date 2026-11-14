export default function OfflinePage() {
  return (
    <main className="offline-page">
      <div className="offline-mark" aria-hidden="true">P</div>
      <p className="eyebrow">PULSEGRID HEALTH</p>
      <h1>You’re offline</h1>
      <p>
        PulseGrid could not reach the network. Reconnect to continue to your
        workspace. For your security, private workspace data is not stored for
        offline access.
      </p>
      <button type="button" onClick="window.location.reload()">Try again</button>
    </main>
  );
}
