import time
from nose.tools import eq_, ok_

from rest_framework.test import APITestCase
from rest_framework import status

from django.urls import reverse
from django.forms.models import model_to_dict
from django.core import mail
from django.conf import settings
from factory import Sequence

from partenon.helpdesk import HelpDeskTicket, HelpDesk
from partenon.ERP import ERPAviso

from .factories import (
    ServiceFactory, ServiceRequestFactory, StateFactory,
    DayFactory, DateServiceRequestFactory, DayTypeFactory,
    QuotationFactory)
from integrabackend.solicitude.enums import Subjects, StateEnums
from ...users.test.factories import UserFactory
from integrabackend.resident.test.factories import (
    PropertyFactory, PropertyTypeFactory, ResidentFactory)


class TestServiceRequestTestCase(APITestCase):
    """
    Test /solicitude-service CRUD
    """

    def setUp(self):
        from django.conf import settings
        settings.CELERY_ALWAYS_EAGER = True

        self.model = ServiceRequestFactory._meta.model 
        self.factory = ServiceRequestFactory
        self.base_name = 'servicerequest'
        self.url = reverse('%s-list' % self.base_name)
        self.url_aviso = reverse('create_aviso-list')
    
    def service_request_data(self):
        property = PropertyFactory(
            property_type=PropertyTypeFactory.create())
        date_service_request = DateServiceRequestFactory()
        day_type = DayTypeFactory()
        day = DayFactory(day_type=day_type)
        date_service_request.day.add(day)
        service_request = ServiceRequestFactory(
            service=ServiceFactory.create(),
            state=StateFactory.create(),
            user=UserFactory.create(), 
            property=property,
            sap_customer=4259,
            date_service_request=date_service_request)
        data = model_to_dict(service_request)
        data.pop('user')
        data['property'] = str(property.id)
        data['date_service_request'] = model_to_dict(date_service_request)
        data['date_service_request']['day'] = [day.id]
        service_request.delete()

        return data
    
    def create_aviso(self, service_request_id):
        service_object = self.model.objects.get(pk=service_request_id)

        params = {'ticket_id': service_object.ticket_id}
        response = self.client.post(self.url_aviso, params)
        return response 
    
    def approve_quotation(self, service_request_id):
        url_detail = reverse(
            "%s-detail" % self.base_name,
            kwargs=dict(pk=service_request_id))
        url_approve = url_detail + 'approve-quotation/' 
        return self.client.post(url_approve, {})
    
    def modify_aviso_to_race(self, aviso_id):
        state_data = {'state': StateEnums.aviso.requires_acceptance_closing}
        url = reverse('create_aviso-detail', kwargs={'pk': aviso_id}) 
        return self.client.put(url, state_data)
    
    def modify_aviso_to_raco(self, aviso_id):
        state_data = {'state': StateEnums.aviso.requires_quote_approval}
        url = reverse('create_aviso-detail', kwargs={'pk': aviso_id}) 
        return self.client.put(url, state_data)
    
    def approve_work(self, service_request_id):
        url_detail = reverse(
            "%s-detail" % self.base_name,
            kwargs=dict(pk=service_request_id))
        url_approve = url_detail + 'approve-work/' 
        return self.client.post(url_approve, {})
    
    def reject_quotation(self, service_request_id):
        url_detail = reverse(
            "%s-detail" % self.base_name,
            kwargs=dict(pk=service_request_id))
        url_reject = url_detail + 'reject-quotation/' 
        return self.client.post(url_reject, {})
    
    def reject_work(self, service_request_id):
        url_detail = reverse(
            "%s-detail" % self.base_name,
            kwargs=dict(pk=service_request_id))
        url_approve = url_detail + 'reject-work/' 
        return self.client.post(url_approve, {})

    def test_good_path(self):
        # Create service request
        self.client.force_authenticate(user=UserFactory())
        data = self.service_request_data()
        response = self.client.post(self.url, data, format='json')
        eq_(response.status_code, status.HTTP_201_CREATED) 

        # Validate service_request
        service = response.json()
        ok_(service.get('id'))
        ok_(service.get('service'))
        ok_(service.get('note'))
        ok_(service.get('phone'))
        ok_(service.get('email'))
        ok_(service.get('property'))

        # Create aviso
        response_aviso = self.create_aviso(service.get('id'))
        eq_(response_aviso.status_code, status.HTTP_201_CREATED)

        service_object = self.model.objects.get(pk=service.get('id'))
        ok_(service_object.aviso_id is not None)

        # Validate exists aviso
        aviso_info = ERPAviso().info(service_object.aviso_id)
        eq_(aviso_info.get('estado_aviso'), StateEnums.aviso.initial_status)

        service_object.aviso_id = 514958 
        service_object.save()

        # Modify aviso to RACO
        state_data = {'state': StateEnums.aviso.requires_quote_approval}
        url = reverse(
            'create_aviso-detail',
            kwargs={'pk': service_object.aviso_id}) 
        response_aviso_to_raco = self.client.put(url, state_data) 

        # Validate response for change status
        eq_(response_aviso_to_raco.status_code, status.HTTP_200_OK)
        service_object = self.model.objects.get(pk=service.get('id'))
        
        # Validate quotation
        ok_(service_object.quotation)
        ok_(service_object.quotation.file.__bool__())
        eq_(service_object.quotation.state.name, StateEnums.quotation.pending)

        # Validate ticket
        ticket = HelpDeskTicket.get_specific_ticket(service_object.ticket_id)
        eq_(ticket.state.name, StateEnums.ticket.waiting_approval_quotation)

        # Validate ServiceRequest
        eq_(service_object.state.name,
            StateEnums.service_request.waith_valid_quotation)
        
        # Validate Email
        email = mail.outbox[0]
        subject = Subjects.build_subject(
            Subjects.valid_quotation, ticket.ticket_number)
        eq_(email.subject, subject)
        ok_(service_object.user.email in email.to)
        ok_(settings.DEFAULT_SOPORT_EMAIL in email.cc)

        # Aprove quotation
        response_aprove_quotation = self.approve_quotation(service.get('id'))

        # Validate response
        eq_(response_aprove_quotation.status_code, status.HTTP_200_OK)
        service_object = self.model.objects.get(pk=service.get('id'))

        # Validate change ticket state
        ticket = HelpDeskTicket.get_specific_ticket(service_object.ticket_id)
        eq_(ticket.state.name, StateEnums.ticket.aprove_quotation)

        # Validate change aviso state
        aviso_info = ERPAviso().info(service_object.aviso_id)
        eq_(aviso_info.get('estado_orden'), StateEnums.aviso.aprove_quotation)

        # Validate Quotation
        eq_(service_object.quotation.state.name, StateEnums.quotation.approved)
        
        # Validate ServiceRequest
        eq_(service_object.state.name,
            StateEnums.service_request.approve_quotation)
        
        # Modify aviso to RACE
        response_aviso_to_race = self.modify_aviso_to_race(service_object.aviso_id)

        # Validate response for change status
        eq_(response_aviso_to_race.status_code, status.HTTP_200_OK)
        service_object = self.model.objects.get(pk=service.get('id'))

        # Validate change ticket state
        ticket = HelpDeskTicket.get_specific_ticket(service_object.ticket_id)
        eq_(ticket.state.name, StateEnums.ticket.waiting_validate_work)
        
        # Validate ServiceRequest
        eq_(service_object.state.name,
            StateEnums.service_request.waith_valid_work)

        # Validate Email
        email = mail.outbox[1]
        subject = Subjects.build_subject(
            Subjects.valid_work, ticket.ticket_number)
        eq_(email.subject, subject)
        ok_(service_object.user.email in email.to)
        ok_(settings.DEFAULT_SOPORT_EMAIL in email.cc)

        # Approve work
        response_aprove_quotation = self.approve_work(service_object.pk) 

        # Validate response for change status
        eq_(response_aviso_to_race.status_code, status.HTTP_200_OK)
        service_object = self.model.objects.get(pk=service.get('id'))
        
        # Validate ServiceRequest
        eq_(service_object.state.name,
            StateEnums.service_request.approved)
        
        # Validate change ticket state
        ticket = HelpDeskTicket.get_specific_ticket(service_object.ticket_id)
        eq_(ticket.state.name, StateEnums.ticket.closed)
        
        # Validate change status aviso
        aviso_info = ERPAviso().info(service_object.aviso_id)
        eq_(aviso_info.get('estado_aviso'), StateEnums.aviso.accepted_work)
    
    def test_client_reject_quotation(self):
        data = self.service_request_data()

        # Create service request
        self.client.force_authenticate(user=UserFactory())
        response = self.client.post(self.url, data, format='json')
        eq_(response.status_code, status.HTTP_201_CREATED) 

        service = response.json()

        ok_(service.get('id'))
        ok_(service.get('service'))
        ok_(service.get('note'))
        ok_(service.get('phone'))
        ok_(service.get('email'))
        ok_(service.get('property'))

        # Create aviso
        response_aviso = self.create_aviso(service.get('id')) 
        
        eq_(response_aviso.status_code, status.HTTP_201_CREATED)
        service_object = self.model.objects.get(pk=service.get('id'))
        ok_(service_object.aviso_id is not None)

        # Validate exists aviso
        aviso_info = ERPAviso().info(service_object.aviso_id)
        eq_(aviso_info.get('estado_aviso'), StateEnums.aviso.initial_status)

        service_object.aviso_id = 514958 
        service_object.save()

        # Modify aviso to RACO
        response_aviso_to_raco = self.modify_aviso_to_raco(service_object.aviso_id) 

        # Validate response for change status
        eq_(response_aviso_to_raco.status_code, status.HTTP_200_OK)
        service_object = self.model.objects.get(pk=service.get('id'))
        
        # Validate quotation
        ok_(service_object.quotation)
        ok_(service_object.quotation.file.__bool__())
        eq_(service_object.quotation.state.name, StateEnums.quotation.pending)

        # Validate ticket
        ticket = HelpDeskTicket.get_specific_ticket(service_object.ticket_id)
        eq_(ticket.state.name, StateEnums.ticket.waiting_approval_quotation)

        # Validate ServiceRequest
        eq_(service_object.state.name,
            StateEnums.service_request.waith_valid_quotation)
        
        # Validate Email
        email = mail.outbox[0]
        subject = Subjects.build_subject(
            Subjects.valid_quotation, ticket.ticket_number)
        eq_(email.subject, subject)
        ok_(service_object.user.email in email.to)
        ok_(settings.DEFAULT_SOPORT_EMAIL in email.cc)

        # Reject quotation
        response_reject_quotation = self.reject_quotation(service_object.pk) 

        # Validate response
        eq_(response_reject_quotation.status_code, status.HTTP_200_OK)
        service_object = self.model.objects.get(pk=service.get('id'))

        # Validate change ticket state
        ticket = HelpDeskTicket.get_specific_ticket(service_object.ticket_id)
        eq_(ticket.state.name, StateEnums.ticket.reject_quotation)

        # Validate change aviso state
        aviso_info = ERPAviso().info(service_object.aviso_id)
        eq_(aviso_info.get('estado_orden'), StateEnums.aviso.reject_quotation)

        # Validate Quotation
        eq_(service_object.quotation.state.name, StateEnums.quotation.reject)
        
        # Validate ServiceRequest
        eq_(service_object.state.name,
            StateEnums.service_request.reject_quotation)


    def test_client_reject_work(self):
        data = self.service_request_data() 

        # Create service request
        self.client.force_authenticate(user=UserFactory())
        response = self.client.post(self.url, data, format='json')
        eq_(response.status_code, status.HTTP_201_CREATED) 

        service = response.json()

        ok_(service.get('id'))
        ok_(service.get('service'))
        ok_(service.get('note'))
        ok_(service.get('phone'))
        ok_(service.get('email'))
        ok_(service.get('property'))

        # Create aviso
        response_aviso = self.create_aviso(service.get('id')) 
        
        eq_(response_aviso.status_code, status.HTTP_201_CREATED)
        service_object = self.model.objects.get(pk=service.get('id'))
        ok_(service_object.aviso_id is not None)

        # Validate exists aviso
        aviso_info = ERPAviso().info(service_object.aviso_id)
        eq_(aviso_info.get('estado_aviso'), StateEnums.aviso.initial_status)

        service_object.aviso_id = 514958 
        service_object.save()

        # Modify aviso to RACO
        response_aviso_to_raco = self.modify_aviso_to_raco(service_object.aviso_id)

        # Validate response for change status
        eq_(response_aviso_to_raco.status_code, status.HTTP_200_OK)
        service_object = self.model.objects.get(pk=service.get('id'))
        
        # Validate quotation
        ok_(service_object.quotation)
        ok_(service_object.quotation.file.__bool__())
        eq_(service_object.quotation.state.name, StateEnums.quotation.pending)

        # Validate ticket
        ticket = HelpDeskTicket.get_specific_ticket(service_object.ticket_id)
        eq_(ticket.state.name, StateEnums.ticket.waiting_approval_quotation)

        # Validate ServiceRequest
        eq_(service_object.state.name,
            StateEnums.service_request.waith_valid_quotation)
        
        # Validate Email
        email = mail.outbox[0]
        subject = Subjects.build_subject(
            Subjects.valid_quotation, ticket.ticket_number)
        eq_(email.subject, subject)
        ok_(service_object.user.email in email.to)
        ok_(settings.DEFAULT_SOPORT_EMAIL in email.cc)

        # Aprove quotation
        response_aprove_quotation = self.approve_quotation(service_object.pk) 

        # Validate response
        eq_(response_aprove_quotation.status_code, status.HTTP_200_OK)
        service_object = self.model.objects.get(pk=service.get('id'))

        # Validate change ticket state
        ticket = HelpDeskTicket.get_specific_ticket(service_object.ticket_id)
        eq_(ticket.state.name, StateEnums.ticket.aprove_quotation)

        # Validate change aviso state
        aviso_info = ERPAviso().info(service_object.aviso_id)
        eq_(aviso_info.get('estado_orden'), StateEnums.aviso.aprove_quotation)

        # Validate Quotation
        eq_(service_object.quotation.state.name, StateEnums.quotation.approved)
        
        # Validate ServiceRequest
        eq_(service_object.state.name,
            StateEnums.service_request.approve_quotation)
        
        # Modify aviso to RACE
        response_aviso_to_race = self.modify_aviso_to_race(service_object.aviso_id)

        # Validate response for change status
        eq_(response_aviso_to_race.status_code, status.HTTP_200_OK)
        service_object = self.model.objects.get(pk=service.get('id'))

        # Validate change ticket state
        ticket = HelpDeskTicket.get_specific_ticket(service_object.ticket_id)
        eq_(ticket.state.name, StateEnums.ticket.waiting_validate_work)
        
        # Validate ServiceRequest
        eq_(service_object.state.name,
            StateEnums.service_request.waith_valid_work)

        # Validate Email
        email = mail.outbox[1]
        subject = Subjects.build_subject(
            Subjects.valid_work, ticket.ticket_number)
        eq_(email.subject, subject)
        ok_(service_object.user.email in email.to)
        ok_(settings.DEFAULT_SOPORT_EMAIL in email.cc)

        # Reject work
        response_aprove_quotation = self.reject_work(service_object.pk)

        # Validate response for change status
        eq_(response_aviso_to_race.status_code, status.HTTP_200_OK)
        service_object = self.model.objects.get(pk=service.get('id'))
        
        # Validate change ticket state
        ticket = HelpDeskTicket.get_specific_ticket(service_object.ticket_id)
        eq_(ticket.state.name, StateEnums.ticket.reject_work)
        
        # Validate change status aviso
        # aviso_info = ERPAviso().info(service_object.aviso_id)
        # eq_(aviso_info.get('estado_aviso'), StateEnums.aviso.reject_work)

        # Validate send email
        email = mail.outbox[2]
        subject = Subjects.build_subject(
            Subjects.reject_work, ticket.ticket_number)
        aviso = ERPAviso(aviso=service_object.aviso_id) 
        eq_(email.subject, subject)
        ok_(aviso.responsable.correo in email.to)
        ok_(settings.DEFAULT_SOPORT_EMAIL in email.cc)

        # Validate ServiceRequest
        eq_(service_object.state.name,
            StateEnums.service_request.reject_work)
    
    def test_create_service_request_for_faveo(self):
        # Login
        self.client.force_authenticate(user=UserFactory())

        # Create user
        user = UserFactory()
        resident = ResidentFactory(user=user, sap_customer=4259)
        property_ = PropertyFactory(property_type=PropertyTypeFactory())
        resident.properties.add(property_)

        # Create user on Faveo
        helpdesk_user = HelpDesk.user.create_user(
            user.email, user.first_name, user.last_name)
        
        # Create mutiple services
        for i in range(10):
            ServiceFactory(name=f'TEST {i}')
        else:
            last_service = ServiceFactory()

        # Search service by name
        service_url = reverse(
            'service-detail', kwargs={'pk': last_service.id})
        service_response = self.client.get(service_url)
        eq_(service_response.status_code, status.HTTP_200_OK)
        ok_('id' in service_response.json().keys())
        ok_('name' in service_response.json().keys())
        eq_(service_response.json().get('name'), last_service.name)

        # Create ticket on Faveo
        priority = HelpDesk.prioritys.objects.get_by_name('Normal')
        topic = HelpDesk.topics.objects.get_by_name(
            service_response.json().get('name'))
        ticket = helpdesk_user.ticket.create(
        "Solicitud: Test de integracion", 'Prueba de Faveo a Integra',
        priority, topic)
        ok_(hasattr(ticket, 'ticket_id'))

        # Search User by email
        user_url = reverse('user-list')
        user_response = self.client.get(user_url, data={"email": user.email})
        eq_(user_response.status_code, status.HTTP_200_OK)
        eq_(len(user_response.json()), 1)
        eq_(user_response.json()[0].get('email'), user.email)
        eq_(user_response.json()[0].get('resident'), user.resident.id)

        # Search Resident by ID
        resident_pk = user_response.json()[0].get('resident')
        url_resident = reverse(
            'resident-detail', kwargs={'pk': resident_pk})
        response_resident = self.client.get(url_resident)
        eq_(response_resident.status_code, status.HTTP_200_OK)
        ok_('properties' in response_resident.json().keys())
        for property_ in response_resident.json().get('properties'):
            ok_('id' in property_.keys())
            ok_('direction' in property_.keys())

        # Search client info
        client_info_url = reverse("client_info-list")
        client_info_sap_customer = response_resident.json().get('sap_customer')
        client_info_response = self.client.get(
            client_info_url, data={'client': client_info_sap_customer})
        eq_(client_info_response.status_code, status.HTTP_200_OK)
        ok_('telefono' in client_info_response.json().keys())
        ok_('e_mail' in client_info_response.json().keys())

        # Search Day service
        day_type = DayTypeFactory()
        day = DayFactory(day_type=day_type)
        day_url = reverse('day-detail', kwargs={'pk': day.id})
        day_response = self.client.get(day_url)
        eq_(day_response.status_code, status.HTTP_200_OK)
        ok_('id' in day_response.json().keys())

        # Build data for create Service Request
        day = list()
        day.append(day_response.json().get('id'))
        data = dict(
            user=user_response.json()[0].get('id'),
            service=service_response.json().get('id'),
            note='Prueba de Faveo a Integra',
            phone=client_info_response.json().get('telefono'),
            email=client_info_response.json().get('e_mail'),
            property=response_resident.json().get('properties')[0].get('id'),
            date_service_request=dict(
                day=day,
                checking='12:00:00', checkout='12:00:00',
            ),
            sap_customer=response_resident.json().get('sap_customer'),
            require_quotation=False,
            ticket_id=ticket.ticket_id
        )


        # Create service request
        url_faveo = reverse("%s-list" % self.base_name) + 'faveo/' 
        self.client.force_authenticate(user=UserFactory())
        response = self.client.post(url_faveo, data, format='json')
        eq_(response.status_code, status.HTTP_201_CREATED) 
        service = response.json()

        # Validation
        ok_(service.get('id'))
        eq_(service.get('note'), data.get('note'))
        eq_(service.get('phone'), data.get('phone'))
        eq_(service.get('email'), data.get('email'))
        eq_(service.get('property'), data.get('property'))
        eq_(service.get('ticket_id'), ticket.ticket_id)
        eq_(service.get('service'), data.get('service'))
        eq_(service.get('user'), str(user.id))