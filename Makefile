build:
	python manage.py collectstatic --no-input
run:
	python manage.py runserver --settings=kawori.settings.development
makemigrations:
	python manage.py makemigrations --settings=kawori.settings.development
migrate:
	python manage.py migrate --settings=kawori.settings.development
test:
	python manage.py test --settings=kawori.settings.development
restore-dump:
	psql -U postgres -h localhost -c "drop database kawori;"
	psql -U postgres -h localhost -c "create database kawori;"
	psql -U postgres -h localhost kawori < ~/documents/dump/kawori.tar
activate-run:
	.venv/bin/python3.13 manage.py runserver --settings=kawori.settings.development