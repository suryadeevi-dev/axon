// Server component wrapper — required for static export of dynamic routes
import AgentPageClient from "@/components/AgentPageClient";

export function generateStaticParams() {
  return [];
}

export const dynamicParams = true;

export default function AgentPage() {
  return <AgentPageClient />;
}
