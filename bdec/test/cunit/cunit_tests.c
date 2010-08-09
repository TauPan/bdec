
#include <CUnit/CUnit.h>
#include <CUnit/Basic.h>
#include <CUnit/TestDB.h>

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "spec.h"

BitBuffer* createBitBufferFromFilename(char* filename);

void test_packed_statement(void);
void test_to_string(void);

int main(int argc, char **argv) {
    CU_pSuite bdecTemplate_suite;
    unsigned int result;
    
    CU_initialize_registry();

    bdecTemplate_suite = CU_add_suite("bdec template functions tests",
                                      NULL, NULL); // setup, teardown

    CU_ADD_TEST(bdecTemplate_suite, test_packed_statement);
    CU_ADD_TEST(bdecTemplate_suite, test_to_string);

    CU_basic_set_mode(CU_BRM_VERBOSE);
    CU_basic_run_tests();
    result = CU_get_number_of_failures();
    CU_cleanup_registry();
    return result;
}

void test_packed_statement() {
    struct Spec specStruct;
//    printf("ull: %lu | int: %lu\n", sizeof(unsigned long long), sizeof(int));
//    printf("struct: %lu | should: %lu\n", sizeof(specStruct.packed_test_packed), (sizeof(uint64_t)+sizeof(uint8_t)));
    CU_ASSERT_FATAL(sizeof(specStruct.packed_test_packed) >= (sizeof(uint64_t)+sizeof(uint8_t)));
    CU_ASSERT_FATAL(sizeof(specStruct.packed_test_packed) < (sizeof(uint64_t)*2));
    CU_ASSERT_FATAL(sizeof(specStruct.packed_test_unpacked) == (sizeof(uint64_t)*2));
}

void test_to_string() {
    char **resultString = malloc(sizeof(char**));
    char *filename = "spec.input";
    BitBuffer* buffer = createBitBufferFromFilename(filename);
    struct Spec* spec;
    decodeSpec(buffer, spec);
    free(buffer);

    int8ToString(&spec->to_string_sequence.int8, resultString);
    CU_ASSERT_FATAL(*resultString == "");
    int16ToString(&spec->to_string_sequence.int16, resultString);
    CU_ASSERT_FATAL(*resultString == "");
    int32ToString(&spec->to_string_sequence.int32, resultString);
    CU_ASSERT_FATAL(*resultString == "");
    int64ToString(&spec->to_string_sequence.int64, resultString);
    CU_ASSERT_FATAL(*resultString == "");
    int2ToString(&spec->to_string_sequence.int2, resultString);
    CU_ASSERT_FATAL(*resultString == "");
    int6ToString(&spec->to_string_sequence.int6, resultString);
    CU_ASSERT_FATAL(*resultString == "");
    hex64ToString(&spec->to_string_sequence.hex64, resultString);
    CU_ASSERT_FATAL(*resultString == "");
    hex8ToString(&spec->to_string_sequence.hex8, resultString);
    CU_ASSERT_FATAL(*resultString == "");
    bin13ToString(&spec->to_string_sequence.bin13, resultString);
    CU_ASSERT_FATAL(*resultString == "");
    bin19ToString(&spec->to_string_sequence.bin19, resultString);
    CU_ASSERT_FATAL(*resultString == "");
    bin32ToString(&spec->to_string_sequence.bin32, resultString);
    CU_ASSERT_FATAL(*resultString == "");
    text32ToString(&spec->to_string_sequence.text32, resultString);
    CU_ASSERT_FATAL(*resultString == "");
    text15ToString(&spec->to_string_sequence.text15, resultString);
    CU_ASSERT_FATAL(*resultString == "");
    text17ToString(&spec->to_string_sequence.text17, resultString);
    CU_ASSERT_FATAL(*resultString == "");

    freeSpec(spec);
}

BitBuffer* createBitBufferFromFilename(char* filename) {
    FILE* datafile = fopen(filename, "rb");
    if (datafile == 0)
    { 
        /* Failed to open file */
        fprintf(stderr, "Failed to open file!\n");
        return 0;
    }
    fseek(datafile, 0, SEEK_END);
    long int length = ftell(datafile);
    fseek(datafile, 0, SEEK_SET);
    
    /* Load the data file into memory */
    unsigned char* data = (unsigned char*)malloc(length);
    fread(data, length, 1, datafile);
    fclose(datafile);
    BitBuffer* buffer = (BitBuffer*)malloc(sizeof(BitBuffer));
    buffer->buffer = data;
    buffer->start_bit = 0;
    buffer->num_bits = length*8;
    return buffer;
}
