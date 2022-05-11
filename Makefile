build:
	# Build the backend
	npm run scss
	python ./manage.py collectstatic --no-input
run:
	python ./manage.py runserver --settings=kawori.settings.development