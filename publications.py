import os
import logging
import vk_api
import telegram
import service_functions


logger = logging.getLogger('smmplaner')


def upload_photo_to_vk(vk_session, vk_group_id, vk_album_id, filename):
    uploader = vk_api.VkUpload(vk_session)
    photo_to_post = uploader.photo(
        filename,
        album_id=vk_album_id,
        group_id=vk_group_id
    )
    return photo_to_post


def upload_photo_to_facebook(fb_token, fb_group_id, filename):
    url = 'https://graph.facebook.com/v7.0/{0}/photos'.format(fb_group_id)
    with open(filename, 'rb') as file_handler:
        files = {
            'source': file_handler
        }
        facebook_params = {
            'access_token': fb_token,
            'published': False,
        }
        dict_data = service_functions.query_to_site(url, facebook_params, files)
        if dict_data:
            return dict_data['id']


def post_vkontakte(vk_token, vk_group_id, vk_album_id, message, images):
    vk_session = vk_api.VkApi(token=vk_token)
    vk = vk_session.get_api()
    photos_to_post = [upload_photo_to_vk(vk_session, vk_group_id, vk_album_id, image) for image in images if images]
    attachments = [service_functions.get_attachment(photo_to_post) for photo_to_post in photos_to_post if photos_to_post]
    vk.wall.post(
        owner_id=-vk_group_id,
        attachments=','.join(attachments),
        message=message
    )


def post_telegram(telegram_token, telegram_chat_id, message, images):
    proxy = telegram.utils.request.Request(proxy_url=os.environ.get('TELEGRAM_PROXIES'))
    telegram_bot = telegram.Bot(token=telegram_token, request=proxy)
    for image in images:
        with open(image, 'rb') as file_handler:
            telegram_bot.sendPhoto(chat_id=telegram_chat_id, photo=file_handler)
    telegram_bot.sendMessage(chat_id=telegram_chat_id, text=message)


def post_facebook(fb_token, fb_group_id, message, images):
    url = 'https://graph.facebook.com/v7.0/{0}/feed'.format(fb_group_id)
    fb_params = {
        'access_token': fb_token,
        'facebook_group_id': fb_group_id,
        'message': message
    }
    photo_ids = [upload_photo_to_facebook(fb_token, fb_group_id, image) for image in images if images]
    attachments = ["{'media_fbid':'%s'}" % str(photo_id) for photo_id in photo_ids if photo_ids]
    if images and not attachments:
        raise ValueError('Ошибка загрузки изображений! Публикация в facebook не выполнена!')
    fb_params['attached_media'] = '[%s]' % ','.join(attachments)

    service_functions.query_to_site(url, fb_params)
