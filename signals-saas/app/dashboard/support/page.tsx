import { PageHeader } from "@/components/ui";
import { Chat } from "@/components/Chat";

export default function SupportPage() {
  return (
    <>
      <PageHeader title="Support chat" subtitle="Ask about a signal, your subscription or your setup. Attach screenshots of trades if it helps." />
      <Chat me="USER" />
    </>
  );
}
