"use client";

import { ErrorState } from "@/components/states";

export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="mx-auto flex min-h-screen max-w-md items-center px-4">
      <ErrorState
        className="w-full"
        message="An unexpected error occurred. Please try again."
        onRetry={reset}
      />
    </div>
  );
}
