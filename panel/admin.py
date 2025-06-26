from django.contrib import admin
from panel.models import *


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'first_name', 'last_name', 'created_at', 'data')
    fields = ('id', 'username', 'first_name', 'last_name', 'created_at')

    exclude = ('data',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class AttachmentsInline(admin.TabularInline):
    model = Attachments

    exclude = ('file_id',)

    extra = 0


@admin.register(Mailing)
class MailingAdmin(admin.ModelAdmin):
    list_display = ['datetime', 'text', 'is_ok']
    readonly_fields = ['is_ok']
    inlines = [AttachmentsInline]


@admin.register(MultPack)
class MailingAdmin(admin.ModelAdmin):
    fields = ('template', 'file_id')
    list_display = ('id', 'template', 'file_id')


@admin.register(LovePack)
class MailingAdmin(admin.ModelAdmin):
    fields = ('template',)
    list_display = ('id', 'template')


@admin.register(GamePack)
class MailingAdmin(admin.ModelAdmin):
    fields = ('template',)
    list_display = ('id', 'template')


@admin.register(Text)
class MailingAdmin(admin.ModelAdmin):
    fields = ('name', 'text')
    list_display = ('name', 'text')
    readonly_fields = ['name']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=...):
        return False


@admin.register(Statistic)
class MailingAdmin(admin.ModelAdmin):
    fields = ('name', 'value')
    list_display = ('name', 'value')
    readonly_fields = ['name', 'value']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=...):
        return False
