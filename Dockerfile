FROM ubuntu:14.04.2
MAINTAINER "Jeremy Nelson <jermnelson@gmail.com>"

RUN apt-get update
RUN apt-get install -y software-properties-common

# Install Oracle Java 8 from 
# https://github.com/dockerfile/java/blob/master/oracle-java8/Dockerfile
RUN \
  echo oracle-java8-installer shared/accepted-oracle-license-v1-1 select true | debconf-set-selections && \
  add-apt-repository -y ppa:webupd8team/java && \
  apt-get update && \
  apt-get install -y oracle-java8-installer && \
  rm -rf /var/lib/apt/lists/* && \
  rm -rf /var/cache/oracle-jdk8-installer
ENV JAVA_HOME /usr/lib/jvm/java-8-oracle

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

VOLUME ["fedora", "cache"]

COPY fedora/. fedora/.
COPY lib/ldfs/ lib/ldfs/
COPY lib/semantic_server/. /lib/semantic_server/

EXPOSE 5100

ENTRYPOINT ["/opt/badges/"]

CMD ["python3", "badges.py", "serve"]
