import os
import requests
import re
import string
from urllib.parse import urlparse, parse_qs


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
    regex_object = re.compile(r'''((?:
                                  (?:https|ftp|http)                    #начало веб ссылки
                                  :(?:/{1,3}|[a-z0-9%])|[a-z0-9.\-]+[.] #тело веб ссылки с ":" до последней точки перед доменной зоной
                                  (?:com|org|uk)                        #доменная зона
                                  /)                                    #завершение группы
                                  [\S]*?[";@{};:,<>«»“”‘’\s]            #любая последовательность кроме пробела, с одним из завершающих веб ссылку символов
                                  )''', re.VERBOSE)
    urls = regex_object.findall(hyperlink)
    list_urls = [''.join(x for x in url if x in string.printable and not x == '"') for url in urls]
    if list_urls:
        return list_urls[0]


def get_file_id(hyperlink):
    url = extracturl(hyperlink)
    if not url:
        return None
    url_info = urlparse(url)
    params = parse_qs(url_info.query).get('id')
    return params[0] if params else None


def get_header_height(range):
    header_height = re.findall(r'(\d{0,9}):+', range)
    return int(header_height[0]) if header_height else 0


def remove_files(files):
    for file in files:
        if file:
            os.remove(file)
