import type { Metadata } from "next";
import { AccountsPanel } from "@/components/accounts/accounts-panel";
import { PageHeader } from "@/components/states";

export const metadata: Metadata = { title: "Accounts" };

export default function AccountsPage() {
  return (
    <>
      <PageHeader
        title="Connected accounts"
        description="Authorized provider connections used to run your jobs."
      />
      <AccountsPanel detailed />
    </>
  );
}
