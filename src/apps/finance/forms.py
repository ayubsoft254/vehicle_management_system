"""
Forms for the finance app.
"""
from django import forms

from .models import AccountReconciliation, FinancialAccount, InternalTransfer, LedgerTransaction

INPUT_CLASS = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
SELECT_CLASS = INPUT_CLASS
CHECKBOX_CLASS = 'h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
TEXTAREA_CLASS = INPUT_CLASS


class FinancialAccountForm(forms.ModelForm):
    """Form for creating and editing a FinancialAccount."""

    class Meta:
        model = FinancialAccount
        fields = [
            'name', 'code', 'account_type',
            'bank_name', 'branch_name', 'account_number',
            'paybill_number', 'till_number', 'business_shortcode',
            'currency', 'opening_balance', 'opening_balance_date',
            'description', 'status', 'is_default',
            'allow_manual_transactions', 'require_approval',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'e.g. DIB Hoza'}),
            'code': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'e.g. DIB-HOZA'}),
            'account_type': forms.Select(attrs={'class': SELECT_CLASS}),
            'bank_name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'branch_name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'account_number': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'paybill_number': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'till_number': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'business_shortcode': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'currency': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'opening_balance': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01', 'min': '0'}),
            'opening_balance_date': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 3}),
            'status': forms.Select(attrs={'class': SELECT_CLASS}),
            'is_default': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'allow_manual_transactions': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'require_approval': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        }

    def clean_code(self):
        code = self.cleaned_data['code'].strip().upper()
        return code


class LedgerTransactionForm(forms.ModelForm):
    """Manual transaction entry against a specific FinancialAccount (account is set by the view)."""

    class Meta:
        model = LedgerTransaction
        fields = [
            'transaction_date', 'direction', 'transaction_type', 'amount', 'currency',
            'related_client', 'related_vehicle', 'related_party_label',
            'payment_method', 'description', 'supporting_document',
        ]
        widgets = {
            'transaction_date': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'direction': forms.Select(attrs={'class': SELECT_CLASS}),
            'transaction_type': forms.Select(attrs={'class': SELECT_CLASS}),
            'amount': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01', 'min': '0.01'}),
            'currency': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'related_client': forms.Select(attrs={'class': SELECT_CLASS}),
            'related_vehicle': forms.Select(attrs={'class': SELECT_CLASS}),
            'related_party_label': forms.TextInput(attrs={
                'class': INPUT_CLASS, 'placeholder': 'Supplier / vendor / auctioneer name (if not a client or vehicle)'
            }),
            'payment_method': forms.Select(attrs={'class': SELECT_CLASS}),
            'description': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3}),
            'supporting_document': forms.ClearableFileInput(attrs={'class': INPUT_CLASS}),
        }

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero.')
        return amount


class LedgerTransactionEditForm(forms.ModelForm):
    """Edit a transaction that hasn't been approved yet. Requires a reason (stored as edit_reason)."""

    edit_reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 2, 'placeholder': 'Why is this being edited?'}),
        help_text='Required — stored in the audit trail.',
    )

    class Meta:
        model = LedgerTransaction
        fields = [
            'transaction_date', 'transaction_type', 'amount', 'currency',
            'related_client', 'related_vehicle', 'related_party_label',
            'payment_method', 'description', 'supporting_document',
        ]
        widgets = {
            'transaction_date': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'transaction_type': forms.Select(attrs={'class': SELECT_CLASS}),
            'amount': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01', 'min': '0.01'}),
            'currency': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'related_client': forms.Select(attrs={'class': SELECT_CLASS}),
            'related_vehicle': forms.Select(attrs={'class': SELECT_CLASS}),
            'related_party_label': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'payment_method': forms.Select(attrs={'class': SELECT_CLASS}),
            'description': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3}),
            'supporting_document': forms.ClearableFileInput(attrs={'class': INPUT_CLASS}),
        }

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero.')
        return amount


class TransactionReversalForm(forms.Form):
    reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3, 'placeholder': 'Why is this transaction being reversed?'}),
    )


class TransactionCorrectionForm(forms.Form):
    correct_amount = forms.DecimalField(
        required=True, max_digits=14, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01', 'min': '0.01'}),
        label='Correct Amount',
    )
    reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3, 'placeholder': 'What was wrong, and what is the correct amount?'}),
    )

    def clean_correct_amount(self):
        amount = self.cleaned_data['correct_amount']
        if amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero.')
        return amount


class InternalTransferForm(forms.ModelForm):
    """Form for creating a transfer between two FinancialAccount records."""

    class Meta:
        model = InternalTransfer
        fields = ['from_account', 'to_account', 'amount', 'transfer_date', 'notes']
        widgets = {
            'from_account': forms.Select(attrs={'class': SELECT_CLASS}),
            'to_account': forms.Select(attrs={'class': SELECT_CLASS}),
            'amount': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01', 'min': '0.01'}),
            'transfer_date': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['from_account'].queryset = FinancialAccount.objects.filter(status='active')
        self.fields['to_account'].queryset = FinancialAccount.objects.filter(status='active')

    def clean(self):
        cleaned_data = super().clean()
        from_account = cleaned_data.get('from_account')
        to_account = cleaned_data.get('to_account')
        amount = cleaned_data.get('amount')
        if from_account and to_account and from_account.pk == to_account.pk:
            raise forms.ValidationError('The source and destination accounts must be different.')
        if amount is not None and amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero.')
        return cleaned_data


class AccountReconciliationForm(forms.ModelForm):
    """Form for starting a new reconciliation against an account's external statement."""

    class Meta:
        model = AccountReconciliation
        fields = ['reconciliation_date', 'statement_balance', 'notes']
        widgets = {
            'reconciliation_date': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'statement_balance': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3}),
        }


class SuspenseAllocationForm(forms.Form):
    """Identify who an unmatched suspense payment belongs to."""

    client = forms.ModelChoiceField(queryset=None, required=False, widget=forms.Select(attrs={'class': SELECT_CLASS}))
    client_vehicle = forms.ModelChoiceField(
        queryset=None, required=False, label='Client Vehicle (purchase)',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 2, 'placeholder': 'Optional notes about this allocation'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.clients.models import Client, ClientVehicle
        self.fields['client'].queryset = Client.objects.all().order_by('first_name', 'last_name')
        self.fields['client_vehicle'].queryset = ClientVehicle.objects.select_related('client', 'vehicle').all()

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('client') and not cleaned_data.get('client_vehicle'):
            raise forms.ValidationError('Select a client or a client vehicle to allocate this payment to.')
        return cleaned_data
