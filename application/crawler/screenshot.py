from homura import download
from .config_crawler import get_splash_uri, get_save_path

def get_screenshot(url, filename):
    # Use try to handle errors with calling the download function. 
    try:
        download(url=get_splash_uri(url),path=get_save_path(filename))
    except:
        pass