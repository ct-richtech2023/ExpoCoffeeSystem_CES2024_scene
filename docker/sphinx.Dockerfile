FROM sphinxdoc/sphinx:4.4.0
EXPOSE 8000

RUN pip3 install sphinx-autobuild
RUN pip3 install plantweb
