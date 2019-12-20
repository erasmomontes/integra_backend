import uuid

from django.contrib.contenttypes.fields import GenericRelation, GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Status(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    name = models.CharField(max_length=50)

    class Meta:
        abstract = True
    
    def __unicode__(self):
        """Unicode representation of StatusDocument."""
        return self.name


class StatusDocument(Status):
    pass


class StatusCreditcard(Status):
    pass


class CreditCard(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    token = models.CharField(max_length=100)
    status = models.ForeignKey(
        "payment.StatusCreditCard", on_delete=models.CASCADE)
    owner = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE, related_name='credit_card')
    brand = models.CharField('Brand', max_length=10)
    data_vault_expiration = models.CharField(
        'DataVaultExpiration', max_length=6)


class ResponsePaymentAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_attempt = models.OneToOneField(
        "payment.PaymentAttempt",
        on_delete=models.DO_NOTHING,
        related_name='response')
    date = models.DateTimeField('Create DateTime', auto_now_add=True)
    response_code = models.CharField('Response Code', max_length=10)
    authorization_code = models.CharField('Authorization Code', max_length=10)
    order_id = models.CharField('Order ID', max_length=10)


class PaymentAttempt(models.Model):
    """Model definition for StatusDocument. """

    sap_customer = models.IntegerField()
    date = models.DateTimeField(auto_now_add=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    process_payment = models.CharField(
        'Process Payment',
        max_length=50,
        blank=True, null=True
    )
    transaction = models.IntegerField()
    user = models.ForeignKey("users.User", on_delete=models.DO_NOTHING, null=True)

    @property
    def total_invoice_amount(self):
        return self.invoices.values(
            'amount_dop'
        ).aggregate(
            total_amount=models.Sum('amount_dop')
        ).get('total_amount')
    
    @property
    def total_invoice_tax(self):
        return self.invoices.values(
            'tax'
        ).aggregate(
            total_tax=models.Sum('tax')
        ).get('total_tax')

    def save(self, *args, **kwargs):
        last = PaymentAttempt.objects.order_by('transaction').last()
        if not last:
            self.transaction = 1
        else:
            self.transaction = last.transaction + 1
        return super(PaymentAttempt, self).save()


class PaymentDocument(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()

    payment_attempt = models.ForeignKey(
        'payment.PaymentAttempt',
        related_name='%(class)ss',
        on_delete=models.CASCADE
    )

    status = models.ForeignKey(
        "payment.StatusDocument",
        on_delete=models.DO_NOTHING,
    )

    class Meta:
        abstract = True


class Invoice(PaymentDocument):
    amount_dop = models.DecimalField(max_digits=10, decimal_places=2)
    company = models.IntegerField('Company')
    company_name = models.CharField('Company Name', max_length=50)
    currency = models.CharField('Currency', max_length=3)
    date = models.DateTimeField(auto_now_add=True)
    day_pass_due = models.CharField('Day pass due', max_length=50)
    document_date = models.DateField('Document Date')
    document_number = models.BigIntegerField('Document Number')
    merchant_number = models.CharField(max_length=50)
    position = models.CharField('Position', max_length=50)
    reference = models.CharField("Reference", max_length=50)
    tax = models.DecimalField('Tax', max_digits=10, decimal_places=2)


class AdvancePayment(PaymentDocument):
    concept = models.ForeignKey(
        "payment.AdvanceConcept",
        on_delete=models.DO_NOTHING,
        null=True
    )


class AdvanceConcept(models.Model):
    name = models.CharField('Concept', max_length=50)
