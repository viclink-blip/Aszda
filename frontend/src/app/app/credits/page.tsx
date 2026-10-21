import type { Metadata } from "next";
import { CreditsView } from "@/components/account/credits-view";

export const metadata: Metadata = { title: "Credits" };

export default function CreditsPage() {
  return <CreditsView />;
}
