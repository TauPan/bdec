
.. _format-sequenceof:

==================
SequenceOf entries
==================

SequenceOf entries are repeitions of another element a given number of times.
The repeated entry may be repeated a `given number of times`_, it may may
repeated `until a buffer is empty`_, or it may repeat until a `condition is
met`_.

.. _given number of times: `Count loops`_
.. _until a buffer is empty: `Length loops`_
.. _condition is met: `End-Sequenceof loops`_


Specification
=============

Bdec sequenceof entries can have 3 attributes;

  * A name
  * A count_ (optional)
  * A length_ (optional)

A sequenceof should have either a count, a length, or have an embedded 
`end-sequenceof`_ to indicate when to stop repeating the element.

SequenceOf entries must contain one entry that is to be repeated (ie: a
:ref:`field <format-field>`, a :ref:`sequence <format-sequence>`, a sequenceof,
or a :ref:`choice <format-choice>`).

.. _count: `Count loops`_
.. _length: `Length loops`_
.. _end-sequenceof: `End-sequenceof loops`_


Count loops
===========

The count attribute is an :ref:`expression <bdec-expressions>` that indicates
the number of times the embedded item should repeat.


Length loops
============

The length attribute is an :ref:`expression <bdec-expressions>` that indicates
the size of the buffer in bits. The embedded entry will be repeated until the
buffer is empty.


End-sequenceof loops
====================

By embedding an 'end-sequenceof' tag somewhere in the child, when that child
item is decoded, the sequenceof will end. This is useful when loops are 
terminated with an 'end' tag in the buffer. It is usually used with a 
:ref:`choice <format-choice>` entry.

For example, a `null terminated string`_ can be defined by a sequence of 
characters ended by a null character.

.. _null terminated string: `null-terminated-string`_

Examples
========

A block of 100 name/value pairs::

  <sequenceof name="data" count="100">
    <sequence name="entry">
      <field name="name" length="64" type="text" />
      <field name="value" length="32" type="integer" encoding="little endian" />
    </sequence>
  </sequenceof>

.. _null-terminated-string:

A null terminated string is a repeated block of characters that
is terminated by a 'null' character. This can be represented by::

  <sequenceof name="null terminated string">
    <choice name="entry">
      <field name="null" length="8" value="0x0"><end-sequenceof /></field>
      <field name="char" length="8" />
    </choice>
  </sequenceof>

A repeated loop of entries that has a known length (eg: the header in the 
wma/wmv specification) can be defined as::

  <field name="buffer length" length="32" type="integer" />
  <sequenceof name="items" length="${buffer length} * 8">
    <sequence name="item">
      <field name="a" length="8" />
      <field name="b" length="16" />
    </sequence>
  </sequenceof>
