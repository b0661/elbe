#!/usr/bin/env python
#
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
import shutil


import elbepack
from elbepack.asciidoclog import ASCIIDocLog, StdoutLog
from elbepack.treeutils import etree
from elbepack.validate import validate_xml
from elbepack.pkgutils import copy_kinitrd, NoKinitrdException, get_project_repo_pkg_list, apt_sources_list, debian_installer_mirror_preseed
from elbepack.xmldefaults import ElbeDefaults
from elbepack.version import elbe_version
from elbepack.templates import write_template, get_initvm_preseed
from elbepack.repomanager import ProjectRepo

from optparse import OptionParser

def run_command( argv ):
    elbe_dir = os.path.dirname(os.path.abspath(__file__))
    pack_dir = elbepack.__path__[0]
    template_dir = os.path.join( pack_dir, "init" )

    oparser = OptionParser( usage="usage: %prog init [options] <filename>" )

    oparser.add_option( "--skip-validation", action="store_true",
                        dest="skip_validation", default=False,
                        help="Skip xml schema validation" )

    oparser.add_option( "--skip-cds", action="store_true", dest="skip_cds",
                        default=False,
                        help="Skip cd generation" )

    oparser.add_option( "--directory", dest="directory",
                        help="Working directory. Overrides ELBE XML setting or default ./build.",
                        metavar="FILE" )
    
    oparser.add_option( "--include-pkg", action="append", dest="project_repo_pkgs",
		        type="string", nargs=2, 
                        help="Include debian package (.deb, .dsc, .changes) in project repository (<package> <component>).",
                        metavar="FILE" )

    oparser.add_option( "--build-sources", action="store_true",
                        dest="buildsources", default=False,
                        help="Build source cdrom" )

    oparser.add_option( "--proxy", dest="proxy",
                        help="Override the http Proxy" )

    oparser.add_option( "--buildtype", dest="buildtype",
                        help="Override the buildtype" )

    oparser.add_option( "--debug", dest="debug",
                        action="store_true", default=False,
                        help="start qemu in graphical mode to enable console switch" )

    (opt,args) = oparser.parse_args(argv)

    print opt.directory

    if len(args) == 0:
        print "no filename specified"
        oparser.print_help()
        sys.exit(20)
    elif len(args) > 1:
        print "too many filenames specified"
        oparser.print_help()
        sys.exit(20)

    if not opt.skip_validation:
        if not validate_xml( args[0] ):
            print "xml validation failed. Bailing out"
            sys.exit(20)

    xml = etree( args[0] )

    if not xml.has( "initvm" ):
        print "fatal error: xml missing mandatory section 'initvm'"
        sys.exit(20)

    if opt.buildtype:
        buildtype = opt.buildtype
    elif xml.has( "initvm/buildtype" ):
        buildtype = xml.text( "/initvm/buildtype" )
    else:
        buildtype = "nodefaults"

    defs = ElbeDefaults( buildtype )

    http_proxy = ""
    if opt.proxy:
        http_proxy = opt.proxy
    elif xml.has("initvm/mirror/primary_proxy"):
        http_proxy = xml.text("initvm/mirror/primary_proxy")
    # remember actual proxy definition in xml
    http_proxy_node = xml.node("initvm/mirror").ensure_child("primary_proxy")
    http_proxy_node.set_text(http_proxy)

    if opt.directory:
        path = opt.directory
    elif xml.has("initvm/directory"):
        path = xml.text("initvm/directory")
    else:
        path = "./build"
    # remember actual working directory in xml
    path = os.path.abspath(path)
    directory_node = xml.node("initvm").ensure_child("directory")
    directory_node.set_text(path)

    try:
        os.makedirs(path)
    except:
        print 'unable to create project directory: %s' % path
        sys.exit(30)

    out_path = os.path.join(path,".elbe-in")
    try:
        os.makedirs(out_path)
    except:
        print 'unable to create subdirectory: %s' % out_path
        sys.exit(30)

    # Create project package repository directory.
    project_repo_path = os.path.abspath(os.path.join(path, ".elbe-repo"))       
    try:
        os.makedirs(project_repo_path)
    except:
        print 'unable to create subdirectory: %s' % project_repo_path
        sys.exit(30)

    # Create project package repository
    project_repo = ProjectRepo(xml, project_repo_path, StdoutLog())
    project_repo.include_packages(get_project_repo_pkg_list(xml.node("/initvm")))
    if opt.project_repo_pkgs:
	project_repo.include_packages(opt.project_repo_pkgs)
	
    if http_proxy != "":
        os.putenv ("http_proxy", http_proxy)
        os.putenv ("no_proxy", "localhost,127.0.0.1")

    try:
        copy_kinitrd(xml.node("/initvm"), out_path, defs, arch="amd64")
    except NoKinitrdException:
        print "Failure to download kernel/initrd debian Package"
        print "Check Mirror configuration"
        sys.exit(20)

    templates = os.listdir( template_dir )

    template_vars = {
         "elbe_version": elbe_version,
         "defs": defs,
         "opt": opt,
         "xml": xml,
         "prj": xml.node("/initvm"),
         "http_proxy": http_proxy,
         "pkgs": xml.node("/initvm/pkg-list") or [],
         "preseed": get_initvm_preseed(xml),
         "project_repo": project_repo,
         "apt_sources_list": apt_sources_list(xml.node("/initvm"), defs),
         "mirror_preseed": debian_installer_mirror_preseed(xml.node("/initvm"), defs)
        }

    make_executable = [ "init-elbe.sh.mako",
                        "preseed.cfg.mako" ]

    for t in templates:
        o = t.replace( ".mako", "" )

        if t == "Makefile.mako":
            write_template(os.path.join(path,o), os.path.join(template_dir, t), template_vars )
        else:
            write_template(os.path.join(out_path,o), os.path.join(template_dir, t), template_vars )

        if t in make_executable:
            os.chmod( os.path.join(out_path,o), 0755 )

    shutil.copyfile( args[0],
       os.path.join(out_path, "source.xml" ) )
