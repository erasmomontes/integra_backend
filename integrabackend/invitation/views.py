from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.mixins import ListModelMixin
from rest_framework.response import Response

from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend

from . import models, serializers, mixins, enums, permissions
from ..resident.models import Property


class InvitationViewSet(viewsets.ModelViewSet):
    """
    CRUD Invitation
    """
    filter_backends = (DjangoFilterBackend,)
    filter_fields = [
        'number',
        'ownership__address',
        'invitated__name']

    permission_classes = [permissions.OnlyUpdatePending]
    queryset = models.Invitation.objects.all()
    serializer_class = serializers.InvitationSerializer

    status_class = models.StatusInvitation
    status_enums = enums.StatusInvitationEnums

    def _get_initial_status(self):
        status, _ = self.status_class.objects.get_or_create(
            name=self.status_enums.pending
        )
        return status

    def get_queryset(self):
        queryset = super(InvitationViewSet, self).get_queryset()
        if (
            self.request.user.is_monitoring_center
            or self.request.user.is_aplication
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
