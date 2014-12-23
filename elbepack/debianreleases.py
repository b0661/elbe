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

suite2codename = { 'oldstable': 'squeeze', 
                   'stable': 'wheezy',
                   'testing': 'jessie',
                   'unstable': 'sid',

                   'lucid': 'lucid',
                   'precise': 'precise',
                   'quantal': 'quantal',
                   'raring': 'raring',
                   'saucy': 'saucy',
                   }


# generate reverse mapping
codename2suite = dict( [(v,k) for k,v in suite2codename.items()] )

machine2arch = { 'i386': 'i386',
                 'i686': 'i386',
                 'x86_64': 'amd64',
                 
                 # map arch on itself, just in case
                 'amd64': 'amd64',
               }

def installer_cdrom(suite, arch):
    """ Default uri of the installer cdrom iso for the suite and architecture.
    """
    if suite in ('oldstable', 'stable', 'testing', 'unstable'):
        codename = suite2codename[ suite ]
    else:
        codename = suite
        suite = codename2suite[ codename ]
    arch = machine2arch[ arch ]
    installer_iso = None

    if suite == 'unstable':
        pass
    elif suite == 'testing':
        installer_iso = "http://cdimage.debian.org/cdimage/weekly-builds/%s/iso-cd/debian-%s-%s-netinst.iso" % (arch, suite, arch)
    elif suite == 'stable':
        installer_iso = "http://cdimage.debian.org/debian-cd/current/%s/iso-cd/debian-7.7.0-%s-netinst.iso" % (arch, arch)
    elif suite == 'oldstable':
        pass

    return installer_iso