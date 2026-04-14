# lib/scheduler.py
import ujson
import uos
import time

class Scheduler:
    def __init__(self, filepath='schedules.json'):
        self.filepath = filepath
        self.schedules = []

    def load_schedules(self):
        """Loads schedules from the JSON file into memory."""
        try:
            with open(self.filepath, 'r') as f:
                self.schedules = ujson.load(f)
            print(f"Loaded {len(self.schedules)} schedules from {self.filepath}")
        except (OSError, ValueError):
            print("schedules.json not found or invalid, starting with an empty schedule list.")
            self.schedules = []
        return self.schedules

    def save_schedules(self):
        """Saves the current schedules from memory to the JSON file."""
        try:
            with open(self.filepath, 'w') as f:
                ujson.dump(self.schedules, f)
            print(f"Saved {len(self.schedules)} schedules to {self.filepath}")
        except OSError as e:
            print(f"Failed to save schedules: {e}")

    def get_schedules(self):
        """Returns the list of all schedules."""
        return self.schedules

    def add_schedule(self, data):
        """Adds a new schedule and saves the list."""
        # Generate a unique ID using the current timestamp
        data['id'] = time.time()
        self.schedules.append(data)
        self.save_schedules()
        return data

    def update_schedule(self, schedule_id, data):
        """Updates an existing schedule by its ID."""
        for i, sched in enumerate(self.schedules):
            if sched.get('id') == schedule_id:
                self.schedules[i] = data
                self.save_schedules()
                return data
        return None # Not found

    def delete_schedule(self, schedule_id):
        """Deletes a schedule by its ID."""
        original_len = len(self.schedules)
        self.schedules = [s for s in self.schedules if s.get('id') != schedule_id]
        if len(self.schedules) < original_len:
            self.save_schedules()
            return True
        return False
