from django.urls import reverse
from django.forms.models import model_to_dict
from faker import Faker
from rest_framework import status
from rest_framework.test import APITestCase
from nose.tools import eq_, ok_

from .factories import (
    ServiceFactory, ServiceRequestFactory, StateFactory,
    DayFactory, DateServiceRequestFactory)
from ...users.test.factories import UserFactory
from integrabackend.resident.test.factories import PropertyFactory, PropertyTypeFactory


faker = Faker()

class TestServiceTestCase(APITestCase):
    """
    Tests /service list.
    """

    def setUp(self):
        self.model = ServiceFactory._meta.model
        self.factory = ServiceFactory
        self.base_name = 'service'
        self.url = reverse('%s-list' % self.base_name)
        self.client.force_authenticate(user=UserFactory.build())

    def test_get_request_list_succeeds(self):
        self.factory.create()
        response = self.client.get(self.url)
        for service in response.json().get('results'):
            ok_(service.get('id'))
            ok_(service.get('name') is not None)

    def test_get_request_with_pk_succeeds(self):
        service = self.factory.create()
        url = reverse(
            '%s-detail' % self.base_name,
            kwargs={'pk': service.id})

        response = self.client.get(url)

        service = response.json()
        ok_(service.get('id'))
        ok_(service.get('name') is not None)


class TestSolicitudeServiceTestCase(APITestCase):
    """
    Test /solicitude-service CRUD
    """

    def setUp(self):
        self.model = ServiceRequestFactory._meta.model 
        self.factory = ServiceRequestFactory
        self.base_name = 'servicerequest'
        self.url = reverse('%s-list' % self.base_name)
        self.client.force_authenticate(user=UserFactory.build())
    
    def test_request_post_success(self):
        property = PropertyFactory(
            property_type=PropertyTypeFactory.create())
        date_service_request = DateServiceRequestFactory()
        date_service_request.day.add(DayFactory.create())
        service_request = ServiceRequestFactory(
            service=ServiceFactory.create(),
            state=StateFactory.create(),
            user=UserFactory.create(), 
            property=property,
            date_service_request=date_service_request)
        data = model_to_dict(service_request)
        data['date_service_request'] = model_to_dict(date_service_request)
        data['date_service_request']['day'] = [DayFactory.create().pk]

        response = self.client.post(self.url, data)

        eq_(response.status_code, status.HTTP_201_CREATED)
        service = response.json()
        ok_(service.get('id'))
        ok_(service.get('creation_date'))
        eq_(service.get('service'), service_request.service.pk)
        eq_(service.get('state'), service_request.state.pk)
        eq_(service.get('note'), service_request.note)
        eq_(service.get('phone'), service_request.phone)
        eq_(service.get('email'), service_request.email)
        eq_(service.get('ownership'), service_request.ownership)
