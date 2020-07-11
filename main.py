from __future__ import print_function
import os
import logging
import argparse
import pickle
import time
import datetime
import requests
import vk_api
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from telegram import TelegramError
import service_functions
import publications


OK = 'да'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
WEEKDAYS = {0: 'понедельник', 1: 'вторник', 2: 'среда', 3: 'четверг', 4: 'пятница', 5: 'суббота', 6: 'воскресенье'}
logger = logging.getLogger('smmplaner')


def get_google_drive_file(google_drive, hyperlink):
    file_id = service_functions.get_file_id(hyperlink)
    if file_id:
        file = google_drive.CreateFile({'id': file_id})
        file.FetchMetadata()
        return file


def download_article(google_drive, hyperlink):
    text_file = get_google_drive_file(google_drive, hyperlink)
    if text_file:
        file_name = '%s.txt' % text_file['title']
        text_file.GetContentFile(file_name, mimetype='text/plain')
        return file_name


def download_image(google_drive, hyperlink):
    image_file = get_google_drive_file(google_drive, hyperlink)
    if image_file:
        file_name = image_file['originalFilename']
        image_file.GetContentFile(file_name)
        return file_name


def get_credentials():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds


def read_spreadsheet(spreadsheet_id, range):

    creds = get_credentials()
    google_api_client = build('sheets', 'v4', credentials=creds)
    sheet = google_api_client.spreadsheets()
    result = sheet.values().get(spreadsheetId=spreadsheet_id,
                                range=range,
                                valueRenderOption='FORMULA').execute()
    return result.get('values', [])


def save_into_spreadsheet(spreadsheet_id, range):

    body = {'values': [[OK]]}
    creds = get_credentials()
    google_api_client = build('sheets', 'v4', credentials=creds)
    sheet = google_api_client.spreadsheets()
    sheet.values().update(spreadsheetId=spreadsheet_id,
                          range=range,
                          valueInputOption='RAW',
                          body=body).execute()


def publish_posts(google_drive, article, image, vk, tg, fb):
    article_file = download_article(google_drive, article)
    if not article_file:
        raise ValueError('Ошибка загрузки статьи!')
    image_file = download_image(google_drive, image)
    message = service_functions.get_message(article_file)
    if OK in vk.lower():
        publications.post_vkontakte(os.getenv('VK_ACCESS_TOKEN'),
                                    int(os.getenv('VK_GROUP_ID')),
                                    int(os.getenv('VK_ALBUM_ID')),
                                    message, [image_file])

    if OK in tg.lower():
        publications.post_telegram(os.getenv('TELEGRAM_ACCESS_TOKEN'),
                                   os.getenv('TELEGRAM_CHAT_ID'),
                                   message, [image_file])

    if OK in fb.lower():
        publications.post_facebook(os.getenv('FACEBOOK_ACCESS_TOKEN'),
                                   os.getenv('FACEBOOK_GROUP_ID'),
                                   message, [image_file])

    service_functions.remove_files([article_file, image_file])


def is_published(weekday, publish_time, published):
    today = datetime.datetime.now()
    if OK in published.lower():
        return False

    if WEEKDAYS[today.weekday()] not in weekday.lower():
        return False

    if publish_time != int(today.strftime("%H")):
        return False

    return True


def create_parser():
    parser = argparse.ArgumentParser(description='Параметры запуска скрипта')
    parser.add_argument('-s', '--sleep', default=30, help='Пауза между опросом Google таблицы')
    parser.add_argument('-l', '--log', help='Путь к каталогу с log файлом')
    return parser


def initialize_logger(log_path):
    if log_path:
        output_dir = log_path
    else:
        output_dir = os.path.dirname(os.path.realpath(__file__))
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(os.path.join(output_dir, 'log.txt'), "a")
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def main():

    load_dotenv()
    parser = create_parser()
    args = parser.parse_args()
    initialize_logger(args.log)

    spreadsheet_id = os.getenv('SPREADSHEET_ID')
    range = os.getenv('RANGE_NAME')
    table_header_height = service_functions.get_header_height(range)

    gauth = GoogleAuth()
    gauth.LocalWebserverAuth()
    google_drive = GoogleDrive(gauth)

    while True:
        try:
            spreadsheet_data = read_spreadsheet(spreadsheet_id, range)
            for num, row in enumerate(spreadsheet_data):
                try:
                    vk, tg, fb, weekday, publish_time, article, image, published = row
                    if not is_published(weekday, publish_time, published):
                        continue
                    publish_posts(google_drive, article, image, vk, tg, fb)
                    save_into_spreadsheet(spreadsheet_id, f'H{num+table_header_height}')

                except (vk_api.VkApiError, vk_api.ApiHttpError, vk_api.AuthError) as error:
                    logger.error('Ошибка публикации поста на сайт вконтакте: {0}'.format(error))

                except TelegramError as error:
                    logger.error('Ошибка публикации поста в телеграмме: {0}'.format(error))

                except requests.exceptions.HTTPError as error:
                    logger.error('Ошибка загрузки данных на сайт: {0}'.format(error))

                except OSError as error:
                    logger.error('Ошибка чтения файлов с содержимым поста: {0}'.format(error))

                except (KeyError, TypeError, ValueError) as error:
                    logger.exception(f'{error}')
                    continue

        except Exception as error:
            logger.exception(f'{error}')

        finally:
            time.sleep(int(args.sleep))


if __name__ == '__main__':
    main()
