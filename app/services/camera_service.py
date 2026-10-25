from threading import Condition, Event, Thread, current_thread

import cv2


class CameraError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class CameraManager:
    def __init__(
        self,
        device_index,
        width,
        height,
        fps,
        capture_factory=None,
        frame_encoder=None,
        startup_timeout=5.0,
    ):
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps
        self.capture_factory = capture_factory or cv2.VideoCapture
        self.frame_encoder = frame_encoder or cv2.imencode
        self.startup_timeout = startup_timeout
        self._condition = Condition()
        self._camera_state = "unknown"
        self._stream_state = "idle"
        self._error_code = None
        self._latest_frame = None
        self._frame_sequence = 0
        self._stop_event = None
        self._ready_event = None
        self._worker = None
        self._viewer_id = None

    def status(self):
        with self._condition:
            return {
                "camera": self._camera_state,
                "stream": self._stream_state,
                "error_code": self._error_code,
            }

    @property
    def latest_frame(self):
        with self._condition:
            return self._latest_frame

    def owns_active_viewer(self, viewer_id):
        with self._condition:
            return self._stream_state == "streaming" and self._viewer_id == viewer_id

    def start(self, viewer_id=None):
        with self._condition:
            if self._stream_state == "streaming":
                if self._viewer_id != viewer_id:
                    raise CameraError("camera_in_use")
                return self.status()
            if self._stream_state == "starting":
                if self._viewer_id != viewer_id:
                    raise CameraError("camera_in_use")
                ready_event = self._ready_event
            else:
                self._camera_state = "unknown"
                self._stream_state = "starting"
                self._error_code = None
                self._viewer_id = viewer_id
                self._latest_frame = None
                self._frame_sequence = 0
                self._stop_event = Event()
                self._ready_event = Event()
                ready_event = self._ready_event
                self._worker = Thread(
                    target=self._capture_loop,
                    args=(self._stop_event, self._ready_event),
                    name="camera-capture",
                    daemon=True,
                )
                self._worker.start()

        if not ready_event.wait(self.startup_timeout):
            with self._condition:
                self._stream_state = "error"
                self._error_code = "camera_start_timeout"
                self._stop_event.set()
                self._condition.notify_all()
            raise CameraError("camera_start_timeout")

        with self._condition:
            if self._stream_state != "streaming":
                raise CameraError(self._error_code or "camera_unavailable")
            return self.status()

    def stop(self, viewer_id=None, join_timeout=2.0, force=False):
        with self._condition:
            worker = self._worker
            if worker is None:
                if self._stream_state != "error":
                    self._stream_state = "idle"
                    self._camera_state = "unknown"
                    self._error_code = None
                self._viewer_id = None
                return self.status()
            if not force and self._viewer_id != viewer_id:
                raise CameraError("camera_in_use")
            self._stream_state = "stopping"
            self._stop_event.set()
            self._condition.notify_all()

        if worker is not current_thread():
            worker.join(join_timeout)
        return self.status()

    def disconnect(self, viewer_id):
        return self.stop(viewer_id=viewer_id)

    def wait_for_frame(self, after_sequence=0, timeout=None):
        with self._condition:
            self._condition.wait_for(
                lambda: self._frame_sequence > after_sequence
                or self._stream_state != "streaming",
                timeout=timeout,
            )
            if self._frame_sequence <= after_sequence:
                return None, self._frame_sequence
            return self._latest_frame, self._frame_sequence

    def _capture_loop(self, stop_event, ready_event):
        capture = None
        try:
            capture = self.capture_factory(self.device_index)
            if not capture.isOpened():
                self._set_error("camera_unavailable", camera_state="unavailable")
                return

            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            capture.set(cv2.CAP_PROP_FPS, self.fps)

            success, frame = capture.read()
            if not success:
                self._set_error("camera_read_failed")
                return

            encoded, image = self.frame_encoder(".jpg", frame)
            if not encoded:
                self._set_error("frame_encode_failed")
                return

            if stop_event.is_set():
                return
            self._publish_frame(image)
            ready_event.set()

            while not stop_event.is_set():
                success, frame = capture.read()
                if not success:
                    self._set_error("camera_read_failed")
                    break

                encoded, image = self.frame_encoder(".jpg", frame)
                if not encoded:
                    self._set_error("frame_encode_failed")
                    break

                self._publish_frame(image)
                stop_event.wait(1 / self.fps)
        except Exception:
            self._set_error("camera_error")
        finally:
            if capture is not None:
                try:
                    capture.release()
                except Exception:
                    self._set_error("camera_release_failed")

            with self._condition:
                if self._stream_state == "stopping":
                    self._stream_state = "idle"
                    self._camera_state = "unknown"
                    self._error_code = None
                elif self._stream_state == "starting" and stop_event.is_set():
                    self._stream_state = "idle"
                    self._camera_state = "unknown"
                if self._stream_state in ("idle", "error"):
                    self._viewer_id = None
                    self._worker = None
                ready_event.set()
                self._condition.notify_all()

    def _publish_frame(self, image):
        if hasattr(image, "tobytes"):
            image = image.tobytes()
        else:
            image = bytes(image)

        with self._condition:
            self._camera_state = "available"
            self._stream_state = "streaming"
            self._latest_frame = image
            self._frame_sequence += 1
            self._condition.notify_all()

    def _set_error(self, code, camera_state="error"):
        with self._condition:
            self._camera_state = camera_state
            self._stream_state = "error"
            self._error_code = code
            if self._stop_event is not None:
                self._stop_event.set()
            self._condition.notify_all()