from rest_framework import viewsets, status, exceptions
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.mixins import ListModelMixin
from rest_framework.response import Response

from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend

from . import models, serializers, mixins, enums, permissions, helpers, filters
from ..resident.models import Property


class InvitationViewSet(viewsets.ModelViewSet):
    """
    CRUD Invitation
    """
    filter_backends = (DjangoFilterBackend,)
    filter_class = filters.InvitationFilter

    permission_classes = [permissions.OnlyUpdatePending]
    queryset = models.Invitation.objects.all()

    status_class = models.StatusInvitation
    status_enums = enums.StatusInvitationEnums

    model_status = models.StatusInvitation
    model_terminal = models.Terminal

    checkin_serializer = serializers.CheckInSerializer
    checkout_serializer = serializers.CheckOutSerializer

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return serializers.InvitationSerializerDetail
        return serializers.InvitationSerializer

    def _get_initial_status(self):
        status, _ = self.status_class.objects.get_or_create(
            name=self.status_enums.pending
        )
        return status

    def get_queryset(self):
        queryset = super(InvitationViewSet, self).get_queryset()
        if (
            self.request.user.is_monitoring_center or
            self.request.user.is_aplication
        ):
            return queryset

        if self.request.user.is_security_agent:
            areas = self.request.user.areapermission_set.values('area')
            return queryset.filter(ownership__project__area__in=areas)

        return queryset.filter(create_by_id=self.request.user.id)

    def perform_create(self, serializer):
        serializer.save(
            create_by_id=self.request.user.id,
            status=self._get_initial_status())

        helpers.notify_invitation.delay(serializer.instance.id.hex)

    def perform_update(self, serializer):
        super(InvitationViewSet, self).perform_update(serializer)

        helpers.notify_invitation.delay(serializer.instance.id.hex)

    def apply_action_to_invitation(self, action, status):
        action_serializers = {
            'checkin': self.checkin_serializer,
            'checkout': self.checkout_serializer}

        if not self.request.user.is_security_agent:
            raise exceptions.PermissionDenied()

        self.object = self.get_object()
        if hasattr(self.object, action):
            msg = f'Invitation has {action} relationship'
            raise exceptions.ParseError(detail=msg)

        self.request.data.update(
            dict(invitation=self.object.id)
        )
        serializer = action_serializers.get(
            action
        )(data=self.request.data)
        serializer.is_valid(raise_exception=True)

        terminal = self.model_terminal.objects.filter(
            ip_address=self.request._request.META.get('REMOTE_ADDR'))

        if not terminal.exists():
            raise exceptions.PermissionDenied()

        terminal = terminal.first()

        if not terminal.check_point.type_invitation_allowed.filter(
            id=self.object.type_invitation.id
        ):
            raise exceptions.PermissionDenied()

        serializer.save(
            invitation=self.object,
            user=self.request.user,
            terminal=terminal)

        self.object.status, _ = self.model_status.objects.get_or_create(
            name=status)
        self.object.save()
        return serializer

    @action(detail=True, methods=['POST'], url_path='resend-notification')
    def resend_notification(self, request, pk):
        if request.user.is_aplication or request.user.is_backoffice:
            raise exceptions.PermissionDenied()

        self.object = self.get_object()
        if not self.object.is_pending:
            raise exceptions.PermissionDenied('Invitation is not pending')

        helpers.notify_invitation.delay(self.object.id.hex)

        return Response({}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['POST'], url_path='cancel')
    def cancel(self, request, pk):
        if request.user.is_aplication or request.user.is_backoffice:
            raise exceptions.PermissionDenied()

        self.object = self.get_object()
        if not self.object.is_pending:
            raise exceptions.PermissionDenied('Invitation is not pending')

        helpers.notify_invitation.delay(
            self.object.id.hex,
            email_template='emails/invitation/cancel.html')

        self.object.status, _ = models.StatusInvitation.objects.get_or_create(
            name=enums.StatusInvitationEnums.cancel
        )
        self.object.save()
        return Response({}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['POST'], url_path='check-in')
    def check_in(self, request, pk):
        serializer = self.apply_action_to_invitation(
            'checkin',
            enums.StatusInvitationEnums.check_in)
        return Response(serializer.data, status.HTTP_201_CREATED)

    @action(detail=True, methods=['POST'], url_path='check-out')
    def check_out(self, request, pk):
        self.object = self.get_object()
        if (not self.object.status.name == self.status_enums.check_in):
            msg = 'Only can check-in invitation in {}'.format(
                    self.status_enums.check_in)
            raise exceptions.PermissionDenied(detail=msg)

        serializer = self.apply_action_to_invitation(
            'checkout',
            enums.StatusInvitationEnums.check_out)
        return Response(serializer.data, status.HTTP_201_CREATED)


class TypeInvitationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List type invitation
    """
    queryset = models.TypeInvitation.objects.all()
    serializer_class = serializers.TypeInvitationSerializer

    @action(detail=True, methods=['GET'])
    def property(self, request, pk):
        self.object = self.get_object()

        if not request.query_params:
            return Response(
                {'error': 'Should be send id of property'},
                status=status.HTTP_400_BAD_REQUEST)

        property_ = get_object_or_404(
            Property, pk=request.query_params.get('id'))

        typeinvitation_proyect = get_object_or_404(
            models.TypeInvitationProyect,
            type_invitation=self.object, project=property_.project
        )

        serializer = serializers.TypeInvitationProyectSerializer(
            instance=typeinvitation_proyect)

        return Response(serializer.data)


class StatusInvitationViewSet(
    mixins.ModelTranslateMixin,
    viewsets.ReadOnlyModelViewSet
):
    queryset = models.StatusInvitation.objects.all()
    serializer_class = serializers.StatusInvitationSerializer
    serializer_language = dict(
        en=serializers.StatusInvitationSerializer,
        es=serializers.StatusInvitationESSerializer
    )


class MedioViewSet(
        mixins.ModelTranslateMixin,
        viewsets.ReadOnlyModelViewSet):
    """
    List medio
    """
    queryset = models.Medio.objects.all()
    serializer_class = serializers.MedioSerializer
    serializer_language = dict(
        en=serializers.MedioSerializer,
        es=serializers.MedioESSerializer
    )


class ColorViewSet(
        mixins.ModelTranslateMixin,
        viewsets.ReadOnlyModelViewSet):
    """
    List color 
    """
    queryset = models.Color.objects.all()
    serializer_class = serializers.ColorSerializer
    serializer_language = dict(
        en=serializers.ColorSerializer,
        es=serializers.ColorESSerializer)
