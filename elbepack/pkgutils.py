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
import sys
import platform
import subprocess

from tempfile import mkdtemp
from urlparse import urlsplit
import urllib2

from elbepack.debianreleases import suite2codename, codename2suite

try:
    from elbepack import virtapt
    from apt_pkg import TagFile
    virtapt_imported = True
except ImportError:
    print "WARNING - python-apt not available: if there are multiple versions of"
    print " kinitrd packages on the mirror(s) elbe selects the first package it"
    print " has found. There is no guarantee that the latest package is used."
    print " To ensure this, the python-apt package needs to be installed."
    import urllib2
    virtapt_imported = False


class NoKinitrdException(Exception):
    pass

def apt_mirror_spec( prj, defs, uri, localmachine):
    url = urlsplit(uri.strip())
    mirror_spec = ""
    if url.scheme == "" or url.scheme == "file":
        # sanitize file url (abs path).
        # make shure file scheme is available
        mirror_spec += "file://%s" % (os.path.normpath(url.path))
    elif prj.has("mirror/apt-cacher") and url.scheme == "http":
        # Only http requests can be rerouted via apt-cacher
        mirror_spec += "http://%s/" % prj.text("mirror/apt-cacher").strip()
	mirror_spec += url.hostname
	mirror_spec += url.path
    else:
        mirror_spec += url.geturl()
    return mirror_spec.replace("LOCALMACHINE", localmachine)
    
def apt_sources_list( prj, defs, for_host = None):
    ''' Create apt sources.list either for host environment or for VM.
    '''
    suite = prj.text("suite")

    slist = ""
    mirror = ""
    localmachine = ""
    if not for_host is None:
        # Create for host environment
        localmachine = "localhost"
    else:
        # Create for virtual machine (initvm) environment.
        # From the VM the host can be reached by 10.0.2.2 on default.
        localmachine = "10.0.2.2"

    if prj.node("repository/pkg-list"):
        if not for_host is None:
	    mirror = "file://%s/.elbe-repo" % prj.text("directory")
	else:
	    mirror = "file:///media/elbe-repo"
	slist += "# Local project repository. Shared between host and VM.\n"
        slist += "deb %s %s main\n" % (mirror, suite)
        slist += "deb-src %s %s main\n" % (mirror, suite)
      
    if prj.has("mirror/primary_host"):
        mirror = apt_mirror_spec(prj, defs, 
				 "%s://%s%s" % ( prj.text("mirror/primary_proto"),
		                                 prj.text("mirror/primary_host"),
		                                 prj.text("mirror/primary_path") ),
				 localmachine)
	slist += "# Primary host.\n"
        slist += "deb %s %s main\n" % (mirror, suite)
        slist += "deb-src %s %s main\n" % (mirror, suite)

    if prj.has("mirror/cdrom"):
        tmpdir = mkdtemp()
        kinitrd = prj.text("buildimage/kinitrd", default=defs, key="kinitrd")
        os.system( '7z x -o%s "%s" pool/main/%s/%s dists' % (tmpdir, prj.text("mirror/cdrom"), kinitrd[0], kinitrd) )
        slist += "# CDROM (.iso) repository.\n"
        slist += "deb file://%s %s main\n" % (tmpdir,suite)

    if prj.node("mirror/url-list"):
        slist += "# Additional repositories.\n"
        for n in prj.node("mirror/url-list"):
            if n.has("binary"):
	        # split in url and components
	        deb_spec = n.text("binary").split(None, 1)
	        mirror = apt_mirror_spec(prj, defs, deb_spec[0], localmachine)
                slist += "deb %s %s\n" % (mirror, deb_spec[1])
            if n.has("source"):
	        # split in url and components
	        deb_spec = n.text("source").split(None, 1)
	        mirror = apt_mirror_spec(prj, defs, deb_spec[0], localmachine)
                slist += "deb-src %s %s\n" % (mirror, deb_spec[1])

    return slist
    
def get_sources_list( prj, defs ):
    # Compatibility function
    # use apt_sources_list instead

    if sys.argv[1] == "init":
	return apt_sources_list( prj, defs, True)
      
    return apt_sources_list( prj, defs)


