import Link from "next/link";

export default function OfflinePage() {
  return (
    <main
      style={{
        maxWidth: 560,
        minHeight: "70vh",
        margin: "0 auto",
        padding: "48px 22px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "flex-start",
        gap: 12,
        color: "#142b45",
        fontFamily: "Arial, Helvetica, sans-serif",
      }}
    >
      <div style={{ width: 48, height: 48, display: "grid", placeItems: "center", borderRadius: 15, background: "#dff4ef", color: "#12665f", fontSize: 27, fontWeight: 800 }}>P</div>
      <p style={{ color: "#176b65", fontSize: 11, fontWeight: 800, letterSpacing: 1.4 }}>PULSEGRID HEALTH</p>
      <h1 style={{ margin: 0, fontSize: 34 }}>You’re offline</h1>
      <p style={{ color: "#68788c", lineHeight: 1.6 }}>
        PulseGrid could not reach the network. Reconnect to continue to your
        workspace. For your security, private workspace data is not stored for
        offline access.
      </p>
      <Link href="/" style={{ display: "inline-flex", alignItems: "center", minHeight: 44, padding: "10px 16px", borderRadius: 8, background: "#176b65", color: "#fff", fontWeight: 700, textDecoration: "none" }}>Try again</Link>
    </main>
  );
}
