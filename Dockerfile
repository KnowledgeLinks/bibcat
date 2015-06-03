FROM ubuntu
MAINTAINER "Jeremy Nelson"
RUN wget https://github.com/fcrepo4/fcrepo4/releases/download/fcrepo-4.2.0/fcrepo-webapp-4.2.0-jetty-console.jar
RUN sudo mv fcrepo-webapp-4.2.0-jetty-console.jar /opt/badges/fedora/.
