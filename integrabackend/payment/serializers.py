import re
from django.contrib.auth import get_user_model

from rest_framework import serializers

from . import models



class ResponsePaymentAttemptSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.ResponsePaymentAttempt
        fields = "__all__"
        read_only_fields = ('id', 'payment_attempt')


class RequestPaymentAttemptSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = models.RequestPaymentAttempt
        fields = "__all__"
        read_only_fields = ('id', 'payment_attempt')


class CreditCardSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.CreditCard
        exclude = ('token', )


class InvoiceSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Invoice
        fields = '__all__'
        read_only_fields = ('id', 'payment_attempt', 'status')


class AdvancePaymentSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.AdvancePayment
        fields = '__all__'
        read_only_fields = ('id', 'payment_attempt', 'status')


class ItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Item
        fields = '__all__'
        read_only_fields = ('id', 'payment_attempt', 'status')


class PaymentUserSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = get_user_model()
        fields = (
            'id', 'username', 'email',
            'first_name', 'last_name',)
        read_only_fields = ('id', 'last_login', 'date_joined')


class PaymentAttemptSerializer(serializers.ModelSerializer):
    invoices = InvoiceSerializer(
        many=True, required=False)
    advancepayments = AdvancePaymentSerializer(
        many=True, required=False)
    items = ItemSerializer(many=True, required=False)

    response = ResponsePaymentAttemptSerializer(read_only=True)
    request = RequestPaymentAttemptSerializer(read_only=True)
    user = PaymentUserSerializer(read_only=True)

    total = serializers.CharField(read_only=True)
    status_process_payment = serializers.SlugRelatedField(
        read_only=True, slug_field='name')
    status_compensation = serializers.SlugRelatedField(
        read_only=True, slug_field='name')

    class Meta:
        model = models.PaymentAttempt
        fields = "__all__"
        read_only_fields = (
            'date',
            'id',
            'process_payment',
            'total_advancepayment_amount'

            'total_invoice_amount',
            'total_invoice_amount_usd',
            'total_invoice_tax',

            'total_item_amount',
            'total_item_amount_dop',
            'total_item_tax',
            'transaction',
        )

    def create(self, validated_data):
        invoices = validated_data.pop('invoices', [])
        advancepayments = validated_data.pop('advancepayments', [])
        items = validated_data.pop('items', [])

        payment_attempt = super(PaymentAttemptSerializer, self).create(validated_data)

        status_pending, _ = models.StatusDocument.objects.get_or_create(
            name='Pendiente'
        )

        def make_many(serializer, data):
            serializer = serializer(data=data)
            serializer.is_valid(raise_exception=True)

            serializer.save(
                payment_attempt=payment_attempt,
                status=status_pending
            )

        for invoice in invoices:
            make_many(InvoiceSerializer, invoice)
        
        for advancepayment in advancepayments:
            make_many(AdvancePaymentSerializer, advancepayment)
        
        for item in items:
            make_many(ItemSerializer, item)

        payment_attempt.save()
        return payment_attempt


class PaymentAttemptPaySerializer(serializers.Serializer):
    cvc = serializers.CharField(max_length=4)
    expiration = serializers.CharField(max_length=6)
    name = serializers.CharField(max_length=500)
    number = serializers.CharField(max_length=19)
    save = serializers.BooleanField()


class PaymentAttemptVerifoneSerializer(serializers.Serializer):
    cvc = serializers.CharField(max_length=4)
    expiration = serializers.CharField(max_length=6)
    name = serializers.CharField(max_length=500)
    number = serializers.CharField(max_length=19)