import type { Metadata } from "next";
import { ReceiptView } from "@/components/billing/receipt-view";

export const metadata: Metadata = { title: "Receipt" };

export default function ReceiptPage() {
  return <ReceiptView />;
}
