import { mobilePane } from "../state/store";
import { AboutDialog } from "./AboutDialog";
import { MapView } from "./MapView";
import { MobileTabs } from "./MobileTabs";
import { Sidebar } from "./Sidebar";
import { Toast } from "./StatusViews";
import { TopBar } from "./TopBar";

export function App() {
  return (
    <div class="app">
      <TopBar />
      <main class="workspace" data-pane={mobilePane.value}>
        <MobileTabs />
        <Sidebar />
        <section class="map-area" aria-label="Mapa">
          <MapView />
        </section>
      </main>
      <AboutDialog />
      <Toast />
    </div>
  );
}
