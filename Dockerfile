FROM ubuntu:14.04.2
MAINTAINER "Jeremy Nelson <jermnelson@gmail.com>"

RUN apt-get update
RUN apt-get install -y software-properties-common

# Install Python3 setuptools and pip
RUN apt-get update
#RUN apt-get install -y python3-setuptools

# Install gcc for hiredis
#RUN add-apt-repository "deb http://archive.ubuntu.com/ubuntu $(lsb_release -sc) main universe"
RUN apt-get install -y gcc libc6-dev build-essential python3.4-dev python3-setuptools

# Install needed Python3 modules
RUN easy_install3 pip
ADD requirements.txt /opt/badges/requirements.txt
RUN cd /opt/badges; pip install -r requirements.txt

COPY lib/ldfs/ lib/ldfs/
COPY lib/semantic_server/. /lib/semantic_server/

EXPOSE 5100

ENTRYPOINT ["/opt/badges/"]

CMD ["python3", "badges.py", "serve"]
