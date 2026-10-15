import { AlertIcon } from "@/components/icons";

export function PageLoading({ label = "Loading PulseOps…" }: { label?: string }) {
  return (
    <div aria-label={label} role="status" className="space-y-7">
      <div className="h-8 w-64 animate-pulse rounded bg-[#e9e9e5]" />
      <div className="grid gap-4 md:grid-cols-4">
        {[0, 1, 2, 3].map((item) => (
          <div key={item} className="h-28 animate-pulse rounded-xl border border-[#e5e5e1] bg-white" />
        ))}
      </div>
      <div className="h-64 animate-pulse rounded-xl border border-[#e5e5e1] bg-white" />
    </div>
  );
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-[#ead4cf] bg-[#fff8f6] p-6">
      <div className="flex items-start gap-3">
        <AlertIcon className="mt-0.5 size-5 text-[#9a4438]" />
        <div>
          <h2 className="text-sm font-semibold">Unable to load PulseOps</h2>
          <p className="mt-1 text-sm text-[#6d5b56]">{message}</p>
          {retry ? (
            <button type="button" onClick={retry} className="mt-4 text-sm font-semibold underline underline-offset-4">
              Try again
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-dashed border-[#d9d9d3] bg-white px-6 py-12 text-center">
      <p className="text-sm font-semibold">{title}</p>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#73736d]">{body}</p>
    </div>
  );
}
