import { ActivityLog } from "@/components/ActivityLog";
import { AudioPanel } from "@/components/AudioPanel";
import { CameraWindow } from "@/components/CameraWindow";
import { DemoTray } from "@/components/DemoTray";
import { Disclaimer } from "@/components/Disclaimer";
import { Header } from "@/components/Header";
import { MorningRecapCard } from "@/components/MorningRecapCard";
import { NamePrompt } from "@/components/NamePrompt";
import { StateHero } from "@/components/StateHero";
import { StateRibbon } from "@/components/StateRibbon";
import { VitalsPanel } from "@/components/VitalsPanel";

export default function Home() {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-5 sm:px-8">
      <Header />
      <StateHero />
      <NamePrompt />
      <main className="mt-9 grid content-start gap-12 lg:grid-cols-[minmax(0,1fr)_21rem] lg:gap-16">
        <div className="flex flex-col gap-7">
          <CameraWindow />
          <StateRibbon />
          <div className="mt-4"><ActivityLog /></div>
        </div>
        <aside className="flex flex-col gap-12 lg:pt-1">
          <VitalsPanel />
          <AudioPanel />
        </aside>
      </main>
      <MorningRecapCard />
      <DemoTray />
      <Disclaimer />
    </div>
  );
}