def debian_installer_mirror_preseed( prj, defs):
    # Create debian installer preseed.cfg data for apt package mirrors.
    suite = prj.text("suite")

    preseed_cfg = ""
    mirror = ""
    # From the VM the host can be reached by 10.0.2.2 on default.
    localmachine = "10.0.2.2"

    # Package repository in shared directory can not be accessed by debian installer.
    # Just ignore for now.
      
    if prj.has("mirror/primary_host"):
        preseed_cfg += "d-i apt-setup/use_mirror      boolean true\n"
        preseed_cfg += "d-i mirror/country            string manual\n"
        if prj.has("mirror/apt-cacher") and prj.text("mirror/primary_proto") == "http":
	    preseed_cfg += "d-i mirror/http/hostname string %s\n" % prj.text("mirror/apt-cacher").replace("LOCALMACHINE", "10.0.2.2")
	    preseed_cfg += "d-i mirror/http/directory string /%s%s\n" % (prj.text("mirror/primary_host").replace("LOCALMACHINE", "10.0.2.2"),
								         prj.text("mirror/primary_path"))
	    preseed_cfg += "d-i mirror/http/directory string /%s%s\n" % (prj.text("mirror/primary_host").replace("LOCALMACHINE", "10.0.2.2"),
								         prj.text("mirror/primary_path"))
	else:
	    preseed_cfg += "d-i mirror/http/hostname string %s\n" % prj.text("mirror/primary_host").replace("LOCALMACHINE", "10.0.2.2")
	    preseed_cfg += "d-i mirror/http/directory string %s\n" % prj.text("mirror/primary_path")
	    preseed_cfg += "d-i mirror/http/directory string %s\n" % prj.text("mirror/primary_path")
        preseed_cfg += "d-i mirror/http/proxy string %s\n" % prj.text("mirror/primary_proxy")
        preseed_cfg += "d-i mirror/protocol string %s\n" % prj.text("mirror/primary_proto")
	    
    if prj.has("mirror/cdrom"):
        preseed_cfg += "base-config apt-setup/uri_type select cdrom\n"
        preseed_cfg += "base-config apt-setup/cd/another boolean false\n"
        preseed_cfg += "base-config apt-setup/another boolean false\n"
        if not prj.has("mirror/primary_host"):
	    preseed_cfg += "apt-mirror-setup apt-setup/use_mirror boolean false\n"

    if prj.node("mirror/url-list"):
        i = 0
        for n in prj.node("mirror/url-list"):
	    index = i
	    preseed_cfg += "d-i apt-setup/local%s/repository string %s\n" % (index,
				apt_mirror_spec(prj, defs, n.text("binary"), localmachine))
	    preseed_cfg += "d-i apt-setup/local%s/comment string local server\n" % index
	    preseed_cfg += "d-i apt-setup/local%s/source boolean true\n" % index
	    #d-i apt-setup/local${i}/key string http://local.server/key
	    i += 1

    return preseed_cfg    

def get_project_repo_pkg_list( prj):

    slist = []
    if not prj.node("repository/pkg-list") is None:
        for n in prj.node("repository/pkg-list"):
            if n.tag == "pkg-source":
                slist += [n.text(".").split()]

    return slist

def get_initrd_pkg( prj, defs ):
    initrdname = prj.text("buildimage/kinitrd", default=defs, key="kinitrd")

    return initrdname

def get_url ( arch, suite, target_pkg, mirror ):
    try:
        packages = urllib2.urlopen("%s/dists/%s/main/binary-%s/Packages" %
          (mirror.replace("LOCALMACHINE", "localhost"), suite, arch))

        packages = packages.readlines()
        packages = filter( lambda x: x.startswith( "Filename" ), packages )
        packages = filter( lambda x: x.find( target_pkg ) != -1, packages )

        tmp = packages.pop()
        urla = tmp.split()
        url = "%s/%s" % (mirror.replace("LOCALMACHINE", "localhost"), urla[1])
    except IOError:
        url = ""
    except IndexError:
        url = ""


    return url

def get_initrd_uri( prj, defs, arch ):
    if arch == "default":
        arch  = prj.text("buildimage/arch", default=defs, key="arch")
    suite = prj.text("suite")

    name  = prj.text("name", default=defs, key="name")
    apt_sources = get_sources_list(prj, defs)

    target_pkg = get_initrd_pkg(prj, defs)

    if virtapt_imported:
        v = virtapt.VirtApt( name, arch, suite, apt_sources, "" )
        d = virtapt.apt_pkg.DepCache(v.cache)

        pkg = v.cache[target_pkg]

        c=d.get_candidate_ver(pkg)
        x=v.source.find_index(c.file_list[0][0])

        r=virtapt.apt_pkg.PackageRecords(v.cache)
        r.lookup(c.file_list[0])
        uri = x.archive_uri(r.filename)
        return uri
    else:
        url = "%s://%s/%s" % (prj.text("mirror/primary_proto"),
          prj.text("mirror/primary_host"),
          prj.text("mirror/primary_path") )
        pkg = get_url ( arch, suite, target_pkg, url )

        if pkg:
            return pkg

        for n in prj.node("mirror/url-list"):
            url = n.text("binary")
            urla = url.split()
            pkg = get_url ( arch, suite, target_pkg,
              urla[0].replace("BUILDHOST", "localhost") )

            if pkg:
                return pkg

    return ""


