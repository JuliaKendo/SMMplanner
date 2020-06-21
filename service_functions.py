import requests
import re
import string
from urllib.parse import urlparse


def get_message(filename):
    with open(filename, "r") as file_handler:
        return file_handler.read()


def get_attachment(photo_to_post):
    attachment = ''
    if photo_to_post:
        attachment = 'photo{0}_{1}'.format(photo_to_post[0]['owner_id'], photo_to_post[0]['id'])
    return attachment


def query_to_site(url, params, files=None):
    response = requests.post(url, data=params, files=files or {})
    response.raise_for_status()
    return response.json()


def extracturl(hyperlink):
    urls = re.findall(r'((?:(?:https|ftp|http)?:(?:/{1,3}|[a-z0-9%])|[a-z0-9.\-]+[.](?:com|org|uk)/)[\s\S]*?[";@{};:,<>«»“”‘’])', hyperlink)
    list_urls = [''.join(x for x in url if x in string.printable and not x == '"') for url in urls]
    if list_urls:
        return list_urls[0]


def get_file_id(hyperlink):
    url = extracturl(hyperlink)
    url_info = urlparse(url)
    for param in url_info.query.split('&'):
        if 'id' in param:
            return re.sub(r'(id=)', '', param)


def get_header_height(range):
    num_row = re.findall(r'(\d{0,9}):+', range)
    return int(num_row[0]) if num_row else 0
