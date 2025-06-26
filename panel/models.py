from django.db import models


class User(models.Model):
    id = models.BigIntegerField('Идентификатор Телеграм', primary_key=True, blank=False)

    username = models.CharField('Юзернейм', max_length=64, null=True, blank=True)
    first_name = models.CharField('Имя', null=True, blank=True)
    last_name = models.CharField('Фамилия', null=True, blank=True)

    created_at = models.DateTimeField('Дата регистрации', auto_now_add=True, blank=True)

    data = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f'id{self.id} | @{self.username or "-"} {self.first_name or "-"} {self.last_name or "-"}'

    class Meta:
        verbose_name = 'Телеграм пользователь'
        verbose_name_plural = 'Телеграм пользователи'


class Attachments(models.Model):
    types = {
        'photo': 'Фото',
        'video': 'Видео',
        'document': 'Документ'
    }

    type = models.CharField('Тип вложения', choices=types)
    file = models.FileField('Файл', upload_to='media/mailing')
    file_id = models.TextField(null=True)
    mailing = models.ForeignKey('Mailing', on_delete=models.SET_NULL, null=True, related_name='attachments')

    class Meta:
        verbose_name = 'Вложение'
        verbose_name_plural = 'Вложения'


class Mailing(models.Model):
    text = models.TextField('Текст', blank=True, null=True)
    datetime = models.DateTimeField('Дата/Время')
    is_ok = models.BooleanField('Статус отправки', default=False)

    class Meta:
        verbose_name = 'Рассылка'
        verbose_name_plural = 'Рассылки'


class MultPack(models.Model):
    template = models.FileField('Шаблон', upload_to='media/templates/mult', null=True)
    file_id = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'Шаблон МультМемчики'
        verbose_name_plural = 'Шаблоны "МультМемчики"'

    def __str__(self):
        return str(self.template.url)

    def save(self, *args, **kwargs):
        if self.pk:
            old_photo = MultPack.objects.get(pk=self.pk).template
            if old_photo != self.template:
                self.file_id = None
        super().save(*args, **kwargs)


class LovePack(models.Model):
    template = models.FileField('Шаблон', upload_to='media/templates/mult', null=True)
    file_id = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'Шаблон "Love is..."'
        verbose_name_plural = 'Шаблоны "Love is..."'

    def __str__(self):
        return str(self.template.url)

    def save(self, *args, **kwargs):
        if self.pk:
            old_photo = LovePack.objects.get(pk=self.pk).template
            if old_photo != self.template:
                self.file_id = None
        super().save(*args, **kwargs)


class GamePack(models.Model):
    template = models.FileField('Шаблон', upload_to='media/templates/mult', null=True)
    file_id = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'Шаблон "Игра престолов"'
        verbose_name_plural = 'Шаблоны "Игра престолов"'

    def __str__(self):
        return str(self.template.url)

    def save(self, *args, **kwargs):
        if self.pk:
            old_photo = GamePack.objects.get(pk=self.pk).template
            if old_photo != self.template:
                self.file_id = None
        super().save(*args, **kwargs)


class Text(models.Model):
    name = models.CharField('Название текста', primary_key=True)
    text = models.TextField('Текст', null=True)

    class Meta:
        verbose_name = 'Текст'
        verbose_name_plural = 'Тексты'

    def __str__(self):
        return self.name


class Statistic(models.Model):
    name = models.CharField('Название', primary_key=True)
    value = models.IntegerField('Значение', default=0)

    class Meta:
        verbose_name = 'Статистика'
        verbose_name_plural = 'Статистика'

    def __str__(self):
        return str(self.name)

    @staticmethod
    async def setup():
        await Statistic.objects.aget_or_create(name='Стикеров МультМемчики')
        await Statistic.objects.aget_or_create(name='Стикеров Love is...')
        await Statistic.objects.aget_or_create(name='Стикеров Игра престолов')
        await Statistic.objects.aget_or_create(name='Стикеров Кастомных')
        await Statistic.objects.aget_or_create(name='Стикеров Всего')