def get_dsc_size( fname ):
    if not virtapt_imported:
        return 0

    tf = TagFile( fname )

    sz = os.path.getsize(fname)
    for sect in tf:
        if sect.has_key('Files'):
            files = sect['Files'].split('\n')
            files = [ f.strip().split(' ') for f in files ]
            for f in files:
                sz += int(f[1])

    return sz

def copy_initvm_kinitrdiso(xml, target_dir, defs):
    """ Try to get initrd.gz and vmlinuz and cdrom.iso for initvm.
    """
    err = None
    
    # suite = oldstable, stable, testing, ...
    suite = codename2suite[ xml.text("initvm/suite") ]
    # codename = wheezy, jessie, ...
    codename = suite2codename[ suite ]
    arch = platform.machine()
    if arch == "i686":
        arch = "i386"
    if arch == "x86_64":
        arch = "amd64"

    # default installation cdrom iso.
    iso_cd_source = "http://cdimage.debian.org/cdimage/weekly-builds/%s/iso-cd/debian-%s-%s-netinst.iso" % (arch, suite, arch)
    if xml.has("initvm/installer/cdrom.iso"):
        iso_cd_source = xml.text("initvm/installer/cdrom.iso")
    iso_cd_dest = os.path.join(target_dir, "cdrom.iso")

    # Download cdrom iso.
    try:
        response = urllib2.urlopen(iso_cd_source)
    except urllib2.URLError as err:
        raise NoKinitrdException( 'Retrieval of %s failed: %s.' % (iso_cd_source, err.reason) )
        return
    fd = open( iso_cd_dest, 'wb')
    fd.write( response.read() )
    fd.close()

    # Generate a list of files of the cdrom iso image
    filelist = subprocess.check_output("isoinfo -J -f -i %s" % iso_cd_dest, shell=True)
    # search for vmlinuz and initrd.gz
    for line in filelist.splitlines():
        # exclude typical installer sub dirs
        if "/gtk/" in line:
            continue
        if "/xen/" in line:
            continue
        # search
        if "vmlinuz" in line:
            iso_path_vmlinuz = line
        if "initrd.gz" in line:
            iso_path_initrd = line

    files = (("initvm/installer/initrd.gz", iso_path_initrd, "initrd.gz"), 
             ("initvm/installer/vmlinuz", iso_path_vmlinuz, "vmlinuz"))

    for key, source_file, dest_file in files:
        if xml.has(key):
            source_file = xml.text(key)
        try:
            dest_file = os.path.join(target_dir, dest_file)
            file_content = subprocess.check_output("isoinfo -J -i %s -x %s" % (iso_cd_dest, source_file), shell=True)
            dest_file = os.path.join(target_dir, dest_file)
            fd = open( dest_file, 'wb')
            fd.write( file_content )
            fd.close()
        except:
            raise NoKinitrdException( 'Extraction of %s to %s failed.' % (source_file, dest_file) )
            return

def copy_kinitrd( prj, target_dir, defs, arch="default" ):
    if arch == "default":
        arch  = prj.text("buildimage/arch", default=defs, key="arch")
    suite = prj.text("suite")

    try:
        uri = get_initrd_uri(prj, defs, arch)
    except KeyError:
        raise NoKinitrdException ('no kinitrd/elbe-bootstrap package available')
        return
    except SystemError:
        raise NoKinitrdException ('a configured mirror is not reachable')
        return

    tmpdir = mkdtemp()

    if uri.startswith("file://"):
        os.system( 'cp "%s" "%s"' % ( uri[len("file://"):], os.path.join(tmpdir, "pkg.deb") ) )
    elif uri.startswith("http://"):
        os.system( 'wget -O "%s" "%s"' % ( os.path.join(tmpdir, "pkg.deb"), uri ) )
    elif uri.startswith("ftp://"):
        os.system( 'wget -O "%s" "%s"' % ( os.path.join(tmpdir, "pkg.deb"), uri ) )
    else:
        raise NoKinitrdException ('no kinitrd/elbe-bootstrap package available')

    os.system( 'dpkg -x "%s" "%s"' % ( os.path.join(tmpdir, "pkg.deb"), tmpdir ) )

    if prj.has("mirror/cdrom"):
        os.system( 'cp "%s" "%s"' % ( os.path.join( tmpdir, 'var', 'lib', 'elbe', 'initrd', 'initrd-cdrom.gz' ), os.path.join(target_dir, "initrd.gz") ) )
    else:
        os.system( 'cp "%s" "%s"' % ( os.path.join( tmpdir, 'var', 'lib', 'elbe', 'initrd', 'initrd.gz' ), os.path.join(target_dir, "initrd.gz") ) )
    os.system( 'cp "%s" "%s"' % ( os.path.join( tmpdir, 'var', 'lib', 'elbe', 'initrd', 'vmlinuz' ), os.path.join(target_dir, "vmlinuz") ) )

    os.system( 'rm -r "%s"' % tmpdir )
