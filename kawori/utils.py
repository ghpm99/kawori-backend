from datetime import datetime
from django.core.paginator import Paginator

DEFAULT_PAGINATION_PER_PAGE = 15


def paginate(object_list: list, page_number: int, per_page: int = DEFAULT_PAGINATION_PER_PAGE) -> dict:
    '''
        "paginate" generates a default pattern to API paginations using Django Paginator.

        Parameters:
            - object_list (list): Data that will be divided into pages;
            - page_number (int): Data from which page will be get;
            - per_page (int): Itens per page.

        Returns:
            - data (dict): Dict containing page information and dataset.
    '''

    paginator = Paginator(object_list, per_page)
    page = paginator.get_page(page_number)
    result = page.__dict__.get('object_list')

    return {
        'current_page': page.number,
        'total_pages': paginator.num_pages,
        'has_previous': page.has_previous(),
        'has_next': page.has_next(),
        'data': result,
    }


def format_date(string_date: str) -> datetime:
    try:
        return datetime.strptime(string_date, '%Y-%m-%d')
    except Exception:
        return None


def boolean(string: str) -> bool:
    try:
        string = int(string)

        if string == 0:
            return False
        if string == 1:
            return True
    except Exception:
        if isinstance(string, str):
            if string.lower() in ["0", "no", "false"]:
                return False
            if string.lower() in ["1", "yes", "true"]:
                return True
