from tempfile import NamedTemporaryFile, mkstemp
import os

class TempResourceManager(object):
    """ Manage all requests for temporary files, maps, etc.

    We use this so that we can register it to monitor kill signals and
    do all tidy up in one place.
    """
    FILE = 0
    MAP = 0
    REGION = 0

    def __init__(self):
        self.temp_files = set()

    def temp_filename(self, prefix, suffix=''):
        """ mkstemp annoying opens a unix file descriptor instead of just creating a filename """
        f, filename = mkstemp(prefix=prefix, suffix=suffix)
        self.temp_files.add((self.FILE, filename))
        os.close(f)
        return filename

    def release(self, filename, resource_type=FILE):
        if resource_type == TempResourceManager.FILE:
            os.remove(self.filename)
        elif resource_type == TempResourceManager.MAP:
            pass
        elif resource_type == TempResourceManager.REGION:
            pass


trm = TempResourceManager()
