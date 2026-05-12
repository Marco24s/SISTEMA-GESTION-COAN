from django.contrib import admin
from .models import (
    BudgetFiscalYear, BudgetFF, BudgetSubprog, BudgetProg,
    BudgetPPPInc, BudgetPPInc, BudgetPreInc, BudgetIncisosAgrupado,
    BudgetInc, BudgetCredit, BudgetAllocation, BudgetExecution
)

@admin.register(BudgetFiscalYear)
class BudgetFiscalYearAdmin(admin.ModelAdmin):
    list_display = ('year', 'status')
    list_filter = ('status',)

@admin.register(BudgetFF)
class BudgetFFAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')

@admin.register(BudgetProg)
class BudgetProgAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')

@admin.register(BudgetSubprog)
class BudgetSubprogAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')

@admin.register(BudgetPPPInc, BudgetPPInc, BudgetPreInc, BudgetIncisosAgrupado)
class GenericClassifierAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')

@admin.register(BudgetInc)
class BudgetIncAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')


@admin.register(BudgetCredit)
class BudgetCreditAdmin(admin.ModelAdmin):
    list_display = (
        'fiscal_year', 'ff', 'programa', 'subprog', 
        'inc', 'ppp_inc', 'pp_inc', 'pre_inc', 'incisos_agrupado', 
        'total_amount'
    )
    list_filter = ('fiscal_year', 'ff', 'programa', 'inc', 'ppp_inc')

@admin.register(BudgetAllocation)
class BudgetAllocationAdmin(admin.ModelAdmin):
    list_display = ('unit', 'credit', 'allocated_amount')
    list_filter = ('unit',)

@admin.register(BudgetExecution)
class BudgetExecutionAdmin(admin.ModelAdmin):
    list_display = ('reference_code', 'allocation', 'commitment_amount', 'accrued_amount', 'paid_amount', 'user')
    list_filter = ('allocation__unit', 'user')
