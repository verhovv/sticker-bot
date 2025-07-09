import json
import time
from contextlib import ExitStack
from io import BytesIO

import requests
from PIL import Image, ImageDraw

from celery import shared_task
from rembg import remove

from config import config
from config import font
from panel.models import Mailing, User, Text, MultPack, LovePack, GamePack

LOVEIS_POINTS = ((37, 126), (474, 380))
GAME_POINTS = ((40, 20), (473, 440))
MULT_POINTS = ((37, 44), (474, 380))


@shared_task
def send_mailing(mailing_id: int):
    mailing = Mailing.objects.get(id=mailing_id)

    attachments = mailing.attachments.all()

    def send_mail(user_id):
        if not attachments:
            requests.post(
                url=f'https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage',
                json={
                    'chat_id': user_id,
                    'text': mailing.text,
                }
            )
            return

        if len(attachments) == 1:
            attachment = attachments[0]
            attachment_type = attachment.type

            if not attachment.file_id:
                with open(attachment.file.path, 'rb') as f:
                    files = {attachment_type: f}
                    response = requests.post(
                        url=f'https://api.telegram.org/bot{config.BOT_TOKEN}/send{attachment_type.capitalize()}',
                        data={
                            'chat_id': user_id,
                            'caption': mailing.text
                        },
                        files=files
                    )

                    if attachment_type == 'photo':
                        file_id = response.json()['result']['photo'][-1]['file_id']
                    else:
                        file_id = response.json()['result'][attachment_type]['file_id']

                    attachment.file_id = file_id
                    attachment.save()
                    return

            requests.post(
                url=f'https://api.telegram.org/bot{config.BOT_TOKEN}/send{attachment_type.capitalize()}',
                data={
                    'chat_id': user_id,
                    'caption': mailing.text,
                    attachment_type: attachment.file_id,
                }
            )
            return

        with ExitStack() as stack:
            media_group = [
                {
                    'type': attachment.type,
                    'media': f'attach://{attachment.file.name}' if not attachment.file_id else attachment.file_id,
                } for attachment in attachments
            ]

            media_group[0]['caption'] = mailing.text

            files = {}
            for attachment in attachments:
                if not attachment.file_id:
                    file_obj = stack.enter_context(open(attachment.file.path, 'rb'))
                    files[attachment.file.name] = file_obj

            response = requests.post(
                f'https://api.telegram.org/bot{config.BOT_TOKEN}/sendMediaGroup',
                data={'chat_id': user_id, 'media': json.dumps(media_group)},
                files=files if files else None
            )

            json_response = response.json()

            for i, attachment in enumerate(attachments):
                if attachment.type == 'photo':
                    attachment.file_id = json_response['result'][i][attachment.type][-1]['file_id']
                else:
                    attachment.file_id = json_response['result'][i][attachment.type]['file_id']
                attachment.save()

    def send_mail_delay(user_id: int):
        send_mail(user_id)
        time.sleep(0.01)

    for user in User.objects.all():
        send_mail_delay(user.id)

    mailing.is_ok = True
    mailing.save()


@shared_task
def process_template(file_id, user_id: int, delete_message_id):
    user = User.objects.get(id=user_id)

    pack_classes = [MultPack, LovePack, GamePack]
    pack = pack_classes[['mult', 'love', 'game'].index(user.data['current_template'])]

    if pack == LovePack:
        points = LOVEIS_POINTS
    elif pack == MultPack:
        points = MULT_POINTS
    elif pack == GamePack:
        points = GAME_POINTS

    width, height = points[1][0] - points[0][0], points[1][1] - points[0][1]
    current_n = user.data['current_n']

    template_obj = pack.objects.all()[current_n - 1]
    with open(template_obj.template.path, 'rb') as f:
        template_image = Image.open(BytesIO(f.read()))

    file_id = file_id
    file_info = requests.get(
        f"https://api.telegram.org/bot{config.BOT_TOKEN}/getFile?file_id={file_id}"
    ).json()
    file_path = file_info['result']['file_path']
    image_data = requests.get(f"https://api.telegram.org/file/bot{config.BOT_TOKEN}/{file_path}").content
    image = Image.open(BytesIO(image_data))

    result = Image.new('RGBA', template_image.size, (255, 255, 255, 0))

    if image.height / image.width > height / width:
        image = image.resize((width, int(image.height / image.width * width)))
    else:
        image = image.resize((int(image.width / image.height * height), height))

    result.paste(image, points[0])
    result.alpha_composite(template_image)

    result_byte_arr = BytesIO()
    result.save(result_byte_arr, format='PNG')
    result_byte_arr.seek(0)

    text_ok = Text.objects.get(name='Делаем стикерпак (Кнопка Оставляем)')
    text_again = Text.objects.get(name='Делаем стикерпак (Кнопка Поменять фото)')

    requests.post(
        f"https://api.telegram.org/bot{config.BOT_TOKEN}/deleteMessage",
        json={
            'chat_id': user.id,
            'message_id': delete_message_id
        }
    )

    sticker_response = requests.post(
        f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendSticker",
        files={'sticker': ('result.png', result_byte_arr.getvalue())},
        data={
            'chat_id': user_id,
        }
    )
    user.data['message_ids'].append(sticker_response.json()['result']['message_id'])

    text = Text.objects.get(name='Ваш стикер готов (для шаблонных)')
    response = requests.post(
        f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage",
        json={
            'chat_id': user_id,
            'text': text.text,
            'reply_markup': {
                'inline_keyboard': [
                    [{'text': text_ok.text, 'callback_data': 'agree'}],
                    [{'text': text_again.text, 'callback_data': 'disagree'}]
                ]
            }
        }
    )

    user.data['sticker_id'] = sticker_response.json()['result']['sticker']['file_id']
    user.data['message_ids'].append(response.json()['result']['message_id'])
    user.save()


