import type { Metadata } from "next";
import "./globals.css";
import { Toaster } from "react-hot-toast";
import ThemeProvider from "@/components/ThemeProvider";

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
    <html lang="en" suppressHydrationWarning>
      <body className="bg-axon-bg text-axon-text antialiased">
        <ThemeProvider>
          {children}
          <Toaster
            position="bottom-right"
            toastOptions={{
              style: {
                background: "#111120",
                color: "#e2e8f0",
                border: "1px solid #1e1e32",
                fontFamily: "'Inter', sans-serif",
              },
              success: { iconTheme: { primary: "#34d399", secondary: "#0a0a12" } },
              error:   { iconTheme: { primary: "#ff4444", secondary: "#0a0a12" } },
            }}
          />
        </ThemeProvider>
      </body>
    </html>
  );
}
