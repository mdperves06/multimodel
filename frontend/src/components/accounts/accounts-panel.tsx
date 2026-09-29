"use client";

import { KeyRoundIcon, PlusIcon } from "lucide-react";
import { useState } from "react";
import { CardGridSkeleton, EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { useAccounts } from "@/lib/hooks";
import type { Account } from "@/lib/types";
import { DisconnectDialog, useTestAccount } from "./account-actions";
import { AccountCard } from "./account-card";
import { ConnectProviderDialog } from "./connect-provider-dialog";

export function AccountsPanel({ detailed = false, title }: { detailed?: boolean; title?: string }) {
  const { data, error, isLoading, mutate } = useAccounts();
  const { testingId, test } = useTestAccount();
  const [connectOpen, setConnectOpen] = useState(false);
  const [toDisconnect, setToDisconnect] = useState<Account | null>(null);

  const connectButton = (
    <Button onClick={() => setConnectOpen(true)}>
      <PlusIcon /> Connect Provider
    </Button>
  );

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        {title ? <h2 className="text-lg font-semibold tracking-tight">{title}</h2> : <span />}
        {data && data.length > 0 && connectButton}
      </div>

      {isLoading ? (
        <CardGridSkeleton />
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => mutate()} />
      ) : data && data.length === 0 ? (
        <EmptyState
          icon={KeyRoundIcon}
          title="No providers connected"
          description="Connect an authorized API account to start generating. Credentials are encrypted and never shown again."
          action={connectButton}
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data?.map((account) => (
            <AccountCard
              key={account.id}
              account={account}
              detailed={detailed}
              testing={testingId === account.id}
              onTest={() => test(account)}
              onDisconnect={detailed ? () => setToDisconnect(account) : undefined}
            />
          ))}
        </div>
      )}

      <ConnectProviderDialog open={connectOpen} onOpenChange={setConnectOpen} />
      <DisconnectDialog
        account={toDisconnect}
        open={toDisconnect !== null}
        onOpenChange={(o) => !o && setToDisconnect(null)}
      />
    </section>
  );
}
