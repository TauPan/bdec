HOME=/home/schwardt/bdec-carmentis/
TEMPLATE=${HOME}bdec/templates/c/
OUTPUT=${HOME}bdec/test/cunit/
SPEC=${OUTPUT}spec.xml

all:
	(cd ${HOME}; ./compile --template=${TEMPLATE} -d ${OUTPUT} ${SPEC})
	(export LD_RUN_PATH=/usr/local/lib/;\
    export LD_LIBRARY_PATH=/usr/local/lib/;\
    cd ${OUTPUT};\
    rm main.c;\
    rm cunit_tests;\
    gcc *.c -o cunit_tests -lcunit -lcs_logging -ggdb -O0 -Wall -Werror;\
    echo "\n\n|=========================== now starting the test ============================|\n\n";\
    ./cunit_tests)
