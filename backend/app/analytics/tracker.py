import numpy as np
import time
from collections import OrderedDict
from scipy.spatial import distance as dist

class TrackedObject:
    def __init__(self, object_id, centroid, bbox, class_name="person"):
        self.object_id = object_id
        self.centroid = centroid  # (x, y)
        self.bbox = bbox  # (x1, y1, x2, y2)
        self.class_name = class_name
        self.first_seen = time.time()
        self.last_seen = time.time()
        self.disappeared_frames = 0
        self.history = [centroid]  # list of (x, y) coordinates
        self.velocity = 0.0  # pixels per second
        self.dwell_time = 0.0
        self.crossed_line = False
        self.in_zone = False
        self.zone_entry_time = None

    def update(self, centroid, bbox):
        now = time.time()
        dt = max(now - self.last_seen, 0.001)
        # compute velocity
        dx = centroid[0] - self.centroid[0]
        dy = centroid[1] - self.centroid[1]
        distance_moved = np.sqrt(dx**2 + dy**2)
        self.velocity = distance_moved / dt

        self.centroid = centroid
        self.bbox = bbox
        self.last_seen = now
        self.disappeared_frames = 0
        self.history.append(centroid)
        if len(self.history) > 30:
            self.history.pop(0)
        self.dwell_time = now - self.first_seen

class CentroidTracker:
    def __init__(self, max_disappeared=20, max_distance=60):
        self.next_object_id = 1
        self.objects = OrderedDict()
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def register(self, centroid, bbox, class_name="person"):
        obj = TrackedObject(self.next_object_id, centroid, bbox, class_name)
        self.objects[self.next_object_id] = obj
        self.next_object_id += 1
        return obj

    def deregister(self, object_id):
        if object_id in self.objects:
            del self.objects[object_id]

    def update(self, rects, class_names=None):
        """
        rects: list of [x1, y1, x2, y2]
        """
        if class_names is None:
            class_names = ["person"] * len(rects)

        if len(rects) == 0:
            for object_id in list(self.objects.keys()):
                self.objects[object_id].disappeared_frames += 1
                if self.objects[object_id].disappeared_frames > self.max_disappeared:
                    self.deregister(object_id)
            return self.objects

        input_centroids = np.zeros((len(rects), 2), dtype="int")
        for i, (startX, startY, endX, endY) in enumerate(rects):
            cX = int((startX + endX) / 2.0)
            cY = int((startY + endY) / 2.0)
            input_centroids[i] = (cX, cY)

        if len(self.objects) == 0:
            for i in range(0, len(rects)):
                self.register(input_centroids[i], rects[i], class_names[i])
        else:
            object_ids = list(self.objects.keys())
            object_centroids = [obj.centroid for obj in self.objects.values()]

            D = dist.cdist(np.array(object_centroids), input_centroids)
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]

            used_rows = set()
            used_cols = set()

            for (row, col) in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue

                if D[row, col] > self.max_distance:
                    continue

                object_id = object_ids[row]
                self.objects[object_id].update(input_centroids[col], rects[col])

                used_rows.add(row)
                used_cols.add(col)

            unused_rows = set(range(0, D.shape[0])).difference(used_rows)
            unused_cols = set(range(0, D.shape[1])).difference(used_cols)

            for row in unused_rows:
                object_id = object_ids[row]
                self.objects[object_id].disappeared_frames += 1
                if self.objects[object_id].disappeared_frames > self.max_disappeared:
                    self.deregister(object_id)

            for col in unused_cols:
                self.register(input_centroids[col], rects[col], class_names[col])

        return self.objects
