
#include <CUnit/CUnit.h>
#include <CUnit/Basic.h>
#include <CUnit/TestDB.h>

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

//#include <libcs_logging.h>

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
    char **resultString = malloc(sizeof(char*));
    char *expected;
    char *filename = "spec.input";
    printf("\ncreating BitBuffer from filename...\n");
    BitBuffer* buffer = createBitBufferFromFilename(filename);
    struct Spec* spec = calloc(1, sizeof(struct Spec));
    printf("decoding spec...\n");
    decodeSpec(buffer, spec);
    free(buffer);

    printf("now starting the tests...\n");

    expected = "97";
    uint8ToString(&spec->to_string_sequence.uint8, resultString);
    printf("called uint8ToString()...\n");
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);

    expected = "25187";
    uint16ToString(&spec->to_string_sequence.uint16, resultString);
    printf("called uint16ToString()...\n");
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);
   
    expected = "1684366951";
    uint32ToString(&spec->to_string_sequence.uint32, resultString);
    printf("called uint32ToString()...\n");
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);
    
    expected = "7523661662112280432";
    uint64ToString(&spec->to_string_sequence.uint64, resultString);
    printf("called int64ToString()...\n");
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);
    
    expected = "1";
    uint2ToString(&spec->to_string_sequence.uint2, resultString);
    printf("called uint2ToString()...\n");
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);

    expected = "54";
    uint6ToString(&spec->to_string_sequence.uint6, resultString);
    printf("called uint6ToString()...\n");
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);
    
    expected = "97";
    int8ToString(&spec->to_string_sequence.int8, resultString);
    printf("called uint8ToString()...\n");
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);

    expected = "25187";
    int16ToString(&spec->to_string_sequence.int16, resultString);
    printf("called uint16ToString()...\n");
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);
   
    expected = "1684366951";
    int32ToString(&spec->to_string_sequence.int32, resultString);
    printf("called uint32ToString()...\n");
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);
    
    expected = "7523661662112280432";
    int64ToString(&spec->to_string_sequence.int64, resultString);
    printf("called int64ToString()...\n");
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);
    
    expected = "1";
    int2ToString(&spec->to_string_sequence.int2, resultString);
    printf("called uint2ToString()...\n");
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);

    expected = "54";
    int6ToString(&spec->to_string_sequence.int6, resultString);
    printf("called uint6ToString()...\n");
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);
   
    expected = "0x7778797a61626364";
    hex64ToString(&spec->to_string_sequence.hex64, resultString);
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);
    
    expected = "65";
    hex8ToString(&spec->to_string_sequence.hex8, resultString);
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);
    
    bin13ToString(&spec->to_string_sequence.bin13, resultString);
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);
    
    bin19ToString(&spec->to_string_sequence.bin19, resultString);
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);
    
    bin32ToString(&spec->to_string_sequence.bin32, resultString);
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);
    
    text32ToString(&spec->to_string_sequence.text32, resultString);
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);
    
    text15ToString(&spec->to_string_sequence.text15, resultString);
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);
    
    text17ToString(&spec->to_string_sequence.text17, resultString);
    CU_ASSERT_STRING_EQUAL_FATAL(*resultString, expected);
    free(*resultString);

    printf("\nfinished the tests...\n");

    freeSpec(spec);
    printf("freed spec...\n");
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
