import AgentPageClient from "@/components/AgentPageClient";

// Static export requires at least one entry; 404.html provides the SPA fallback
// for real agent IDs not in this list (GitHub Pages SPA routing pattern).
export function generateStaticParams() {
  return [{ id: "new" }];
}

export default function AgentPage() {
  return <AgentPageClient />;
}
