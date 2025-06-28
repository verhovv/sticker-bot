import uuid
from urllib.parse import quote

from aiogram import Router, F, Bot
from aiogram.enums import StickerFormat, StickerType
from aiogram.filters.command import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, \
    FSInputFile, InputSticker
from asgiref.sync import sync_to_async

from panel.models import *

router = Router()

LOVEIS_POINTS = ((37, 126), (474, 380))
GAME_POINTS = ((40, 20), (473, 440))
MULT_POINTS = ((37, 44), (474, 380))


@router.callback_query(F.data == 'menu')
@router.message(CommandStart())
async def command_start(message: Message, user: User):
    if isinstance(message, Message):
        await message.delete()
    if isinstance(message, CallbackQuery):
        message = message.message

    text = await Text.objects.aget(name='Приветственное сообщение')

    await message.answer(
        text=text.text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text='Cтикерпак «МультМемчики»', callback_data='mult')],
                [InlineKeyboardButton(text='Стикерпак «Love is...»', callback_data='love')],
                [InlineKeyboardButton(text='Стикерпак «Игра престолов "Битва за игрушки"»', callback_data='game')],
                [InlineKeyboardButton(text='Создать свой стикерпак', callback_data='my')],
            ]
        )
    )


@router.callback_query(F.data.in_({'mult', 'love', 'game'}))
async def on_template_stickers(callback: CallbackQuery, user: User, bot):
    pack = (MultPack, LovePack, GamePack)[['mult', 'love', 'game'].index(callback.data)]
    templates = await sync_to_async(lambda: list(pack.objects.all()))()

    text = await Text.objects.aget(name='Просим загрузить фотографию ребенка')
    back_text = await Text.objects.aget(name='Назад в меню')

    if 'current_n' in user.data:
        await bot.delete_messages(chat_id=user.id, message_ids=user.data['message_ids'])
        current_n = user.data['current_n']
        current_template = templates[current_n - 1]

        stickers_amount = await sync_to_async(len)(pack.objects.all())

        msg = await callback.message.answer_photo(
            photo=FSInputFile(
                path=current_template.template.path) if not current_template.file_id else current_template.file_id,
            caption=text.text + f'\n\nОсталось сделать {stickers_amount - current_n + 1} стикеров',
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=back_text.text, callback_data='back')]
                ]
            )
        )

        user.data['message_ids'] = [msg.message_id]
        await user.asave()
        return

    up_text = await Text.objects.aget(name='Выше вы можете увидеть')

    media_group1 = list()
    for template in templates[:10]:
        media_group1.append(
            InputMediaPhoto(
                media=FSInputFile(path=template.template.path) if not template.file_id else template.file_id)
        )

    media_group2 = list()
    for template in templates[10:]:
        media_group2.append(
            InputMediaPhoto(
                media=FSInputFile(path=template.template.path) if not template.file_id else template.file_id)
        )
    (media_group2 or media_group1)[0].caption = \
        up_text.text.replace(
            'НАЗВАНИЕ СТИКЕРПАКА',
            ("МультМемчики", "Love is…", "Игра престолов. Битва за игрушки")
            [['mult', 'love', 'game'].index(callback.data)]
        )

    media_group1 = await callback.message.answer_media_group(
        media=media_group1
    )
    user.data['message_ids'] = [msg.message_id for msg in media_group1] + []

    media_group2 = await callback.message.answer_media_group(
        media=media_group2
    )
    user.data['message_ids'].extend([msg.message_id for msg in media_group2])

    full_media_group = media_group1 + media_group2
    for i in range(len(full_media_group)):
        template = templates[i]
        template.file_id = full_media_group[i].photo[-1].file_id
        await template.asave()

    text = await Text.objects.aget(name='Начинаем делать стикерпак')
    text_start = await Text.objects.aget(name='Начинаем делать стикерпак (Кнопка Начать)')
    text_back = await Text.objects.aget(name='Начинаем делать стикерпак (Кнопка Назад)')

    msg = await callback.message.answer(
        text=text.text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=text_start.text, callback_data=callback.data),
                    InlineKeyboardButton(text=text_back.text, callback_data='back'),
                ]
            ]
        )
    )

    user.data['message_ids'].append(msg.message_id)
    user.data['current_template'] = callback.data
    user.data['current_n'] = 1
    await user.asave()


@router.callback_query(F.data == 'back')
async def back(callback: CallbackQuery, user: User, bot: Bot):
    await bot.delete_messages(chat_id=user.id, message_ids=user.data['message_ids'])

    user.data.clear()
    await user.asave()

    await command_start(callback, user)


@router.message(F.document | F.photo)
async def on_photo(message: Message, user: User, bot: Bot):
    from panel.tasks import process_template

    await bot.delete_messages(chat_id=user.id, message_ids=user.data['message_ids'])
    await message.delete()

    if user.data['current_template'] == 'my':
        await on_my_photo(message, user, bot)
        return

    wait_text = await Text.objects.aget(name='Текст ожидания')
    msg = await message.answer(
        text=wait_text.text
    )

    process_template.delay(
        message.document.file_id if message.document else message.photo[-1].file_id,
        user.id, msg.message_id
    )


