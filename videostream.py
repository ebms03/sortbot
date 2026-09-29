import threading
import cv2


class VideoStream:
    def __init__(self, src):
        self._frame_index = 0
        self.cap = cv2.VideoCapture(src)
        if not self.cap.isOpened():
            print(f"Error: Could not open video stream [{src}]")
            exit()
        # print("Width:", self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        # print("Height:", self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        # print("FPS:", self.cap.get(cv2.CAP_PROP_FPS))
        # print("Total Frames:", int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)))

        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._ret, self._frame = self.cap.read()
        self.running = True

        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()

    def update(self):
        while self.running:
            ret, frame = self.cap.read()

            if not ret:
                continue
            
            with self.lock:
                self._frame = frame
                self._ret = ret
                self._frame_index += 1

    def read(self):
        with self.lock:
            return self._ret, self._frame, self._frame_index

    def stop(self):
        self.running = False
        self.cap.release()
