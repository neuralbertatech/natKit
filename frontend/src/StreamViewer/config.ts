// Shared connection details for the stream_viewer websocket.
//
// This was duplicated verbatim in VisualProgramming/page.svelte and
// StreamViewer/page.svelte; a third copy (the IMU Experiment library) was one
// too many. Same-origin by construction, so the Vite dev proxy and the nginx
// production config both work without configuration.
export function getWebSocketUrl(): string {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${wsProtocol}//${window.location.host}/ws/stream_viewer`;
}
