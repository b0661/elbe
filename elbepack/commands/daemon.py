# ELBE - Debian Based Embedded Rootfilesystem Builder
# Copyright (C) 2014  Linutronix GmbH
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

import cherrypy
from cherrypy.process.plugins import Daemonizer, PIDFile

from optparse import OptionParser
from pkgutil import iter_modules

import elbepack.daemons

import sys
import os

def get_daemonlist():
    return [ x for _, x, _ in iter_modules(elbepack.daemons.__path__) ]

def run_command( argv ):
    daemons = get_daemonlist()

    if not daemons:
        print 'no elbe server applications installed'

    oparser = OptionParser(usage="usage: %prog")
    oparser.add_option( "--no-daemon", action="store_true",
		        dest="no_daemon", default=False,
                        help="Do not detach elbe server into the background so that error messages will be displayed on console." )
    oparser.add_option( "--host", dest="host", default='0.0.0.0',
                        help="Network interface to bind the elbe server to." )
    oparser.add_option( "--port", dest="port", default=8080,
                        help="Port to bind elbe server to." )
    oparser.add_option( "--pid-file", dest="pid_file", default="/var/run/elbe-daemon.pid",
                        help="Process id file of elbe server." )

    for d in daemons:
        oparser.add_option( "--"+str(d), dest=str(d), default=False,
                action="store_true",		 help="Enable "+str(d)+" daemon application.")

    (options,args) = oparser.parse_args(argv)

    active = False

    for d in daemons:
        for o in dir(options):
            if str(o) == str(d):
                if getattr(options,o) == True:
                    active = True
                    print "enable", str(d)
                    module = "elbepack.daemons." + str(d)
                    mod = __import__(module)
                    cmdmod = sys.modules[module]
                    cherrypy.tree.graft(cmdmod.get_app(), "/"+str(d))
    if not active:
        print 'No elbe server application activated, use'
        for d in daemons:
            print '   --'+d
        print 'and activate at least one elbe server application.'
        return

    cherrypy.server.unsubscribe()
    server = cherrypy._cpserver.Server()
    server.socket_host = options.host
    server.socket_port = int(options.port)
    server.thread_pool = 30

    # For SSL Support
    # server.ssl_module            = 'pyopenssl'
    # server.ssl_certificate       = 'ssl/certificate.crt'
    # server.ssl_private_key       = 'ssl/private.key'
    # server.ssl_certificate_chain = 'ssl/bundle.crt'

    if options.no_daemon:
	server.subscribe()	
    else:
        # Don't print anything to stdout/sterr.
        cherrypy.config.update({'log.screen' : False})
	Daemonizer(cherrypy.engine).subscribe()

    if options.pid_file:
	PIDFile(cherrypy.engine, options.pid_file).subscribe()

    if hasattr(cherrypy.engine, "signal_handler"):
	cherrypy.engine.signal_handler.subscribe()
    if hasattr(cherrypy.engine, "console_control_handler"):
	cherrypy.engine.console_control_handler.subscribe()

    # Always start the engine; this will start all other services
    try:
	cherrypy.engine.start()
    except:
	# Assume the error has been logged already via bus.log.
	sys.exit(1)
    else:
	cherrypy.engine.block()
