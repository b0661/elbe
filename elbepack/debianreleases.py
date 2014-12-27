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

import platform

debian_releases = ( 'unstable', 'testing', 'stable', 'oldstable',
                    'sid', 'jessie', 'wheezy', 'squeeze', 'lenny', 'etch', 'woody' )

ubuntu_releases = ( 'utopic', 'trusty', 'saucy', 'raring', 'quantal', 'precise', 'lucid' )

suite2codename = { # Debian releases
                   'unstable' : 'sid',
                   'testing'  : 'jessie',
                   'stable'   : 'wheezy',
                   'oldstable': 'squeeze', 
                   # Old Debian releases
                   'lenny'    : 'lenny',
                   'etch'     : 'etch',
                   'woody'    : 'woody',
                   # Ubuntu releases
                   'utopic'   : 'utopic',
                   'trusty'   : 'trusty',
                   'saucy'    : 'saucy',
                   'raring'   : 'raring',
                   'quantal'  : 'quantal',
                   'precise'  : 'precise',
                   'lucid'    : 'lucid',
                   }


# generate reverse mapping
codename2suite = dict( [(v,k) for k,v in suite2codename.items()] )

__machine2arch = { # Map machine to arch
                # Machine definitions that are not an architecture by itself
                'i686'        : 'i386',
                'x86_64'      : 'amd64',
                'AMD64'       : 'amd64',
                # qemu-system-[arch] machine definitions not covered by above or below
                'alpha'       : None,   # Not supported any more
                'arm'         : 'arm',  # Need extra info to decide on armel or armhf or arm64
                'cris'        : None,   # Not supported
                'lm32'        : None,   # Not supported
                'm68k'        : None,   # Not supported
                'microblaze'  : 'armhf',
                'microblazeel': 'armel',
                'mips64'      : 'mips',
                'mips64el'    : 'mipsel',
                'or32'        : None,   # Not supported
                'ppc'         : 'powerpc',
                'ppc64'       : 'ppc64el',
                'ppcemb'      : 'powerpc',
                'sh4'         : None,   # Not supported
                'sh4eb'       : None,   # Not supported
                'sparc'       : None,   # Not supported
                'sparc64'     : None,   # Not supported
                'unicore32'   : None,   # Not supported
                'xtensa'      : None,   # Not supported
                'xtensaeb'    : None,   # Not supported

                # Map architectures on itself - just in case
                # Debian only
                'arm64'       : 'arm64',
                'armel'       : 'armel',
                'armhf'       : 'armhf',
                'kfreebsd-amd64' : 'kfreebsd-amd64',
                'kfreebsd-i386'  : 'kfreebsd-i386',
                'mips'        : 'mips',
                'mipsel'      : 'mipsel',
                'powerpc'     : 'powerpc',
                'ppc64el'     : 'ppc64el',
                's390x'       : 's390x',
                # Debian/ Ubuntu
                'i386'        : 'i386',
                'amd64'       : 'amd64',
                # Ubuntu only
                'amd64+mac'   : 'amd64+mac',
                'armhf+omap4' : 'armhf+omap4',
            }

def codename_suite( suite ):
    """ Get the codename and suite from a suite definition.
    Returns ( codename, suite )
    """
    if suite in ('oldstable', 'stable', 'testing', 'unstable'):
        codename = suite2codename[ suite ]
    else:
        codename = suite
        suite = codename2suite[ codename ]
    return (codename, suite)

def installer_arch(suite, machine = None, board = None):
    """ Default architecture of the installer for the suite and machine.
    """
    arch = None
    if not machine:
        machine = platform.machine()
    arch = __machine2arch[ machine ]

    codename, suite = codename_suite( suite )
    # architecture name depends on debian/ ubuntu codename.
    if codename in ubuntu_releases:
        # Ubuntu suite
        if arch == 'amd64':
            # There is also a mac version
            if board == 'mac':
                arch = 'amd64+mac'    
            elif board is None and platform.system() == 'Darwin':
                arch = 'amd64+mac'
        elif arch == 'arm' or arch == 'armhf':
            # Ubuntu only supports omap4
            arch = 'armhf+omap4'
    elif codename in debian_releases:
        # Debian suite
        if arch == 'arm':
            # decide on armel vs. armhf vs. arm64
            arch = 'armel' #default decision
            if board == '':
                arch = 'armhf'
    else:
        # unknown codename - take arch as it is.
        pass

    return arch


