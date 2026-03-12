"""
Arquivo principal de testes para views do payment app.
Importa todos os testes dos submódulos para que o Django os encontre.
"""

from .views.test_get_all_view import GetAllViewTestCase
from .views.test_save_new_view import SaveNewViewTestCase
from .views.test_get_payments_month import GetPaymentsMonthTestCase
from .views.test_detail_view import DetailViewTestCase
from .views.test_save_detail_view import SaveDetailViewTestCase
from .views.test_payoff_detail_view import PayoffDetailViewTestCase
from .views.test_get_all_scheduled_view import GetAllScheduledViewTestCase
from .views.test_get_csv_mapping import GetCSVMappingViewTestCase
from .views.test_process_csv_upload import ProcessCSVUploadViewTestCase
from .views.test_csv_resolve_imports_view import CSVResolveImportsViewTestCase
from .views.test_csv_import_view import CSVImportViewTestCase
from .views.test_statement_view import StatementViewTestCase

__all__ = [
    'GetAllViewTestCase',
    'SaveNewViewTestCase',
    'GetPaymentsMonthTestCase',
    'DetailViewTestCase',
    'SaveDetailViewTestCase',
    'PayoffDetailViewTestCase',
    'GetAllScheduledViewTestCase',
    'GetCSVMappingViewTestCase',
    'ProcessCSVUploadViewTestCase',
    'CSVResolveImportsViewTestCase',
    'CSVImportViewTestCase',
    'StatementViewTestCase',
]
