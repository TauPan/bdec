Name:           python-bdec
Version:        0.6.2
Release:        1%{?dist}
Summary:        Library for decoding binary files

Group:          Development/Tools/Other
License:        LGPL 2.1
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
Source:         ftp://example.org/%{name}-%{version}.tar.bz2
PreReq:         %install_info_prereq

%py_requires
BuildRequires:  python-base, python-devel, python-setuptools
Requires:       python-setuptools, python-mako, python-nose, python-pyparsing, python-xml

%description
A set of tools for decoding binary files.

Writing decoders for binary formats is typically tedious and error prone.
Binary formats are usually specified in text documents that developers have
to read if they are to create decoders, a time consuming, frustrating, and
costly process.

While there are high level markup languages such as ASN.1 for specifying
formats, few specifications make use of these languages, and such markup
languages cannot be retro-fitted to existing binary formats. 'bdec' is an
attempt to specify arbitrary binary formats in a markup language, and create
decoders automatically for that binary format given the high level
specification.


%prep
%setup -q


%build
%__python ./setup.py build


%install
%__python ./setup.py install \
    --prefix="%{_prefix}" \
    --root="%{buildroot}" \
    --record-rpm=files.lst


%clean
rm -rf $RPM_BUILD_ROOT


%files -f files.lst
%defattr(-,root,root)
%doc README CHANGELOG LICENSE


%changelog
* Mon Sep  9 2010 Justus Winter <winter@pre-sense.de>
- 0.6.2pre preliminary spec file
