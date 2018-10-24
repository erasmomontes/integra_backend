from rest_framework import serializers
from .models import Resident, Person, Property


class ResidentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Resident
        fields = (
            'id', 'name', 'email', 'telephone',
            'is_active', 'user')
        read_only_fields = ('id', )


class PersonSerializer(serializers.ModelSerializer):

    class Meta:
        model = Person
        fields = ('id', 'name', 'email', 'identification', 'create_by',
                  'type_identification')
        read_only_fields = ('id', )


class PropertySerializer(serializers.ModelSerializer):

    class Meta:
        model = Property
        fields = ('id', 'name')
        read_only_fields = ('id', )