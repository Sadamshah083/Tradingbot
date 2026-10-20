import { PageHeader } from "@/components/ui";
import { SignalsTable } from "@/components/SignalsTable";
import { NewSignalForm } from "@/components/NewSignalForm";

export default function AdminSignalsPage() {
  return (
    <>
      <PageHeader title="Active signals" subtitle="Everything TradingView sends to POST /api/webhook/signal appears here instantly. Edit levels, close at TP/SL or cancel." action={<NewSignalForm />} />
      <SignalsTable admin />
    </>
  );
}