@router.callback_query(F.data == 'agree')
async def agree(callback: CallbackQuery, user: User, bot: Bot):
    if 'sticker_file_ids' in user.data:
        user.data['sticker_file_ids'].append(user.data['sticker_id'])
    else:
        user.data['sticker_file_ids'] = [user.data['sticker_id']]

    await bot.delete_messages(chat_id=user.id, message_ids=user.data['message_ids'])

    pack = (LovePack, MultPack, GamePack)[['love', 'mult', 'game'].index(user.data['current_template'])]

    if user.data['current_n'] == await sync_to_async(lambda: len(pack.objects.all()))():
        sticker_pack_name = f's{str(uuid.uuid4()).replace('-', '0')}_by_{(await bot.get_me()).username}'

        match user.data['current_template']:
            case 'mult':
                title = 'МультМемчики'
                s = await Statistic.objects.aget(name='Стикеров МультМемчики')
                s.value += 1
                await s.asave()
            case 'love':
                title = 'Love is...'
                s = await Statistic.objects.aget(name='Стикеров Love is...')
                s.value += 1
                await s.asave()
            case 'game':
                title = 'Игра престолов Битва за игрушки'
                s = await Statistic.objects.aget(name='Стикеров Игра престолов')
                s.value += 1
                await s.asave()

        s = await Statistic.objects.aget(name='Стикеров Всего')
        s.value += 1
        await s.asave()
        await bot.create_new_sticker_set(
            user_id=user.id,
            name=sticker_pack_name,
            title=title,
            stickers=[
                InputSticker(sticker=file_id, emoji_list=['🌞'], format=StickerFormat.STATIC)
                for file_id in user.data['sticker_file_ids']
            ],
            sticker_type=StickerType.REGULAR,
            sticker_format=StickerFormat.STATIC
        )

        sticker_pack = await bot.get_sticker_set(name=sticker_pack_name)
        await callback.message.answer_sticker(sticker=sticker_pack.stickers[0].file_id)

        user.data.clear()
        await user.asave()

        text_done = await Text.objects.aget(name='Текст после создания стикерпака')
        text_share = await Text.objects.aget(name='Кнопка Поделиться')
        text_again = await Text.objects.aget(name='Кнопка Сгенерировать еще')
        text_edit = await Text.objects.aget(name='Текст поделиться (который можно изменять)')

        await callback.message.answer(
            text=text_done.text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=text_again.text, callback_data='menu')],
                    [
                        InlineKeyboardButton(
                            text=text_share.text,
                            url=f'https://t.me/share/url?url=https://t.me/{(await bot.get_me()).username}&'
                                f'text={quote(text_edit.text)}'
                        )
                    ]
                ]
            )
        )
        return

    user.data['current_n'] += 1
    await user.asave()

    callback = CallbackQuery(
        data=user.data['current_template'],
        message=callback.message,
        inline_message_id=None,
        chat_instance=callback.chat_instance,
        id=callback.id,
        from_user=callback.from_user,
    )

    await on_template_stickers(callback, user, bot)


@router.callback_query(F.data == 'disagree')
async def disagree(callback: CallbackQuery, user: User, bot: Bot):
    await callback.message.delete()

    callback = CallbackQuery(
        data=user.data['current_template'],
        message=callback.message,
        inline_message_id=None,
        chat_instance=callback.chat_instance,
        id=callback.id,
        from_user=callback.from_user,
    )

    await on_template_stickers(callback, user, bot)


@router.callback_query(F.data == 'my')
async def my(callback: CallbackQuery, user: User, bot: Bot):
    text = await Text.objects.aget(name='Описание кастомного стикерпака')
    text_start = await Text.objects.aget(name='Начинаем делать стикерпак (Кнопка Начать)')
    text_back = await Text.objects.aget(name='Начинаем делать стикерпак (Кнопка Назад)')

    message = await callback.message.answer(
        text=text.text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=text_start.text, callback_data='my1'),
                    InlineKeyboardButton(text=text_back.text, callback_data='back'),
                ]
            ]
        )
    )

    user.data['message_ids'] = user.data.get('message_ids', []) + [message.message_id]
    await user.asave()


@router.callback_query(F.data == 'my1')
async def my(callback: CallbackQuery, user: User, bot: Bot):
    await callback.message.delete()

    first = 'sticker_file_ids' not in user.data
    text = await Text.objects.aget(
        name='Текст Отправьте текст для стикера (кастом)') if first else await Text.objects.aget(
        name='Текст Отправьте текст для стикера (кастом, последующее)')
    text_back = await Text.objects.aget(name='Кнопка Назад в меню')
    msg = await callback.message.answer(
        text=text.text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=text_back.text, callback_data='back')]]
        )
    )

    if 'current_n' not in user.data:
        user.data['current_n'] = 1

    user.data['current_template'] = 'my'
    user.data['message_ids'] = [msg.message_id]
    user.data['state'] = 'text'
    await user.asave()


