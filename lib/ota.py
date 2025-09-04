# lib/ota.py
import uos
import ujson
import urequests as requests
import machine
import gc

class OTAUpdater:
    """
    A class to manage Over-The-Air updates for a MicroPython application.
    """

    def __init__(self, github_repo, module='', main_dir='main'):
        self._github_repo = github_repo.rstrip('/').replace('https://github.com/', '')
        self._main_dir = main_dir
        self._module = module.rstrip('/')
        
        try:
            with open(self._main_dir + '/main.json', 'r') as f:
                self.current_version = ujson.load(f)['version']
            print(f"Current version: {self.current_version}")
        except (OSError, KeyError):
            print("No version file found. Setting version to 0.")
            self.current_version = "0"


    def _get_latest_version(self):
        url = f'https://api.github.com/repos/{self._github_repo}/releases/latest'
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()['tag_name']
        return None

    def _download_and_install(self, version, files):
        for file in files:
            url = f'https://raw.githubusercontent.com/{self._github_repo}/{version}/{self._module}/{file}'
            print(f'Downloading {file} from {url}')
            
            response = requests.get(url)
            if response.status_code != 200:
                print(f'Failed to download {file}')
                return False

            path_parts = file.split('/')
            if len(path_parts) > 1:
                dir_path = self._main_dir
                for part in path_parts[:-1]:
                    dir_path += '/' + part
                    try:
                        uos.mkdir(dir_path)
                    except OSError as e:
                        if e.args[0] != 17: # EEXIST
                           raise
            
            with open(self._main_dir + '/' + file, 'w') as f:
                f.write(response.text)
            
            response.close()
            gc.collect()

        with open(self._main_dir + '/main.json', 'w') as f:
            ujson.dump({'version': version}, f)
        
        return True

    def download_and_install_update_if_available(self):
        """
        Checks for a new version and installs it if available.
        """
        latest_version = self._get_latest_version()
        if latest_version is None:
            print('Could not fetch latest version info.')
            return False, 'Could not fetch latest version.'
            
        print(f'Latest version is: {latest_version}')

        if latest_version > self.current_version:
            print(f'Newer version available. Updating from {self.current_version} to {latest_version}')
            
            url = f'https://raw.githubusercontent.com/{self._github_repo}/{latest_version}/{self._module}/main.json'
            response = requests.get(url)
            if response.status_code != 200:
                print('Could not fetch file list for new version.')
                return False, 'Could not fetch file list.'
            
            files_to_update = ujson.loads(response.text)['files']
            response.close()

            if self._download_and_install(latest_version, files_to_update):
                print('Update successful. Rebooting...')
                machine.reset()
                return True, 'Update successful.'
            else:
                print('Update failed.')
                return False, 'Update failed during download.'

        else:
            print('Current version is up to date.')
            return False, 'No new update available.'