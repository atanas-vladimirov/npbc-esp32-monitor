# lib/ota.py
import uos
import ujson
import urequests as requests
import machine
import gc
import time # Import time for sleeping
from micropython import const

class OTAUpdater:
    """
    A class to manage Over-The-Air updates for a MicroPython application
    with robust error handling, timeouts, and content validation.
    """
    _TIMEOUT = 10
    _MAX_RETRIES = 3 # Number of times to retry on a network busy error

    def __init__(self, github_repo, module='', main_dir='main'):
        self._TIMEOUT = 10
        self.github_repo = github_repo.rstrip('/').replace('https://github.com/', '')
        if len(self.github_repo.split('/')) != 2:
            raise ValueError("Invalid GitHub repository URL format. Expected 'user/repo'.")
        self._main_dir = main_dir
        self._module = module.rstrip('/')
        try:
            with open(self._main_dir + '/main.json', 'r') as f:
                self.current_version = ujson.load(f)['version']
            print(f"Current version: {self.current_version}")
        except (OSError, ValueError, KeyError):
            print("No valid version file found. Setting version to 0.")
            self.current_version = "0"

    def _request_json(self, url):
        """Perform a robust GET request expecting a JSON response, with retries for busy network."""
        gc.collect()

        for attempt in range(self._MAX_RETRIES):
            try:
                response = requests.get(url, timeout=self._TIMEOUT)
                if response.status_code != 200:
                    print(f"Error: Received status {response.status_code} from {url}")
                    return None, f"HTTP Error {response.status_code}"
                try:
                    json_data = response.json()
                    return json_data, "OK"
                except ValueError:
                    print("Error: Invalid JSON response.")
                    return None, "Invalid JSON response"
            except OSError as e:
                # --- NEW RETRY LOGIC IS HERE ---
                # Check if the error is EBUSY (error code 16)
                if e.args[0] == 16: # uerrno.EBUSY
                    print(f"Network busy, retrying in 2 seconds... (Attempt {attempt + 1}/{self._MAX_RETRIES})")
                    time.sleep(2)
                    continue # Go to the next attempt in the loop
                else:
                    # For any other network error, fail immediately
                    print(f"Network error: {e}")
                    return None, "Network error"
            finally:
                if 'response' in locals() and response:
                    response.close()

        # If all retries failed
        return None, "Network busy after multiple retries"

    # ... (the rest of the OTAUpdater class remains unchanged) ...
    def _get_latest_version(self):
        """Fetch the latest release version tag from GitHub."""
        url = f'https://api.github.com/repos/{self.github_repo}/releases/latest'
        json_data, msg = self._request_json(url)
        if json_data is None:
            return None, msg
        if 'tag_name' not in json_data:
            return None, "Malformed release data: 'tag_name' missing"
        return json_data['tag_name'], "OK"

    def _download_and_install(self, version, files):
        """Download and install all files for the given version."""
        for file in files:
            url = f'https://raw.githubusercontent.com/{self.github_repo}/{version}/{self._module}/{file}'
            print(f'Downloading {file}')

            try:
                response = requests.get(url, timeout=self._TIMEOUT)
                if response.status_code != 200:
                    print(f"Failed to download {file}: HTTP {response.status_code}")
                    return False

                path_parts = file.split('/')
                if len(path_parts) > 1:
                    dir_path = self._main_dir
                    for part in path_parts[:-1]:
                        dir_path += '/' + part
                        try: uos.mkdir(dir_path)
                        except OSError as e:
                            if e.args[0] != 17: raise

                with open(self._main_dir + '/' + file, 'w') as f:
                    f.write(response.text)

                response.close()
                gc.collect()

            except OSError as e:
                print(f"Failed to download {file} due to network error: {e}")
                return False

        try:
            with open(self._main_dir + '/main.json', 'w') as f:
                ujson.dump({'version': version, 'files': files}, f)
            return True
        except OSError:
            print("Failed to write new version file.")
            return False

    def download_and_install_update_if_available(self):
        """
        Checks for a new version and installs it if available.
        Returns a tuple of (bool, str) indicating success and a message.
        """
        latest_version, msg = self._get_latest_version()
        if latest_version is None:
            return False, f"Could not get latest version: {msg}"

        print(f'Latest version is: {latest_version}')

        if latest_version > self.current_version:
            print(f'Newer version available. Updating from {self.current_version} to {latest_version}')

            url = f'https://raw.githubusercontent.com/{self.github_repo}/{latest_version}/{self._module}/main.json'
            manifest_data, msg = self._request_json(url)

            if manifest_data is None:
                return False, f"Could not fetch update manifest: {msg}"
            if 'files' not in manifest_data:
                return False, "Malformed update manifest: 'files' list missing"

            if self._download_and_install(latest_version, manifest_data['files']):
                print('Update successful. Rebooting...')
                machine.reset()
                return True, 'Update successful.'
            else:
                return False, 'Update failed during file download.'
        else:
            print('Current version is up to date.')
            return False, 'No new update available.'