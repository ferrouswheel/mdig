from tempfile import NamedTemporaryFile, mkstemp
import os

class TempResourceManager(object):
    """ Manage all requests for temporary files, maps, etc.

    We use this so that we can register it to monitor kill signals and
    do all tidy up in one place.
    """
    FILE = 0
    MAP = 1
    REGION = 2

    def __init__(self):
        self.temp_files = set()

    def temp_filename(self, prefix, suffix=''):
        """ mkstemp annoying opens a unix file descriptor instead of just creating a filename """
        f, filename = mkstemp(prefix=prefix, suffix=suffix)
        self.temp_files.add((self.FILE, filename))
        os.close(f)
        return filename

    def release(self, filename, resource_type=FILE):
        identifier = (resource_type, filename)
        if identifier not in self.temp_files:
            return ValueError('No such temporary file known')
        self._release(filename, resource_type)
        self.temp_files.remove(identifier)

    def _release(self, filename, resource_type=FILE):
        if resource_type == TempResourceManager.FILE:
            os.remove(filename)
        elif resource_type == TempResourceManager.MAP:
            pass
        elif resource_type == TempResourceManager.REGION:
            pass

    def cleanup(self):
        for file_type, filename in self.temp_files:
            self._release(filename, file_type)


trm = TempResourceManager()
