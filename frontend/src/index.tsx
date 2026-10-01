import "maplibre-gl/dist/maplibre-gl.css";
import "./styles/tokens.css";
import "./styles/layout.css";
import "./styles/components.css";
import { render } from "preact";
import { App } from "./components/App";
import { startApp } from "./state/loader";

render(<App />, document.getElementById("app")!);
void startApp();
