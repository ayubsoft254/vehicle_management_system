
from django.views.generic import ListView, DetailView, CreateView
from .models import Expense, ExpenseCategory
from django.urls import reverse_lazy

class ExpenseListView(ListView):
	model = Expense
	template_name = 'expenses/expense_list.html'
	context_object_name = 'expenses'

class ExpenseDetailView(DetailView):
	model = Expense
	template_name = 'expenses/expense_detail.html'
	context_object_name = 'expense'

class ExpenseCreateView(CreateView):
	model = Expense
	fields = '__all__'
	template_name = 'expenses/expense_form.html'
	success_url = reverse_lazy('expenses:expense-list')

class ExpenseCategoryListView(ListView):
	model = ExpenseCategory
	template_name = 'expenses/expensecategory_list.html'
	context_object_name = 'categories'

class ExpenseCategoryDetailView(DetailView):
	model = ExpenseCategory
	template_name = 'expenses/expensecategory_detail.html'
	context_object_name = 'category'

class ExpenseCategoryCreateView(CreateView):
	model = ExpenseCategory
	fields = '__all__'
	template_name = 'expenses/expensecategory_form.html'
	success_url = reverse_lazy('expenses:expensecategory-list')
