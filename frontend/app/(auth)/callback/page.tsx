import { Suspense } from "react";
import CallbackClient from "@/components/CallbackClient";

export default function CallbackPage() {
  return (
    <Suspense>
      <CallbackClient />
    </Suspense>
  );
}
