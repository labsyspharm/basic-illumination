FROM fiji/fiji:fiji-openjdk-8

RUN wget https://www.helmholtz-muenchen.de/fileadmin/ICB/software/BaSiC/BaSiCPlugin.zip && \
    unzip BaSiCPlugin.zip && \
    mv BaSiCPlugin/BaSiC_.jar Fiji.app/plugins/ && \
    mv BaSiCPlugin/Dependent/*.jar Fiji.app/jars/ && \
    rm -r BaSiCPlugin.zip BaSiCPlugin __MACOSX && \
    rm Fiji.app/jars/jtransforms-2.4.jar

COPY *.py ./
