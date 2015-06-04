FROM ubuntu:14.04.2
MAINTAINER "Jeremy Nelson <jermnelson@gmail.com>"

RUN echo "deb http://archive.ubuntu.com/ubuntu trusty main universe" > /etc/apt/sources.list
RUN apt-get update
RUN apt-get install -y software-properties-common
RUN apt-get upgrade -y

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
RUN apt-get install -y python3-setuptools
RUN easy_install3 pip

# Install needed Python3 modules
ADD requirements.txt /opt/badges/requirements.txt
RUN cd /opt/badges; pip install -r requirements.txt

ADD ["fedora" "/opt/badges/fedora"]
ADD ["lib/ldfs" "/opt/badges/lib/ldfs"]
ADD ["lib/semantic_server" "/opt/badges/lib/semantic_server"]

EXPOSE 5100

ENTRYPOINT ["/opt/badges/"]

CMD ["python3", "badges.py", "serve"]
