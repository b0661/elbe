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

import os
import platform
import urllib
from urlparse import urlparse,urlunparse
import mimetypes
from elbepack.debianreleases import codename2suite, codename_suite, installer_arch
from elbepack.filesystem import Filesystem
from elbepack.pkgutils import get_dsc_size

# Amend mimetypes to also include debian packages
mimetypes.add_type("application/vnd.debian.binary-package", ".deb", False)
mimetypes.add_type("application/vnd.debian.source-package", ".dsc", False)
mimetypes.add_type("application/vnd.debian.changes-package", ".changes", False)


class RepoBase(object):
    def __init__( self, path, log, arch, codename, origin, description, components="main", maxsize=None ):

        self.vol_path = path
        self.volume_count = 0

        self.log = log
        self.codename = codename
        self.arch = arch
        self.components = components
        self.origin = origin
        self.description = description
        self.maxsize = maxsize

        self.fs = self.get_volume_fs(self.volume_count)

        self.gen_repo_conf()

    def get_volume_fs( self, volume ):
        if self.maxsize:
            volname = os.path.join( self.vol_path, "vol%02d" % volume )
            return Filesystem(volname)
        else:
            return Filesystem(self.vol_path)

    def new_repo_volume( self ):
        self.volume_count += 1
        self.fs = self.get_volume_fs(self.volume_count)
        self.gen_repo_conf()

    def gen_repo_conf( self ):
        self.fs.mkdir_p( "conf" )
        fp = self.fs.open( "conf/distributions", "w")

        fp.write( "Origin: " + self.origin + "\n" )
        fp.write( "Label: " + self.origin + "\n" )
        fp.write( "Suite: " + codename2suite[ self.codename ] + "\n" )
        fp.write( "Codename: " + self.codename + "\n" )
        fp.write( "Architectures: " + self.arch + "\n" )
        fp.write( "Components: " + self.components + "\n" )
        fp.write( "Description: " + self.description + "\n" )

        fp.close()

    def includedeb( self, path, component="main"):
        if self.maxsize:
            new_size = self.fs.disk_usage("") + os.path.getsize( path )
            if new_size > self.maxsize:
                self.new_repo_volume()

        self.log.do( 'reprepro --basedir "' + self.fs.path + '" -C ' + component + ' includedeb ' + self.codename + ' ' + path )

    def includedsc( self, path, component="main"):
        if self.maxsize:
            new_size = self.fs.disk_usage("") + get_dsc_size( path )
            if new_size > self.maxsize:
                self.new_repo_volume()

        if self.maxsize and (self.fs.disk_usage("") > self.maxsize):
            self.new_repo_volume()

        self.log.do( 'reprepro --basedir "' + self.fs.path  + '" -C ' + component + ' -P normal -S misc includedsc ' + self.codename + ' ' + path ) 
        
    def includechanges( self, path, component="main"):
        self.log.do( "reprepro --basedir " + self.fs.path + " -C " + component + " --ignore=wrongdistribution include " + self.codename + " " + path )

    def include_packages( self, packages):
	for dpkg in packages:
	    mimetype = mimetypes.guess_type(dpkg[0], False)[0]
	    dpkg_url = urlparse(dpkg[0])
	    dpkg_component = dpkg[1]
            if dpkg_url.scheme == "" or dpkg_url.scheme == "file":
                # sanitize file url (abs path).
                # Remove file scheme as this might confuse.
                dpkg_url = urlparse(os.path.normpath(dpkg_url.path))
            dpkg_source = urlunparse(dpkg_url)
	    if mimetype in ["application/x-debian-package", "application/vnd.debian.binary-package"]:
		dpkg_filespec = urllib.urlretrieve(dpkg_source)
                self.includedeb(dpkg_filespec[0], dpkg_component)
	    elif mimetype in ["text/prs.lines.tag", "application/vnd.debian.source-package" ]:
		dpkg_filespec = urllib.urlretrieve(dpkg_source)
                self.includedsc(dpkg_filespec[0], dpkg_component)
	    elif mimetype in ["application/vnd.debian.changes-package" ]:
		dpkg_filespec = urllib.urlretrieve(dpkg_source)
                self.includechanges(dpkg_filespec[0], dpkg_component)
	    else:
	        self.log.printo("+%s (%s)+ is not a debian package - skipped!" % (dpkg[0], mimetype))

    def buildiso( self, fname ):
        if self.volume_count == 0:
            new_path = '"' + self.fs.path + '"'
            self.log.do( "genisoimage -o %s -J -R %s" % (fname, new_path) )
        else:
            for i in range(self.volume_count+1):
                volfs = self.get_volume_fs(i)
                newname = fname + ("%02d" % i)
                self.log.do( "genisoimage -o %s -J -R %s" % (newname, volfs.path) )



class UpdateRepo(RepoBase):
    def __init__( self, xml, path, log ):
        self.xml  = xml

        arch = xml.text("project/arch", key="arch" )
        codename = xml.text("project/suite")

        RepoBase.__init__( self, path, log, arch, codename, "Update", "Update", "main" )

class CdromBinRepo(RepoBase):
    def __init__( self, xml, path, log, maxsize ):
        self.xml  = xml

        arch = xml.text("project/arch", key="arch" )
        codename = xml.text("project/suite")

        RepoBase.__init__( self, path, log, arch, codename, "Elbe", "Elbe Binary Cdrom Repo", "main added", maxsize )

class CdromSrcRepo(RepoBase):
    def __init__( self, codename, path, log, maxsize ):
        RepoBase.__init__( self, path, log, "source", codename, "Elbe", "Elbe Source Cdrom Repo", "main", maxsize )

class ProjectRepo(RepoBase):
    def __init__( self, xml, path, log ):
        self.xml  = xml

        codename, suite = codename_suite( xml.text("initvm/suite") )
        arch = installer_arch( suite, platform.machine() )

        RepoBase.__init__( self, path, log, "%s source" % arch, codename, "Elbe", "Elbe Project Repo", "main")

class ToolchainRepo(RepoBase):
    def __init__( self, arch, codename, path, log):
        RepoBase.__init__( self, path, log, arch, codename, "toolchain", "Toolchain binary packages Repo", "main" )