@shared_task
def process_sticker(file_id, user_id: int, delete_message_id):
    user = User.objects.get(id=user_id)

    file_response = requests.get(f"https://api.telegram.org/bot{config.BOT_TOKEN}/getFile?file_id={file_id}")
    file_path = file_response.json()['result']['file_path']
    image_data = requests.get(f"https://api.telegram.org/file/bot{config.BOT_TOKEN}/{file_path}").content

    image = Image.open(BytesIO(image_data))
    result = Image.new('RGBA', (512, 512), (255, 255, 255, 0))

    points = ((0, 0), (512, 400))
    width, height = points[1][0] - points[0][0], points[1][1] - points[0][1]

    if image.height / image.width > height / width:
        image = image.resize((width, int(image.height / image.width * width)))
    else:
        image = image.resize((int(image.width / image.height * height), height))

    white_line = Image.new('RGB', (512, 512), (255, 255, 255))
    draw = ImageDraw.Draw(white_line)
    image = remove(image)

    texts = ['']
    for t in user.data['text'].split():
        if len(texts[-1]) + len(t) + 1 > 25:
            texts[-1] = texts[-1].strip()
            texts.append(t)
            continue
        texts[-1] += f' {t}'

    for i, t in enumerate(texts):
        draw.text((250 - font.getlength(t) // 2, 50 * i), text=t, fill=(0, 0, 0), font=font)

    result.paste(image)
    result.paste(white_line, (0, 400))

    result_byte_arr = BytesIO()
    result.save(result_byte_arr, format='PNG')
    result_byte_arr.seek(0)

    text_ok = Text.objects.get(name='Делаем стикерпак (Кнопка Оставляем)').text
    text_again = Text.objects.get(name='Кнопка Переделать стикер (кастом)').text
    text_stop = Text.objects.get(name='Кнопка Закончить стикерпак (кастом)').text
    text_back = Text.objects.get(name='Назад в меню').text

    files = {'sticker': ('result.png', result_byte_arr.getvalue())}

    requests.post(
        f"https://api.telegram.org/bot{config.BOT_TOKEN}/deleteMessage",
        json={
            'chat_id': user.id,
            'message_id': delete_message_id
        }
    )

    sticker_response = requests.post(
        f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendSticker",
        data={
            'chat_id': user.id,
        },
        files=files
    )
    user.data['message_ids'].append(sticker_response.json()['result']['message_id'])

    text = Text.objects.get(name='Ваш стикер готов (для кастомных)')
    response = requests.post(
        f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage",
        json={
            'chat_id': user_id,
            'text': text.text,
            'reply_markup': {
                'inline_keyboard': [
                    [{'text': text_ok, 'callback_data': 'agree_my'}],
                    [{'text': text_again, 'callback_data': 'disagree_my'}],
                    [{'text': text_stop, 'callback_data': 'stop_my'}],
                    [{'text': text_back, 'callback_data': 'back'}]
                ]
            }
        }
    )

    user.data['sticker_id'] = sticker_response.json()['result']['sticker']['file_id']
    user.data['message_ids'].append(response.json()['result']['message_id'])
    user.save()
