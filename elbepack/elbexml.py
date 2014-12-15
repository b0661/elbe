# ELBE - Debian Based Embedded Rootfilesystem Builder
# Copyright (C) 2013  Linutronix GmbH
#
# This file is part of ELBE.
#
# ELBE is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ELBE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ELBE.  If not, see <http://www.gnu.org/licenses/>.

from elbepack.treeutils import etree
from elbepack.validate import validate_xml
from elbepack.xmldefaults import ElbeDefaults

from base64 import standard_b64decode
from tempfile import NamedTemporaryFile

from urlparse import urlsplit

class ValidationError(Exception):
    def __init__(self):
        Exception.__init__(self)

    def __repr__(self):
        return "Elbe XML Validation Error"

class NoInitvmNode(Exception):
    pass

class ElbeXML(object):
    def __init__(self, fname, buildtype=None, skip_validate=False):
        if not skip_validate:
            if not validate_xml(fname):
                raise ValidationError

        self.xml = etree( fname )
        self.prj = self.xml.node("/project")
        self.tgt = self.xml.node("/target")

        if buildtype:
            pass
        elif self.xml.has( "project/buildtype" ):
            buildtype = self.xml.text( "/project/buildtype" )
        else:
            buildtype = "nodefaults"
        self.defs = ElbeDefaults(buildtype)

    def text(self, txt, key=None):
        if key:
            return self.xml.text(txt, default=self.defs, key=key)
        else:
            return self.xml.text(txt)

    def has(self, path):
        return self.xml.has(path)

    def node(self, path):
        return self.xml.node(path)

    def is_cross (self, host_arch):

        target = self.text ("project/buildimage/arch", key="arch")

        if (host_arch == target):
            return False

        if ((host_arch == "amd64") and (target == "i386")):
            return False

        if ((host_arch == "armhf") and (target == "armel")):
            return False

        return True

    def _mirror_spec(self, uri, localmachine):
        ''' Create appropriate mirror specification including additional info for e.g. apt-cacher. '''
	url = urlsplit(uri.strip())
	mirror_spec = ""
	if url.scheme == "" or url.scheme == "file":
	    # sanitize file url (abs path).
	    # make shure file scheme is available
	    mirror_spec += "file://%s" % (os.path.normpath(url.path))
	elif self.prj.has("mirror/apt-cacher") and url.scheme == "http":
	    # Only http requests can be rerouted via apt-cacher
	    mirror_spec += "http://%s/" % self.prj.text("mirror/apt-cacher").strip()
	    mirror_spec += url.hostname
	    mirror_spec += url.path
	else:
	    mirror_spec += url.geturl()
	return mirror_spec.replace("LOCALMACHINE", localmachine)
      
    def get_primary_mirror (self, cdrompath):
        if self.prj.has("mirror/primary_host"):
            m = self.prj.node("mirror")

            mirror = m.text("primary_proto") + "://"
            mirror +=m.text("primary_host")  + "/"
            mirror +=m.text("primary_path")

        elif self.prj.has("mirror/cdrom") and cdrompath:
            mirror = "file://%s" % cdrompath

        return self._mirror_spec(mirror, "10.0.2.2")


    # XXX: maybe add cdrom path param ?
    def create_apt_sources_list (self):
        ''' Create apt sources.list for project. '''
        if not self.prj.has("mirror") and not self.prj.has("mirror/cdrom"):
            return "# no mirrors configured"

        mirror = ""
        if self.prj.has("mirror/primary_host"):
            mirror += "deb " + self.get_primary_mirror (None)
            mirror += " " + self.prj.text("suite") + " main\n"

            if self.prj.has("mirror/url-list"):
                for url in self.prj.node("mirror/url-list"):
                    if url.has("binary"):
                        mirror += "deb " + url.text("binary").strip() + "\n"
                    if url.has("source"):
                        mirror += "deb-src "+url.text("source").strip()+"\n"

        if self.prj.has("mirror/cdrom"):
            mirror += "deb copy:///cdrom %s main added\n" % (self.prj.text("suite"))

        return mirror.replace("LOCALMACHINE", "10.0.2.2")

    def get_target_packages(self):
        return [p.et.text for p in self.xml.node("/target/pkg-list")]

    def get_buildenv_packages(self):
        retval = []
        if self.xml.has("./project/buildimage/pkg-list"):
            retval = [p.et.text for p in self.xml.node("project/buildimage/pkg-list")]

        return retval

    def clear_pkglist( self, name ):
        tree = self.xml.ensure_child( name )
        tree.clear()

    def append_pkg( self, aptpkg, name ):
        tree = self.xml.ensure_child( name )
        pak = tree.append( 'pkg' )
        pak.set_text( aptpkg.name )
        pak.et.tail = '\n'
        pak.et.set( 'version', aptpkg.installed_version )
        pak.et.set( 'md5', aptpkg.installed_md5 )
        if aptpkg.is_auto_installed:
            pak.et.set( 'auto', 'true' )
        else:
            pak.et.set( 'auto', 'false' )

    def clear_full_pkglist( self ):
        tree = self.xml.ensure_child( 'fullpkgs' )
        tree.clear()

    def clear_debootstrap_pkglist( self ):
        tree = self.xml.ensure_child( 'debootstrappkgs' )
        tree.clear()

    def append_full_pkg( self, aptpkg ):
        self.append_pkg( aptpkg, 'fullpkgs' )

    def append_debootstrap_pkg( self, aptpkg ):
        self.append_pkg( aptpkg, 'debootstrappkgs' )

    def archive_tmpfile( self ):
        fp = NamedTemporaryFile()
        fp.write( standard_b64decode( self.text("archive") ) )
        fp.file.flush()
        return fp

    def get_debootstrappkgs_from( self, other ):
        tree = self.xml.ensure_child( 'debootstrappkgs' )
        tree.clear()

        for e in other.node( 'debootstrappkgs' ):
            tree.append_treecopy( e )

    def get_initvmnode_from( self, other ):
        ivm = other.node( 'initvm' )
        if ivm is None:
            raise NoInitvmNode()

        tree = self.xml.ensure_child( 'initvm' )
        tree.clear()

        for e in ivm:
            tree.append_treecopy( e )

        self.xml.set_child_position( tree, 0 )
