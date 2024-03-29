import factory
import random
import calendar
from ..models import CHOICE_DAY, CHOICE_TIME, CHOICE_TYPE_DATE
from integrabackend.users.test.factories import UserFactory
from integrabackend.resident.test.factories import PropertyFactory


class StateFactory(factory.django.DjangoModelFactory):
    id = factory.Faker('uuid4')
    name = factory.Sequence(lambda n: f'testuser{n}')

    class Meta:
        model = 'solicitude.State'


class ServiceFactory(factory.django.DjangoModelFactory):
    
    class Meta:
        model = 'solicitude.Service'

    id = factory.Faker('uuid4')
    name = "Desbloqueo de Usuario"
    sap_code_service = 'S4'


class DateServiceRequestFactory(factory.django.DjangoModelFactory):

    class Meta:
        model = 'solicitude.DateServiceRequested'
    
    id = factory.Faker('uuid4')
    checking = factory.Sequence(lambda n: f'{n}:00:00')
    checkout = factory.Sequence(lambda n: f'{n}:00:00')


class ServiceRequestFactory(factory.django.DjangoModelFactory):

    class Meta:
        model = 'solicitude.ServiceRequest'
    
    id = factory.Faker('uuid4')
    note = factory.Sequence(lambda n: f'note{n}')
    sap_customer = "".join([str(random.randint(1, 9)) for _ in range(5)]) 
    ticket_id = factory.Sequence(lambda n: n)
    phone = factory.Sequence(lambda n: f'note{n}')
    email = factory.Sequence(lambda n: f'{n}@example.com')
    service = factory.SubFactory(ServiceFactory)
    user = factory.SubFactory(UserFactory)
    state = factory.SubFactory(StateFactory)
    _property = factory.SubFactory(PropertyFactory)
    date_service_request = factory.SubFactory(DateServiceRequestFactory)


class DayTypeFactory(factory.DjangoModelFactory):

    class Meta:
        model = 'solicitude.DayType'
    
    id = factory.Faker('uuid4')
    name = 'Laborable'


class DayFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'solicitude.Day'
    
    id = factory.Faker('uuid4')
    name = factory.Iterator(list(calendar.day_name))


class QuotationFactory(factory.django.DjangoModelFactory):
    id = factory.Faker('uuid4')

    class Meta:
        model = 'solicitude.Quotation'
