<%namespace file="/type.tmpl" name="ctype" />

#ifndef ${entry.name}_HEADER_GUARD
#define ${entry.name}_HEADER_GUARD

#include "buffer.h"

${ctype.define(entry)}

// Decode a ${entry.name} from a bit aligned buffer
${entry.name}* decode_${entry.name}( Buffer* buffer);

#endif
