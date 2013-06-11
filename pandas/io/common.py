""" Common api utilities """

import urlparse
from pandas.util import py3compat
from StringIO import StringIO

_VALID_URLS = set(urlparse.uses_relative + urlparse.uses_netloc +
                  urlparse.uses_params)
_VALID_URLS.discard('')


def _is_url(url):
    """Check to see if a URL has a valid protocol.

    Parameters
    ----------
    url : str or unicode

    Returns
    -------
    isurl : bool
        If `url` has a valid protocol return True otherwise False.
    """
    try:
        return urlparse.urlparse(url).scheme in _VALID_URLS
    except:
        return False

def _is_s3_url(url):
    """ Check for an s3 url """
    try:
        return urlparse.urlparse(url).scheme == 's3'
    except:
        return False

def get_filepath_or_buffer(filepath_or_buffer, encoding=None):
    """ 
    if the filepath_or_buffer is a url, translate and return the buffer
    passthrough otherwise

    Parameters
    ----------
    filepath_or_buffer : a url, filepath, or buffer
    encoding : the encoding to use to decode py3 bytes, default is 'utf-8'

    Returns
    -------
    a filepath_or_buffer, the encoding
    
    """

    if _is_url(filepath_or_buffer):

        _, filepath_or_buffer = _req_url(filepath_or_buffer) # raise if not status_code 200?

        if py3compat.PY3:  # pragma: no cover
            if encoding:
                errors = 'strict'
            else:
                errors = 'replace'
                encoding = 'utf-8'
            bytes = filepath_or_buffer.read()
            filepath_or_buffer = StringIO(bytes.decode(encoding, errors))
            return filepath_or_buffer, encoding
        return filepath_or_buffer, None

    if _is_s3_url(filepath_or_buffer):
        try:
            import boto
        except ImportError:
            raise ImportError("boto is required to handle s3 files")
        # Assuming AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
        # are environment variables
        parsed_url = urlparse.urlparse(filepath_or_buffer)
        conn = boto.connect_s3()
        b = conn.get_bucket(parsed_url.netloc)
        k = boto.s3.key.Key(b)
        k.key = parsed_url.path
        filepath_or_buffer = StringIO(k.get_contents_as_string())
        return filepath_or_buffer, None

    return filepath_or_buffer, None

def _req_url(url):
    '''
    Retrieves text output of request to url
    Raises on bad status_code or invalid urls
    Prefer requests module if available

    Parameters
    ----------
    url : string

    Returns
    -------
    status_code : int, the HTTP status_code
    buf_text : the text from the url request

    '''
    try_requests = True
    if try_requests:
        try:
            import requests
            resp = requests.get(url)
            resp.raise_for_status()
            buf_text = StringIO(resp.text)
            status_code = resp.status_code
            return status_code, buf_text
        except (ImportError,):
            pass
        except (requests.exceptions.InvalidURL, 
            requests.exceptions.InvalidSchema):
            # responses can't deal with local files
            pass

    import urllib2
    resp = urllib2.urlopen(url)
    # except urllib2.URLError:  # don't think there was a purpose to this bit, raises itself
    #    raise ValueError('Invalid URL: "{0}"'.format(url))
    status_code = resp.code
    buf_text = resp # if status_code == 200 else '' # If not 200 does it raise?
    return status_code, buf_text
