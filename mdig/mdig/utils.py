def make_path(path):
    """ creates missing directories for the given path and
        returns a normalized absolute version of the path.

    - if the given path already exists in the filesystem
      the filesystem is not modified.

    - otherwise make_path creates directories along the given path
      using the dirname() of the path. You may append
      a '/' to the path if you want it to be a directory path.
    """
    from os import makedirs
    from os.path import normpath, exists, abspath

    dpath = normpath(path)
    if not exists(dpath):
        makedirs(dpath)
    return normpath(abspath(path))


def open_anything(source):
    """URI, filename, or string --> stream

    This function lets you define parsers that take any input source
    (URL, pathname to local or network file, or actual data as a string)
    and deal with it in a uniform manner.  Returned object is guaranteed
    to have all the basic stdio read methods (read, readline, readlines).
    Just .close() the object when you're done with it.
    
    Examples:
    >>> from xml.dom import minidom
    >>> sock = open_anything("http://localhost/kant.xml")
    >>> doc = minidom.parse(sock)
    >>> sock.close()
    >>> sock = open_anything("c:\\inetpub\\wwwroot\\kant.xml")
    >>> doc = minidom.parse(sock)
    >>> sock.close()
    >>> sock = open_anything("<ref id='conjunction'><text>and</text><text>or</text></ref>")
    >>> doc = minidom.parse(sock)
    >>> sock.close()
    """
    if hasattr(source, "read"):
        return source

    if source == '-':
        import sys
        return sys.stdin

    # try to open with urllib (if source is http, ftp, or file URL)
    import urllib
    try:
        return urllib.urlopen(source)
    except (IOError, OSError):
        pass
    
    # try to open with native open function (if source is pathname)
    try:
        return open(source)
    except (IOError, OSError):
        pass
    
    # treat source as string
    import StringIO
    return StringIO.StringIO(str(source)) 


def mean_std_dev(values):
    """ Calculate mean and standard deviation of data values[]: """
    from math import sqrt
    length, mean, std = len(values), 0, 0
    for value in values:
        mean = mean + value
    mean = mean / float(length)
    for value in values:
        std = std + (value - mean) ** 2
    std = sqrt(std / float(length))
    return mean, std
