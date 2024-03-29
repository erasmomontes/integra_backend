import uuid
import calendar
import datetime as dt
from django.conf import settings
from django.db import models
from partenon.helpdesk import Topics, HelpDeskTicket

day_name = list(calendar.day_name)
CHOICE_DAY = [list(a) for a in zip(day_name, day_name)]

# March 1, 2020, was a Sunday.
CHOICE_DAY_CODE = [
    (str(i), dt.date(2020, 3, i+1).strftime('%A')) for i in range(7)]

CHOICE_TIME = [(i, dt.time(i).strftime('%I %p')) for i in range(24)]
CHOICE_TYPE_DATE = [
    ('Laborable', 'Laborable'),
    ('Fin de semana', 'Fin de semana')]


class Service(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)

    name = models.CharField(max_length=255)
    generate_aviso = models.BooleanField(
        "Generar automaticamente aviso", default=False)
    skip_credit_validation =  models.BooleanField(
        "No validar si tiene credito", default=False)
    generates_invoice = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=False)
    sap_code_service = models.CharField(max_length=50)
    scheduled = models.BooleanField(default=True)

    # Translation - ENGLISH
    en_name = models.CharField(
        "Name in english",
        max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.nane

    class Meta:
        ordering = ('name',)


class State(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    name = models.CharField(max_length=60)

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name


class ServiceRequest(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    sap_customer = models.CharField(max_length=5)
    creation_date = models.DateTimeField(auto_now_add=True)
    close_date = models.DateTimeField(null=True, blank=True)
    note = models.TextField(null=True)
    phone = models.CharField(max_length=32)
    email = models.EmailField()
    require_quotation = models.BooleanField(default=False)
    ticket_id = models.IntegerField(null=True)
    aviso_id = models.IntegerField(null=True)

    service = models.ForeignKey("solicitude.Service", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    state = models.ForeignKey(
        'solicitude.State',
        on_delete=models.CASCADE)
    _property = models.ForeignKey(
        'resident.Property',
        related_name='property',
        on_delete=models.PROTECT,)
    date_service_request = models.OneToOneField(
        'solicitude.DateServiceRequested',
        on_delete=models.CASCADE)
    
    class Meta:
        ordering = ('-creation_date',)
    
    @property
    def ticket_number(self):
        try:
            ticket = HelpDeskTicket.get_specific_ticket(self.ticket_id)
            return ticket.ticket_number
        except Exception:
            return ''

    @property
    def ticket(self):
        if not self.ticket_id:
            return
        try:
            return HelpDeskTicket.get_specific_ticket(self.ticket_id)
        except Exception:
            return


class Quotation(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    file = models.FileField(upload_to='quotation', null=True)
    note = models.TextField(null=True)

    service_request = models.OneToOneField(
        'solicitude.ServiceRequest',
        related_name='quotation', on_delete=models.CASCADE)
    state = models.ForeignKey(
        'solicitude.State', on_delete=models.PROTECT)


class DateServiceRequested(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    checking = models.TimeField(auto_now=False, auto_now_add=False)
    checkout = models.TimeField(auto_now=False, auto_now_add=False)
    day = models.ManyToManyField('solicitude.Day')


class Day(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    name = models.CharField(
        max_length=10, choices=CHOICE_DAY,
        unique=True)
    active = models.BooleanField(default=True)
    day_type = models.ForeignKey(
        'solicitude.DayType',
        on_delete=models.PROTECT)
    order = models.IntegerField(blank=True, null=True)
    code = models.CharField(
        max_length=10, choices=CHOICE_DAY_CODE,
        unique=True, blank=True, null=True)

    class Meta:
        ordering = ('order',)

    def __str__(self):
        return self.name


class DayType(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    name = models.CharField(
        max_length=20, choices=CHOICE_TYPE_DATE)
    
    def __str__(self):
        return self.name

    @property
    def holiday(self):
        return True if self.name == 'Fin de semana' else False


class ScheduleAvailability(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    day_type = models.OneToOneField(
        'solicitude.DayType',
        on_delete=models.PROTECT,
        related_name='schedule_availability')
    start_time = models.TimeField()
    end_time = models.TimeField()
    msg_display = models.CharField(max_length=50)
