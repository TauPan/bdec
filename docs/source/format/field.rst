
.. _format-field:

=============
Field entries
=============

Field entries are the core element in a specification; they represent all the
data that is found in the binary file. Some characteristics of this data are;

  * The data on disk can be many types, such as text (in any encoding),
    integers, and buffers.
  * The length of the data can be of any; it may be a fixed length, or it may
    be :ref:`variable length <bdec-expressions>`. The data may be less than a 
    byte in length, and it may not be byte aligned.


Specification
=============

Bdec fields can have 4 attributes;

  * A name
  * A :ref:`length <bdec-expressions>` in bits
  * A type_ (optional)
  * An encoding (optional)
  * A value_ (optional)
  * A min_ value (optional)
  * A max_ value (optional)

.. _type: `Field types`_
.. _value: `Expected value`_
.. _min: `Value ranges`_
.. _max: `Value ranges`_


Field types
===========

There are currently four available field types. If the type is not specified,
it is assumed to be binary_.

Integers
--------

Integer fields represent numeric values in the data file. There are two types
of encodings supported, `little endian and big endian`_.

The default encoding is big endian.

.. _little endian and big endian: http://en.wikipedia.org/wiki/Endianness 


Text
----

Text fields represent textual data in the binary file (ie: data that can be
printed). It can use any unicode encoding, and defaults to ascii.


Hex
---

Hex fields represent binary data whose length is a multiple of whole bytes. It
has no encoding.


Binary
------

Binary fields represent binary data of any length. It has no encoding.


Expected value
==============

Fields can have a value which specifies the value it expects to find on disk.
If the value doesn't match, the decode will fail.

The decode attribute can be either in hex (ie: value="0xf3"), or in the type
of the field (eg: type="text" value="expected string").


Value ranges
============

It is often desirable to set a minimum and a maximum value for fields. For 
example, you may want to accept all numerical text entries '0' .. '9'. The min
and max attributes can be used to set a range of valid numerical values for the
field.

Both min and max are inclusive; ie::

    min <= value <= max

If the decode value falls outside the minimum or maximum, the field fails to
decode.


Examples
========

A numeric field that is 2 bytes long, in big endian format::

   <field name="data" length="16" type="integer" encoding="big endian" />

A utf-16 text field that is 8 bytes long::

   <field name="name" length="64" type="text" encoding="utf16" />

A single bit boolean flag::

   <field name="is header present" length="1" />

A two byte field that has an expected value::

   <field name="id" length="16" value="0x00f3" />

A single numerical character (eg: characters '0'..'9')::

   <field name="number" length="8" min="48" max="57" />
