import { localizedMetadata } from "@/lib/locale-server";
import ForteWorkspace from "@/components/forte-workspace";

export const dynamic = "force-dynamic";
export const generateMetadata = () => localizedMetadata("Проверки - Forte Vision", "Тексерулер - Forte Vision", "Reviews - Forte Vision", { robots: { index: false, follow: false } });

export default function WorkspacePage() {
  return <ForteWorkspace />;
}
