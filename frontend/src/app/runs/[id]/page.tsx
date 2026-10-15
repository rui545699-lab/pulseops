import { Suspense } from "react";

import { RunDetailClient } from "@/components/run-detail";
import { PageLoading } from "@/components/states";

export default function RunPage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<PageLoading label="Loading investigation run" />}>
      <RunContent params={params} />
    </Suspense>
  );
}

async function RunContent({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RunDetailClient runId={id} />;
}
