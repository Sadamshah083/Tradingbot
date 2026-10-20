import { PageHeader } from "@/components/ui";
import { SignalsTable } from "@/components/SignalsTable";

export default function UserSignalsPage() {
  return (
    <>
      <PageHeader title="Live signals feed" subtitle="Every signal carries an entry, a stop-loss and a take-profit. Use Copy to paste the levels into your broker." />
      <SignalsTable />
    </>
  );
}
