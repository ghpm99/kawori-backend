"""
Arquivo principal de testes para views do payment app.
Importa todos os testes dos submódulos para que o Django os encontre.
"""

from .views.test_get_all_scheduled_view import GetAllScheduledViewTestCase
from .views.test_get_csv_mapping import GetCSVMappingViewTestCase
from .views.test_process_csv_upload import ProcessCSVUploadViewTestCase

__all__ = [
    'GetAllScheduledViewTestCase',
    'GetCSVMappingViewTestCase', 
    'ProcessCSVUploadViewTestCase'
]
