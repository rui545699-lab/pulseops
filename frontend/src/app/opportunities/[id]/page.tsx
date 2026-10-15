import { Suspense } from "react";

import { OpportunityDetailClient } from "@/components/opportunity-detail";
import { PageLoading } from "@/components/states";

export default function OpportunityPage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<PageLoading label="Loading opportunity detail" />}>
      <OpportunityContent params={params} />
    </Suspense>
  );
}

async function OpportunityContent({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <OpportunityDetailClient opportunityId={id} />;
}