@router.callback_query(F.data == 'agree_my')
async def my_agree(callback: CallbackQuery, user: User, bot: Bot):
    await bot.delete_messages(chat_id=callback.message.chat.id, message_ids=user.data['message_ids'])

    if 'sticker_file_ids' in user.data:
        user.data['sticker_file_ids'].append(user.data['sticker_id'])
    else:
        user.data['sticker_file_ids'] = [user.data['sticker_id']]

    user.data['current_n'] += 1
    await user.asave()

    await my(callback, user, bot)


@router.message(F.text)
async def on_text(message: Message, user: User, bot: Bot):
    await bot.delete_messages(chat_id=message.chat.id, message_ids=user.data['message_ids'] + [message.message_id])

    if user.data['state'] != 'text':
        return

    first = 'sticker_file_ids' not in user.data
    text_error = await Text.objects.aget(name='Ошибка много символов (кастом)')
    text_back = await Text.objects.aget(name='Кнопка Назад в меню')
    if len(message.text) > 50:
        await message.answer(
            text=text_error.text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=text_back.text, callback_data='back')]]
            )
        )
        return

    text = await Text.objects.aget(
        name='Текст Отправьте фото для стикера (кастом)') if first else await Text.objects.aget(
        name='Текст Отправьте фото для стикера (кастом, последующее)')
    text_back = await Text.objects.aget(name='Кнопка Назад в меню')
    msg = await message.answer(
        text=text.text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=text_back.text, callback_data='back')]]
        )
    )

    user.data['message_ids'] = [msg.message_id]
    user.data['text'] = message.text.upper()
    await user.asave()


async def on_my_photo(message: Message, user: User, bot: Bot):
    from panel.tasks import process_sticker

    await bot.delete_messages(chat_id=user.id, message_ids=user.data['message_ids'])

    wait_text = await Text.objects.aget(name='Текст ожидания')
    msg = await message.answer(
        text=wait_text.text
    )

    process_sticker.delay(
        message.document.file_id if message.document else message.photo[-1].file_id,
        user.id,
        msg.message_id
    )
    return


@router.callback_query(F.data == 'disagree_my')
async def disagree_my(callback_query: CallbackQuery, user: User, bot: Bot):
    await bot.delete_messages(
        chat_id=callback_query.message.chat.id,
        message_ids=user.data['message_ids'] + [callback_query.message.message_id]
    )

    await my(callback_query, user, bot)


@router.callback_query(F.data == 'stop_my')
async def stop_my(callback: CallbackQuery, user: User, bot: Bot):
    if 'sticker_file_ids' in user.data:
        user.data['sticker_file_ids'].append(user.data['sticker_id'])
    else:
        user.data['sticker_file_ids'] = [user.data['sticker_id']]

    await bot.delete_messages(
        chat_id=callback.message.chat.id,
        message_ids=user.data['message_ids'] + [callback.message.message_id]
    )

    sticker_pack_name = f's{str(uuid.uuid4()).replace('-', '0')}_by_{(await bot.get_me()).username}'

    await bot.create_new_sticker_set(
        user_id=user.id,
        name=sticker_pack_name,
        title='Мой стикерпак',
        stickers=[
            InputSticker(sticker=file_id, emoji_list=['🌞'], format=StickerFormat.STATIC)
            for file_id in user.data['sticker_file_ids']
        ],
        sticker_type=StickerType.REGULAR,
        sticker_format=StickerFormat.STATIC
    )

    sticker_pack = await bot.get_sticker_set(name=sticker_pack_name)
    await callback.message.answer_sticker(sticker=sticker_pack.stickers[0].file_id)

    user.data.clear()
    await user.asave()

    text_done = await Text.objects.aget(name='Текст после создания стикерпака')
    text_share = await Text.objects.aget(name='Кнопка Поделиться')
    text_again = await Text.objects.aget(name='Кнопка Сгенерировать еще')
    text_edit = await Text.objects.aget(name='Текст поделиться (который можно изменять)')

    await callback.message.answer(
        text=text_done.text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=text_again.text, callback_data='menu')],
                [
                    InlineKeyboardButton(
                        text=text_share.text,
                        url=f'https://t.me/share/url?url=https://t.me/{(await bot.get_me()).username}&'
                            f'text={quote(text_edit.text)}'
                    )
                ]
            ]
        )
    )

    s = await Statistic.objects.aget(name='Стикеров Кастомных')
    s.value += 1
    await s.asave()

    s = await Statistic.objects.aget(name='Стикеров Всего')
    s.value += 1
    await s.asave()


@router.startup()
async def on_startup():
    from bot import texts
    await texts.setup_texts()
    await Statistic.setup()
