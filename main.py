from __future__ import print_function
import os
import logging
import argparse
import pickle
import time
import datetime
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from pydrive.files import ApiRequestError
import service_functions
import publications


OK = 'да'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
logger = logging.getLogger('smmplaner')


def get_google_drive_file(hyperlink):
    file_id = service_functions.get_file_id(hyperlink)
    if file_id:
        file = drive.CreateFile({'id': file_id})
        file.FetchMetadata()
        return file


def download_article(hyperlink):
    text_file = get_google_drive_file(hyperlink)
    if text_file:
        file_name = '%s.txt' % text_file['title']
        text_file.GetContentFile(file_name, mimetype='text/plain')
        return file_name


def download_image(hyperlink):
    image_file = get_google_drive_file(hyperlink)
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


def publish_posts(article_file, image_file, vk, telegram, fb):
    num_of_publications = 0
    message = service_functions.get_message(article_file)
    if OK in vk:
        if publications.post_on_social_media(publications.post_vkontakte, message, [image_file],
                                             token=os.getenv('VK_ACCESS_TOKEN'),
                                             id=int(os.getenv('VK_GROUP_ID')),
                                             album_id=int(os.getenv('VK_ALBUM_ID')),
                                             title='vc'):
            num_of_publications += 1
    if OK in telegram:
        if publications.post_on_social_media(publications.post_telegram, message, [image_file],
                                             token=os.getenv('TELEGRAM_ACCESS_TOKEN'),
                                             id=os.getenv('TELEGRAM_CHAT_ID'),
                                             title='telegram'):
            num_of_publications += 1
    if OK in fb:
        if publications.post_on_social_media(publications.post_facebook, message, [image_file],
                                             token=os.getenv('FACEBOOK_ACCESS_TOKEN'),
                                             id=os.getenv('FACEBOOK_GROUP_ID'),
                                             title='facebook'):
            num_of_publications += 1

    return num_of_publications > 0


def is_publish(weekday, publish_time, published):
    today = datetime.datetime.now()
    if OK in published:
        return False

    if today.weekday() == 0 and 'понедельник' not in weekday:
        return False
    elif today.weekday() == 1 and 'вторник' not in weekday:
        return False
    elif today.weekday() == 2 and 'среда' not in weekday:
        return False
    elif today.weekday() == 3 and 'четверг' not in weekday:
        return False
    elif today.weekday() == 4 and 'пятница' not in weekday:
        return False
    elif today.weekday() == 5 and 'суббота' not in weekday:
        return False
    elif today.weekday() == 6 and 'воскресенье' not in weekday:
        return False

    if str(publish_time) != today.strftime("%H"):
        return False

    return True


def create_parser():
    parser = argparse.ArgumentParser(description='Параметры запуска скрипта')
    parser.add_argument('-s', '--sleep', default=300, help='Пауза между опросом Google таблицы')
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
    header_height = service_functions.get_header_height(range)

    while True:
        try:
            spreadsheet_data = read_spreadsheet(spreadsheet_id, range)
            saved_files = ()
            for num, row in enumerate(spreadsheet_data):
                vk, telegram, fb, weekday, publish_time, article, image, published = row
                if not is_publish(weekday, publish_time, published):
                    continue
                article_file = download_article(article)
                image_file = download_image(image)
                saved_files += (article_file, image_file)
                if publish_posts(article_file, image_file, vk, telegram, fb):
                    save_into_spreadsheet(spreadsheet_id, f'H{num+header_height}')

        except ApiRequestError as error:
            logger.error(f'{error}')

        except (KeyError, TypeError) as error:
            logger.error(f'{error}')

        except ValueError as error:
            logger.error(f'{error}')

        else:
            logger.info('Публикация выполнена успешно!') if saved_files else None

        finally:
            for saved_file in saved_files:
                os.remove(saved_file)
            time.sleep(int(args.sleep))


if __name__ == '__main__':
    gauth = GoogleAuth()
    gauth.LocalWebserverAuth()
    drive = GoogleDrive(gauth)
    main()
