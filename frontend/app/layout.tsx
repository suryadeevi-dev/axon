import type { Metadata } from "next";
import "./globals.css";
import { Toaster } from "react-hot-toast";

export const metadata: Metadata = {
  title: "AXON — Your Agent. Your Cloud.",
  description:
    "Autonomous AI agents with dedicated cloud compute. Chat with your agent, execute tasks, build anything.",
  openGraph: {
    title: "AXON",
    description: "Autonomous AI agents with dedicated cloud compute.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-axon-bg text-axon-text antialiased">
        {children}
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: "#0f0f1a",
              color: "#e2e2f0",
              border: "1px solid #1e1e2e",
              fontFamily: "'Inter', sans-serif",
            },
            success: { iconTheme: { primary: "#00ff88", secondary: "#08080f" } },
            error: { iconTheme: { primary: "#ff4444", secondary: "#08080f" } },
          }}
        />
      </body>
    </html>
  );
}