def installer_cdrom(suite, arch):
    """ Default uri of the installer cdrom iso for the suite and architecture.
    """
    cdrom = None
    # sanitize codename, suite definition
    codename, suite = codename_suite( suite )
    # sanitize architecture
    arch = installer_arch( suite, arch )

    # Debian
    if suite == 'unstable': # sid
        pass
    elif suite == 'testing': # jessie
        cdrom = "http://cdimage.debian.org/cdimage/daily-builds/daily/arch-latest/%s/iso-cd/debian-testing-%s-netinst.iso" % (arch, arch)
    elif suite == 'stable': # wheezy
        cdrom = "http://cdimage.debian.org/debian-cd/current/%s/iso-cd/debian-7.7.0-%s-netinst.iso" % (arch, arch)
    elif suite == 'oldstable': # squeeze
        cdrom = "http://cdimage.debian.org/cdimage/archive/6.0.10/%s/iso-cd/debian-6.0.10-%s-netinst.iso" % (arch, arch)
    elif codename == 'wheezy':
        cdrom = "http://cdimage.debian.org/debian-cd/current/%s/iso-cd/debian-7.7.0-%s-netinst.iso" % (arch, arch)
    elif codename == 'squeeze':
        cdrom = "http://cdimage.debian.org/cdimage/archive/6.0.10/%s/iso-cd/debian-6.0.10-%s-netinst.iso" % (arch, arch)
    elif codename == 'lenny':
        cdrom = "http://cdimage.debian.org/cdimage/archive/5.0.9/%s/iso-cd/debian-509-%s-netinst.iso" % (arch, arch)
    elif codename == 'etch':
        cdrom = "http://cdimage.debian.org/cdimage/archive/4.0_r8/%s/iso-cd/debian-40r8-%s-netinst.iso" % (arch, arch)
    elif codename == 'sarge':
        cdrom = "http://cdimage.debian.org/cdimage/archive/3.1_r8/%s/iso-cd/debian-31r8-%s-netinst.iso" % (arch, arch)
    elif codename == 'woody':
        cdrom = "http://cdimage.debian.org/cdimage/archive/3.0_r6/%s/iso-cd/debian-30r6-%s-netinst.iso" % (arch, arch)
    # Ubuntu
    elif codename == 'utopic':
        if arch in ( 'i386', 'amd64'):
            cdrom = "http://releases.ubuntu.com/trusty/ubuntu-14.10-server-%s.iso" % (arch)
    elif codename == 'trusty':
        if arch in ( 'i386', 'amd64'):
            cdrom = "http://releases.ubuntu.com/trusty/ubuntu-14.04.1-server-%s.iso" % (arch)
    elif codename == 'saucy':
        if arch in ( 'i386', 'amd64', 'amd64+mac', 'armhf+omap4'):
            cdrom = "http://releases.ubuntu.com/quantal/ubuntu-13.10-server-%s.iso" % (arch)
    elif codename == 'raring':
        if arch in ( 'i386', 'amd64', 'amd64+mac', 'armhf+omap4'):
            cdrom = "http://releases.ubuntu.com/quantal/ubuntu-13.04-server-%s.iso" % (arch)
    elif codename == 'quantal':
        if arch in ( 'i386', 'amd64', 'amd64+mac'):
            cdrom = "http://releases.ubuntu.com/quantal/ubuntu-12.10-server-%s.iso" % (arch)
        elif arch in ( 'armhf+omap4' ):
            cdrom = "http://releases.ubuntu.com/quantal/ubuntu-12.10-desktop-%s.iso" % (arch)
    elif codename == 'precise':
        if arch in ( 'i386', 'amd64' ):
            cdrom = "http://releases.ubuntu.com/precise/ubuntu-12.04.5-server-%s.iso" % (arch)
    elif codename == 'lucid':
        if arch in ( 'i386', 'amd64' ):
            cdrom = "http://releases.ubuntu.com/lucid/ubuntu-10.04.4-server-%s.iso" % (arch)

    return cdrom
