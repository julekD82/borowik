import { aboutOpen } from "../state/store";
import { Icon } from "./icons";

const close = () => { aboutOpen.value = false; };

export function AboutDialog() {
  if (!aboutOpen.value) return null;
  return (
    <div class="overlay" onClick={(event) => { if (event.target === event.currentTarget) close(); }}>
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="about-title">
        <button type="button" class="icon-button dialog-close" aria-label="Zamknij" onClick={close}><Icon name="close" /></button>
        <h2 id="about-title">O danych i ograniczeniach</h2>
        <p>
          Borowik porównuje lasy w wybranym promieniu: siedlisko (skład drzew, typ siedliska), pogodę i to, ilu innych
          grzybiarzy można spotkać. To model ekspercki, nieskalibrowany na danych z terenu. Wynik porównuje miejsca w tej
          analizie i nie jest prawdopodobieństwem znalezienia grzybów.
        </p>
        <ul>
          <li>Klasy na mapie to procent najlepszych wydzieleń w tej analizie (najlepsze 5%, 5–20%, 20–50%) — te same co w eksporcie na telefon.</li>
          <li>Panel pogody pokazuje fakty: dzienny opad (radar IMGW scalony z modelem, prognoza Open-Meteo), sumę z 26 dni i normę z E-OBS 1991–2020. Pomiar i norma pochodzą z różnych źródeł, więc porównanie jest przybliżone.</li>
          <li>Wilgotność na mapie to składnik modelu; w obecnym modelu najmocniej liczy się ostatni deszcz, a dane z Bielefeld wskazują, że deszcz działa mniej więcej równo przez ok. 3 tygodnie.</li>
          <li>„Nawiguj” prowadzi do środka wydzielenia lub rejonu, nie do parkingu ani wejścia do lasu.</li>
          <li>Rezerwaty i parki narodowe są wykluczone; okresowe zakazy wstępu sprawdzane są tylko dla najlepszych wydzieleń, na dzień przygotowania analizy.</li>
        </ul>
        <p class="sources">
          Źródła: <a href="https://www.bdl.lasy.gov.pl/" target="_blank" rel="noopener noreferrer">Bank Danych o Lasach</a>,{" "}
          <a href="https://danepubliczne.imgw.pl/" target="_blank" rel="noopener noreferrer">IMGW-PIB (radar RainGRS)</a>,{" "}
          <a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer">Open-Meteo</a>,{" "}
          <a href="https://surfobs.climate.copernicus.eu/" target="_blank" rel="noopener noreferrer">E-OBS</a>, GDOŚ,{" "}
          <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>; podkład{" "}
          <a href="https://openfreemap.org/" target="_blank" rel="noopener noreferrer">OpenFreeMap</a>.
        </p>
        <p class="sources" lang="en">
          {"We acknowledge the E-OBS dataset from the EU-FP6 project UERRA (https://www.uerra.eu) and the Copernicus Climate Change Service, and the data providers in the ECA&D project (https://www.ecad.eu)."}
        </p>
        <p class="sources" lang="en">
          Cornes, R., G. van der Schrier, E.J.M. van den Besselaar, P.D. Jones (2018): An Ensemble Version of the E-OBS
          Temperature and Precipitation Datasets. J. Geophys. Res. Atmos., 123. doi:10.1029/2017JD028200.
        </p>
      </div>
    </div>
  );
}
