import json
from mock import patch, MagicMock
from django.urls import reverse
from django.forms.models import model_to_dict
from django.core import mail
from faker import Faker
from rest_framework import status
from rest_framework.test import APITestCase
from nose.tools import eq_, ok_

from .factories import (
    ServiceFactory, ServiceRequestFactory, StateFactory,
    DayFactory, DateServiceRequestFactory, DayTypeFactory,
    QuotationFactory)
from ..enums import StateEnums
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
        for service in response.json():
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


class TestServiceRequestTestCase(APITestCase):
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
        _property = PropertyFactory(
            property_type=PropertyTypeFactory.create())
        date_service_request = DateServiceRequestFactory()
        day_type = DayTypeFactory()
        day = DayFactory(day_type=day_type)
        date_service_request.day.add(day)
        service_request = ServiceRequestFactory(
            service=ServiceFactory.create(),
            state=StateFactory.create(),
            user=UserFactory.create(), 
            _property=_property,
            date_service_request=date_service_request)
        data = model_to_dict(service_request)
        data.pop('user')
        data['_property'] = str(_property.id)
        data['date_service_request'] = model_to_dict(date_service_request)
        data['date_service_request']['day'] = [day.id]

        self.client.force_authenticate(user=UserFactory())
        response = self.client.post(self.url, data, format='json')

        eq_(response.status_code, status.HTTP_201_CREATED)
        service = response.json()
        ok_(service.get('id'))
        eq_(service.get('service'), service_request.service.pk)
        eq_(service.get('note'), service_request.note)
        eq_(service.get('phone'), service_request.phone)
        eq_(service.get('email'), service_request.email)
        eq_(service.get('_property'), str(service_request._property.pk))
    
    @patch('integrabackend.solicitude.helpers.ERPAviso')
    @patch('integrabackend.solicitude.views.helpers.HelpDeskTicket')
    @patch('integrabackend.solicitude.helpers.Status')
    def test_can_aprove_service_request(self, mock_status, mock_ticket, mock_aviso):
        # GIVEN
        _property = PropertyFactory(
            property_type=PropertyTypeFactory.create())
        date_service_request = DateServiceRequestFactory()
        date_service_request.day.add(
            DayFactory(day_type=DayTypeFactory()))
        user = UserFactory.create()
        service_request = ServiceRequestFactory(
            service=ServiceFactory.create(),
            state=StateFactory.create(),
            user=user, 
            _property=_property,
            date_service_request=date_service_request)
        QuotationFactory.create(
            service_request=service_request,
            state=StateFactory.create()) 
        state_mock = MagicMock()
        mock_status.get_status_by_name.return_value = state_mock 

        mock_object = MagicMock()
        mock_object.change_state.return_value = True
        mock_ticket.return_value = mock_object
        
        # WHEN
        self.client.force_authenticate(user=user)
        url = reverse(
            'servicerequest-aprove-quotation',
            kwargs={'pk': service_request.id}) 
        response = self.client.post(url, {})

        # THEN
        eq_(response.status_code, status.HTTP_200_OK)
        eq_(response.json(), {'success': 'ok'})
        mock_status.get_state_by_name.assert_called()
        mock_ticket.assert_called()
        mock_object.change_state.assert_called()



class TestAvisoTestCase(APITestCase):
    """
    Test /aviso endpoint
    """
    def setUp(self):
        self.base_name = 'create_aviso'
        self.url = reverse('%s-list' % self.base_name)
        self.client.force_authenticate(user=UserFactory.build())
        return super(TestAvisoTestCase, self).setUp()
    
    def test_request_post_without_ticket_id(self):
        response = self.client.post(self.url, data=dict())
        eq_(response.status_code, status.HTTP_404_NOT_FOUND)
        eq_(response.json(), {'detail': 'Not found.'})
    
    def test_request_post_service_request_not_exists(self):
        response = self.client.post(self.url, data={'ticket_id': 1} )
        eq_(response.status_code, status.HTTP_404_NOT_FOUND)
        eq_(response.json(), {'detail': 'Not found.'})
    
    def test_request_get_without_ticket_id(self):
        response = self.client.get(self.url)
        eq_(response.status_code, status.HTTP_404_NOT_FOUND)
        eq_(response.json(), {'detail': 'Not found.'})       
    
    def test_request_get_service_request_not_exists(self):
        response = self.client.get(self.url, data={'ticket_id': 1})
        eq_(response.status_code, status.HTTP_404_NOT_FOUND)
        eq_(response.json(), {'detail': 'Not found.'})
    
    @patch('integrabackend.solicitude.views.ERPAviso')
    def test_request_get_success(self, mock_aviso):
        _property = PropertyFactory(
            property_type=PropertyTypeFactory.create())
        date_service_request = DateServiceRequestFactory()
        day_type = DayTypeFactory()
        day = DayFactory(day_type=day_type)
        date_service_request.day.add(day)
        service_request = ServiceRequestFactory(
            service=ServiceFactory.create(),
            state=StateFactory.create(),
            user=UserFactory.create(), 
            _property=_property,
            date_service_request=date_service_request,
            ticket_id=1, aviso_id=1)
        
        aviso = MagicMock()
        aviso.info.return_value = {"test": "test"}
        mock_aviso.return_value = aviso

        body = {'ticket_id': service_request.ticket_id} 
        response = self.client.get(self.url, body)
        eq_(response.status_code, status.HTTP_200_OK)
        eq_(response.json(), {'test': 'test'})
        aviso.info.assert_called()
        aviso.info.assert_called_with(aviso=service_request.aviso_id)
    
    @patch('integrabackend.solicitude.views.helpers')
    def test_request_patch_success(self, mock_helpers):
        _property = PropertyFactory(
            property_type=PropertyTypeFactory.create())
        date_service_request = DateServiceRequestFactory()
        day_type = DayTypeFactory()
        day = DayFactory(day_type=day_type)
        date_service_request.day.add(day)
        service_request = ServiceRequestFactory(
            service=ServiceFactory.create(),
            state=StateFactory.create(),
            user=UserFactory.create(), 
            _property=_property,
            date_service_request=date_service_request,
            ticket_id=1, aviso_id=1)
        
        mock_helpers.client_valid_quotation.return_value = True
        
        body = {'state': StateEnums.aviso.requires_quote_approval} 
        url = reverse("%s-detail" % self.base_name, kwargs={"pk": 1})
        response = self.client.put(url, data=body)

        eq_(response.status_code, status.HTTP_200_OK)
        ok_(response.json().get('success'))