#Dockerfile for Islandora OpenBadges REST API 
FROM python:3.5.0
MAINTAINER Jeremy Nelson <jermnelson@gmail.com>

# Set environmental variables
ENV IOB_HOME /opt/islandora-open-badges
ENV NGINX_HOME /etc/nginx

# Update Ubuntu and install Python 3 setuptools, git and other
# packages
RUN apt-get update && apt-get install -y && \
  apt-get install -y python3-setuptools &&\
  apt-get install -y git &&\
  apt-get install -y nginx &&\
  apt-get install -y python3-pip 

COPY . $IOB_HOME

RUN cd $IOB_HOME \
    && pip3 install -r requirements.txt \
    && rm $NGINX_HOME/sites-enabled/default \
    && cp islandora.conf $NGINX_HOME/sites-available/islandora.conf \
    && ln -s $NGINX_HOME/sites-available/islandora.conf $NGINX_HOME/sites-enabled/islandora.conf
    
EXPOSE 80
WORKDIR $IOB_HOME
# Run application with gunicorn and nginx
COPY docker-entrypoint.sh $IOB_HOME/
ENTRYPOINT ["./docker-entrypoint.sh"]
