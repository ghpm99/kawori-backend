build:
	# Build the backend
	npm run scss
	python ./manage.py collectstatic --no-input
run:
	python ./manage.py runserver --settings=kawori.settings.development
makemigrations:
	python ./manage.py makemigrations --settings=kawori.settings.development
migrate:
	python ./manage.py migrate --settings=kawori.settings.development