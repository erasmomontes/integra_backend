from rest_framework import serializers
from . import models, enums
from ..resident.serializers import PersonSerializer


class MedioSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = models.Medio
        fields = '__all__'
        read_only_fields = ('id', )


class ColorSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = models.Color
        fields = '__all__'
        read_only_fields = ('id', )


class InvitationSerializer(serializers.ModelSerializer):
    invitated = PersonSerializer(many=True)

    class Meta:
        model = models.Invitation
        fields = (
            'id', 'type_invitation', 'date_entry',
            'date_out', 'invitated', 'note', 'number')
        read_only_fields = ('id', 'number')
    
    def create(self, validated_data):
        invitateds = validated_data.pop('invitated')
        invitation = super(InvitationSerializer, self).create(validated_data)
        
        for invitated in invitateds:
            type_identification = invitated.pop('type_identification')
            invitated['type_identification'] = str(type_identification.id)

            serializer = PersonSerializer(data=invitated)
            serializer.is_valid(raise_exception=True)

            serializer.save(create_by=invitation.create_by)
            invitation.invitated.add(serializer.instance)

        return invitation


class TypeInvitationSerializer(serializers.ModelSerializer):

    class Meta:
        model = TypeInvitation
        fields = ('id', 'name')
        read_only_fields = ('id', )
