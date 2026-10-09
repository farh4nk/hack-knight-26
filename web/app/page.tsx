import { AudioPanel } from "@/components/AudioPanel";
import { DebugPanel } from "@/components/DebugPanel";
import { DemoControls } from "@/components/DemoControls";
import { Disclaimer } from "@/components/Disclaimer";
import { Header } from "@/components/Header";
import { MorningRecapCard } from "@/components/MorningRecapCard";
import { SignalStats } from "@/components/SignalStats";
import { StreamCard } from "@/components/StreamCard";
import { BreathingCard, HeartRateCard } from "@/components/VitalsCard";

export default function Home() {
  return (
    <div className="mx-auto flex min-h-full w-full max-w-7xl flex-1 flex-col px-6">
      <Header />
      <main className="grid flex-1 grid-cols-1 gap-6 pb-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          <StreamCard />
          <AudioPanel />
          <DebugPanel />
        </div>
        <aside className="flex flex-col gap-6">
          <BreathingCard />
          <HeartRateCard />
          <MorningRecapCard />
          <SignalStats />
          <DemoControls />
        </aside>
      </main>
      <Disclaimer />
    </div>
  );
}
