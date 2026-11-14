import type { Metadata, Viewport } from "next";
import PwaBootstrap from "../components/pwa-bootstrap";
import "./globals.css";

export const metadata: Metadata = {
  title: "PulseGrid Health",
  description: "Population and workforce health intelligence",
  applicationName: "PulseGrid Health",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: [{ url: "/icon.svg", type: "image/svg+xml" }],
  },
  appleWebApp: {
    capable: true,
    title: "PulseGrid",
    statusBarStyle: "default",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#176b65",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <PwaBootstrap />
        {children}
      </body>
    </html>
  );
}
