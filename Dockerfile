FROM fiji/fiji:fiji-openjdk-8

ENTRYPOINT []

RUN wget https://github.com/marrlab/BaSiC/raw/b6943502853c052fd93c6fabc807bc40907e73ce/BaSiCPlugin.zip && \
    unzip BaSiCPlugin.zip && \
    mv BaSiCPlugin/BaSiC_.jar Fiji.app/plugins/ && \
    mv BaSiCPlugin/Dependent/*.jar Fiji.app/jars/ && \
    rm -r BaSiCPlugin.zip BaSiCPlugin __MACOSX && \
    rm Fiji.app/jars/jtransforms-2.4.jar

COPY *.py ./
