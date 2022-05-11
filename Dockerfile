# pull official base image
FROM python:3.9.7

# set environment variables
ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE kawori.settings.production

RUN mkdir /kawori

# set work directory
WORKDIR /kawori

# install dependencies
ADD requirements.txt /kawori/
RUN pip install -r requirements.txt

ADD . /kawori/

EXPOSE 8000