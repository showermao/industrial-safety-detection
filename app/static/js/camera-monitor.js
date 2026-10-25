import axios from "axios";
import "bootstrap/dist/css/bootstrap.min.css";
import "../css/tailwind.input.css";
import { createApp, h, onBeforeUnmount, ref } from "vue";

export function createCameraApi(csrfToken = "") {
  const client = axios.create({ baseURL: "/api/v1", headers: { Accept: "application/json" } });
  if (csrfToken) client.defaults.headers.common["X-CSRF-Token"] = csrfToken;
  return client;
}
export const cameraApi = createCameraApi();
export function createViewerId(random = globalThis.crypto?.randomUUID) {
  const value = random ? random() : `${Date.now()}-${Math.random()}`;
  return `viewer-${value.replace(/[^A-Za-z0-9_-]/g, "")}`;
}
const labels = { idle: "待機", starting: "啟動中", streaming: "串流中", stopping: "停止中", error: "發生錯誤" };
const resultLabels = { normal: "正常", unrecognized: "無法辨識", problem: "問題" };
const errorMessage = (error) => error?.response?.data?.message || "相機操作失敗，請稍後再試";

export function createCameraMonitorComponent({ api = cameraApi } = {}) {
  return {
    name: "CameraMonitor",
    setup() {
      const stream = ref("idle"); const message = ref(""); const imageSource = ref("");
      const resultImage = ref(""); const result = ref(null); const recorded = ref(false); const captureMode = ref("manual"); const captureSeconds = ref(10);
      const viewerId = createViewerId(); let stopped = false; let captureTimer = null;
      const clearStream = () => { imageSource.value = ""; };
      const stopAutoCapture = () => { if (captureTimer) { clearInterval(captureTimer); captureTimer = null; } };
      const capture = async (save = false) => {
        if (stream.value !== "streaming") return;
        try { const response = await api.post("/video/capture", { viewer_id: viewerId, save }); result.value = response.data.data; resultImage.value = result.value.image || ""; recorded.value = save; }
        catch (error) { message.value = errorMessage(error); }
      };
      const record = async () => {
        if (!result.value || recorded.value) return;
        try { const response = await api.post("/video/records", { viewer_id: viewerId, result: result.value }); result.value.record_id = response.data.data.record_id; recorded.value = true; message.value = "檢測結果已紀錄"; }
        catch (error) { message.value = errorMessage(error); }
      };
      const startAutoCapture = () => { stopAutoCapture(); if (captureMode.value === "auto" && stream.value === "streaming") captureTimer = setInterval(() => capture(true), Math.max(1, Number(captureSeconds.value)) * 1000); };
      const start = async () => {
        if (["starting", "streaming"].includes(stream.value)) return;
        stopped = false; clearStream(); stopAutoCapture(); message.value = "正在啟動相機…"; stream.value = "starting";
        try { await api.post("/video/start", { viewer_id: viewerId }); if (stopped) return; stream.value = "streaming"; imageSource.value = `/api/v1/video/stream?viewer_id=${encodeURIComponent(viewerId)}&t=${Date.now()}`; message.value = "即時影像已啟動"; startAutoCapture(); }
        catch (error) { stream.value = "error"; message.value = errorMessage(error); clearStream(); }
      };
      const stop = async () => {
        if (["idle", "stopping"].includes(stream.value)) return;
        stopped = true; stopAutoCapture(); stream.value = "stopping"; clearStream();
        try { await api.post("/video/stop", { viewer_id: viewerId }); stream.value = "idle"; message.value = "即時影像已停止"; }
        catch (error) { stream.value = "error"; message.value = errorMessage(error); }
      };
      const forceStop = async () => {
        stopAutoCapture();
        try { await api.post("/video/force-stop"); stream.value = "idle"; clearStream(); message.value = "已強制停止遺留的相機連線"; }
        catch (error) { message.value = errorMessage(error); }
      };
      const streamFailed = () => { if (stream.value === "streaming") { stream.value = "error"; message.value = "影像串流中斷"; clearStream(); stopAutoCapture(); } };
      onBeforeUnmount(() => { stopped = true; stopAutoCapture(); clearStream(); if (["starting", "streaming", "error"].includes(stream.value)) api.post("/video/stop", { viewer_id: viewerId }).catch(() => {}); });
      return { stream, message, imageSource, resultImage, result, recorded, captureMode, captureSeconds, start, stop, forceStop, capture, record, streamFailed, startAutoCapture, labels, resultLabels };
    },
    render() {
      const busy = ["starting", "stopping"].includes(this.stream); const streaming = this.stream === "streaming" && this.imageSource; const data = this.result;
      return h("div", { class: "camera-monitor" }, [
        h("div", { class: "camera-toolbar" }, [h("div", [h("p", { class: "eyebrow" }, "YOLOV8 INSPECTION"), h("h2", { class: "camera-title" }, "即時影像檢測")]), h("span", { class: ["camera-status", `camera-status-${this.stream}`], role: "status" }, this.labels[this.stream])]),
        h("div", { class: "camera-frame", "aria-live": "polite" }, [streaming ? h("img", { src: this.imageSource, alt: "即時相機影像", onError: this.streamFailed }) : h("div", { class: "camera-placeholder" }, [h("strong", {}, this.stream === "error" ? "相機無法使用" : this.labels[this.stream]), h("span", {}, this.message || "啟動相機後開始檢測")])]),
        h("div", { class: "camera-controls" }, [h("button", { class: "primary-button", type: "button", disabled: busy || streaming, onClick: this.start }, "啟動即時影像"), h("button", { class: "secondary-button", type: "button", disabled: this.stream === "idle" || busy, onClick: this.stop }, "停止"), h("button", { class: "secondary-button", type: "button", disabled: busy, onClick: this.forceStop }, "強制停止"), this.stream === "error" ? h("button", { class: "secondary-button", type: "button", disabled: busy, onClick: this.start }, "重新連線") : null]),
        h("div", { class: "capture-settings", "aria-label": "擷取設定" }, [h("label", {}, ["擷取模式", h("select", { value: this.captureMode, onChange: (e) => { this.captureMode = e.target.value; this.startAutoCapture(); } }, [h("option", { value: "manual" }, "手動擷取"), h("option", { value: "auto" }, "自動擷取")])]), h("label", {}, ["自動擷取間隔（秒）", h("input", { type: "number", min: "1", max: "3600", value: this.captureSeconds, disabled: this.captureMode !== "auto", onInput: (e) => { this.captureSeconds = e.target.value; this.startAutoCapture(); } })]), h("button", { class: "primary-button", type: "button", disabled: !streaming, onClick: this.capture }, "擷取並比對")]),
        data ? h("section", { class: "inspection-result", "aria-live": "polite" }, [h("div", { class: "result-heading" }, [h("h3", {}, "比對結果"), h("span", { class: ["result-badge", `result-${data.status}`] }, this.resultLabels[data.status] || data.status_label)]), this.resultImage ? h("img", { class: "result-image", src: this.resultImage, alt: "YOLOv8 比對結果" }) : null, h("dl", { class: "result-details" }, [h("dt", {}, "比對時間"), h("dd", {}, data.comparison_time), h("dt", {}, "問題說明"), h("dd", {}, data.problem_description)]), h("div", { class: "camera-controls" }, [h("button", { class: "primary-button", type: "button", disabled: this.recorded, onClick: this.record }, this.recorded ? "已紀錄" : "紀錄"), h("button", { class: "secondary-button", type: "button", onClick: () => { this.result = null; this.resultImage = ""; this.recorded = false; } }, "放棄，下一張")])]) : null,
        this.message ? h("p", { class: ["camera-message", this.stream === "error" ? "camera-message-error" : ""] }, this.message) : null,
      ]);
    },
  };
}
export function mountCameraMonitor(root, component) { return createApp(component).mount(root); }
const root = document.querySelector("#camera-monitor");
if (root) mountCameraMonitor(root, createCameraMonitorComponent({ api: createCameraApi(root.dataset.csrfToken || "") }));
